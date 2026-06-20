from __future__ import annotations

from pathlib import Path
from typing import Any

from agentlens.schemas import TaskConfig, load_experiment_config
from agentlens.validators.answers import validate_answer


def evaluate_outcome(
    trajectory: dict[str, Any],
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate final task outcome from trajectory metadata and final answer.

    The adapter records a validation event at run time. This evaluator preserves
    that original result and, when a config is available, recomputes the current
    validator so changed validators are visible without mutating the trajectory.
    """
    validation = _last_event_data(trajectory, "validation_event")
    metrics = trajectory.get("metrics") or {}
    final_answer = _final_answer(trajectory)
    task_payload = trajectory.get("task") or {}
    current = None
    if config_path is not None:
        task = _task_from_config(config_path, str(task_payload.get("id") or ""))
        if task is not None:
            success, score, message = validate_answer(
                final_answer,
                task,
                final_url=validation.get("final_url") if isinstance(validation, dict) else None,
                screenshot_paths=_screenshot_paths(trajectory),
            )
            current = {
                "success": success,
                "score": score,
                "message": message,
                "validator": task.answer_validator,
            }

    return {
        "phase": "evaluating",
        "kind": "outcome",
        "recorded": {
            "success": metrics.get("success"),
            "score": metrics.get("score"),
            "message": validation.get("message") if isinstance(validation, dict) else None,
            "validator": validation.get("answer_validator") if isinstance(validation, dict) else task_payload.get("answer_validator"),
            "final_answer": final_answer,
            "expected_answer": task_payload.get("expected_answer"),
        },
        "current": current,
    }


def _last_event_data(trajectory: dict[str, Any], event_type: str) -> dict[str, Any]:
    for event in reversed(trajectory.get("events", [])):
        if event.get("event_type") == event_type and isinstance(event.get("data"), dict):
            return event["data"]
    return {}


def _final_answer(trajectory: dict[str, Any]) -> str | None:
    for event in trajectory.get("events", []):
        data = event.get("data") or {}
        action = data.get("action") or {}
        if action.get("type") == "final_answer":
            answer = action.get("answer")
            return str(answer) if answer is not None else None
    validation = _last_event_data(trajectory, "validation_event")
    answer = validation.get("answer")
    return str(answer) if answer is not None else None


def _screenshot_paths(trajectory: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for event in trajectory.get("events", []):
        if event.get("event_type") == "screenshot":
            paths.extend(Path(str(path)) for path in event.get("artifact_paths", []) or [])
    return paths


def _task_from_config(config_path: Path, task_id: str) -> TaskConfig | None:
    try:
        config = load_experiment_config(config_path)
    except Exception:
        return None
    for task in config.tasks:
        if task.id == task_id:
            return task
    return None
