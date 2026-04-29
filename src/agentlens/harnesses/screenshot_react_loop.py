from __future__ import annotations

from pathlib import Path
from typing import Callable

from agentlens.harnesses.browser_actions import (
    capture_screenshot_event,
    execute_action,
    format_action,
)
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
            screenshot_path=last_screenshot_path if (use_screenshot or use_marks) else None,
            url=page.url,
            viewport=page.viewport_size or {"width": 0, "height": 0},
            axtree_text=axtree_text if use_axtree else None,
            mark_registry=mark_registry if use_marks else None,
            tool_output_since_last_step=pending_tool_output,
        )
        pending_tool_output = None  # one-shot — model consumed it now

        try:
            model_step = model.step(goal=goal, observation=observation, history=history)
        except Exception as exc:  # noqa: BLE001 - model errors belong in trajectory data.
            err = f"{type(exc).__name__}: {exc}"
            _log(log_action, f"[{run_id} step={step_index}] model_error: {err}")
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.MODEL_MESSAGE,
                    step_index=step_index,
                    data={"error": err, "mock": False},
                )
            )
            break

        history.append(model_step)
        action = model_step.action
        _log(log_action, f"[{run_id} step={step_index}] {format_action(action)}")

        events.append(
            TrajectoryEvent(
                event_type=TrajectoryEventType.MODEL_MESSAGE,
                step_index=step_index,
                data={
                    "thought": model_step.thought,
                    "action": action.model_dump(mode="json"),
                    "tool_name": tool_name_for(action),
                    "raw_response": model_step.raw_response,
                    "prompt_tokens": model_step.prompt_tokens,
                    "completion_tokens": model_step.completion_tokens,
                    "model_meta": model_step.extra,
                    "mock": False,
                },
            )
        )

        # Gate the action against the harness's tool allow-list.
        allowed, gating_msg = toolset.gate_action(action)
        if not allowed:
            _log(log_action, f"[{run_id} step={step_index}] gating: {gating_msg}")
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.GATING_VIOLATION,
                    step_index=step_index,
                    data={
                        "action": action.model_dump(mode="json"),
                        "tool_name": tool_name_for(action),
                        "message": gating_msg,
                    },
                )
            )
            # Skip execution but keep looping; next step the model gets a
            # fresh screenshot (unchanged) and can pick something allowed.
            continue

        if action.type == "final_answer":
            answer = action.answer
            break

        # Handle tool actions that don't touch the page (no Playwright call,
        # no screenshot capture). Result is queued for the next observation.
        if action.type == "web_search":
            from agentlens.tools.openai_search import (
                format_for_observation,
                openai_web_search,
            )
            search_result = openai_web_search(action.query or "")
            pending_tool_output = format_for_observation(search_result)
            _log(
                log_action,
                f"[{run_id} step={step_index}] web_search -> "
                f"{len(search_result.text)} chars, {len(search_result.sources)} sources"
                + (f" (error: {search_result.error})" if search_result.error else ""),
            )
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.TOOL_CALL,
                    step_index=step_index,
                    data={
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
            continue

        # Sandbox-only multi-tool actions. Require an AIOSandboxSession.
        if action.type in {"run_python", "shell", "read_file", "write_file"}:
            if sandbox is None:
                err_msg = (
                    f"action {action.type!r} requires a sandbox session "
                    f"(set tool_harness.extra.browser_source=aio_sandbox)"
                )
                pending_tool_output = f"[{action.type} unavailable: {err_msg}]"
                _log(log_action, f"[{run_id} step={step_index}] {action.type}: {err_msg}")
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.TOOL_CALL,
                        step_index=step_index,
                        data={
                            "tool_name": tool_name_for(action),
                            "action": action.model_dump(mode="json"),
                            "error": err_msg,
                        },
                    )
                )
                continue
            result = _run_sandbox_action(sandbox, action)
            pending_tool_output = _format_sandbox_result(action, result)
            _log(
                log_action,
                f"[{run_id} step={step_index}] {action.type} -> "
                f"{'ok' if result.ok else 'err'} ({len(result.output)} chars)"
                + (f" err={result.error[:80]!r}" if result.error else ""),
            )
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.TOOL_CALL,
                    step_index=step_index,
                    data={
                        "tool_name": tool_name_for(action),
                        "action": action.model_dump(mode="json"),
                        "ok": result.ok,
                        "output": result.output,
                        "error": result.error,
                        "extra": result.extra,
                    },
                )
            )
            continue

        action_error = execute_action(page, action)
        if action_error:
            _log(log_action, f"[{run_id} step={step_index}] error: {action_error}")
        events.append(
            TrajectoryEvent(
                event_type=TrajectoryEventType.BROWSER_ACTION,
                step_index=step_index,
                data={
                    "action": action.model_dump(mode="json"),
                    "error": action_error,
                },
            )
        )

        screenshot_event = capture_screenshot_event(
            page=page, screenshot_dir=screenshot_dir, step_index=step_index, goal=goal
        )
        events.append(screenshot_event)
        last_screenshot_path = screenshot_event.artifact_paths[0]
        _log(log_action, f"[{run_id} step={step_index}] screenshot -> {last_screenshot_path}")

    return answer, events


def _log(log_action: Callable[[str], None] | None, message: str) -> None:
    if log_action is not None:
        log_action(message)


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
