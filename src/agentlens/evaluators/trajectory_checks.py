from __future__ import annotations

from collections import Counter
from typing import Any


def evaluate_trajectory_checks(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Compute process-level flags directly from raw trajectory events."""
    model_actions = _actions(trajectory, event_types={"model_message"})
    executed_actions = _actions(
        trajectory,
        event_types={"browser_action", "tool_call", "shell_command", "file_edit"},
    )
    errors = _errors(trajectory)
    loops = _repeated_action_runs(model_actions)
    tool_counts = Counter(action.get("tool_name") or action.get("type") for action in model_actions)
    executed_tool_counts = Counter(
        action.get("tool_name") or action.get("type") for action in executed_actions
    )
    action_type_counts = Counter(action.get("type") for action in model_actions)
    final_answer_steps = [
        action["step_index"] for action in model_actions if action.get("type") == "final_answer"
    ]
    step_count = (trajectory.get("metrics") or {}).get("steps")
    flags = []
    if not final_answer_steps:
        flags.append("missing_final_answer")
    if errors:
        flags.append("execution_or_model_errors")
    if loops:
        flags.append("repeated_action_loop")
    if step_count and final_answer_steps and final_answer_steps[-1] == step_count:
        flags.append("final_answer_at_step_limit")

    return {
        "phase": "evaluating",
        "kind": "trajectory",
        "model_action_count": len(model_actions),
        "executed_action_count": len(executed_actions),
        "tool_counts": dict(sorted(tool_counts.items())),
        "executed_tool_counts": dict(sorted(executed_tool_counts.items())),
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "final_answer_steps": final_answer_steps,
        "error_count": len(errors),
        "errors": errors[:20],
        "repeated_action_runs": loops,
        "flags": flags,
    }


def _actions(
    trajectory: dict[str, Any],
    *,
    event_types: set[str],
) -> list[dict[str, Any]]:
    out = []
    for event in trajectory.get("events", []):
        if event.get("event_type") not in event_types:
            continue
        data = event.get("data") or {}
        action = data.get("action")
        if not isinstance(action, dict):
            continue
        out.append(
            {
                **action,
                "step_index": event.get("step_index"),
                "event_type": event.get("event_type"),
                "tool_name": data.get("tool_name") or action.get("mcp_tool"),
            }
        )
    return out


def _errors(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for event in trajectory.get("events", []):
        data = event.get("data") or {}
        error = data.get("error")
        if error:
            out.append(
                {
                    "step_index": event.get("step_index"),
                    "event_type": event.get("event_type"),
                    "error": str(error),
                }
            )
    return out


def _repeated_action_runs(
    actions: list[dict[str, Any]],
    *,
    threshold: int = 5,
) -> list[dict[str, Any]]:
    runs = []
    current_sig = None
    current: list[dict[str, Any]] = []
    for action in actions:
        sig = _signature(action)
        if sig != current_sig:
            if len(current) >= threshold:
                runs.append(_run_record(current_sig, current))
            current_sig = sig
            current = []
        current.append(action)
    if len(current) >= threshold:
        runs.append(_run_record(current_sig, current))
    return runs


def _signature(action: dict[str, Any]) -> str:
    return "|".join(
        str(action.get(key) or "")
        for key in ("type", "tool_name", "x", "y", "selector", "bid", "mark", "mcp_tool")
    )


def _run_record(signature: str | None, actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "signature": signature,
        "start_step": actions[0].get("step_index"),
        "end_step": actions[-1].get("step_index"),
        "count": len(actions),
        "action_type": actions[0].get("type"),
        "tool_name": actions[0].get("tool_name"),
    }
