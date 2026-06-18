from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from agentlens.analysis.canonical import (
    CanonicalEvent,
    action_to_text,
    canonical_event_to_record,
    extract_canonical_events,
    load_trajectory,
)
from agentlens.analysis.semantic_segments import (
    action_target_signature,
    semantic_intent,
    semantic_signature,
    should_split_semantically,
    summarize_semantic_group,
)

MAX_DIFF = 100000.0
DEFAULT_STATE_DIFF_THRESHOLD = 8000.0


def analyze_wang_workflow(
    trajectory_path: Path,
    *,
    state_diff_threshold: float = DEFAULT_STATE_DIFF_THRESHOLD,
) -> dict[str, Any]:
    """Apply an AgentLens-native Wang-style workflow-induction adapter.

    This mirrors the workflow-induction-toolkit shape: raw trajectory actions
    become action nodes with before/after state, then state-transition segments,
    then higher-level workflow steps. The semantic merge here is deterministic;
    a later LLM pass can replace only that merge layer.
    """
    trajectory = load_trajectory(trajectory_path)
    events = extract_canonical_events(trajectory)
    action_nodes = [
        _action_node_record(trajectory_path, trajectory, event, previous_event=events[i - 1] if i else None)
        for i, event in enumerate(events)
    ]
    state_segments = _segment_by_state_and_phase(action_nodes, threshold=state_diff_threshold)
    workflow_steps = _merge_segments_to_workflow(trajectory_path, trajectory, state_segments)
    summary = _summary_record(trajectory_path, trajectory, action_nodes, state_segments, workflow_steps)
    return {
        "method": "wang_workflow",
        "trajectory_path": str(trajectory_path),
        "canonical_events": [
            canonical_event_to_record(trajectory_path, trajectory, event) for event in events
        ],
        "action_nodes": action_nodes,
        "state_segments": state_segments,
        "workflow_steps": workflow_steps,
        "summary": summary,
    }


def write_wang_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "action_nodes": output_dir / "action_nodes.jsonl",
        "state_segments": output_dir / "state_segments.jsonl",
        "workflow_steps": output_dir / "workflow_steps.jsonl",
        "workflow": output_dir / "workflow.json",
        "workflow_text": output_dir / "workflow.txt",
        "summary": output_dir / "summary.json",
    }
    _write_jsonl(paths["action_nodes"], result["action_nodes"])
    _write_jsonl(paths["state_segments"], result["state_segments"])
    _write_jsonl(paths["workflow_steps"], result["workflow_steps"])
    paths["workflow"].write_text(
        json.dumps(
            {
                "method": result["method"],
                "trajectory_path": result["trajectory_path"],
                "workflow": result["workflow_steps"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    paths["workflow_text"].write_text(
        "\n".join(
            f"[{step['workflow_step_id']}] {step['goal']} | Status: {step['status']}"
            for step in result["workflow_steps"]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["summary"].write_text(
        json.dumps(result["summary"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return paths


def _action_node_record(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    event: CanonicalEvent,
    *,
    previous_event: CanonicalEvent | None,
) -> dict[str, Any]:
    diff_score = _state_diff(event.before_screenshot, event.after_screenshot)
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
        "node_type": "action",
        "step_index": event.index,
        "phase": event.phase,
        "action_type": event.action_type,
        "tool_name": event.tool_name,
        "action": action_to_text(event.action),
        "goal": _goal_for_event(event),
        "semantic_intent": semantic_intent(event.thought, action_type=event.action_type),
        "semantic_signature": semantic_signature(
            event.action_type,
            action_to_text(event.action),
            event.thought,
        ),
        "action_target": action_target_signature(event.action_type, action_to_text(event.action)),
        "state": {
            "before": event.before_screenshot,
            "after": event.after_screenshot,
            "diff_score": diff_score,
            "diff_method": "pixel_mse_pillow"
            if diff_score is not None and diff_score < MAX_DIFF
            else "unavailable_or_shape_mismatch",
        },
        "transition": _transition_label(previous_event, event, diff_score=diff_score),
        "status": "failure" if event.errors else "unknown",
        "status_reason": "; ".join(event.errors),
        "evidence": {
            "thought": event.thought,
            "event_types": event.event_types,
            "artifact_created": event.artifact_created,
            "artifact_modified": event.artifact_modified,
            "intervention_messages": event.intervention_messages,
            "observation_texts": event.observation_texts,
        },
    }


def _segment_by_state_and_phase(
    action_nodes: list[dict[str, Any]],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for node in action_nodes:
        diff = node["state"].get("diff_score")
        high_state_diff = isinstance(diff, (int, float)) and diff >= threshold
        hard_break = (
            node["phase"] == "finalize"
            or node["status"] == "failure"
            or high_state_diff
            or bool(node["evidence"].get("intervention_messages"))
        )
        phase_changed = current and node["phase"] != current[-1]["phase"]
        semantic_break = current and should_split_semantically(current[-1], node)
        if current and (phase_changed or semantic_break or hard_break):
            segments.append(_segment_record(len(segments) + 1, current, threshold=threshold))
            current = []
        current.append(node)
        if hard_break:
            segments.append(_segment_record(len(segments) + 1, current, threshold=threshold))
            current = []
    if current:
        segments.append(_segment_record(len(segments) + 1, current, threshold=threshold))
    return segments


def _segment_record(
    segment_id: int,
    nodes: list[dict[str, Any]],
    *,
    threshold: float,
) -> dict[str, Any]:
    phases = Counter(node["phase"] for node in nodes)
    action_types = Counter(node["action_type"] for node in nodes if node.get("action_type"))
    title, summary = summarize_semantic_group(nodes)
    diff_scores = [
        node["state"].get("diff_score")
        for node in nodes
        if isinstance(node["state"].get("diff_score"), (int, float))
    ]
    return {
        "segment_id": segment_id,
        "node_type": "sequence" if len(nodes) > 1 else "action",
        "phase": phases.most_common(1)[0][0],
        "start_index": nodes[0]["step_index"],
        "end_index": nodes[-1]["step_index"],
        "action_count": len(nodes),
        "action_counts": dict(sorted(action_types.items())),
        "title": title,
        "state_diff_threshold": threshold,
        "max_state_diff": max(diff_scores) if diff_scores else None,
        "mean_state_diff": sum(diff_scores) / len(diff_scores) if diff_scores else None,
        "goal": _segment_goal(nodes),
        "summary": summary,
        "status": "failure" if any(node["status"] == "failure" for node in nodes) else "unknown",
        "node_step_indices": [node["step_index"] for node in nodes],
        "nodes": nodes,
    }


def _merge_segments_to_workflow(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    state_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # At this stage the state segments already include deterministic semantic
    # splits. Preserve them as workflow steps; otherwise long GUI runs collapse
    # into unhelpful labels like "GUI manipulation".
    merged: list[list[dict[str, Any]]] = [[segment] for segment in state_segments]

    metrics = trajectory.get("metrics") or {}
    out = []
    for i, group in enumerate(merged, start=1):
        actions = Counter(
            action_type
            for segment in group
            for action_type, count in segment["action_counts"].items()
            for _ in range(count)
        )
        status = "failure" if any(segment["status"] == "failure" for segment in group) else "unknown"
        out.append(
            {
                "trajectory_path": str(trajectory_path),
                "trajectory_id": trajectory.get("trajectory_id"),
                "experiment_id": trajectory.get("experiment_id"),
                "run_id": trajectory.get("run_id"),
                "task_id": (trajectory.get("task") or {}).get("id"),
                "benchmark": (trajectory.get("task") or {}).get("benchmark"),
                "success": metrics.get("success"),
                "score": metrics.get("score"),
                "workflow_step_id": i,
                "phase": group[0]["phase"],
                "title": group[0].get("title") or group[0]["phase"],
                "start_index": group[0]["start_index"],
                "end_index": group[-1]["end_index"],
                "source_segment_ids": [segment["segment_id"] for segment in group],
                "action_counts": dict(sorted(actions.items())),
                "goal": _workflow_goal(group),
                "status": status,
                "summary": _workflow_summary(group, actions),
                "intermediate": {
                    "state_segments": [
                        {
                            "segment_id": segment["segment_id"],
                            "start_index": segment["start_index"],
                            "end_index": segment["end_index"],
                            "goal": segment["goal"],
                            "title": segment.get("title"),
                            "summary": segment.get("summary"),
                            "max_state_diff": segment["max_state_diff"],
                        }
                        for segment in group
                    ]
                },
            }
        )
    return out


def _summary_record(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    action_nodes: list[dict[str, Any]],
    state_segments: list[dict[str, Any]],
    workflow_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "method": "wang_workflow",
        "trajectory_path": str(trajectory_path),
        "trajectory_id": trajectory.get("trajectory_id"),
        "run_id": trajectory.get("run_id"),
        "task_id": (trajectory.get("task") or {}).get("id"),
        "action_node_count": len(action_nodes),
        "state_segment_count": len(state_segments),
        "workflow_step_count": len(workflow_steps),
        "phase_counts": dict(Counter(step["phase"] for step in workflow_steps)),
        "sequence_summary": " -> ".join(
            f"{step['workflow_step_id']}:{step['title']}" for step in workflow_steps
        ),
    }


def _goal_for_event(event: CanonicalEvent) -> str:
    if event.thought:
        return event.thought[:280]
    return action_to_text(event.action)[:280]


def _segment_goal(nodes: list[dict[str, Any]]) -> str:
    goal = next((node["goal"] for node in nodes if node.get("goal")), "")
    actions = ", ".join(f"{k}x{v}" for k, v in sorted(Counter(n["action_type"] for n in nodes).items()))
    return goal or f"Perform actions: {actions}"


def _workflow_goal(segments: list[dict[str, Any]]) -> str:
    if len(segments) == 1:
        return segments[0]["goal"]
    return " / ".join(segment["goal"] for segment in segments if segment.get("goal"))[:500]


def _workflow_summary(group: list[dict[str, Any]], actions: Counter[str]) -> str:
    if len(group) == 1 and group[0].get("summary"):
        return group[0]["summary"]
    action_text = ", ".join(f"{name}x{count}" for name, count in sorted(actions.items()))
    segment_text = ", ".join(f"S{segment['segment_id']}" for segment in group)
    return f"Workflow phase {group[0]['phase']} from {segment_text}; actions: {action_text or 'none'}."


def _transition_label(
    previous_event: CanonicalEvent | None,
    event: CanonicalEvent,
    *,
    diff_score: float | None,
) -> str:
    if previous_event is None:
        return "initial"
    if event.phase != previous_event.phase:
        return "phase_change"
    if diff_score is not None and diff_score >= DEFAULT_STATE_DIFF_THRESHOLD:
        return "large_visual_state_change"
    if diff_score == 0:
        return "no_detected_visual_change"
    return "within_phase"


def _state_diff(before: str | None, after: str | None) -> float | None:
    if not before or not after or before == after:
        return 0.0 if before and after else None
    before_path = Path(before)
    after_path = Path(after)
    if not before_path.exists() or not after_path.exists():
        return None
    try:
        from PIL import Image

        with Image.open(before_path) as img1, Image.open(after_path) as img2:
            img1 = img1.convert("L").resize((160, 90))
            img2 = img2.convert("L").resize((160, 90))
            if img1.size != img2.size:
                return MAX_DIFF
            p1 = list(img1.getdata())
            p2 = list(img2.getdata())
            return sum((a - b) ** 2 for a, b in zip(p1, p2)) / len(p1)
    except Exception:  # noqa: BLE001
        return None


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
