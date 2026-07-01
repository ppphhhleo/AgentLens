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
    "mcp_tool": "mcp.*",
    "desktop_screenshot": "desktop.screenshot",
    "desktop_click": "desktop.click",
    "desktop_double_click": "desktop.double_click",
    "desktop_scroll": "desktop.scroll",
    "desktop_move": "desktop.move",
    "desktop_drag": "desktop.drag",
    "desktop_type": "desktop.type",
    "desktop_keypress": "desktop.keypress",
    "desktop_launch_app": "desktop.launch_app",
    "desktop_pyautogui": "desktop.pyautogui",
    "desktop_shell": "desktop.shell",
    "desktop_wait": "desktop.wait",
}

TOOL_NAME_TO_ACTION_TYPE: dict[str, str] = {v: k for k, v in TOOL_NAME_BY_ACTION_TYPE.items()}


# Per-action prompt schema fragments. Order in this dict drives the
# rendered list order in the system prompt. Keep concise — these are
# token cost.
_ACTION_SCHEMA_FRAGMENTS: dict[str, str] = {
    "click":         '- {{"type": "click", <TARGET>, "button": "left"|"right"|"middle", "keys": ["SHIFT"]?}}',
    "double_click":  '- {{"type": "double_click", <TARGET>, "button": "left", "keys": []?}}',
    "scroll":        '- {{"type": "scroll", <TARGET>, "scroll_x": int, "scroll_y": int, "keys": []?}}',
    "type":          '- {{"type": "type", "text": "...", <OPTIONAL_TARGET>}}',
    "keypress":      '- {{"type": "keypress", "keys": ["Enter"]}}',
    "wait":          '- {{"type": "wait", "ms": 1000}}',
    "move":          '- {{"type": "move", <TARGET>, "keys": []?}}',
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
    "desktop_screenshot": '- {{"type": "desktop_screenshot"}}',
    "desktop_click":      '- {{"type": "desktop_click", "x": int, "y": int, "button": "left"|"right"|"middle"}}',
    "desktop_double_click": '- {{"type": "desktop_double_click", "x": int, "y": int, "button": "left"|"right"|"middle"}}',
    "desktop_scroll":     '- {{"type": "desktop_scroll", "x": int?, "y": int?, "scroll_x": int, "scroll_y": int}}',
    "desktop_move":       '- {{"type": "desktop_move", "x": int, "y": int}}',
    "desktop_drag":       '- {{"type": "desktop_drag", "path": [{{"x": int, "y": int}}, ...]}}',
    "desktop_type":       '- {{"type": "desktop_type", "text": "..."}}',
    "desktop_keypress":   '- {{"type": "desktop_keypress", "keys": ["Enter"]}}',
    "desktop_launch_app": '- {{"type": "desktop_launch_app", "app": "blender"}}  (launches a GUI app detached from the shell tool)',
    "desktop_pyautogui":  '- {{"type": "desktop_pyautogui", "code": "pyautogui.click(100, 200)"}}  (executes pyautogui code in the desktop sandbox)',
    "desktop_shell":      '- {{"type": "desktop_shell", "cmd": "..."}}  (runs a shell command in the desktop sandbox; output in NEXT observation)',
    "desktop_wait":       '- {{"type": "desktop_wait", "ms": 1000}}',
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
        if action_type == "mcp_tool":
            return False
        tool_name = TOOL_NAME_BY_ACTION_TYPE.get(action_type)
        if tool_name is None:
            # Unknown action types are conservatively rejected when gating
            # is on; this surfaces typos and keeps the prompt aligned.
            return False
        return tool_name in self.allowed

    def gate_action(self, action: ComputerAction) -> tuple[bool, str | None]:
        """Returns (allowed, error_message_if_denied)."""
        if action.type == "mcp_tool":
            tool_name = action.mcp_tool or "mcp.unknown"
            if self.is_unrestricted or tool_name in self.allowed:
                return True, None
            return (
                False,
                f"MCP tool {tool_name!r} is not in this harness's allowed tools: "
                f"{sorted(self.allowed)}",
            )
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


_TARGET_HINTS = {
    "coordinate": '"x": int, "y": int',
    "bid":        '"bid": "<element id from the AXTree, e.g. \\"a23\\">"',
    "selector":   '"selector": "<CSS selector>"',
    "mark":       '"mark": "<mark label, e.g. \\"A3\\">"',
}


def render_action_schema(
    toolset: ToolSet,
    addressing_modes: list[str] | None = None,
) -> str:
    """Render the bullet list of allowed action shapes for the system prompt.

    `addressing_modes` is the list of allowed ways to address an element
    for click/double_click/scroll/move (e.g. ["coordinate"], ["bid"],
    ["bid", "mark"], ["coordinate", "bid"]). Defaults to ["coordinate"]
    for backward compat. The schema fragments substitute the matching
    `<TARGET>` placeholder with the right hint(s).

    For `type`, the target is optional — the agent may either fill a
    targeted element (bid/selector/mark) or type into whatever's
    currently focused (no target).
    """
    if not addressing_modes:
        addressing_modes = ["coordinate"]
    valid = [m for m in addressing_modes if m in _TARGET_HINTS]
    if not valid:
        valid = ["coordinate"]
    target_doc = " OR ".join(_TARGET_HINTS[m] for m in valid)
    target_block = f"({target_doc})"
    optional_target_block = f"[OPTIONAL: {target_doc}]"

    rendered: list[str] = []
    for t in toolset.allowed_action_types():
        frag = _ACTION_SCHEMA_FRAGMENTS[t]
        frag = frag.replace("<TARGET>", target_block)
        frag = frag.replace("<OPTIONAL_TARGET>", optional_target_block)
        rendered.append(frag)
    return "\n".join(rendered)


def tool_name_for(action: ComputerAction) -> str:
    """Lookup helper for telemetry — never raises."""
    if action.type == "mcp_tool":
        return action.mcp_tool or "mcp.unknown"
    return TOOL_NAME_BY_ACTION_TYPE.get(action.type, f"unknown.{action.type}")


# ---------- USER-side tool gating ------------------------------------
#
# Symmetric to the agent's TOOL_NAME map but for user actor actions
# (see schemas.UserActionType). Lives in the same module so every
# adapter has one place to look for "what's allowed to be emitted".

USER_TOOL_NAME_BY_ACTION_TYPE: dict[str, str] = {
    "no_intervention": "user.no_intervention",
    "accept": "user.accept",
    "reject": "user.reject",
    "send_message": "user.send_message",
    "request_clarification": "user.request_clarification",
}

USER_TOOL_NAME_TO_ACTION_TYPE: dict[str, str] = {
    v: k for k, v in USER_TOOL_NAME_BY_ACTION_TYPE.items()
}


_USER_ACTION_SCHEMA_FRAGMENTS: dict[str, str] = {
    "accept":                '- {{"type": "accept", "text": "<short reason>"}}',
    "reject":                '- {{"type": "reject", "text": "<reason agent should know>"}}',
    "send_message":          '- {{"type": "send_message", "text": "..."}}',
    "request_clarification": '- {{"type": "request_clarification", "text": "<question to the agent>"}}',
    "no_intervention":       '- {{"type": "no_intervention"}}',
}


@dataclass(frozen=True)
class UserToolSet:
    """Allow-list for user-actor actions. Empty = unrestricted."""

    allowed: frozenset[str]

    @classmethod
    def from_harness(cls, harness) -> UserToolSet:
        return cls(allowed=frozenset(getattr(harness, "tools", []) or []))

    @property
    def is_unrestricted(self) -> bool:
        return len(self.allowed) == 0

    def is_allowed(self, action_type: str) -> bool:
        if self.is_unrestricted:
            return True
        tool = USER_TOOL_NAME_BY_ACTION_TYPE.get(action_type)
        return tool is not None and tool in self.allowed

    def allowed_action_types(self) -> list[str]:
        if self.is_unrestricted:
            return list(_USER_ACTION_SCHEMA_FRAGMENTS.keys())
        return [
            t
            for t in _USER_ACTION_SCHEMA_FRAGMENTS.keys()
            if USER_TOOL_NAME_BY_ACTION_TYPE.get(t) in self.allowed
        ]


def render_user_action_schema(toolset: UserToolSet) -> str:
    return "\n".join(
        _USER_ACTION_SCHEMA_FRAGMENTS[t] for t in toolset.allowed_action_types()
    )


def user_tool_name_for(action_type: str) -> str:
    return USER_TOOL_NAME_BY_ACTION_TYPE.get(action_type, f"unknown.{action_type}")
