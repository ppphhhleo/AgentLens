from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from agentlens.analysis.canonical import (
    CanonicalEvent,
    action_to_text,
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

DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[3] / "third_party" / "actonomy" / "act-onomy_taxonomy.csv"
)

PHASE_LABELS = {
    "observe": "Observation",
    "inspect_or_orient": "Inspection",
    "navigate": "Navigation",
    "gui_manipulate": "GUI manipulation",
    "external_search": "External search",
    "programmatic_work": "Programmatic work",
    "finalize": "Submit",
    "other": "Other",
    "meta": "Meta",
}


def analyze_actonomy(
    trajectory_path: Path,
    *,
    taxonomy_path: Path = DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    """Apply Act-onomy-style codebook assignment and session aggregation.

    The upstream skill uses LLM-assisted quote-level coding. This adapter keeps
    the method separate but deterministic: each AgentLens action receives one
    or more codebook labels from a pinned Act-onomy taxonomy snapshot.
    """
    taxonomy = load_taxonomy(taxonomy_path)
    trajectory = load_trajectory(trajectory_path)
    events = extract_canonical_events(trajectory)
    turns = [
        _turn_annotation(trajectory_path, trajectory, event, taxonomy=taxonomy)
        for event in events
    ]
    sessions = _aggregate_sessions(trajectory_path, trajectory, turns)
    profile = _profile(trajectory_path, trajectory, turns, sessions)
    return {
        "method": "actonomy",
        "trajectory_path": str(trajectory_path),
        "taxonomy_path": str(taxonomy_path),
        "turns": turns,
        "sessions": sessions,
        "profile": profile,
    }


def write_actonomy_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "annotations": output_dir / "annotations.jsonl",
        "sessions": output_dir / "sessions.jsonl",
        "profile": output_dir / "profile.json",
        "summary": output_dir / "summary.txt",
    }
    _write_jsonl(paths["annotations"], result["turns"])
    _write_jsonl(paths["sessions"], result["sessions"])
    paths["profile"].write_text(
        json.dumps(result["profile"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["summary"].write_text(
        _profile_text(result["profile"], result["sessions"]),
        encoding="utf-8",
    )
    return paths


def load_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> dict[str, dict[str, str]]:
    taxonomy: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            code = row.get("code") or row.get("taxonomy_code")
            if not code:
                continue
            taxonomy[code] = {
                "code": code,
                "action": row.get("Action") or "",
                "subaction": row.get("Subaction") or "",
                "instance": row.get("Instance") or "",
                "definition": row.get("definition") or "",
            }
    return taxonomy


def _turn_annotation(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    event: CanonicalEvent,
    *,
    taxonomy: dict[str, dict[str, str]],
) -> dict[str, Any]:
    codes = _codes_for_event(event)
    annotations = []
    for code, evidence, reason in codes:
        tax = taxonomy.get(code)
        if not tax:
            continue
        annotations.append(
            {
                "taxonomy_code": code,
                "action": tax["action"],
                "subaction": tax["subaction"],
                "instance": tax["instance"],
                "evidence": evidence,
                "assignment_reason": reason,
                "confidence": "rule",
            }
        )
    phase = _actonomy_phase(event)
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
        "turn": event.index,
        "phase": phase,
        "phase_label": PHASE_LABELS.get(event.phase, event.phase),
        "headline": _headline(event),
        "semantic_intent": semantic_intent(event.thought, action_type=event.action_type),
        "semantic_signature": semantic_signature(
            event.action_type,
            action_to_text(event.action),
            event.thought,
        ),
        "action_target": action_target_signature(event.action_type, action_to_text(event.action)),
        "obs": "\n".join(event.observation_texts),
        "thought": event.thought,
        "action_surface": action_to_text(event.action),
        "action_type": event.action_type,
        "tool_name": event.tool_name,
        "annotations": annotations,
        "screenshot": event.after_screenshot,
        "errors": event.errors,
        "artifacts": {
            "created": event.artifact_created,
            "modified": event.artifact_modified,
        },
    }


def _codes_for_event(event: CanonicalEvent) -> list[tuple[str, str, str]]:
    action_type = event.action_type
    tool_name = event.tool_name or event.action.get("mcp_tool")
    thought = event.thought or ""
    action_text = action_to_text(event.action)
    codes: list[tuple[str, str, str]] = []

    if thought:
        codes.append(("T2.1.2.1", _short(thought), "thought states a near-term plan or subgoal"))
    if action_type == "mcp_tool":
        if tool_name in {"mcp.chrome.snapshot", "mcp.chrome.get_text"}:
            codes.append(("T1.1.2.1", action_text, "structured browser state retrieval"))
            codes.append(("T2.3.2.1", _short(thought or action_text), "inspects page evidence"))
        elif tool_name == "mcp.chrome.goto":
            codes.append(("T3.1.3.1", action_text, "navigates the browser through Chrome MCP"))
        elif tool_name in {"mcp.chrome.click_selector", "mcp.chrome.type_selector"}:
            codes.append(("T3.1.3.1", action_text, "grounds work in the live browser DOM"))
            codes.append(("T3.2.1.1", action_text, "performs a concrete browser action"))
        elif tool_name == "mcp.chrome.evaluate":
            codes.append(("T3.1.5.1", action_text, "executes JavaScript to inspect or compute page state"))
            codes.append(("T2.2.2.2", _short(thought or action_text), "programmatic browser analysis"))
    elif action_type == "web_search":
        codes.append(("T1.1.4.1", action_text, "open-web retrieval action"))
    elif action_type == "read_file":
        codes.append(("T1.1.2.1", action_text, "local file retrieval action"))
    elif action_type == "write_file":
        codes.append(("T3.1.3.2", action_text, "writes or edits a local artifact"))
    elif action_type == "run_python":
        codes.append(("T3.1.5.1", action_text, "executes code to transform or compute information"))
        codes.append(("T2.2.2.2", _short(thought or action_text), "programmatic analysis/computation"))
    elif action_type == "shell":
        codes.append(("T3.1.3.3", action_text, "executes a shell command"))
    elif action_type in {
        "click",
        "double_click",
        "drag",
        "type",
        "keypress",
        "scroll",
        "move",
        "desktop_click",
        "desktop_double_click",
        "desktop_scroll",
        "desktop_move",
        "desktop_drag",
        "desktop_type",
        "desktop_keypress",
        "desktop_pyautogui",
    }:
        codes.append(("T3.1.3.1", action_text, "grounds work in the visible GUI/action surface"))
        codes.append(("T3.2.1.1", action_text, "performs a concrete UI action"))
    elif action_type == "desktop_launch_app":
        codes.append(("T3.1.3.1", action_text, "opens a desktop application for GUI work"))
        codes.append(("T3.2.1.1", action_text, "prepares the visible work surface"))
    elif action_type == "desktop_shell":
        codes.append(("T3.1.3.3", action_text, "executes a shell command in the desktop environment"))
    elif action_type in {"goto", "back", "forward", "reload"}:
        codes.append(("T3.1.3.1", action_text, "navigates the browser state"))
    elif action_type == "final_answer":
        codes.append(("T3.2.3.1", action_text, "commits to a final decision/answer"))

    if _has_verification_signal(event):
        codes.append(("T2.3.2.1", _short(thought or action_text), "detected checking or verification signal"))
    if event.errors or any(word in thought.casefold() for word in ("failed", "error", "retry", "wrong")):
        codes.append(("T4.2.1.2", _short(thought or action_text), "failure or recovery signal"))
    return _dedupe_codes(codes)


def _aggregate_sessions(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    turns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for turn in turns:
        code_signature = _major_action(turn)
        hard_break = turn["phase"] in {"submit", "recover"} or bool(turn["errors"])
        semantic_break = current and should_split_semantically(current[-1], turn)
        if current and (code_signature != _major_action(current[-1]) or semantic_break or hard_break):
            sessions.append(_session_record(trajectory_path, trajectory, len(sessions) + 1, current))
            current = []
        current.append(turn)
        if hard_break:
            sessions.append(_session_record(trajectory_path, trajectory, len(sessions) + 1, current))
            current = []
    if current:
        sessions.append(_session_record(trajectory_path, trajectory, len(sessions) + 1, current))
    return sessions


def _session_record(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    session_id: int,
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    action_counts = Counter(
        annotation["action"] for turn in turns for annotation in turn["annotations"]
    )
    code_counts = Counter(
        annotation["taxonomy_code"] for turn in turns for annotation in turn["annotations"]
    )
    phase_counts = Counter(turn["phase_label"] for turn in turns)
    action_type_counts = Counter(turn["action_type"] for turn in turns if turn.get("action_type"))
    metrics = trajectory.get("metrics") or {}
    dominant_action = _dominant_action(action_counts)
    dominant_phase = phase_counts.most_common(1)[0][0] if phase_counts else "Unphased"
    title, summary = summarize_semantic_group(turns)
    return {
        "trajectory_path": str(trajectory_path),
        "trajectory_id": trajectory.get("trajectory_id"),
        "experiment_id": trajectory.get("experiment_id"),
        "run_id": trajectory.get("run_id"),
        "task_id": (trajectory.get("task") or {}).get("id"),
        "benchmark": (trajectory.get("task") or {}).get("benchmark"),
        "success": metrics.get("success"),
        "score": metrics.get("score"),
        "session_id": session_id,
        "start_turn": turns[0]["turn"],
        "end_turn": turns[-1]["turn"],
        "turn_count": len(turns),
        "dominant_phase": dominant_phase,
        "dominant_action": dominant_action,
        "title": title,
        "phase_counts": dict(sorted(phase_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "taxonomy_code_counts": dict(sorted(code_counts.items())),
        "summary": summary,
        "turns": [turn["turn"] for turn in turns],
    }


def _profile(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    turns: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    action_counts = Counter(
        annotation["action"] for turn in turns for annotation in turn["annotations"]
    )
    subaction_counts = Counter(
        annotation["subaction"] for turn in turns for annotation in turn["annotations"]
    )
    code_counts = Counter(
        annotation["taxonomy_code"] for turn in turns for annotation in turn["annotations"]
    )
    phase_counts = Counter(session["dominant_phase"] for session in sessions)
    return {
        "method": "actonomy",
        "trajectory_path": str(trajectory_path),
        "trajectory_id": trajectory.get("trajectory_id"),
        "run_id": trajectory.get("run_id"),
        "task_id": (trajectory.get("task") or {}).get("id"),
        "turn_count": len(turns),
        "session_count": len(sessions),
        "annotation_count": sum(len(turn["annotations"]) for turn in turns),
        "action_counts": dict(sorted(action_counts.items())),
        "subaction_counts": dict(sorted(subaction_counts.items())),
        "taxonomy_code_counts": dict(sorted(code_counts.items())),
        "phase_counts": dict(sorted(phase_counts.items())),
        "session_summaries": [session["summary"] for session in sessions],
        "sequence_summary": " -> ".join(
            f"{session['session_id']}:{session['title']}"
            for session in sessions
        ),
        "license_note": "Act-onomy taxonomy/codebook content is used under CC BY 4.0.",
    }


def _actonomy_phase(event: CanonicalEvent) -> str:
    if event.errors:
        return "recover"
    if event.action_type == "final_answer":
        return "submit"
    if event.action_type == "mcp_tool":
        tool_name = event.tool_name or event.action.get("mcp_tool")
        if tool_name in {"mcp.chrome.snapshot", "mcp.chrome.get_text"}:
            return "localize"
        if tool_name == "mcp.chrome.evaluate":
            return "verify"
        return "edit"
    if event.action_type in {"read_file", "web_search", "scroll", "move", "desktop_scroll", "desktop_move"}:
        return "localize"
    if event.action_type in {
        "click",
        "double_click",
        "drag",
        "type",
        "keypress",
        "run_python",
        "shell",
        "write_file",
        "desktop_launch_app",
        "desktop_shell",
        "desktop_click",
        "desktop_double_click",
        "desktop_drag",
        "desktop_type",
        "desktop_keypress",
        "desktop_pyautogui",
    }:
        return "edit"
    if _has_verification_signal(event):
        return "verify"
    return "other"


def _headline(event: CanonicalEvent) -> str:
    action = event.action_type or "event"
    if event.action_type == "final_answer":
        return "Submit final answer"
    if event.errors:
        return f"Recover from {action} issue"
    return f"{PHASE_LABELS.get(event.phase, event.phase)} via {action}"


def _major_action(turn: dict[str, Any]) -> str:
    annotations = turn.get("annotations") or []
    for annotation in annotations:
        if annotation["action"] != "Planning":
            return annotation["action"]
    return annotations[0]["action"] if annotations else "Uncoded"


def _dominant_action(action_counts: Counter[str]) -> str:
    if not action_counts:
        return "Uncoded"
    non_planning = Counter({k: v for k, v in action_counts.items() if k != "Planning"})
    if non_planning:
        return non_planning.most_common(1)[0][0]
    return action_counts.most_common(1)[0][0]


def _profile_text(profile: dict[str, Any], sessions: list[dict[str, Any]]) -> str:
    lines = [
        f"Act-onomy profile for {profile.get('run_id')}",
        f"Turns: {profile['turn_count']}; sessions: {profile['session_count']}; annotations: {profile['annotation_count']}",
        f"Sequence: {profile['sequence_summary']}",
        "",
        "Sessions:",
    ]
    lines.extend(f"- {session['summary']}" for session in sessions)
    lines.append("")
    lines.append(profile["license_note"])
    return "\n".join(lines) + "\n"


def _has_verification_signal(event: CanonicalEvent) -> bool:
    text = " ".join([event.thought, action_to_text(event.action), *event.observation_texts]).casefold()
    return any(
        term in text
        for term in ("verify", "check", "confirm", "validate", "inspect", "read back", "test")
    )


def _short(text: str, limit: int = 220) -> str:
    clean = " ".join(text.split())
    return clean[:limit]


def _dedupe_codes(codes: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    seen = set()
    out = []
    for code, evidence, reason in codes:
        if code in seen:
            continue
        seen.add(code)
        out.append((code, evidence, reason))
    return out


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
