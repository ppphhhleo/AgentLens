from __future__ import annotations

import re
from typing import Any


_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def trajectory_case_slug(plan: Any) -> str:
    """Return a readable, stable folder name for one trajectory case.

    The timestamp/snapshot lives in the parent run folder. This slug keeps the
    per-case directory easy to scan by task, prompt condition, model, harness,
    seed, and trial.
    """

    task = getattr(plan, "task", None)
    model = getattr(plan, "model", None)
    tool_harness = getattr(plan, "tool_harness", None)

    parts = [
        _task_app(task),
        _task_name(task),
        _prompt_style(task),
        _model_name(model),
        _agent_or_harness(model, tool_harness),
        f"seed{getattr(plan, 'seed', 0)}",
        f"trial{getattr(plan, 'trial', 1)}",
    ]
    return "__".join(_slug(part) for part in parts if _slug(part))


def gui_vs_cli_case_slug(
    *,
    app: str | None,
    task_id: str,
    prompt_style: str,
    model: str | None,
    agent_id: str,
) -> str:
    """Readable folder name for gui-vs-cli script-produced trajectories."""

    return "__".join(
        _slug(part)
        for part in [app, task_id, prompt_style, model, agent_id]
        if _slug(part)
    )


def _task_app(task: Any) -> str:
    extra = _extra(task)
    return str(
        extra.get("app")
        or extra.get("application")
        or extra.get("task_family")
        or getattr(task, "benchmark", "")
        or "task"
    )


def _task_name(task: Any) -> str:
    extra = _extra(task)
    return str(
        extra.get("canonical_task")
        or extra.get("paired_task_id")
        or extra.get("standard_task_id")
        or getattr(task, "id", "")
        or getattr(task, "task_id", "")
        or "unknown_task"
    )


def _prompt_style(task: Any) -> str:
    extra = _extra(task)
    value = extra.get("prompt_variant") or extra.get("source_type") or "standard"
    value = str(value)
    if value == "grounded_prompt":
        return "grounded"
    if value == "grounded_procedure":
        return "grounded"
    return value


def _model_name(model: Any) -> str:
    return str(getattr(model, "id", "") or getattr(model, "name", "") or "model")


def _agent_or_harness(model: Any, tool_harness: Any) -> str:
    model_extra = _extra(model)
    interaction_backend = str(model_extra.get("interaction_backend") or "")
    if interaction_backend and interaction_backend != "tool_call":
        return interaction_backend
    return str(getattr(tool_harness, "id", "") or interaction_backend or "harness")


def _extra(obj: Any) -> dict[str, Any]:
    value = getattr(obj, "extra", None)
    return value if isinstance(value, dict) else {}


def _slug(value: Any, *, max_len: int = 72) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _SLUG_RE.sub("_", text).strip("_").lower()
    text = re.sub(r"_+", "_", text)
    return text[:max_len].rstrip("_")
