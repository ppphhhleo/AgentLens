from __future__ import annotations

import json
from collections import Counter
from typing import Any

from agentlens.analysis.actonomy import load_taxonomy
from agentlens.analysis.llm_client import call_json_llm


ALLOWED_ACTONOMY = """
Use these Act-onomy labels only.
- Retrieval | Retrieve from local corpus | Retrieve from local corpus
- Retrieval | Retrieve from open web | Retrieve from open web
- Planning | Formulate a workflow or plan | Formulate a high-level plan
- Planning | Formulate a workflow or plan | Plan function or tool use
- Reasoning | Analysing | Analyse artifact structure and behavior
- Reasoning | Analysing | Detect patterns or trends in data
- Reasoning | Comparing & Ranking | Compare values across sources
- Reasoning | Comparing & Ranking | Rank items by criteria
- Reasoning | Inferring | Infer hidden state from observable evidence
- Evaluate | Evaluating with goals/requirements/constraints | goal-completion check
- Evaluate | Evaluating without ground truth | Evaluate intermediate results
- Grounding | Interact with digital environments | Navigate digital interfaces
- Grounding | Interact with digital environments | Modify digital objects
- Grounding | Interact with digital environments | Issue operational commands
- Grounding | Augment with external computation | Execute code
- Executing | Executing plan | Execute strategy
- Executing | Terminating | Provide final answer
- Reflection | Reflect on errors and failures | Inspect Error Pattern
- Reflection | Reflect on self-outcomes | Pre-action self-check
""".strip()


def refine_methods_with_llm(
    wang: dict[str, Any],
    actonomy: dict[str, Any],
    *,
    provider: str = "auto",
    model: str | None = None,
) -> dict[str, Any]:
    turns = _turn_payload(wang, actonomy)
    prompt = _build_prompt(turns)
    result = call_json_llm(prompt, provider=provider, model=model)
    data = result.data

    warnings: list[str] = []
    wang_steps = _build_wang_steps_from_llm(wang, data, warnings)
    sessions = _build_actonomy_sessions_from_llm(actonomy, data, warnings)
    turns_refined = _build_actonomy_turns_from_llm(actonomy, data, warnings)

    if wang_steps:
        wang["workflow_steps"] = wang_steps
        wang["summary"] = _wang_summary(wang, wang_steps, result)
    if turns_refined:
        actonomy["turns"] = turns_refined
    if sessions:
        actonomy["sessions"] = sessions
        actonomy["profile"] = _actonomy_profile(actonomy, sessions, result)

    meta = {
        "annotation_mode": "llm",
        "provider": result.provider,
        "model": result.model,
        "warnings": warnings,
        "raw_response_path": None,
    }
    wang["llm_refinement"] = meta
    actonomy["llm_refinement"] = meta
    return {"wang": wang, "actonomy": actonomy, "llm": meta, "raw": result.raw}


def _build_prompt(turns: list[dict[str, Any]]) -> str:
    return f"""
Analyze this GUI/computer-use trajectory using two method lenses.

Input turns are ordered. Each turn has a model thought and tool call. Produce:

1. Wang-style workflow steps:
   Merge consecutive turns into semantically meaningful workflow phases. These
   should be human-readable activity phases, not just action types.

2. Act-onomy per-turn annotations:
   For each turn, assign 1-3 Act-onomy tags grounded in short evidence quotes
   from the thought or action surface.

3. Act-onomy aggregation:
   Merge consecutive turns into named phases and summarize what the actor did.

{ALLOWED_ACTONOMY}

Return only this JSON object:
{{
  "wang_workflow_steps": [
    {{"start": 1, "end": 3, "title": "...", "summary": "..."}}
  ],
  "actonomy_turn_annotations": [
    {{
      "turn": 1,
      "annotations": [
        {{
          "action": "Planning",
          "subaction": "Formulate a workflow or plan",
          "instance": "Formulate a high-level plan",
          "evidence": "exact or short quote from thought/action"
        }}
      ]
    }}
  ],
  "actonomy_sessions": [
    {{"start": 1, "end": 3, "title": "...", "summary": "..."}}
  ]
}}

Guidelines:
- Spans must be consecutive and use existing turn numbers only.
- Prefer 2-5 phases for short trajectories unless the activity truly changes more often.
- Titles should be concise verb phrases, e.g. "Inspect the relevant data field".
- Summaries should describe the actual work, not restate code labels.
- Keep evidence quotes short.

Trajectory turns:
{json.dumps(turns, indent=2, ensure_ascii=False)}
""".strip()


def _turn_payload(wang: dict[str, Any], actonomy: dict[str, Any]) -> list[dict[str, Any]]:
    act_turns = {turn["turn"]: turn for turn in actonomy.get("turns", [])}
    payload = []
    for event in wang.get("canonical_events", []):
        turn = act_turns.get(event["step_index"], {})
        payload.append(
            {
                "turn": event["step_index"],
                "tool": event.get("tool_name") or event.get("action_type"),
                "action_type": event.get("action_type"),
                "thought": event.get("thought") or "",
                "action": turn.get("action_surface") or event.get("action_text") or "",
            }
        )
    return payload


def _build_wang_steps_from_llm(
    wang: dict[str, Any],
    data: dict[str, Any],
    warnings: list[str],
) -> list[dict[str, Any]]:
    source = data.get("wang_workflow_steps")
    if not isinstance(source, list):
        warnings.append("missing wang_workflow_steps")
        return []
    action_nodes = {node["step_index"]: node for node in wang.get("action_nodes", [])}
    metrics_template = wang.get("workflow_steps", [{}])[0] if wang.get("workflow_steps") else {}
    out = []
    for i, item in enumerate(source, start=1):
        span = _validated_span(item, action_nodes, warnings, label=f"wang[{i}]")
        if not span:
            continue
        start, end = span
        nodes = [action_nodes[idx] for idx in range(start, end + 1) if idx in action_nodes]
        actions = Counter(node.get("action_type") for node in nodes if node.get("action_type"))
        out.append(
            {
                **_base_record(metrics_template),
                "workflow_step_id": len(out) + 1,
                "phase": nodes[0].get("phase") if nodes else "llm_phase",
                "title": str(item.get("title") or f"Workflow step {i}"),
                "start_index": start,
                "end_index": end,
                "source_segment_ids": [],
                "action_counts": dict(sorted(actions.items())),
                "goal": str(item.get("summary") or item.get("title") or ""),
                "status": "failure" if any(node.get("status") == "failure" for node in nodes) else "unknown",
                "summary": str(item.get("summary") or item.get("title") or ""),
                "intermediate": {"llm_source": "wang_workflow_steps"},
            }
        )
    return out


def _build_actonomy_turns_from_llm(
    actonomy: dict[str, Any],
    data: dict[str, Any],
    warnings: list[str],
) -> list[dict[str, Any]]:
    source = data.get("actonomy_turn_annotations")
    if not isinstance(source, list):
        warnings.append("missing actonomy_turn_annotations")
        return []
    taxonomy = load_taxonomy()
    code_by_label = {
        (row["action"], row["subaction"], row["instance"]): row["code"]
        for row in taxonomy.values()
    }
    by_turn = {turn["turn"]: dict(turn) for turn in actonomy.get("turns", [])}
    for item in source:
        turn_id = item.get("turn")
        if turn_id not in by_turn:
            warnings.append(f"unknown actonomy turn: {turn_id}")
            continue
        annotations = []
        for ann in item.get("annotations") or []:
            key = (
                str(ann.get("action") or ""),
                str(ann.get("subaction") or ""),
                str(ann.get("instance") or ""),
            )
            annotations.append(
                {
                    "taxonomy_code": code_by_label.get(key, "LLM_UNMAPPED"),
                    "action": key[0],
                    "subaction": key[1],
                    "instance": key[2],
                    "evidence": str(ann.get("evidence") or ""),
                    "assignment_reason": "llm",
                    "confidence": "llm",
                }
            )
        if annotations:
            by_turn[turn_id]["annotations"] = annotations
    return [by_turn[key] for key in sorted(by_turn)]


def _build_actonomy_sessions_from_llm(
    actonomy: dict[str, Any],
    data: dict[str, Any],
    warnings: list[str],
) -> list[dict[str, Any]]:
    source = data.get("actonomy_sessions")
    if not isinstance(source, list):
        warnings.append("missing actonomy_sessions")
        return []
    turns = {turn["turn"]: turn for turn in actonomy.get("turns", [])}
    template = actonomy.get("sessions", [{}])[0] if actonomy.get("sessions") else {}
    out = []
    for i, item in enumerate(source, start=1):
        span = _validated_span(item, turns, warnings, label=f"actonomy_session[{i}]")
        if not span:
            continue
        start, end = span
        span_turns = [turns[idx] for idx in range(start, end + 1) if idx in turns]
        action_counts = Counter(
            ann["action"] for turn in span_turns for ann in turn.get("annotations", [])
        )
        code_counts = Counter(
            ann["taxonomy_code"] for turn in span_turns for ann in turn.get("annotations", [])
        )
        action_type_counts = Counter(
            turn.get("action_type") for turn in span_turns if turn.get("action_type")
        )
        out.append(
            {
                **_base_record(template),
                "session_id": len(out) + 1,
                "start_turn": start,
                "end_turn": end,
                "turn_count": len(span_turns),
                "dominant_phase": "LLM named phase",
                "dominant_action": action_counts.most_common(1)[0][0] if action_counts else "Uncoded",
                "title": str(item.get("title") or f"Act-onomy phase {i}"),
                "phase_counts": {"LLM named phase": 1},
                "action_counts": dict(sorted(action_counts.items())),
                "action_type_counts": dict(sorted(action_type_counts.items())),
                "taxonomy_code_counts": dict(sorted(code_counts.items())),
                "summary": str(item.get("summary") or item.get("title") or ""),
                "turns": [turn["turn"] for turn in span_turns],
            }
        )
    return out


def _wang_summary(wang: dict[str, Any], steps: list[dict[str, Any]], result) -> dict[str, Any]:
    old = dict(wang.get("summary") or {})
    old.update(
        {
            "annotation_mode": "llm",
            "llm_provider": result.provider,
            "llm_model": result.model,
            "workflow_step_count": len(steps),
            "phase_counts": dict(Counter(step["title"] for step in steps)),
            "sequence_summary": " -> ".join(
                f"{step['workflow_step_id']}:{step['title']}" for step in steps
            ),
        }
    )
    return old


def _actonomy_profile(actonomy: dict[str, Any], sessions: list[dict[str, Any]], result) -> dict[str, Any]:
    turns = actonomy.get("turns", [])
    action_counts = Counter(
        ann["action"] for turn in turns for ann in turn.get("annotations", [])
    )
    code_counts = Counter(
        ann["taxonomy_code"] for turn in turns for ann in turn.get("annotations", [])
    )
    profile = dict(actonomy.get("profile") or {})
    profile.update(
        {
            "annotation_mode": "llm",
            "llm_provider": result.provider,
            "llm_model": result.model,
            "session_count": len(sessions),
            "annotation_count": sum(len(turn.get("annotations", [])) for turn in turns),
            "action_counts": dict(sorted(action_counts.items())),
            "taxonomy_code_counts": dict(sorted(code_counts.items())),
            "phase_counts": dict(Counter(session["title"] for session in sessions)),
            "session_summaries": [session["summary"] for session in sessions],
            "sequence_summary": " -> ".join(
                f"{session['session_id']}:{session['title']}" for session in sessions
            ),
        }
    )
    return profile


def _validated_span(
    item: dict[str, Any],
    valid_records: dict[int, Any],
    warnings: list[str],
    *,
    label: str,
) -> tuple[int, int] | None:
    try:
        start = int(item.get("start"))
        end = int(item.get("end"))
    except Exception:  # noqa: BLE001
        warnings.append(f"{label}: invalid span")
        return None
    if start > end or start not in valid_records or end not in valid_records:
        warnings.append(f"{label}: span out of range {start}-{end}")
        return None
    return start, end


def _base_record(template: dict[str, Any]) -> dict[str, Any]:
    return {
        key: template.get(key)
        for key in (
            "trajectory_path",
            "trajectory_id",
            "experiment_id",
            "run_id",
            "task_id",
            "benchmark",
            "success",
            "score",
        )
    }
