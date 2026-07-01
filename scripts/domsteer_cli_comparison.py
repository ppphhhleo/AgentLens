#!/usr/bin/env python3
"""Collect DOMSteer exact-answer trajectories with CLI-only agents.

This runner is intentionally separate from the GUI/browser AgentLens harnesses.
It preserves the CLI agent's raw provider stream and validates only the final
answer, so CLI trajectories can be compared with GUI-only and computer-use
trajectories without converting shell/tool events into mouse actions.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY_GUI_VS_CLI = REPO_ROOT / "third_party" / "gui-vs-cli"

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None


CLI_ONLY_PROMPT = """<SYSTEM_CAPABILITY>
You are running inside an isolated Ubuntu desktop/task container.
You may use command-line tools, package managers, Python, curl, and read-only
web/data access to solve the task. Do not use GUI clicking, screenshot-based
interaction, browser automation, DevTools, or the visible DataVoyager interface.

This is a CLI-only trajectory collection. Preserve a clear record of what you
checked and compute the answer from data or reproducible terminal inspection.
When you know the answer, end with a line exactly in this form:

FINAL_ANSWER: <answer>

Return only the concise answer value after FINAL_ANSWER. Do not ask the user
for clarification.
</SYSTEM_CAPABILITY>

<TASK_CONTEXT>
Benchmark: DOMSteer
Application: DataVoyager 2
Start URL: {start_url}
Dataset hint: Vega cars dataset / vega_datasets.cars
</TASK_CONTEXT>

<USER_TASK>
{goal}
</USER_TASK>
"""


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--agent", action="append", help="Agent id to run. Repeatable.")
    parser.add_argument("--task", action="append", help="Task id to run. Repeatable.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text()) or {}
    _ensure_import_paths()

    selected_agents = _select(config.get("agents", []), args.agent)
    selected_tasks = _select(config.get("tasks", []), args.task)
    output_root = args.output_dir or Path(config.get("output_dir", "runs/domsteer_cli_comparison"))
    run_dir = output_root / datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))

    results = []
    for task_ref in selected_tasks:
        task = _load_domsteer_task(task_ref)
        for agent in selected_agents:
            results.append(
                _run_case(
                    config=config,
                    task=task,
                    agent=agent,
                    run_dir=run_dir,
                    timeout_s=args.timeout or int(config.get("timeout_s", 200)),
                )
            )

    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSummary: {summary_path}")
    return 0 if all(item.get("ok") for item in results) else 1


def _ensure_import_paths() -> None:
    for path in [THIRD_PARTY_GUI_VS_CLI, REPO_ROOT / "src", REPO_ROOT / "scripts"]:
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _select(items: list[dict[str, Any]], ids: list[str] | None) -> list[dict[str, Any]]:
    if not ids:
        return [item for item in items if item.get("enabled", True)]
    wanted = set(ids)
    selected = [item for item in items if item.get("id") in wanted]
    missing = wanted - {item.get("id") for item in selected}
    if missing:
        raise ValueError(f"unknown id(s): {sorted(missing)}")
    return selected


def _load_domsteer_task(task_ref: dict[str, Any]) -> dict[str, Any]:
    task_path = REPO_ROOT / task_ref["path"]
    payload = yaml.safe_load(task_path.read_text()) or {}
    payload["path"] = str(task_path)
    return payload


def _run_case(
    *,
    config: dict[str, Any],
    task: dict[str, Any],
    agent: dict[str, Any],
    run_dir: Path,
    timeout_s: int,
) -> dict[str, Any]:
    from agentlens.schemas import TaskConfig
    from agentlens.validators.answers import validate_answer
    from evaluation.runtime.cli_agent_runner import parse_stream_json
    from evaluation.runtime.sandbox_session import setup_sandbox_session

    task_id = task["id"]
    agent_id = agent["id"]
    provider = agent.get("cli_provider") or agent.get("provider")
    if provider == "anthropic":
        provider = "claude"
    if provider == "openai":
        provider = "codex"
    if provider not in {"claude", "codex"}:
        raise ValueError(f"unsupported CLI provider: {provider!r}")

    case_dir = run_dir / "trajectories" / f"{task_id}__{agent_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    session = None
    print(f"\n=== {task_id} / {agent_id} / {provider} ===")

    try:
        session = setup_sandbox_session(
            "chrome",
            {
                "id": task_id,
                "task": task.get("goal") or "",
                "env": {"files": []},
            },
            sandbox_timeout=int(config.get("sandbox_timeout", 600)),
            run_id=run_dir.name,
            run_mode="cli",
            env_backend=config.get("env_backend", "docker"),
            docker_image=config.get("docker_image"),
            docker_platform=config.get("docker_platform"),
            docker_shm_size=config.get("docker_shm_size"),
            docker_ready_timeout=int(config.get("docker_ready_timeout", 180)),
        )
        _write_cli_env_file(session.sandbox)
        binary = "claude" if provider == "claude" else "codex"
        binary_check = _check_cli_binary(session.sandbox, binary)
        if not binary_check["ok"]:
            raise RuntimeError(binary_check["error"])

        prompt = CLI_ONLY_PROMPT.format(
            start_url=task.get("start_url") or "",
            goal=task.get("goal") or "",
        )
        session.sandbox.files.write("/home/user/domsteer_cli_prompt.txt", prompt)
        model_name = agent.get("model", "")
        log_file = f"/home/user/{provider}_domsteer_stream.jsonl"
        if provider == "claude":
            cli_cmd = (
                "bash -lc "
                + shlex.quote(
                    "cd /home/user && "
                    f"timeout {timeout_s}s claude -p --model {shlex.quote(model_name)} "
                    "--output-format stream-json --verbose --dangerously-skip-permissions "
                    "< /home/user/domsteer_cli_prompt.txt "
                    f"2>&1 | tee {shlex.quote(log_file)}"
                )
            )
        else:
            cli_cmd = (
                "bash -lc "
                + shlex.quote(
                    "cd /home/user && "
                    f"timeout {timeout_s}s codex exec --json "
                    f"--dangerously-bypass-approvals-and-sandbox -m {shlex.quote(model_name)} "
                    "< /home/user/domsteer_cli_prompt.txt "
                    f"2>&1 | tee {shlex.quote(log_file)}"
                )
            )

        start = time.time()
        command_result = session.sandbox.commands.run(cli_cmd, timeout=timeout_s + 60)
        elapsed = time.time() - start
        raw_log = _read_sandbox_file(session.sandbox, log_file)
        (case_dir / f"{provider}_stream.jsonl").write_text(raw_log, encoding="utf-8")
        events = parse_stream_json(raw_log)
        final_answer = _extract_final_answer(provider, events, raw_log)

        task_config = TaskConfig(**{k: v for k, v in task.items() if k != "path"})
        success, score, validation_message = validate_answer(final_answer, task_config)
        completed_at = datetime.now(timezone.utc)
        trajectory = {
            "experiment_id": config.get("id"),
            "run_id": f"{task_id}__{agent_id}",
            "benchmark": "domsteer",
            "agent": {
                "id": agent_id,
                "family": "paper_style_cli",
                "provider": provider,
                "model": model_name,
            },
            "task": task,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "events": [
                {
                    "event_type": "cli_prompt",
                    "step_index": 0,
                    "timestamp": started_at.isoformat(),
                    "data": {
                        "prompt_file": "domsteer_cli_prompt.txt",
                        "policy": "cli_only_data_analysis",
                    },
                },
                {
                    "event_type": "cli_execution",
                    "step_index": 1,
                    "timestamp": completed_at.isoformat(),
                    "data": {
                        "provider": provider,
                        "model": model_name,
                        "command_exit_code": getattr(command_result, "exit_code", 0),
                        "stdout_excerpt": (getattr(command_result, "stdout", "") or "")[:4000],
                        "stderr_excerpt": (getattr(command_result, "stderr", "") or "")[:4000],
                        "event_count": len(events),
                        "events": events,
                        "raw_log_file": f"{provider}_stream.jsonl",
                    },
                },
                {
                    "event_type": "validation_event",
                    "step_index": 1,
                    "timestamp": completed_at.isoformat(),
                    "data": {
                        "success": success,
                        "score": score,
                        "message": validation_message,
                        "answer": final_answer,
                        "expected_answer": task.get("expected_answer"),
                        "answer_validator": task.get("answer_validator"),
                    },
                },
            ],
            "metrics": {
                "success": success,
                "score": score,
                "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
                "steps": 1,
                "tool_calls": _count_cli_tool_events(provider, events),
                "extra": {
                    "elapsed_cli_seconds": round(elapsed, 1),
                    "raw_provider_events": len(events),
                    "stream_url": session.stream_url,
                },
            },
            "artifact_dir": str(case_dir),
        }
        (case_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, default=str))
        result = {
            "ok": bool(success),
            "task_id": task_id,
            "agent": agent_id,
            "provider": provider,
            "model": model_name,
            "final_answer": final_answer,
            "expected_answer": task.get("expected_answer"),
            "score": score,
            "message": validation_message,
            "trajectory": str(case_dir / "trajectory.json"),
            "elapsed_seconds": round((completed_at - started_at).total_seconds(), 1),
        }
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
        return result
    except Exception as exc:  # noqa: BLE001
        completed_at = datetime.now(timezone.utc)
        result = {
            "ok": False,
            "task_id": task_id,
            "agent": agent_id,
            "provider": provider,
            "model": agent.get("model"),
            "error": str(exc),
            "elapsed_seconds": round((completed_at - started_at).total_seconds(), 1),
        }
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
        return result
    finally:
        if session is not None:
            try:
                session.sandbox.kill()
            except Exception:
                pass


def _write_cli_env_file(sandbox: Any) -> None:
    keys = [
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "GEMINI_API_KEY",
        "GOOGLE_AI_STUDIO_API_KEY",
        "JUDGE_API_KEY",
        "OPENROUTER_API_KEY",
    ]
    lines = []
    for key in keys:
        value = os.environ.get(key)
        if value:
            lines.append(f"export {key}={shlex.quote(value)}")
    content = "\n".join(lines) + ("\n" if lines else "")
    sandbox.files.write("/home/user/.agentlens_cli_env", content)
    sandbox.commands.run(
        "chown user:user /home/user/.agentlens_cli_env && chmod 600 /home/user/.agentlens_cli_env",
        timeout=10,
    )
    has_codex_auth = _copy_codex_auth_if_available(sandbox)
    if os.environ.get("OPENAI_API_KEY") and not has_codex_auth:
        codex_config = """model_provider = "openai_env"

[model_providers.openai_env]
name = "OpenAI API"
base_url = "https://api.openai.com/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = true
"""
        sandbox.commands.run("mkdir -p /home/user/.codex", timeout=10)
        sandbox.files.write("/home/user/.codex/config.toml", codex_config)
        sandbox.commands.run("chown -R user:user /home/user/.codex && chmod 700 /home/user/.codex", timeout=10)


def _copy_codex_auth_if_available(sandbox: Any) -> bool:
    auth_path = REPO_ROOT / ".secrets" / "codex" / "auth.json"
    if not auth_path.exists():
        return False
    sandbox.commands.run("mkdir -p /home/user/.codex", timeout=10)
    sandbox.files.write("/home/user/.codex/auth.json", auth_path.read_bytes())
    sandbox.commands.run(
        "chown -R user:user /home/user/.codex && chmod 700 /home/user/.codex "
        "&& chmod 600 /home/user/.codex/auth.json",
        timeout=10,
    )
    return True


def _check_cli_binary(sandbox: Any, binary: str) -> dict[str, Any]:
    try:
        result = sandbox.commands.run(f"bash -lc 'command -v {shlex.quote(binary)}'", timeout=10)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "binary": binary, "error": str(exc)}
    path = (result.stdout or "").strip()
    return {"ok": bool(path), "binary": binary, "path": path, "error": None if path else "not found"}


def _read_sandbox_file(sandbox: Any, path: str) -> str:
    try:
        data = sandbox.files.read(path)
    except Exception:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return str(data)


def _extract_final_answer(provider: str, events: list[dict[str, Any]], raw_log: str) -> str | None:
    texts: list[str] = []
    for event in events:
        if provider == "claude":
            if event.get("type") == "result" and isinstance(event.get("result"), str):
                texts.append(event["result"])
            message = event.get("message")
            if isinstance(message, dict):
                for block in message.get("content", []) or []:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        texts.append(block["text"])
        else:
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    texts.append(text)
            if isinstance(event.get("message"), str):
                texts.append(event["message"])
    for text in reversed(texts):
        answer = _answer_from_text(text)
        if answer:
            return answer
    answer = _answer_from_text(raw_log)
    if answer:
        return answer
    for text in reversed(texts):
        stripped = text.strip()
        if stripped and len(stripped) < 200:
            return stripped
    return None


def _answer_from_text(text: str) -> str | None:
    matches = list(
        re.finditer(r"(?im)^\s*FINAL_ANSWER\s*:\s*(.+?)\s*$", text)
    )
    if not matches:
        return None
    return matches[-1].group(1).strip().strip("`\"'")


def _count_cli_tool_events(provider: str, events: list[dict[str, Any]]) -> int:
    count = 0
    for event in events:
        if provider == "claude":
            message = event.get("message")
            if isinstance(message, dict):
                for block in message.get("content", []) or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        count += 1
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "command_execution":
            count += 1
    return count


if __name__ == "__main__":
    raise SystemExit(main())
