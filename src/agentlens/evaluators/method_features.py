from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from agentlens.analysis.actonomy import analyze_actonomy
from agentlens.analysis.wang_workflow import analyze_wang_workflow


def evaluate_method_features(
    trajectory_path: Path,
    *,
    state_diff_threshold: float = 8000.0,
) -> dict[str, Any]:
    """Run Wang-style and Act-onomy-style analyses as evaluator features."""
    wang = analyze_wang_workflow(
        trajectory_path,
        state_diff_threshold=state_diff_threshold,
    )
    actonomy = analyze_actonomy(trajectory_path)
    return {
        "phase": "evaluating",
        "kind": "analysis_methods",
        "wang": _wang_features(wang),
        "actonomy": _actonomy_features(actonomy),
    }


def _wang_features(wang: dict[str, Any]) -> dict[str, Any]:
    steps = wang.get("workflow_steps", [])
    titles = [str(step.get("title") or step.get("phase") or "") for step in steps]
    statuses = Counter(step.get("status") for step in steps)
    return {
        "workflow_step_count": len(steps),
        "state_segment_count": len(wang.get("state_segments", [])),
        "action_node_count": len(wang.get("action_nodes", [])),
        "phase_sequence": titles,
        "status_counts": dict(sorted(statuses.items())),
        "has_recovery_phase": any("recover" in title.casefold() for title in titles),
        "has_verification_phase": any("verify" in title.casefold() or "check" in title.casefold() for title in titles),
    }


def _actonomy_features(actonomy: dict[str, Any]) -> dict[str, Any]:
    profile = actonomy.get("profile") or {}
    sessions = actonomy.get("sessions") or []
    action_counts = profile.get("action_counts") or {}
    code_counts = profile.get("taxonomy_code_counts") or {}
    return {
        "turn_count": profile.get("turn_count"),
        "session_count": profile.get("session_count"),
        "annotation_count": profile.get("annotation_count"),
        "action_counts": action_counts,
        "taxonomy_code_counts": code_counts,
        "session_sequence": [session.get("title") for session in sessions],
        "has_evaluate_tag": bool(action_counts.get("Evaluate")),
        "has_reflection_tag": bool(action_counts.get("Reflection")),
        "has_grounding_tag": bool(action_counts.get("Grounding")),
    }
