from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
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
}

CODEBOOK = {
    "programmatic_approach": "Uses code, shell, file I/O, or web search as part of task work.",
    "ui_centric_exploration": "Uses browser navigation, scrolling, moving, waiting, or GUI manipulation.",
    "direct_gui_manipulation": "Manipulates visible UI elements through click, drag, type, or keypress.",
    "verification_attempt": "Checks output, reads files, runs shell inspection, or expresses verification intent.",
    "artifact_creation": "Creates or modifies task artifacts/files.",
    "repeated_action_loop": "Repeats the same action signature for a configured consecutive threshold.",
    "tool_or_action_error": "A browser/tool action returned an error or failed status.",
    "intervention_triggered": "A step-level or user-level intervention event occurred.",
    "final_answer": "The step contains the task final answer.",
    "final_answer_without_verification": "Final answer appears before any detected verification attempt.",
    "recovery_attempt": "The step appears to respond to an error/stuck state or uses retry language.",
    "no_final_answer": "The trajectory ended without a detected final answer.",
}

VERIFY_TERMS = {
    "verify",
    "check",
    "confirm",
    "validate",
    "inspect",
    "read",
    "test",
    "evaluate",
    "look at",
    "make sure",
}

RECOVERY_TERMS = {
    "try again",
    "instead",
    "recover",
    "error",
    "failed",
    "not work",
    "wrong",
    "adjust",
    "retry",
}


@dataclass
class MicroStep:
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
    urls: list[str] = field(default_factory=list)
    intervention_messages: list[str] = field(default_factory=list)


@dataclass
class WorkflowStep:
    step_id: int
    phase: str
    start_index: int
    end_index: int
    micro_steps: list[MicroStep]
    labels: list[str]
    summary: str
    evidence: dict[str, Any]


def process_trajectories(
    inputs: list[Path],
    output_dir: Path,
    *,
    repeat_threshold: int = 5,
) -> dict[str, Path]:
    """Process trajectory.json files into workflow steps and behavior summaries."""
    from agentlens.analysis.methods import process_method_outputs

    trajectory_paths = _resolve_trajectory_paths(inputs)
    output_dir.mkdir(parents=True, exist_ok=True)

    steps_path = output_dir / "workflow_steps.jsonl"
    summaries_jsonl_path = output_dir / "trajectory_summaries.jsonl"
    summaries_csv_path = output_dir / "trajectory_summaries.csv"
    codebook_path = output_dir / "behavior_codebook.json"

    summaries: list[dict[str, Any]] = []
    with steps_path.open("w", encoding="utf-8") as steps_file, summaries_jsonl_path.open(
        "w", encoding="utf-8"
    ) as summaries_file:
        for path in trajectory_paths:
            processed = process_one_trajectory(path, repeat_threshold=repeat_threshold)
            summaries.append(processed["summary"])
            summaries_file.write(json.dumps(processed["summary"], ensure_ascii=False) + "\n")
            for step in processed["steps"]:
                steps_file.write(json.dumps(step, ensure_ascii=False) + "\n")

    _write_summaries_csv(summaries, summaries_csv_path)
    codebook_path.write_text(json.dumps(CODEBOOK, indent=2, ensure_ascii=False), encoding="utf-8")
    method_paths = process_method_outputs(trajectory_paths, output_dir / "methods")
    return {
        "workflow_steps": steps_path,
        "trajectory_summaries_jsonl": summaries_jsonl_path,
        "trajectory_summaries_csv": summaries_csv_path,
        "behavior_codebook": codebook_path,
        **{f"methods_{name}": path for name, path in method_paths.items()},
    }


def process_one_trajectory(path: Path, *, repeat_threshold: int = 5) -> dict[str, Any]:
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    micro_steps = _extract_micro_steps(trajectory)
    repeated_indices = _detect_repeated_indices(micro_steps, threshold=repeat_threshold)
    workflow_steps = _aggregate_workflow_steps(micro_steps, repeated_indices=repeated_indices)
    summary = _summarize_trajectory(path, trajectory, micro_steps, workflow_steps)
    return {
        "summary": summary,
        "steps": [
            _workflow_step_to_record(path, trajectory, step)
            for step in workflow_steps
        ],
    }


def _resolve_trajectory_paths(inputs: list[Path]) -> list[Path]:
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


def _extract_micro_steps(trajectory: dict[str, Any]) -> list[MicroStep]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in trajectory.get("events", []):
        idx = event.get("step_index")
        if isinstance(idx, int):
            grouped[idx].append(event)

    micro_steps: list[MicroStep] = []
    for idx in sorted(grouped):
        events = grouped[idx]
        model_event = _first_event(events, "model_message")
        action = _action_from_events(events)
        thought = ""
        tool_name = None
        if model_event:
            data = model_event.get("data", {})
            thought = str(data.get("thought") or "")
            tool_name = data.get("tool_name")
        action_type = action.get("type") if isinstance(action, dict) else None
        phase = ACTION_PHASES.get(str(action_type), "meta" if action_type is None else "other")
        step = MicroStep(
            index=idx,
            phase=phase,
            action_type=str(action_type) if action_type else None,
            tool_name=str(tool_name) if tool_name else None,
            thought=thought,
            action=action if isinstance(action, dict) else {},
            events=events,
            event_types=[str(event.get("event_type")) for event in events],
        )
        for event in events:
            _merge_event_evidence(step, event)
        if step.action_type or step.event_types:
            micro_steps.append(step)
    return micro_steps


def _first_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    for event in events:
        if event.get("event_type") == event_type:
            return event
    return None


def _action_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event_type in ("model_message", "browser_action", "tool_call"):
        event = _first_event(events, event_type)
        if not event:
            continue
        data = event.get("data", {})
        action = data.get("action")
        if isinstance(action, dict):
            return action
    return {}


def _merge_event_evidence(step: MicroStep, event: dict[str, Any]) -> None:
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


def _detect_repeated_indices(
    micro_steps: list[MicroStep],
    *,
    threshold: int,
) -> set[int]:
    repeated: set[int] = set()
    window: list[tuple[Any, ...]] = []
    indices: list[int] = []
    for step in micro_steps:
        if not step.action_type or step.action_type == "final_answer":
            window.clear()
            indices.clear()
            continue
        sig = _action_signature(step)
        window.append(sig)
        indices.append(step.index)
        if len(window) > threshold:
            window.pop(0)
            indices.pop(0)
        if len(window) == threshold and len(set(window)) == 1:
            repeated.update(indices)
    return repeated


def _action_signature(step: MicroStep) -> tuple[Any, ...]:
    action = step.action or {}
    action_type = step.action_type
    if action_type == "drag":
        return (action_type,)
    if action_type in {"click", "double_click", "move", "scroll"}:
        target = (
            action.get("bid")
            or action.get("selector")
            or action.get("mark")
            or _coarse_xy(action.get("x"), action.get("y"))
        )
        return (action_type, target)
    if action_type in {"type", "keypress", "goto", "read_file", "write_file"}:
        return (
            action_type,
            action.get("text") or tuple(action.get("keys") or []) or action.get("url")
            or action.get("file_path"),
        )
    return (action_type,)


def _coarse_xy(x: Any, y: Any) -> tuple[int, int] | None:
    if x is None or y is None:
        return None
    try:
        return (round(float(x) / 25) * 25, round(float(y) / 25) * 25)
    except Exception:  # noqa: BLE001
        return None


def _aggregate_workflow_steps(
    micro_steps: list[MicroStep],
    *,
    repeated_indices: set[int],
) -> list[WorkflowStep]:
    chunks: list[list[MicroStep]] = []
    current: list[MicroStep] = []
    for step in micro_steps:
        hard_break = (
            step.phase == "finalize"
            or bool(step.errors)
            or bool(step.intervention_messages)
            or step.index in repeated_indices
        )
        if current and (step.phase != current[-1].phase or hard_break):
            chunks.append(current)
            current = []
        current.append(step)
        if hard_break:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)

    workflow_steps: list[WorkflowStep] = []
    for i, chunk in enumerate(chunks, start=1):
        labels = _labels_for_chunk(chunk, repeated_indices=repeated_indices)
        phase = _dominant_phase(chunk)
        workflow_steps.append(
            WorkflowStep(
                step_id=i,
                phase=phase,
                start_index=chunk[0].index,
                end_index=chunk[-1].index,
                micro_steps=chunk,
                labels=labels,
                summary=_summarize_chunk(chunk, labels=labels),
                evidence=_evidence_for_chunk(chunk),
            )
        )
    _mark_final_without_verification(workflow_steps)
    return workflow_steps


def _labels_for_chunk(chunk: list[MicroStep], *, repeated_indices: set[int]) -> list[str]:
    labels: set[str] = set()
    action_types = {step.action_type for step in chunk if step.action_type}
    thoughts = " ".join(step.thought for step in chunk).casefold()
    if action_types & {"run_python", "shell", "read_file", "write_file", "web_search"}:
        labels.add("programmatic_approach")
    if action_types & {
        "scroll",
        "move",
        "wait",
        "goto",
        "back",
        "forward",
        "reload",
        "click",
        "double_click",
        "drag",
        "type",
        "keypress",
    }:
        labels.add("ui_centric_exploration")
    if action_types & {"click", "double_click", "drag", "type", "keypress"}:
        labels.add("direct_gui_manipulation")
    if any(term in thoughts for term in VERIFY_TERMS) or action_types & {"read_file", "shell"}:
        labels.add("verification_attempt")
    if any(step.artifact_created or step.artifact_modified for step in chunk):
        labels.add("artifact_creation")
    if any(step.index in repeated_indices for step in chunk):
        labels.add("repeated_action_loop")
    if any(step.errors for step in chunk):
        labels.add("tool_or_action_error")
    if any(step.intervention_messages for step in chunk):
        labels.add("intervention_triggered")
    if "final_answer" in action_types:
        labels.add("final_answer")
    if any(term in thoughts for term in RECOVERY_TERMS):
        labels.add("recovery_attempt")
    return sorted(labels)


def _dominant_phase(chunk: list[MicroStep]) -> str:
    counts = Counter(step.phase for step in chunk)
    return counts.most_common(1)[0][0]


def _summarize_chunk(chunk: list[MicroStep], *, labels: list[str]) -> str:
    action_counts = Counter(step.action_type for step in chunk if step.action_type)
    actions = ", ".join(f"{k}x{v}" for k, v in sorted(action_counts.items()))
    label_text = ", ".join(labels) if labels else "unlabeled"
    thought = next((step.thought for step in chunk if step.thought), "")
    thought_suffix = f" Thought: {thought[:180]}" if thought else ""
    return f"{label_text}. Actions: {actions or 'none'}.{thought_suffix}"


def _evidence_for_chunk(chunk: list[MicroStep]) -> dict[str, Any]:
    return {
        "action_types": [step.action_type for step in chunk if step.action_type],
        "tool_names": [step.tool_name for step in chunk if step.tool_name],
        "event_types": sorted({etype for step in chunk for etype in step.event_types}),
        "errors": [err for step in chunk for err in step.errors],
        "artifact_created": [path for step in chunk for path in step.artifact_created],
        "artifact_modified": [path for step in chunk for path in step.artifact_modified],
        "intervention_messages": [
            msg for step in chunk for msg in step.intervention_messages
        ],
        "screenshots": [path for step in chunk for path in step.screenshot_paths],
        "urls": _unique([url for step in chunk for url in step.urls]),
    }


def _mark_final_without_verification(workflow_steps: list[WorkflowStep]) -> None:
    seen_verification = False
    for step in workflow_steps:
        if "verification_attempt" in step.labels:
            seen_verification = True
        if "final_answer" in step.labels and not seen_verification:
            step.labels = sorted({*step.labels, "final_answer_without_verification"})
            step.summary = _summarize_chunk(step.micro_steps, labels=step.labels)


def _workflow_step_to_record(
    path: Path,
    trajectory: dict[str, Any],
    step: WorkflowStep,
) -> dict[str, Any]:
    metrics = trajectory.get("metrics") or {}
    return {
        "trajectory_path": str(path),
        "trajectory_id": trajectory.get("trajectory_id"),
        "experiment_id": trajectory.get("experiment_id"),
        "run_id": trajectory.get("run_id"),
        "task_id": (trajectory.get("task") or {}).get("id"),
        "benchmark": (trajectory.get("task") or {}).get("benchmark"),
        "success": metrics.get("success"),
        "score": metrics.get("score"),
        "workflow_step_id": step.step_id,
        "phase": step.phase,
        "start_index": step.start_index,
        "end_index": step.end_index,
        "labels": step.labels,
        "summary": step.summary,
        "evidence": step.evidence,
    }


def _summarize_trajectory(
    path: Path,
    trajectory: dict[str, Any],
    micro_steps: list[MicroStep],
    workflow_steps: list[WorkflowStep],
) -> dict[str, Any]:
    metrics = trajectory.get("metrics") or {}
    labels = Counter(label for step in workflow_steps for label in step.labels)
    phases = Counter(step.phase for step in workflow_steps)
    action_counts = Counter(step.action_type for step in micro_steps if step.action_type)
    has_final = any(step.action_type == "final_answer" for step in micro_steps)
    if not has_final:
        labels["no_final_answer"] += 1
    return {
        "trajectory_path": str(path),
        "trajectory_id": trajectory.get("trajectory_id"),
        "experiment_id": trajectory.get("experiment_id"),
        "run_id": trajectory.get("run_id"),
        "model": (trajectory.get("model") or {}).get("id"),
        "tool_harness": (trajectory.get("tool_harness") or {}).get("id"),
        "task_id": (trajectory.get("task") or {}).get("id"),
        "benchmark": (trajectory.get("task") or {}).get("benchmark"),
        "success": metrics.get("success"),
        "score": metrics.get("score"),
        "micro_step_count": len(micro_steps),
        "workflow_step_count": len(workflow_steps),
        "action_counts": dict(sorted(action_counts.items())),
        "phase_counts": dict(sorted(phases.items())),
        "behavior_label_counts": dict(sorted(labels.items())),
        "challenge_patterns": _challenge_patterns(labels),
        "sequence_summary": _sequence_summary(workflow_steps),
    }


def _challenge_patterns(label_counts: Counter[str]) -> list[str]:
    patterns = []
    for label in (
        "repeated_action_loop",
        "tool_or_action_error",
        "final_answer_without_verification",
        "no_final_answer",
    ):
        if label_counts.get(label):
            patterns.append(label)
    return patterns


def _sequence_summary(workflow_steps: list[WorkflowStep]) -> str:
    parts = []
    for step in workflow_steps:
        label = ",".join(step.labels) if step.labels else step.phase
        parts.append(f"{step.step_id}:{step.phase}[{label}]")
    return " -> ".join(parts)


def _write_summaries_csv(summaries: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "trajectory_path",
        "experiment_id",
        "run_id",
        "model",
        "tool_harness",
        "task_id",
        "benchmark",
        "success",
        "score",
        "micro_step_count",
        "workflow_step_count",
        "challenge_patterns",
        "behavior_label_counts",
        "phase_counts",
        "action_counts",
        "sequence_summary",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for summary in summaries:
            row = dict(summary)
            for key in (
                "challenge_patterns",
                "behavior_label_counts",
                "phase_counts",
                "action_counts",
            ):
                row[key] = json.dumps(row.get(key), ensure_ascii=False, sort_keys=True)
            writer.writerow({key: row.get(key) for key in fieldnames})


def _unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
