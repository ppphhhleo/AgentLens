from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import json
import re
import subprocess
import time
from typing import Callable

from agentlens.harnesses.browser_actions import (
    capture_screenshot_event,
    execute_action,
    format_action,
    show_hint,
)
from agentlens.harnesses.interventions import RepeatedActionIntervention
from agentlens.harnesses.tool_gating import ToolSet, tool_name_for
from agentlens.models.base import ChatModel, ModelStep, ScreenshotObservation
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType


def _maybe_axtree(page, *, capture: bool) -> str | None:
    if not capture:
        return None
    try:
        from agentlens.perception import snapshot_axtree
        return snapshot_axtree(page).text
    except Exception:  # noqa: BLE001 - perception is best-effort
        return None


def _maybe_marks(page, *, enable: bool) -> dict[str, str]:
    if not enable:
        return {}
    try:
        from agentlens.perception import inject_marks
        som = inject_marks(page)
        return dict(som.registry)
    except Exception:  # noqa: BLE001
        return {}


def _strip_marks(page, *, enabled: bool) -> None:
    if not enabled:
        return
    try:
        from agentlens.perception import strip_marks
        strip_marks(page)
    except Exception:  # noqa: BLE001
        pass


def _model_retry_delay_seconds(
    exc: Exception,
    *,
    attempt: int,
    base_sleep_s: float,
    max_sleep_s: float,
) -> float:
    """Choose a retry delay, respecting provider rate-limit hints when present."""

    base = max(float(base_sleep_s), 0.1)
    cap = max(float(max_sleep_s), base)
    exponential = min(cap, base * (2 ** max(attempt - 1, 0)))
    hinted = _provider_retry_hint_seconds(str(exc))
    if hinted is None:
        return exponential
    return min(cap, max(exponential, hinted * 1.5, base))


def _provider_retry_hint_seconds(message: str) -> float | None:
    match = re.search(
        r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s|sec|seconds?)",
        message,
        re.I,
    )
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "ms":
        return value / 1000.0
    return value


def run_screenshot_react_loop(
    *,
    page,
    model: ChatModel,
    goal: str,
    max_steps: int,
    screenshot_dir: Path,
    run_id: str,
    toolset: ToolSet | None = None,
    sandbox=None,                  # AIOSandboxSession or None for browser-only runs
    input_modes: list[str] | None = None,
    intervention_config: dict | None = None,
    model_max_attempts: int = 3,
    model_retry_sleep_s: float = 1.0,
    model_retry_max_sleep_s: float = 45.0,
    max_actions_per_round: int = 1,
    log_action: Callable[[str], None] | None = None,
) -> tuple[str | None, list[TrajectoryEvent]]:
    """Mode-aware ReAct loop.

    `input_modes` controls which perceptual modalities are placed in
    each observation:
      ["screenshot"]            (default) — current vision-only behavior
      ["axtree"]                — DOM/AXTree-only (text), no screenshot in prompt
      ["screenshot", "axtree"]  — both (max-info hybrid)

    Screenshots are ALWAYS captured to disk for trajectory record,
    regardless of mode — they're just only fed into the model prompt
    when "screenshot" is in input_modes.

    Returns (final_answer, events). final_answer is None if the loop
    exits without one.
    """
    events: list[TrajectoryEvent] = []
    history: list[ModelStep] = []
    answer: str | None = None
    if toolset is None:
        toolset = ToolSet(allowed=frozenset())  # unrestricted
    if not input_modes:
        input_modes = ["screenshot"]
    use_screenshot = "screenshot" in input_modes
    use_axtree = "axtree" in input_modes
    # set_of_marks implies "screenshot" (we mark + capture). It also requires
    # axtree to have run first so elements have bid attributes; we ensure
    # axtree extraction below regardless of `use_axtree` if marks are on.
    use_marks = "set_of_marks" in input_modes

    initial_screenshot = capture_screenshot_event(
        page=page, screenshot_dir=screenshot_dir, step_index=0, goal=goal
    )
    events.append(initial_screenshot)
    _log(log_action, f"[{run_id} step=0] screenshot -> {initial_screenshot.artifact_paths[0]}")

    last_screenshot_path: Path = initial_screenshot.artifact_paths[0]
    pending_tool_output: str | None = None  # carries web_search etc. into next obs
    intervention = RepeatedActionIntervention.from_config(intervention_config)

    for step_index in range(1, max_steps + 1):
        # Always extract axtree if marks are on (marks need bids on the page).
        axtree_text = _maybe_axtree(page, capture=use_axtree or use_marks)
        # If marks mode is enabled, inject the overlay, capture a fresh
        # screenshot WITH marks visible, then strip them so the page stays
        # clean for any subsequent non-marked observations.
        mark_registry: dict[str, str] = {}
        if use_marks:
            mark_registry = _maybe_marks(page, enable=True)
            # Use suffix so this doesn't collide with the post-action
            # capture below (which writes step_NNN.png unsuffixed).
            marked_screenshot = capture_screenshot_event(
                page=page,
                screenshot_dir=screenshot_dir,
                step_index=step_index,
                goal=goal,
                name_suffix="marks",
            )
            events.append(marked_screenshot)
            last_screenshot_path = marked_screenshot.artifact_paths[0]
            _strip_marks(page, enabled=True)

        observation = ScreenshotObservation(
            step_index=step_index,
            max_steps=max_steps,
            screenshot_path=last_screenshot_path if (use_screenshot or use_marks) else None,
            url=page.url,
            viewport=page.viewport_size or {"width": 0, "height": 0},
            axtree_text=axtree_text if use_axtree else None,
            mark_registry=mark_registry if use_marks else None,
            tool_output_since_last_step=pending_tool_output,
        )
        pending_tool_output = None  # one-shot — model consumed it now

        model_step: ModelStep | None = None
        for attempt in range(1, max(model_max_attempts, 1) + 1):
            try:
                model_step = model.step(goal=goal, observation=observation, history=history)
                break
            except Exception as exc:  # noqa: BLE001 - model errors belong in trajectory data.
                err = f"{type(exc).__name__}: {exc}"
                exhausted = attempt >= max(model_max_attempts, 1)
                _log(
                    log_action,
                    f"[{run_id} step={step_index}] model_error "
                    f"attempt={attempt}/{max(model_max_attempts, 1)}: {err}",
                )
                retry_sleep_s = _model_retry_delay_seconds(
                    exc,
                    attempt=attempt,
                    base_sleep_s=model_retry_sleep_s,
                    max_sleep_s=model_retry_max_sleep_s,
                )
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.MODEL_MESSAGE,
                        step_index=step_index,
                        data={
                            "error": err,
                            "mock": False,
                            "retry_attempt": attempt,
                            "retry_exhausted": exhausted,
                            "retry_sleep_s": None if exhausted else retry_sleep_s,
                        },
                    )
                )
                if exhausted:
                    break
                _log(
                    log_action,
                    f"[{run_id} step={step_index}] retrying model call "
                    f"in {retry_sleep_s:.1f}s",
                )
                time.sleep(retry_sleep_s)
        if model_step is None:
            break

        history.append(model_step)
        round_actions = model_step.action_list()
        if max_actions_per_round < 1:
            max_actions_per_round = 1
        if len(round_actions) > max_actions_per_round:
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.GATING_VIOLATION,
                    step_index=step_index,
                    data={
                        "message": (
                            f"model requested {len(round_actions)} actions in one round; "
                            f"executing first {max_actions_per_round}"
                        ),
                        "round_index": step_index,
                    },
                )
            )
            round_actions = round_actions[:max_actions_per_round]

        events.append(
            TrajectoryEvent(
                event_type=TrajectoryEventType.MODEL_MESSAGE,
                step_index=step_index,
                data={
                    "thought": model_step.thought,
                    "action": model_step.action.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
                    "actions": [
                        action.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
                        for action in round_actions
                    ],
                    "tool_name": tool_name_for(model_step.action),
                    "tool_names": [tool_name_for(action) for action in round_actions],
                    "round_index": step_index,
                    "actions_in_round": len(round_actions),
                    "raw_response": model_step.raw_response,
                    "prompt_tokens": model_step.prompt_tokens,
                    "completion_tokens": model_step.completion_tokens,
                    "model_meta": model_step.extra,
                    "provider_tool_call": (model_step.extra or {}).get("provider_tool_call"),
                    "provider_tool_calls": (model_step.extra or {}).get("provider_tool_calls"),
                    "mock": False,
                },
            )
        )

        stop_round = False
        for subaction_index, action in enumerate(round_actions, start=1):
            _log(
                log_action,
                f"[{run_id} step={step_index}.{subaction_index}] {format_action(action)}",
            )
            common = {
                "round_index": step_index,
                "subaction_index": subaction_index,
                "actions_in_round": len(round_actions),
            }

            decision = intervention.observe(action)
            if decision.triggered:
                _log(
                    log_action,
                    f"[{run_id} step={step_index}.{subaction_index}] intervention: "
                    f"{decision.kind} mode={decision.mode}",
                )
                show_hint(page, decision.message)
                pending_tool_output = _merge_tool_outputs(
                    pending_tool_output,
                    f"[intervention:{decision.kind}]\n{decision.message}",
                )
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.USER_INTERVENTION,
                        step_index=step_index,
                        data={
                            **common,
                            "source": "intervention_monitor",
                            "kind": decision.kind,
                            "mode": decision.mode,
                            "message": decision.message,
                            "details": decision.details,
                        },
                    )
                )

            allowed, gating_msg = toolset.gate_action(action)
            if not allowed:
                _log(log_action, f"[{run_id} step={step_index}.{subaction_index}] gating: {gating_msg}")
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.GATING_VIOLATION,
                        step_index=step_index,
                        data={
                            **common,
                            "action": action.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
                            "tool_name": tool_name_for(action),
                            "message": gating_msg,
                        },
                    )
                )
                continue

            if action.type == "final_answer":
                answer = action.answer
                stop_round = True
                break

            if action.type == "web_search":
                from agentlens.tools.openai_search import (
                    format_for_observation,
                    openai_web_search,
                )

                search_result = openai_web_search(action.query or "")
                pending_tool_output = format_for_observation(search_result)
                _log(
                    log_action,
                    f"[{run_id} step={step_index}.{subaction_index}] web_search -> "
                    f"{len(search_result.text)} chars, {len(search_result.sources)} sources"
                    + (f" (error: {search_result.error})" if search_result.error else ""),
                )
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.TOOL_CALL,
                        step_index=step_index,
                        data={
                            **common,
                            "tool_name": "web.openai_search",
                            "query": action.query,
                            "text": search_result.text,
                            "sources": search_result.sources,
                            "model": search_result.model,
                            "input_tokens": search_result.input_tokens,
                            "output_tokens": search_result.output_tokens,
                            "error": search_result.error,
                        },
                    )
                )
                stop_round = True
                break

            if action.type == "mcp_tool":
                from agentlens.tools.mcp import format_for_observation, run_mcp_tool

                mcp_result = run_mcp_tool(action, page=page)
                pending_tool_output = format_for_observation(mcp_result)
                _log(
                    log_action,
                    f"[{run_id} step={step_index}.{subaction_index}] {action.mcp_tool} -> "
                    f"{'ok' if mcp_result.ok else 'err'}"
                    + (f" err={mcp_result.error[:80]!r}" if mcp_result.error else ""),
                )
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.TOOL_CALL,
                        step_index=step_index,
                        data={
                            **common,
                            "tool_name": tool_name_for(action),
                            "action": action.model_dump(
                                mode="json",
                                exclude_none=True,
                                exclude_defaults=True,
                            ),
                            "ok": mcp_result.ok,
                            "output": mcp_result.output,
                            "error": mcp_result.error,
                            "extra": mcp_result.extra,
                        },
                    )
                )
                screenshot_event = capture_screenshot_event(
                    page=page,
                    screenshot_dir=screenshot_dir,
                    step_index=step_index,
                    goal=goal,
                    name_suffix=_subaction_suffix(len(round_actions), subaction_index),
                )
                events.append(screenshot_event)
                last_screenshot_path = screenshot_event.artifact_paths[0]
                _log(log_action, f"[{run_id} step={step_index}.{subaction_index}] screenshot -> {last_screenshot_path}")
                stop_round = True
                break

            if action.type in {"run_python", "shell", "read_file", "write_file"}:
                if sandbox is None:
                    err_msg = (
                        f"action {action.type!r} requires a sandbox session "
                        f"(set tool_harness.extra.browser_source=aio_sandbox)"
                    )
                    pending_tool_output = f"[{action.type} unavailable: {err_msg}]"
                    _log(log_action, f"[{run_id} step={step_index}.{subaction_index}] {action.type}: {err_msg}")
                    events.append(
                        TrajectoryEvent(
                            event_type=TrajectoryEventType.TOOL_CALL,
                            step_index=step_index,
                            data={
                                **common,
                                "tool_name": tool_name_for(action),
                                "action": action.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
                                "error": err_msg,
                            },
                        )
                    )
                    stop_round = True
                    break
                manifest_before = _snapshot_sandbox_files(sandbox)
                result = _run_sandbox_action(sandbox, action)
                manifest_after = _snapshot_sandbox_files(sandbox)
                artifact_diff = _diff_file_manifests(manifest_before, manifest_after)
                pending_tool_output = _format_sandbox_result(action, result)
                _log(
                    log_action,
                    f"[{run_id} step={step_index}.{subaction_index}] {action.type} -> "
                    f"{'ok' if result.ok else 'err'} ({len(result.output)} chars)"
                    + (f" err={result.error[:80]!r}" if result.error else ""),
                )
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.TOOL_CALL,
                        step_index=step_index,
                        data={
                            **common,
                            "tool_name": tool_name_for(action),
                            "action": action.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
                            "ok": result.ok,
                            "output": result.output,
                            "error": result.error,
                            "extra": result.extra,
                            "artifact_diff": artifact_diff,
                        },
                    )
                )
                stop_round = True
                break

            action_error = execute_action(page, action)
            if action_error:
                _log(log_action, f"[{run_id} step={step_index}.{subaction_index}] error: {action_error}")
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.BROWSER_ACTION,
                    step_index=step_index,
                    data={
                        **common,
                        "action": action.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
                        "error": action_error,
                    },
                )
            )

            screenshot_event = capture_screenshot_event(
                page=page,
                screenshot_dir=screenshot_dir,
                step_index=step_index,
                goal=goal,
                name_suffix=_subaction_suffix(len(round_actions), subaction_index),
            )
            events.append(screenshot_event)
            last_screenshot_path = screenshot_event.artifact_paths[0]
            _log(log_action, f"[{run_id} step={step_index}.{subaction_index}] screenshot -> {last_screenshot_path}")

        if answer is not None:
            break
        if stop_round:
            continue

    return answer, events


def _log(log_action: Callable[[str], None] | None, message: str) -> None:
    if log_action is not None:
        log_action(message)


def _subaction_suffix(actions_in_round: int, subaction_index: int) -> str:
    if actions_in_round <= 1:
        return ""
    return f"a{subaction_index:02d}"


def _run_sandbox_action(sandbox, action):
    """Dispatch a sandbox-only action to its session method."""
    if action.type == "run_python":
        return sandbox.run_python(action.code or "")
    if action.type == "shell":
        return sandbox.shell(action.cmd or "")
    if action.type == "read_file":
        return sandbox.read_file(action.file_path or "")
    if action.type == "write_file":
        return sandbox.write_file(action.file_path or "", action.content or "")
    raise ValueError(f"unhandled sandbox action: {action.type!r}")


def _format_sandbox_result(action, result, max_chars: int = 1500) -> str:
    """Compact text block for the next observation."""
    head = f"[{action.type} result]"
    body = result.output
    if result.error:
        body = (body + ("\n" if body else "") + f"ERROR: {result.error}").strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "...[truncated]"
    return f"{head}\n{body or '(no output)'}"


def _merge_tool_outputs(left: str | None, right: str) -> str:
    if not left:
        return right
    return f"{left}\n\n{right}"


def _snapshot_sandbox_files(sandbox, *, max_files: int = 2000) -> dict[str, dict]:
    """Best-effort file manifest for sandbox artifact tracking.

    This is intentionally independent from the agent-visible tool result: it
    records whether code/shell/file actions created or modified artifacts
    without injecting extra text into the model context.
    """
    home_dir = getattr(sandbox, "home_dir", None) or "/home/gem"
    roots = list(
        getattr(sandbox, "watch_paths", None)
        or [home_dir, "/tmp", f"{home_dir}/Downloads"]
    )
    cmd = (
        "python3 - <<'PY'\n"
        "import json, os\n"
        f"roots = {roots!r}\n"
        "skip_dirs = {'.cache', '.config', '.local', '.npm', '__pycache__', "
        "'node_modules', '.venv'}\n"
        "items = {}\n"
        "for root in roots:\n"
        "    if not os.path.exists(root):\n"
        "        continue\n"
        "    for dirpath, dirnames, filenames in os.walk(root):\n"
        "        dirnames[:] = [d for d in dirnames if d not in skip_dirs]\n"
        "        for name in filenames:\n"
        "            path = os.path.join(dirpath, name)\n"
        "            try:\n"
        "                st = os.stat(path)\n"
        "            except OSError:\n"
        "                continue\n"
        "            items[path] = {'size': st.st_size, 'mtime': round(st.st_mtime, 6)}\n"
        f"            if len(items) >= {max_files}:\n"
        "                print(json.dumps(items, sort_keys=True))\n"
        "                raise SystemExit\n"
        "print(json.dumps(items, sort_keys=True))\n"
        "PY"
    )
    output: str | None = _snapshot_with_docker_exec(sandbox, cmd)
    if output is None:
        try:
            result = sandbox.shell(cmd, timeout_sec=15)
        except Exception:  # noqa: BLE001
            return {}
        if not getattr(result, "ok", False):
            return {}
        output = result.output or "{}"
    try:
        payload = json.loads(output)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(path): meta
        for path, meta in payload.items()
        if isinstance(path, str) and isinstance(meta, Mapping)
    }


def _snapshot_with_docker_exec(sandbox, cmd: str) -> str | None:
    container_name = getattr(sandbox, "container_name", None)
    if not container_name:
        return None
    try:
        result = subprocess.run(
            ["docker", "exec", container_name, "bash", "-lc", cmd],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:  # noqa: BLE001
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _diff_file_manifests(
    before: dict[str, dict],
    after: dict[str, dict],
    *,
    max_paths: int = 200,
) -> dict[str, object]:
    before_keys = set(before)
    after_keys = set(after)
    created = sorted(after_keys - before_keys)
    deleted = sorted(before_keys - after_keys)
    modified = sorted(
        path
        for path in (before_keys & after_keys)
        if before.get(path) != after.get(path)
    )
    return {
        "created": created[:max_paths],
        "modified": modified[:max_paths],
        "deleted": deleted[:max_paths],
        "truncated": (
            len(created) > max_paths
            or len(modified) > max_paths
            or len(deleted) > max_paths
        ),
        "before_count": len(before),
        "after_count": len(after),
    }
