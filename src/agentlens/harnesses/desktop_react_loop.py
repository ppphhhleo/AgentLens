from __future__ import annotations

from pathlib import Path
import time
from typing import Callable

from agentlens.harnesses.desktop_actions import (
    capture_desktop_screenshot_event,
    execute_desktop_action,
    format_desktop_action,
)
from agentlens.harnesses.interventions import RepeatedActionIntervention
from agentlens.harnesses.tool_gating import ToolSet, tool_name_for
from agentlens.models.base import ChatModel, ModelStep, ScreenshotObservation
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType


def run_desktop_react_loop(
    *,
    sandbox,
    model: ChatModel,
    goal: str,
    max_steps: int,
    screenshot_dir: Path,
    run_id: str,
    toolset: ToolSet | None = None,
    intervention_config: dict | None = None,
    model_max_attempts: int = 3,
    model_retry_sleep_s: float = 1.0,
    max_actions_per_round: int = 1,
    viewport: dict[str, int] | None = None,
    log_action: Callable[[str], None] | None = None,
) -> tuple[str | None, list[TrajectoryEvent]]:
    events: list[TrajectoryEvent] = []
    history: list[ModelStep] = []
    answer: str | None = None
    if toolset is None:
        toolset = ToolSet(allowed=frozenset())
    intervention = RepeatedActionIntervention.from_config(intervention_config)

    viewport = viewport or {"width": 1920, "height": 1080}
    initial = capture_desktop_screenshot_event(
        sandbox,
        screenshot_dir,
        0,
        goal,
        viewport=viewport,
    )
    events.append(initial)
    last_screenshot = initial.artifact_paths[0] if initial.artifact_paths else None
    pending_tool_output = None
    terminal_step_index = 0
    _log(log_action, f"[{run_id} step=0] desktop screenshot -> {last_screenshot or 'failed'}")

    for step_index in range(1, max_steps + 1):
        terminal_step_index = step_index
        observation = ScreenshotObservation(
            step_index=step_index,
            max_steps=max_steps,
            screenshot_path=last_screenshot,
            url="desktop://sandbox",
            viewport=viewport,
            tool_output_since_last_step=pending_tool_output,
        )
        pending_tool_output = None

        model_step: ModelStep | None = None
        for attempt in range(1, max(model_max_attempts, 1) + 1):
            try:
                model_step = model.step(goal=goal, observation=observation, history=history)
                break
            except Exception as exc:  # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"
                exhausted = attempt >= max(model_max_attempts, 1)
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.MODEL_MESSAGE,
                        step_index=step_index,
                        data={
                            "error": err,
                            "mock": False,
                            "retry_attempt": attempt,
                            "retry_exhausted": exhausted,
                        },
                    )
                )
                _log(
                    log_action, f"[{run_id} step={step_index}] model_error attempt={attempt}: {err}"
                )
                if exhausted:
                    break
                time.sleep(model_retry_sleep_s * attempt)
        if model_step is None:
            break

        history.append(model_step)
        round_actions = model_step.action_list()
        if max_actions_per_round < 1:
            max_actions_per_round = 1
        ordered_action_batch = bool((model_step.extra or {}).get("ordered_action_batch"))
        if len(round_actions) > max_actions_per_round and not ordered_action_batch:
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
                    "action": model_step.action.model_dump(
                        mode="json", exclude_none=True, exclude_defaults=True
                    ),
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
                    "provider_action_group_sizes": (model_step.extra or {}).get(
                        "provider_action_group_sizes"
                    ),
                    "mock": False,
                },
            )
        )

        for subaction_index, action in enumerate(round_actions, start=1):
            _log(
                log_action,
                f"[{run_id} step={step_index}.{subaction_index}] {format_desktop_action(action)}",
            )
            common = {
                "round_index": step_index,
                "subaction_index": subaction_index,
                "actions_in_round": len(round_actions),
            }

            decision = intervention.observe(action)
            if decision.triggered:
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
                pending_tool_output = _merge_tool_outputs(
                    pending_tool_output,
                    f"[gating violation]\n{gating_msg}",
                )
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.GATING_VIOLATION,
                        step_index=step_index,
                        data={
                            **common,
                            "action": action.model_dump(
                                mode="json", exclude_none=True, exclude_defaults=True
                            ),
                            "tool_name": tool_name_for(action),
                            "message": gating_msg,
                        },
                    )
                )
                continue

            if action.type == "final_answer":
                answer = action.answer
                break

            output, error = execute_desktop_action(sandbox, action)
            pending_tool_output = _merge_tool_outputs(
                pending_tool_output,
                _format_tool_output(action.type, output, error),
            )
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.TOOL_CALL,
                    step_index=step_index,
                    data={
                        **common,
                        "tool_name": tool_name_for(action),
                        "expanded_from_tool": ("computer.batch" if ordered_action_batch else None),
                        "action": action.model_dump(
                            mode="json", exclude_none=True, exclude_defaults=True
                        ),
                        "ok": not bool(error),
                        "output": output,
                        "error": error,
                        "extra": {"executor": "desktop_sandbox"},
                    },
                )
            )
            screenshot = capture_desktop_screenshot_event(
                sandbox,
                screenshot_dir,
                step_index,
                goal,
                name_suffix=_subaction_suffix(len(round_actions), subaction_index),
                viewport=viewport,
            )
            events.append(screenshot)
            if screenshot.artifact_paths:
                last_screenshot = screenshot.artifact_paths[0]
            _log(
                log_action,
                f"[{run_id} step={step_index}.{subaction_index}] desktop screenshot -> {last_screenshot or 'failed'}",
            )

        if answer is not None:
            break

    terminal = capture_desktop_screenshot_event(
        sandbox,
        screenshot_dir,
        terminal_step_index,
        goal,
        name_suffix="final",
        viewport=viewport,
    )
    terminal.data["terminal_state"] = True
    events.append(terminal)
    if terminal.artifact_paths:
        last_screenshot = terminal.artifact_paths[0]
    _log(
        log_action,
        f"[{run_id} step={terminal_step_index}] final desktop screenshot -> "
        f"{last_screenshot or 'failed'}",
    )

    return answer, events


def _format_tool_output(action_type: str, output: str, error: str, max_chars: int = 1500) -> str:
    text = output or ""
    if error:
        text = (text + ("\n" if text else "") + f"ERROR: {error}").strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"
    return f"[{action_type} result]\n{text or '(no output)'}"


def _merge_tool_outputs(left: str | None, right: str, max_chars: int = 6000) -> str:
    merged = right if not left else f"{left}\n\n{right}"
    if len(merged) > max_chars:
        return merged[:max_chars] + "...[truncated]"
    return merged


def _subaction_suffix(actions_in_round: int, subaction_index: int) -> str:
    if actions_in_round <= 1:
        return ""
    return f"a{subaction_index:02d}"


def _log(log_action: Callable[[str], None] | None, message: str) -> None:
    if log_action is not None:
        log_action(message)
