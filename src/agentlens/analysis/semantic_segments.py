from __future__ import annotations

import re
from collections import Counter
from typing import Any


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "i",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "will",
    "with",
}

INTENT_PATTERNS = [
    ("submit_answer", ("final answer", "answer")),
    ("verify_or_check", ("verify", "check", "confirm", "ensure", "ensuring", "validate")),
    ("recover_or_retry", ("retry", "again", "failed", "error", "wrong", "instead")),
    ("construct_visualization", ("visualize", "visualization", "encoding", "axis", "chart")),
    ("compute_or_analyze", ("compute", "calculate", "analyze", "analysis", "correlates")),
    ("inspect_data_or_screen", ("inspect", "examine", "look", "view", "see")),
    ("create_or_modify_artifact", ("write", "create", "modify", "edit", "save")),
    ("retrieve_information", ("read", "search", "open", "fetch", "load")),
]

ACTION_TITLE = {
    "click": "Interact with the interface",
    "double_click": "Interact with the interface",
    "drag": "Arrange visual fields",
    "type": "Enter information",
    "keypress": "Enter information",
    "scroll": "Inspect more of the interface",
    "move": "Inspect the interface",
    "goto": "Navigate to a page",
    "web_search": "Search for external information",
    "read_file": "Read local evidence",
    "write_file": "Create or update an artifact",
    "run_python": "Compute with code",
    "shell": "Inspect or execute via shell",
    "final_answer": "Submit the final answer",
    "mcp_tool": "Use browser automation",
    "desktop_screenshot": "Observe the desktop",
    "desktop_wait": "Wait for desktop state",
    "desktop_click": "Interact with the desktop app",
    "desktop_type": "Enter information",
    "desktop_keypress": "Use keyboard shortcut",
    "desktop_shell": "Launch or inspect desktop app",
}


def semantic_intent(text: str, action_type: str | None = None) -> str:
    lowered = text.casefold()
    if action_type == "final_answer":
        return "submit_answer"
    for intent, patterns in INTENT_PATTERNS:
        if any(_contains_pattern(lowered, pattern) for pattern in patterns):
            return intent
    if action_type in {"run_python", "shell", "desktop_shell"}:
        return "compute_or_analyze"
    if action_type in {"read_file", "web_search"}:
        return "retrieve_information"
    if action_type in {"write_file", "type", "keypress", "desktop_type", "desktop_keypress"}:
        return "create_or_modify_artifact"
    if action_type in {"click", "double_click", "drag", "scroll", "move", "desktop_click"}:
        return "interact_with_interface"
    return "general_task_work"


def semantic_signature(action_type: str | None, action_text: str, thought: str) -> str:
    intent = semantic_intent(thought, action_type=action_type)
    target = action_target_signature(action_type, action_text)
    keywords = "-".join(top_keywords(thought, limit=3))
    return "|".join(part for part in [str(action_type or "none"), intent, target, keywords] if part)


def should_split_semantically(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    min_similarity: float = 0.34,
) -> bool:
    if previous.get("phase") != current.get("phase"):
        return True
    if previous.get("action_type") != current.get("action_type"):
        return True
    if previous.get("semantic_signature") == current.get("semantic_signature"):
        return False
    previous_target = previous.get("action_target")
    current_target = current.get("action_target")
    if previous_target and current_target and previous_target != current_target:
        return True
    previous_intent = previous.get("semantic_intent")
    current_intent = current.get("semantic_intent")
    if previous_intent and current_intent and previous_intent != current_intent:
        return True
    return text_similarity(previous.get("goal", ""), current.get("goal", "")) < min_similarity


def action_target_signature(action_type: str | None, action_text: str) -> str:
    if not action_type:
        return ""
    if action_type == "drag":
        points = re.findall(r"'x': ([0-9.]+), 'y': ([0-9.]+)", action_text)
        if points:
            return "drag:" + "->".join(f"{round(float(x))},{round(float(y))}" for x, y in points)
    if action_type in {"click", "double_click", "move", "desktop_click"}:
        match = re.search(r"x=([^ ]+) y=([^ ]+)", action_text)
        if match:
            return f"{action_type}:{match.group(1)},{match.group(2)}"
    if action_type in {"read_file", "write_file"}:
        return action_text.split(":", 1)[-1].strip()
    if action_type == "mcp_tool":
        if "mcp.chrome.goto" in action_text:
            return compact_text(action_text, limit=80)
        if "selector" in action_text:
            return compact_text(action_text, limit=80)
        return action_text.split(":", 1)[0]
    if action_type in {"run_python", "shell", "desktop_shell", "web_search", "final_answer", "goto"}:
        return compact_text(action_text, limit=80)
    return action_type


def summarize_semantic_group(
    records: list[dict[str, Any]],
    *,
    prefix: str = "",
) -> tuple[str, str]:
    if not records:
        return "Empty phase", "No records were available for this phase."
    action_counts = Counter(record.get("action_type") for record in records if record.get("action_type"))
    dominant_action = action_counts.most_common(1)[0][0] if action_counts else None
    title = _title_for_group(records, dominant_action=dominant_action)
    start = records[0].get("step_index") or records[0].get("turn")
    end = records[-1].get("step_index") or records[-1].get("turn")
    thought = first_informative_text(records)
    action_text = ", ".join(f"{k}x{v}" for k, v in sorted(action_counts.items()))
    target = records[0].get("action_target") or records[0].get("action_surface") or records[0].get("action")
    summary = (
        f"{prefix}T{start}-T{end}: {sentence_case(title)}. "
        f"The actor {plain_verb_phrase(title)}"
    )
    if target:
        summary += f" using {compact_text(str(target), limit=110)}"
    if action_text:
        summary += f" ({action_text})"
    if thought:
        summary += f". Evidence: {compact_text(thought, limit=190)}"
    return title, summary + "."


def first_informative_text(records: list[dict[str, Any]]) -> str:
    for record in records:
        text = (
            record.get("goal")
            or record.get("thought")
            or (record.get("evidence") or {}).get("thought")
            or ""
        )
        if text and text != "{}":
            return str(text)
    return ""


def top_keywords(text: str, *, limit: int = 5) -> list[str]:
    words = [
        word
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", text.casefold())
        if word not in STOPWORDS and len(word) > 2
    ]
    return [word for word, _ in Counter(words).most_common(limit)]


def text_similarity(a: str, b: str) -> float:
    left = set(top_keywords(a, limit=20))
    right = set(top_keywords(b, limit=20))
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def compact_text(text: str, *, limit: int = 140) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def plain_verb_phrase(title: str) -> str:
    lowered = title.casefold()
    if lowered.startswith("submit"):
        return "submits"
    if lowered.startswith("compute"):
        return "computes"
    if lowered.startswith("read"):
        return "reads"
    if lowered.startswith("create"):
        return "creates"
    if lowered.startswith("arrange"):
        return "arranges"
    if lowered.startswith("inspect"):
        return "inspects"
    if lowered.startswith("verify"):
        return "verifies"
    if lowered.startswith("recover"):
        return "recovers"
    return "works"


def _title_for_group(records: list[dict[str, Any]], *, dominant_action: str | None) -> str:
    texts = " ".join(
        str(
            record.get("goal")
            or record.get("thought")
            or (record.get("evidence") or {}).get("thought")
            or ""
        )
        for record in records
    ).casefold()
    action_type = dominant_action or records[0].get("action_type")
    intent = semantic_intent(texts, action_type=action_type)
    if intent == "verify_or_check":
        return "Verify the intermediate result"
    if intent == "recover_or_retry":
        return "Recover from a failed attempt"
    if intent == "inspect_data_or_screen":
        return "Inspect the relevant data field"
    if intent == "construct_visualization":
        if "y-axis" in texts or "axis" in texts:
            return "Place the data field into the visual encoding"
        return "Construct a visualization for analysis"
    if intent == "compute_or_analyze":
        return "Analyze or compute the requested result"
    if intent == "create_or_modify_artifact":
        return ACTION_TITLE.get(str(action_type), "Create or update an artifact")
    if intent == "retrieve_information":
        return ACTION_TITLE.get(str(action_type), "Retrieve supporting information")
    if intent == "submit_answer":
        return "Submit the final answer"
    return ACTION_TITLE.get(str(action_type), "Perform task work")


def _contains_pattern(text: str, pattern: str) -> bool:
    if " " in pattern:
        return pattern in text
    return re.search(rf"\b{re.escape(pattern)}\b", text) is not None
