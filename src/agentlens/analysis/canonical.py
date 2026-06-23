from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ACTION_PHASES = {
    "screenshot": "observe",
    "wait": "observe",
    "move": "observe",
    "scroll": "inspect_or_orient",
    "goto": "navigate",
    "back": "navigate",
    "forward": "navigate",
    "reload": "navigate",
    "click": "gui_manipulate",
    "double_click": "gui_manipulate",
    "drag": "gui_manipulate",
    "type": "gui_manipulate",
    "keypress": "gui_manipulate",
    "web_search": "external_search",
    "run_python": "programmatic_work",
    "shell": "programmatic_work",
    "read_file": "programmatic_work",
    "write_file": "programmatic_work",
    "final_answer": "finalize",
    "desktop_screenshot": "observe",
    "desktop_wait": "observe",
    "desktop_click": "gui_manipulate",
    "desktop_type": "gui_manipulate",
    "desktop_keypress": "gui_manipulate",
    "desktop_launch_app": "programmatic_work",
    "desktop_shell": "programmatic_work",
}


@dataclass
class CanonicalEvent:
    """One action-bearing trajectory step in a framework-neutral shape."""

    index: int
    phase: str
    action_type: str | None = None
    tool_name: str | None = None
    thought: str = ""
    action: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifact_created: list[str] = field(default_factory=list)
    artifact_modified: list[str] = field(default_factory=list)
    screenshot_paths: list[str] = field(default_factory=list)
    before_screenshot: str | None = None
    after_screenshot: str | None = None
    urls: list[str] = field(default_factory=list)
    observation_texts: list[str] = field(default_factory=list)
    intervention_messages: list[str] = field(default_factory=list)


def load_trajectory(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_trajectory_paths(inputs: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        if item.is_file() and item.name == "trajectory.json":
            paths.append(item)
        elif item.is_dir():
            paths.extend(item.glob("**/trajectory.json"))
    unique = sorted({path.resolve() for path in paths})
    if not unique:
        raise ValueError("no trajectory.json files found")
    return unique


def extract_canonical_events(trajectory: dict[str, Any]) -> list[CanonicalEvent]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    screenshots_by_step: dict[int, list[str]] = defaultdict(list)
    for event in trajectory.get("events", []):
        idx = event.get("step_index")
        if not isinstance(idx, int):
            continue
        grouped[idx].append(event)
        if event.get("event_type") == "screenshot":
            screenshots_by_step[idx].extend(str(p) for p in event.get("artifact_paths", []))

    steps: list[CanonicalEvent] = []
    for idx in sorted(grouped):
        events = grouped[idx]
        model_event = first_event(events, "model_message")
        action = action_from_events(events)
        thought = ""
        tool_name = None
        if model_event:
            data = model_event.get("data", {})
            thought = str(data.get("thought") or "")
            tool_name = data.get("tool_name")
        action_type = action.get("type") if isinstance(action, dict) else None
        phase = phase_for_action(str(action_type) if action_type else None, tool_name, action)
        step = CanonicalEvent(
            index=idx,
            phase=phase,
            action_type=str(action_type) if action_type else None,
            tool_name=str(tool_name) if tool_name else None,
            thought=thought,
            action=action if isinstance(action, dict) else {},
            events=events,
            event_types=[str(event.get("event_type")) for event in events],
            before_screenshot=_nearest_screenshot_before(screenshots_by_step, idx),
            after_screenshot=_nearest_screenshot_at_or_before(screenshots_by_step, idx),
        )
        for event in events:
            merge_event_evidence(step, event)
        if step.action_type or step.errors or step.intervention_messages:
            steps.append(step)
    return steps


def first_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    for event in events:
        if event.get("event_type") == event_type:
            return event
    return None


def action_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event_type in ("model_message", "browser_action", "tool_call"):
        event = first_event(events, event_type)
        if not event:
            continue
        data = event.get("data", {})
        action = data.get("action")
        if isinstance(action, dict):
            return action
    return {}


def merge_event_evidence(step: CanonicalEvent, event: dict[str, Any]) -> None:
    event_type = str(event.get("event_type"))
    data = event.get("data", {})
    if event_type == "screenshot":
        step.screenshot_paths.extend(str(path) for path in event.get("artifact_paths", []))
        if data.get("url"):
            step.urls.append(str(data["url"]))
    if event_type == "browser_action" and data.get("error"):
        step.errors.append(str(data["error"]))
    if event_type == "tool_call":
        if data.get("ok") is False or data.get("error"):
            step.errors.append(str(data.get("error") or "tool_call failed"))
        if data.get("observation_text"):
            step.observation_texts.append(str(data["observation_text"]))
        diff = data.get("artifact_diff") or {}
        if isinstance(diff, dict):
            step.artifact_created.extend(str(p) for p in diff.get("created", []) or [])
            step.artifact_modified.extend(str(p) for p in diff.get("modified", []) or [])
    if event_type == "gating_violation":
        step.errors.append(str(data.get("message") or "gating violation"))
    if event_type == "user_intervention":
        msg = str(data.get("message") or data.get("text") or data.get("kind") or "")
        if msg:
            step.intervention_messages.append(msg)


def action_to_text(action: dict[str, Any]) -> str:
    action_type = action.get("type") or "none"
    if action_type == "mcp_tool":
        tool_name = action.get("mcp_tool") or "mcp.unknown"
        args = action.get("mcp_args") or {}
        return f"{tool_name}: {json.dumps(args, ensure_ascii=False, sort_keys=True)}"
    if action_type == "desktop_click":
        return f"desktop_click: x={action.get('x')} y={action.get('y')}"
    if action_type == "desktop_type":
        return f"desktop_type: {action.get('text') or ''}".strip()
    if action_type == "desktop_keypress":
        return f"desktop_keypress: {action.get('keys') or []}"
    if action_type == "desktop_launch_app":
        return f"desktop_launch_app: {action.get('app') or ''}".strip()
    if action_type == "desktop_shell":
        return f"desktop_shell: {action.get('cmd') or ''}".strip()
    if action_type in {"desktop_screenshot", "desktop_wait"}:
        return str(action)
    if action_type == "final_answer":
        return f"final_answer: {action.get('answer')}"
    if action_type == "run_python":
        return f"run_python: {action.get('code') or ''}".strip()
    if action_type == "shell":
        return f"shell: {action.get('cmd') or ''}".strip()
    if action_type in {"read_file", "write_file"}:
        return f"{action_type}: {action.get('file_path') or ''}".strip()
    if action_type == "web_search":
        return f"web_search: {action.get('query') or ''}".strip()
    if action_type in {"click", "double_click", "move"}:
        return f"{action_type}: x={action.get('x')} y={action.get('y')}"
    if action_type == "drag":
        return f"drag: {action.get('path') or []}"
    if action_type == "scroll":
        return f"scroll: dx={action.get('scroll_x')} dy={action.get('scroll_y')}"
    if action_type == "type":
        return f"type: {action.get('text') or ''}".strip()
    if action_type == "keypress":
        return f"keypress: {action.get('keys') or []}"
    if action_type == "goto":
        return f"goto: {action.get('url') or ''}".strip()
    return str(action)


def phase_for_action(
    action_type: str | None,
    tool_name: str | None,
    action: dict[str, Any],
) -> str:
    if not action_type:
        return "meta"
    if action_type == "mcp_tool":
        mcp_tool = tool_name or action.get("mcp_tool") or ""
        if mcp_tool.endswith(".snapshot") or mcp_tool.endswith(".get_text"):
            return "inspect_or_orient"
        if mcp_tool.endswith(".goto"):
            return "navigate"
        if mcp_tool.endswith(".click_selector") or mcp_tool.endswith(".type_selector"):
            return "gui_manipulate"
        if mcp_tool.endswith(".evaluate"):
            return "programmatic_work"
        return "other"
    return ACTION_PHASES.get(action_type, "other")


def canonical_event_to_record(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    event: CanonicalEvent,
) -> dict[str, Any]:
    metrics = trajectory.get("metrics") or {}
    return {
        "trajectory_path": str(trajectory_path),
        "trajectory_id": trajectory.get("trajectory_id"),
        "experiment_id": trajectory.get("experiment_id"),
        "run_id": trajectory.get("run_id"),
        "task_id": (trajectory.get("task") or {}).get("id"),
        "benchmark": (trajectory.get("task") or {}).get("benchmark"),
        "success": metrics.get("success"),
        "score": metrics.get("score"),
        "step_index": event.index,
        "phase": event.phase,
        "action_type": event.action_type,
        "tool_name": event.tool_name,
        "thought": event.thought,
        "action_text": action_to_text(event.action),
        "event_types": event.event_types,
        "errors": event.errors,
        "artifact_created": event.artifact_created,
        "artifact_modified": event.artifact_modified,
        "before_screenshot": event.before_screenshot,
        "after_screenshot": event.after_screenshot,
        "screenshots": event.screenshot_paths,
        "urls": unique(event.urls),
        "observation_texts": event.observation_texts,
        "intervention_messages": event.intervention_messages,
    }


def unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _nearest_screenshot_before(
    screenshots_by_step: dict[int, list[str]], idx: int
) -> str | None:
    for candidate in range(idx - 1, -1, -1):
        paths = screenshots_by_step.get(candidate)
        if paths:
            return paths[-1]
    return None


def _nearest_screenshot_at_or_before(
    screenshots_by_step: dict[int, list[str]], idx: int
) -> str | None:
    for candidate in range(idx, -1, -1):
        paths = screenshots_by_step.get(candidate)
        if paths:
            return paths[-1]
    return None
