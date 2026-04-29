"""Eval protocols — how each benchmark wants the agent's answer delivered.

Different benchmarks have different "stop-and-deliver" conventions:
  A. DOM/state-only (MiniWoB) — agent's answer text doesn't matter; only page state
  B. Free-text (AssistantBench, OM2W) — raw answer text; validator matches/judges
  C. Wrapped-text (CocoaBench, BrowseComp) — answer must contain <answer>...</answer>
  D. Tool-call (CocoaBench official) — separate harness; not handled here

This module centralizes the small per-task differences so adapters don't
each reinvent the wrapping / chat-message / prompt-extension dance.

The agent loop (screenshot_react_loop) is unchanged: it always just emits
final_answer with text. The adapter calls:
  - extend_goal(task, goal)   pre-loop, to add per-task format hints
  - prepare_answer(task, raw_answer)  post-loop, to format for the validator

See docs/benchmarks.md "Eval confirmation conventions" for the rationale.
"""
from __future__ import annotations

from typing import Literal

from agentlens.schemas import TaskConfig

AnswerFormat = Literal["identity", "wrap_xml_answer", "chat_message"]


def goal_with_format_hint(task: TaskConfig) -> str:
    """Return the agent-facing goal text, with any task-specific output-format
    hint appended. Pre-loop side of the eval protocol."""
    base = task.goal or ""
    hint = (task.extra or {}).get("output_format_hint")
    if not hint:
        return base
    if base and not base.endswith("\n"):
        base = base + "\n"
    return base + "\n" + str(hint).rstrip() + "\n"


def prepare_answer_for_validator(task: TaskConfig, raw_answer: str | None) -> str | None:
    """Reshape the agent's raw final_answer into what the validator expects.

    The "what to do" comes from `task.extra.answer_format`:
      - identity         (default): pass raw answer through unchanged
      - wrap_xml_answer  : wrap text in <answer>...</answer> if not already
      - chat_message     : (handled by the adapter at call time; this fn
                           still returns the wrapped/raw answer for the
                           assistant message body)

    Post-loop side of the eval protocol.
    """
    if raw_answer is None:
        return None
    fmt = _answer_format(task)
    text = raw_answer.strip()
    if fmt == "wrap_xml_answer" and "<answer>" not in text.lower():
        return f"<answer>{text}</answer>"
    return text


def deliver_as_chat_message(task: TaskConfig) -> bool:
    """Whether the validator expects a synthetic [{role:assistant,...}]
    list rather than a raw answer string. Adapters that call
    `task.validate(page, chat_messages)` (BrowserGym chat-validator tasks)
    consult this to decide how to package the answer."""
    return _answer_format(task) == "chat_message"


def _answer_format(task: TaskConfig) -> AnswerFormat:
    raw = (task.extra or {}).get("answer_format", "identity")
    if raw not in ("identity", "wrap_xml_answer", "chat_message"):
        return "identity"
    return raw  # type: ignore[return-value]
