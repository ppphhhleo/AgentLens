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


def run_screenshot_react_loop(
    *,
    page,
    model: ChatModel,
    goal: str,
    max_steps: int,
    screenshot_dir: Path,
    run_id: str,
    toolset: ToolSet | None = None,
    log_action: Callable[[str], None] | None = None,
) -> tuple[str | None, list[TrajectoryEvent]]:
    """Real screenshot ReAct loop.

    screenshot -> model.step -> execute -> screenshot, until final_answer or max_steps.

    Returns (final_answer, events). final_answer is None if the loop exits without one.
    """
    events: list[TrajectoryEvent] = []
    history: list[ModelStep] = []
    answer: str | None = None
    if toolset is None:
        toolset = ToolSet(allowed=frozenset())  # unrestricted

    initial_screenshot = capture_screenshot_event(
        page=page, screenshot_dir=screenshot_dir, step_index=0, goal=goal
    )
    events.append(initial_screenshot)
    _log(log_action, f"[{run_id} step=0] screenshot -> {initial_screenshot.artifact_paths[0]}")

    last_screenshot_path: Path = initial_screenshot.artifact_paths[0]
    pending_tool_output: str | None = None  # carries web_search etc. into next obs

    for step_index in range(1, max_steps + 1):
        observation = ScreenshotObservation(
            step_index=step_index,
            screenshot_path=last_screenshot_path,
            url=page.url,
            viewport=page.viewport_size or {"width": 0, "height": 0},
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
