#!/usr/bin/env python3
"""Run GUI-vs-CLI full-workflow smoke tasks through AgentLens agents.

This bridge intentionally reuses the gui-vs-cli environment setup, app launch,
seed-file upload, and verifier code. It swaps in AgentLens model wrappers so we
can compare:

- `agentlens_gui_toolcall`: strict GUI-only registered tools.
- `gui_vs_cli_chatgpt`: the paper's ChatGPTAgent computer-use structure.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY_GUI_VS_CLI = REPO_ROOT / "third_party" / "gui-vs-cli"

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional local convenience
    load_dotenv = None

GUI_SCREEN_ONLY_POLICY = """<GUI_SCREEN_ONLY_POLICY>
Hard requirements:
* All task-result changes must be made through the target application's visible GUI.
* Do not directly rewrite task files on disk or mutate their underlying data using Python, shell commands, scripts, automation APIs, databases, archives, config files, or external utilities.
* Editing content through the target application's own GUI is allowed.
* Opening a terminal, REPL, scripting console, developer console, or macro/script editor to execute code or commands is not allowed, even if accessed through the GUI.
</GUI_SCREEN_ONLY_POLICY>"""


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--agent", action="append", help="Agent id to run. Repeatable.")
    parser.add_argument("--task", action="append", help="Task id to run. Repeatable.")
    parser.add_argument("--ready-check-only", action="store_true")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text()) or {}
    _ensure_gui_vs_cli_on_path()

    selected_agents = _select(config.get("agents", []), args.agent)
    selected_tasks = _select(config.get("tasks", []), args.task)
    if args.ready_check_only and not args.agent:
        selected_agents = [{"id": "ready_check_only"}]

    output_root = args.output_dir or Path(config.get("output_dir", "runs/gui_vs_cli_full_workflow_smoke"))
    run_dir = output_root / datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))

    results = []
    for task_ref in selected_tasks:
        task = _load_task(task_ref["id"])
        app = task_ref.get("app") or task.get("app")
        for agent_ref in selected_agents:
            result = _run_one(
                config=config,
                agent_ref=agent_ref,
                task_ref=task_ref,
                task=task,
                app=app,
                run_dir=run_dir,
                ready_check_only=args.ready_check_only,
                max_steps=args.max_steps or int(config.get("max_steps", 40)),
            )
            results.append(result)

    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSummary: {summary_path}")
    return 0 if all(item.get("ok") for item in results) else 1


def _ensure_gui_vs_cli_on_path() -> None:
    if not THIRD_PARTY_GUI_VS_CLI.exists():
        raise RuntimeError(
            "third_party/gui-vs-cli is missing. Clone rebeccaz4/gui-vs-cli before running."
        )
    root = str(THIRD_PARTY_GUI_VS_CLI)
    if root not in sys.path:
        sys.path.insert(0, root)
    repo_src = str(REPO_ROOT / "src")
    if repo_src not in sys.path:
        sys.path.insert(0, repo_src)


def _select(items: list[dict[str, Any]], ids: list[str] | None) -> list[dict[str, Any]]:
    if not ids:
        return [item for item in items if item.get("enabled", True)]
    wanted = set(ids)
    selected = [item for item in items if item.get("id") in wanted]
    missing = wanted - {item.get("id") for item in selected}
    if missing:
        raise ValueError(f"unknown id(s): {sorted(missing)}")
    return selected


def _load_task(task_id: str) -> dict[str, Any]:
    full_task = THIRD_PARTY_GUI_VS_CLI / "task_generator" / "tasks" / task_id / "task.json"
    if full_task.exists():
        return json.loads(full_task.read_text())
    catalog = REPO_ROOT / "tasks" / "gui_vs_cli" / "tasks.jsonl"
    for line in catalog.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("id") == task_id:
            return record
    raise FileNotFoundError(f"GUI-vs-CLI task not found: {task_id}")


def _run_one(
    *,
    config: dict[str, Any],
    agent_ref: dict[str, Any],
    task_ref: dict[str, Any],
    task: dict[str, Any],
    app: str,
    run_dir: Path,
    ready_check_only: bool,
    max_steps: int,
) -> dict[str, Any]:
    from evaluation.runtime.sandbox_session import setup_sandbox_session
    from evaluation.runtime.verification import verify_task

    agent_id = agent_ref["id"]
    task_id = task_ref["id"]
    case_dir = run_dir / f"{task_id}__{agent_id}"
    case_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {task_id} / {agent_id} / {app} ===")
    if _is_paper_style_cli_agent(agent_ref):
        return _run_cli_one(
            config=config,
            agent_ref=agent_ref,
            task=task,
            app=app,
            task_id=task_id,
            run_dir=run_dir,
            case_dir=case_dir,
            ready_check_only=ready_check_only,
            max_iterations=max_steps,
        )

    session = None
    started_at = time.time()
    try:
        session = setup_sandbox_session(
            app,
            task,
            sandbox_timeout=int(config.get("sandbox_timeout", 600)),
            run_id=run_dir.name,
            run_mode="gui",
            env_backend=config.get("env_backend", "docker"),
            docker_image=config.get("docker_image"),
            docker_platform=config.get("docker_platform"),
            docker_shm_size=config.get("docker_shm_size"),
            docker_ready_timeout=int(config.get("docker_ready_timeout", 180)),
        )
        if ready_check_only:
            result = {
                "ok": True,
                "task_id": task_id,
                "app": app,
                "agent": agent_id,
                "ready_check_only": True,
                "stream_url": session.stream_url,
                "elapsed_seconds": round(time.time() - started_at, 1),
            }
            (case_dir / "result.json").write_text(json.dumps(result, indent=2))
            return result

        trajectory = _run_agent_loop(
            agent_ref=agent_ref,
            task=task,
            sandbox=session.sandbox,
            case_dir=case_dir,
            max_steps=max_steps,
        )
        passed, total, details = verify_task(
            session.sandbox,
            app,
            task.get("verification", []),
            trajectory=trajectory,
            traj_dir=case_dir,
        )
        result = {
            "ok": passed == total and total > 0,
            "task_id": task_id,
            "app": app,
            "agent": agent_id,
            "checks_passed": passed,
            "checks_total": total,
            "score": passed / total if total else 0.0,
            "verification_details": details,
            "elapsed_seconds": round(time.time() - started_at, 1),
        }
        (case_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, default=str))
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
        return result
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "task_id": task_id,
            "app": app,
            "agent": agent_id,
            "error": str(exc),
            "elapsed_seconds": round(time.time() - started_at, 1),
        }
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
        print(f"ERROR: {exc}")
        return result
    finally:
        if session is not None:
            try:
                session.sandbox.kill()
            except Exception:
                pass


def _is_paper_style_cli_agent(agent_ref: dict[str, Any]) -> bool:
    return (
        agent_ref.get("family") == "paper_style_cli"
        or agent_ref.get("interaction_backend") == "gui_vs_cli_cli"
    )


def _run_cli_one(
    *,
    config: dict[str, Any],
    agent_ref: dict[str, Any],
    task: dict[str, Any],
    app: str,
    task_id: str,
    run_dir: Path,
    case_dir: Path,
    ready_check_only: bool,
    max_iterations: int,
) -> dict[str, Any]:
    from evaluation.runtime.cli_agent_runner import run_cli_agent_interactive
    from evaluation.runtime.sandbox_session import setup_sandbox_session
    from evaluation.runtime.verification import verify_task

    provider = agent_ref.get("cli_provider") or agent_ref.get("provider")
    if provider == "anthropic":
        provider = "claude"
    if provider == "openai":
        provider = "codex"
    if provider not in {"claude", "codex"}:
        raise ValueError(
            f"paper_style_cli supports cli_provider/provider 'claude' or 'codex', got {provider!r}"
        )

    agent_id = agent_ref["id"]
    started_at = time.time()
    session = None
    try:
        session = setup_sandbox_session(
            app,
            task,
            sandbox_timeout=int(config.get("sandbox_timeout", 600)),
            run_id=run_dir.name,
            run_mode="cli",
            env_backend=config.get("env_backend", "docker"),
            docker_image=config.get("docker_image"),
            docker_platform=config.get("docker_platform"),
            docker_shm_size=config.get("docker_shm_size"),
            docker_ready_timeout=int(config.get("docker_ready_timeout", 180)),
        )
        binary = "claude" if provider == "claude" else "codex"
        binary_check = _check_cli_binary(session.sandbox, binary)

        if ready_check_only:
            result = {
                "ok": binary_check["ok"],
                "task_id": task_id,
                "app": app,
                "agent": agent_id,
                "family": "paper_style_cli",
                "cli_provider": provider,
                "ready_check_only": True,
                "stream_url": session.stream_url,
                "cli_binary_check": binary_check,
                "elapsed_seconds": round(time.time() - started_at, 1),
            }
            (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
            return result

        if not binary_check["ok"]:
            result = {
                "ok": False,
                "task_id": task_id,
                "app": app,
                "agent": agent_id,
                "family": "paper_style_cli",
                "cli_provider": provider,
                "model": agent_ref.get("model"),
                "error": binary_check["error"],
                "cli_binary_check": binary_check,
                "elapsed_seconds": round(time.time() - started_at, 1),
            }
            (case_dir / "trajectory.json").write_text(
                json.dumps({"result": result, "trajectory": []}, indent=2, default=str)
            )
            (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
            return result

        agent_done, steps, trajectory, model_metadata = run_cli_agent_interactive(
            session.sandbox,
            task,
            provider,
            agent_ref.get("model", ""),
            max_iterations,
            case_dir,
        )
        _reload_libreoffice_file_for_cli_verification(session.sandbox, app, task)
        passed, total, details = verify_task(
            session.sandbox,
            app,
            task.get("verification", []),
            trajectory=None,
            traj_dir=case_dir,
        )
        result = {
            "ok": passed == total and total > 0,
            "task_id": task_id,
            "app": app,
            "agent": agent_id,
            "family": "paper_style_cli",
            "cli_provider": provider,
            "agent_done": agent_done,
            "agent_steps": steps,
            "checks_passed": passed,
            "checks_total": total,
            "score": passed / total if total else 0.0,
            "verification_details": details,
            "model_metadata": model_metadata,
            "elapsed_seconds": round(time.time() - started_at, 1),
        }
        (case_dir / "trajectory.json").write_text(
            json.dumps({**result, "trajectory": trajectory}, indent=2, default=str)
        )
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
        return result
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "task_id": task_id,
            "app": app,
            "agent": agent_id,
            "family": "paper_style_cli",
            "cli_provider": provider,
            "error": str(exc),
            "elapsed_seconds": round(time.time() - started_at, 1),
        }
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
        print(f"ERROR: {exc}")
        return result
    finally:
        if session is not None:
            try:
                session.sandbox.kill()
            except Exception:
                pass


def _check_cli_binary(sandbox: Any, binary: str) -> dict[str, Any]:
    try:
        result = sandbox.commands.run(f"bash -lc 'command -v {shlex.quote(binary)}'", timeout=10)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "binary": binary,
            "error": (
                f"{binary!r} is not installed or not available in the Docker image PATH. "
                "Install/authenticate the CLI in the task image before running paper-style CLI agents. "
                f"Raw error: {exc}"
            ),
        }
    path = (result.stdout or "").strip()
    return {
        "ok": bool(path),
        "binary": binary,
        "path": path,
        "error": None if path else f"{binary!r} was not found in the Docker image PATH.",
    }


LIBREOFFICE_RELOAD_MODES = {
    "libreoffice_calc": "--calc",
    "libreoffice_impress": "--impress",
    "libreoffice_writer": "--writer",
    "libreoffice_draw": "--draw",
}


def _reload_libreoffice_file_for_cli_verification(sandbox: Any, app_name: str, task: dict[str, Any]) -> None:
    reload_mode = LIBREOFFICE_RELOAD_MODES.get(app_name)
    if not reload_mode:
        return

    reload_path = _reload_path_from_task(task)
    if not reload_path:
        return

    quoted_path = shlex.quote(reload_path)
    command = (
        "pkill -x soffice.bin 2>/dev/null || true; "
        "pkill -x soffice 2>/dev/null || true; "
        "sleep 1; "
        f"soffice {reload_mode} "
        "'--accept=socket,host=localhost,port=2002;urp;' "
        "--norestore --nologo "
        f"{quoted_path} >/tmp/libreoffice_cli_reload.log 2>&1 & "
        "sleep 4"
    )
    sandbox.commands.run(command, timeout=15)


def _reload_path_from_task(task: dict[str, Any]) -> str | None:
    reload_files = task.get("env", {}).get("reload_files", [])
    if reload_files:
        return str(reload_files[0])

    for file_entry in task.get("env", {}).get("files", []):
        sandbox_path = file_entry.get("sandbox_path")
        if sandbox_path:
            return str(sandbox_path)
    return None


def _run_agent_loop(
    *,
    agent_ref: dict[str, Any],
    task: dict[str, Any],
    sandbox: Any,
    case_dir: Path,
    max_steps: int,
) -> list[dict[str, Any]]:
    from agentlens.models.base import ModelStep, ScreenshotObservation

    screenshots_dir = case_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    model = _build_agentlens_model(agent_ref)
    history: list[ModelStep] = []
    trajectory: list[dict[str, Any]] = []
    if str(agent_ref.get("interaction_backend", "")).startswith("gui_vs_cli_"):
        goal = task["task"]
    else:
        goal = _task_prompt(task["task"], agent_ref.get("prompt_policy"))

    for step_index in range(max_steps):
        screenshot = sandbox.screenshot()
        screenshot_path = screenshots_dir / f"step_{step_index:03d}.png"
        screenshot_path.write_bytes(screenshot)
        observation = ScreenshotObservation(
            step_index=step_index,
            url="",
            viewport={"width": 1920, "height": 1080},
            max_steps=max_steps,
            screenshot_path=screenshot_path,
        )
        model_step = model.step(goal=goal, observation=observation, history=history)
        history.append(model_step)
        step_record = {
            "step": step_index,
            "screenshot_file": str(screenshot_path.relative_to(case_dir)),
            "reasoning": model_step.thought,
            "actions": [
                action.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
                for action in model_step.action_list()
            ],
            "action_results": [],
            "raw_response": model_step.raw_response,
            "extra": model_step.extra,
        }
        done = False
        for action in model_step.action_list():
            if action.type == "final_answer":
                step_record["final_answer"] = action.answer
                done = True
                break
            ok, output = _execute_desktop_action(sandbox, action)
            step_record["action_results"].append(
                {"action": action.type, "success": ok, "output": output[:1000]}
            )
            if not ok:
                break
        trajectory.append(step_record)
        if done:
            break
        time.sleep(0.5)
    return trajectory


def _build_agentlens_model(agent_ref: dict[str, Any]):
    from agentlens.harnesses.tool_gating import ToolSet
    from agentlens.models.base import build_model
    from agentlens.schemas import ModelConfig

    if not agent_ref.get("enabled", True):
        raise RuntimeError(
            f"agent {agent_ref['id']!r} is disabled: {agent_ref.get('status', 'not ready')}"
        )
    config = ModelConfig(
        id=agent_ref["id"],
        provider=agent_ref.get("provider", "openai"),
        name=agent_ref.get("model", "gpt-5.4"),
        temperature=0.0,
        vision=True,
        max_output_tokens=1024,
        extra={
            "interaction_backend": agent_ref.get("interaction_backend", "tool_call"),
            "gui_screen_only_policy": agent_ref.get("prompt_policy") == "gui_screen_only",
            "screen_size": [1920, 1080],
            "computer_environment": "linux",
            "reasoning_effort": "medium",
            "reasoning_summary": "concise",
            "max_steps": 400,
        },
    )
    return build_model(config, toolset=ToolSet(allowed=frozenset(agent_ref.get("tools", []))))


def _task_prompt(task_text: str, prompt_policy: str | None) -> str:
    if prompt_policy != "gui_screen_only":
        return task_text
    return f"{GUI_SCREEN_ONLY_POLICY}\n\n<USER_TASK>\n{task_text}\n</USER_TASK>"


def _execute_desktop_action(sandbox: Any, action: Any) -> tuple[bool, str]:
    if action.type == "desktop_screenshot":
        return True, "screenshot observed"
    if action.type == "desktop_wait":
        time.sleep((action.ms or 1000) / 1000)
        return True, "waited"
    if action.type == "desktop_pyautogui":
        return _run_pyautogui(sandbox, action.code or "")
    code = _desktop_action_to_pyautogui(action)
    if not code:
        return False, f"unsupported action: {action.type}"
    return _run_pyautogui(sandbox, code)


def _desktop_action_to_pyautogui(action: Any) -> str:
    if action.type == "desktop_click":
        return f"pyautogui.click({int(action.x)}, {int(action.y)}, button={action.button or 'left'!r})"
    if action.type == "desktop_double_click":
        return f"pyautogui.doubleClick({int(action.x)}, {int(action.y)}, button={action.button or 'left'!r})"
    if action.type == "desktop_move":
        return f"pyautogui.moveTo({int(action.x)}, {int(action.y)})"
    if action.type == "desktop_scroll":
        return f"pyautogui.moveTo({int(action.x or 960)}, {int(action.y or 540)}); pyautogui.scroll({int(-(action.scroll_y or 0))})"
    if action.type == "desktop_type":
        return f"pyperclip.copy({action.text or ''!r}); pyautogui.hotkey('ctrl', 'v')"
    if action.type == "desktop_keypress":
        keys = _normalize_pyautogui_keys(action.keys or [])
        if len(keys) == 1:
            return f"pyautogui.press({keys[0]!r})"
        return f"pyautogui.hotkey({', '.join(repr(key) for key in keys)})"
    if action.type == "desktop_drag":
        points = action.path or []
        if len(points) < 2:
            return ""
        first = points[0]
        lines = [f"pyautogui.moveTo({int(first['x'])}, {int(first['y'])})", "pyautogui.mouseDown()"]
        for point in points[1:]:
            lines.append(f"pyautogui.moveTo({int(point['x'])}, {int(point['y'])}, duration=0.1)")
        lines.append("pyautogui.mouseUp()")
        return "\n".join(lines)
    return ""


def _normalize_pyautogui_keys(keys: list[Any]) -> list[str]:
    normalized: list[str] = []
    aliases = {
        "control": "ctrl",
        "return": "enter",
        "esc": "escape",
        "cmd": "command",
    }
    for key in keys:
        for part in str(key).replace("-", "+").split("+"):
            cleaned = part.strip().lower()
            if cleaned:
                normalized.append(aliases.get(cleaned, cleaned))
    return normalized


def _run_pyautogui(sandbox: Any, code: str) -> tuple[bool, str]:
    preamble = "import pyautogui, pyperclip, time; pyautogui.FAILSAFE = False"
    script = preamble + "\n" + code
    command = f"DISPLAY=:0 python3 -c {shlex.quote(script)}"
    try:
        result = sandbox.commands.run(command, timeout=60)
        return True, ((result.stdout or "") + (result.stderr or "")).strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


if __name__ == "__main__":
    raise SystemExit(main())
