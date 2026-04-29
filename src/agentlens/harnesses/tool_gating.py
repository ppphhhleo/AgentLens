"""Centralized tool gating.

Single source of truth for "what tools is this harness configured to expose?".
Used by every adapter and every model wrapper, so prompt advertising and
runtime gating can never drift apart.

Three responsibilities:

1. Map between our `ComputerAction.type` strings (the runtime / wire format)
   and the tool-name strings that appear in `ToolHarnessConfig.tools`
   (the experiment-config surface).
2. Hold an immutable ToolSet allow-list per run.
3. Render the action-schema section of the model's system prompt based on
   only the allowed tools.

Adapters call `ToolSet.from_harness(plan.tool_harness)` once per run and
gate every action. Model builders call `render_action_schema(toolset)` to
synthesize the prompt — same toolset, single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass

from agentlens.actions import ComputerAction
from agentlens.schemas import ToolHarnessConfig

# Action.type -> tool name (the string that appears in
# tool_harness.tools).  Bidirectional via TOOL_NAME_TO_ACTION_TYPE below.
TOOL_NAME_BY_ACTION_TYPE: dict[str, str] = {
    "screenshot": "browser.screenshot",
    "click": "browser.click",
    "double_click": "browser.double_click",
    "scroll": "browser.scroll",
    "type": "browser.type",
    "wait": "browser.wait",
    "move": "browser.move",
    "keypress": "browser.keypress",
    "drag": "browser.drag",
    "goto": "browser.goto",
    "back": "browser.back",
    "forward": "browser.forward",
    "reload": "browser.reload",
    "web_search": "web.openai_search",
    "run_python": "code.run_python",
    "shell": "code.shell",
    "read_file": "files.read",
    "write_file": "files.write",
    "final_answer": "task.final_answer",
}

TOOL_NAME_TO_ACTION_TYPE: dict[str, str] = {v: k for k, v in TOOL_NAME_BY_ACTION_TYPE.items()}


# Per-action prompt schema fragments. Order in this dict drives the
# rendered list order in the system prompt. Keep concise — these are
# token cost.
_ACTION_SCHEMA_FRAGMENTS: dict[str, str] = {
    "click":         '- {{"type": "click", "x": int, "y": int, "button": "left"|"right"|"middle", "keys": ["SHIFT"]?}}',
    "double_click":  '- {{"type": "double_click", "x": int, "y": int, "button": "left", "keys": []?}}',
    "scroll":        '- {{"type": "scroll", "x": int, "y": int, "scroll_x": int, "scroll_y": int, "keys": []?}}',
    "type":          '- {{"type": "type", "text": "..."}}',
    "keypress":      '- {{"type": "keypress", "keys": ["Enter"]}}',
    "wait":          '- {{"type": "wait", "ms": 1000}}',
    "move":          '- {{"type": "move", "x": int, "y": int, "keys": []?}}',
    "drag":          '- {{"type": "drag", "path": [{{"x": int, "y": int}}, ...], "keys": []?}}',
    "goto":          '- {{"type": "goto", "url": "https://..."}}',
    "back":          '- {{"type": "back"}}',
    "forward":       '- {{"type": "forward"}}',
    "reload":        '- {{"type": "reload"}}',
    "web_search":    '- {{"type": "web_search", "query": "..."}}  (calls OpenAI native web search; results appear in your NEXT observation, not the current page)',
    "run_python":    '- {{"type": "run_python", "code": "..."}}  (executes Python in a sandboxed Jupyter kernel; stdout/stderr appear in your NEXT observation)',
    "shell":         '- {{"type": "shell", "cmd": "..."}}  (runs a shell command in the sandbox workspace; output in NEXT observation)',
    "read_file":     '- {{"type": "read_file", "file_path": "/abs/or/workspace/path"}}  (reads file contents from sandbox; result in NEXT observation)',
    "write_file":    '- {{"type": "write_file", "file_path": "...", "content": "..."}}  (writes content to a sandbox file; confirmation in NEXT observation)',
    "screenshot":    '- {{"type": "screenshot"}}',
    "final_answer":  '- {{"type": "final_answer", "answer": "..."}}',
}


@dataclass(frozen=True)
class ToolSet:
    """Immutable allow-list for one harness configuration.

    `allowed` is a frozenset of tool-name strings (e.g. "browser.click",
    "task.final_answer"). An EMPTY allowed set means "no gating" (all
    actions permitted) — this keeps backward compatibility with existing
    configs that haven't bothered to enumerate tools.
    """

    allowed: frozenset[str]

    @classmethod
    def from_harness(cls, harness: ToolHarnessConfig) -> ToolSet:
        return cls(allowed=frozenset(harness.tools))

    @property
    def is_unrestricted(self) -> bool:
        return len(self.allowed) == 0

    def is_allowed(self, action_type: str) -> bool:
        """True iff the given ComputerAction.type is permitted."""
        if self.is_unrestricted:
            return True
        tool_name = TOOL_NAME_BY_ACTION_TYPE.get(action_type)
        if tool_name is None:
            # Unknown action types are conservatively rejected when gating
            # is on; this surfaces typos and keeps the prompt aligned.
            return False
        return tool_name in self.allowed

    def gate_action(self, action: ComputerAction) -> tuple[bool, str | None]:
        """Returns (allowed, error_message_if_denied)."""
        if self.is_allowed(action.type):
            return True, None
        return (
            False,
            f"action {action.type!r} (tool {TOOL_NAME_BY_ACTION_TYPE.get(action.type, '?')!r}) "
            f"is not in this harness's allowed tools: {sorted(self.allowed)}",
        )

    def allowed_action_types(self) -> list[str]:
        """List of ComputerAction.type values this toolset permits, in canonical order."""
        if self.is_unrestricted:
            return list(_ACTION_SCHEMA_FRAGMENTS.keys())
        return [
            t
            for t in _ACTION_SCHEMA_FRAGMENTS.keys()
            if TOOL_NAME_BY_ACTION_TYPE.get(t) in self.allowed
        ]


def render_action_schema(toolset: ToolSet) -> str:
    """Render the bullet list of allowed action shapes for the system prompt.

    Used by openai_vision.SYSTEM_PROMPT_TEMPLATE so the prompt only
    advertises tools the gate will actually accept.
    """
    return "\n".join(
        _ACTION_SCHEMA_FRAGMENTS[t] for t in toolset.allowed_action_types()
    )


def tool_name_for(action: ComputerAction) -> str:
    """Lookup helper for telemetry — never raises."""
    return TOOL_NAME_BY_ACTION_TYPE.get(action.type, f"unknown.{action.type}")
