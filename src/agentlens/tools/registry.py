from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from agentlens.actions import ComputerAction


@dataclass(frozen=True)
class ToolSpec:
    """Provider-neutral tool definition.

    `name` is the stable AgentLens tool name used in configs and trajectory
    records. Provider adapters are responsible for translating it into each
    model API's function/tool wire format.
    """

    name: str
    action_type: str
    description: str
    parameters: dict[str, Any]
    executor_family: str
    default_enabled: bool = True

    def to_action(self, args: dict[str, Any]) -> ComputerAction:
        action_args = {
            key: value
            for key, value in args.items()
            if key not in {"reasoning"} and value is not None
        }
        if self.executor_family == "mcp":
            return ComputerAction.from_raw(
                {"type": "mcp_tool", "mcp_tool": self.name, "mcp_args": action_args}
            )
        return ComputerAction.from_raw({"type": self.action_type, **action_args})


@dataclass(frozen=True)
class ToolCallDecision:
    provider: str
    model: str
    tool_name: str
    tool_args: dict[str, Any]
    reasoning: str
    raw_provider_tool_name: str | None = None
    raw_response: dict[str, Any] | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "reasoning": self.reasoning,
            "raw_provider_tool_name": self.raw_provider_tool_name,
            "raw_response": self.raw_response,
            "finish_reason": self.finish_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class ProviderToolAdapter(Protocol):
    provider: str

    def tool_payloads(self, specs: list[ToolSpec]) -> list[dict[str, Any]]:
        """Render provider-specific tool/function declarations."""
        ...

    def parse_decision(self, response: Any, *, model: str) -> ToolCallDecision:
        """Parse a provider response into a provider-neutral tool decision."""
        ...


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self._by_name = {spec.name: spec for spec in specs}
        self._by_action_type: dict[str, list[ToolSpec]] = {}
        for spec in specs:
            self._by_action_type.setdefault(spec.action_type, []).append(spec)

    def get(self, name: str) -> ToolSpec:
        return self._by_name[name]

    def for_action_type(self, action_type: str) -> ToolSpec:
        specs = self._by_action_type[action_type]
        if len(specs) != 1:
            names = ", ".join(spec.name for spec in specs)
            raise ValueError(f"action type {action_type!r} maps to multiple tools: {names}")
        return specs[0]

    def specs_for_tool_names(self, tool_names: list[str], *, strict: bool = False) -> list[ToolSpec]:
        if not tool_names:
            return [spec for spec in self._by_name.values() if spec.default_enabled]
        if strict:
            unknown = sorted(set(tool_names) - set(self._by_name))
            if unknown:
                raise KeyError(f"unknown registered tool name(s): {unknown}")
        return [self._by_name[name] for name in tool_names if name in self._by_name]

    def specs_for_action_types(self, action_types: list[str]) -> list[ToolSpec]:
        return [self.for_action_type(action_type) for action_type in action_types]

    def to_action(self, decision: ToolCallDecision) -> ComputerAction:
        return self.get(decision.tool_name).to_action(decision.tool_args)


def default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolSpec(
                name="browser.screenshot",
                action_type="screenshot",
                executor_family="browser",
                description="Capture the current browser screenshot without changing page state.",
                parameters=_object_schema({}),
            ),
            ToolSpec(
                name="browser.click",
                action_type="click",
                executor_family="browser",
                description="Click one browser target. Provide exactly one target: x/y, bid, selector, or mark.",
                parameters=_targeted_object_schema(
                    {
                        "button": {"type": "string", "enum": ["left", "right", "middle"]},
                        "keys": _string_array("Modifier keys to hold, e.g. SHIFT or CTRL."),
                    }
                ),
            ),
            ToolSpec(
                name="browser.double_click",
                action_type="double_click",
                executor_family="browser",
                description="Double-click one browser target.",
                parameters=_targeted_object_schema(
                    {
                        "button": {"type": "string", "enum": ["left", "right", "middle"]},
                        "keys": _string_array("Modifier keys to hold."),
                    }
                ),
            ),
            ToolSpec(
                name="browser.scroll",
                action_type="scroll",
                executor_family="browser",
                description="Scroll at one browser target or current viewport region.",
                parameters=_targeted_object_schema(
                    {
                        "scroll_x": {"type": "number", "description": "Horizontal scroll delta."},
                        "scroll_y": {"type": "number", "description": "Vertical scroll delta."},
                        "keys": _string_array("Modifier keys to hold."),
                    },
                    required=["scroll_y"],
                ),
            ),
            ToolSpec(
                name="browser.type",
                action_type="type",
                executor_family="browser",
                description="Type text into the focused field or a specified browser target.",
                parameters=_object_schema(
                    {
                        **_target_props(),
                        "text": {"type": "string", "description": "Text to type or fill."},
                    },
                    required=["text"],
                ),
            ),
            ToolSpec(
                name="browser.wait",
                action_type="wait",
                executor_family="browser",
                description="Wait for the page to settle.",
                parameters=_object_schema(
                    {"ms": {"type": "integer", "description": "Milliseconds to wait."}}
                ),
            ),
            ToolSpec(
                name="browser.move",
                action_type="move",
                executor_family="browser",
                description="Move or hover over one browser target.",
                parameters=_targeted_object_schema({"keys": _string_array("Modifier keys.")}),
            ),
            ToolSpec(
                name="browser.keypress",
                action_type="keypress",
                executor_family="browser",
                description="Press one or more keyboard keys.",
                parameters=_object_schema(
                    {"keys": _string_array("Keys to press, e.g. Enter, CTRL, A.")},
                    required=["keys"],
                ),
            ),
            ToolSpec(
                name="browser.drag",
                action_type="drag",
                executor_family="browser",
                description="Drag through a sequence of viewport coordinate points.",
                parameters=_object_schema(
                    {
                        "path": {
                            "type": "array",
                            "minItems": 2,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                },
                                "required": ["x", "y"],
                                "additionalProperties": False,
                            },
                        },
                        "keys": _string_array("Modifier keys to hold."),
                    },
                    required=["path"],
                ),
            ),
            ToolSpec(
                name="browser.goto",
                action_type="goto",
                executor_family="browser",
                description="Navigate the browser to a URL.",
                parameters=_object_schema(
                    {"url": {"type": "string", "description": "Absolute URL to open."}},
                    required=["url"],
                ),
            ),
            ToolSpec(
                name="browser.back",
                action_type="back",
                executor_family="browser",
                description="Go back one browser history entry.",
                parameters=_object_schema({}),
            ),
            ToolSpec(
                name="browser.forward",
                action_type="forward",
                executor_family="browser",
                description="Go forward one browser history entry.",
                parameters=_object_schema({}),
            ),
            ToolSpec(
                name="browser.reload",
                action_type="reload",
                executor_family="browser",
                description="Reload the current page.",
                parameters=_object_schema({}),
            ),
            ToolSpec(
                name="web.openai_search",
                action_type="web_search",
                executor_family="web",
                description="Search the web. Results appear in the next observation.",
                parameters=_object_schema(
                    {"query": {"type": "string", "description": "Search query."}},
                    required=["query"],
                ),
            ),
            ToolSpec(
                name="code.run_python",
                action_type="run_python",
                executor_family="sandbox",
                description="Run Python code in the sandbox. Output appears in the next observation.",
                parameters=_object_schema(
                    {"code": {"type": "string", "description": "Python code to execute."}},
                    required=["code"],
                ),
            ),
            ToolSpec(
                name="code.shell",
                action_type="shell",
                executor_family="sandbox",
                description="Run a shell command in the sandbox. Output appears in the next observation.",
                parameters=_object_schema(
                    {"cmd": {"type": "string", "description": "Shell command to execute."}},
                    required=["cmd"],
                ),
            ),
            ToolSpec(
                name="files.read",
                action_type="read_file",
                executor_family="sandbox",
                description="Read a file from the sandbox.",
                parameters=_object_schema(
                    {"file_path": {"type": "string", "description": "Path to read."}},
                    required=["file_path"],
                ),
            ),
            ToolSpec(
                name="files.write",
                action_type="write_file",
                executor_family="sandbox",
                description="Write a file in the sandbox.",
                parameters=_object_schema(
                    {
                        "file_path": {"type": "string", "description": "Path to write."},
                        "content": {"type": "string", "description": "File content."},
                    },
                    required=["file_path", "content"],
                ),
            ),
            ToolSpec(
                name="desktop.screenshot",
                action_type="desktop_screenshot",
                executor_family="desktop",
                description="Capture the whole virtual desktop screenshot.",
                parameters=_object_schema({}),
            ),
            ToolSpec(
                name="desktop.click",
                action_type="desktop_click",
                executor_family="desktop",
                description="Click a point on the virtual desktop screen.",
                parameters=_object_schema(
                    {
                        "x": {"type": "number", "description": "Screen x coordinate."},
                        "y": {"type": "number", "description": "Screen y coordinate."},
                        "button": {"type": "string", "enum": ["left", "right", "middle"]},
                    },
                    required=["x", "y"],
                ),
            ),
            ToolSpec(
                name="desktop.type",
                action_type="desktop_type",
                executor_family="desktop",
                description="Type text into the currently focused desktop application.",
                parameters=_object_schema(
                    {"text": {"type": "string", "description": "Text to type."}},
                    required=["text"],
                ),
            ),
            ToolSpec(
                name="desktop.keypress",
                action_type="desktop_keypress",
                executor_family="desktop",
                description="Press one or more keyboard keys in the virtual desktop.",
                parameters=_object_schema(
                    {"keys": _string_array("Keys to press, e.g. ctrl+s, Enter, Escape.")},
                    required=["keys"],
                ),
            ),
            ToolSpec(
                name="desktop.launch_app",
                action_type="desktop_launch_app",
                executor_family="desktop",
                description="Launch a GUI application in the desktop sandbox without blocking the shell tool.",
                parameters=_object_schema(
                    {"app": {"type": "string", "description": "Application command, e.g. blender or weka."}},
                    required=["app"],
                ),
            ),
            ToolSpec(
                name="desktop.shell",
                action_type="desktop_shell",
                executor_family="desktop",
                description="Run a non-GUI shell command in the desktop sandbox for inspection or file operations.",
                parameters=_object_schema(
                    {"cmd": {"type": "string", "description": "Shell command to execute."}},
                    required=["cmd"],
                ),
            ),
            ToolSpec(
                name="desktop.wait",
                action_type="desktop_wait",
                executor_family="desktop",
                description="Wait for the desktop application to settle.",
                parameters=_object_schema(
                    {"ms": {"type": "integer", "description": "Milliseconds to wait."}}
                ),
            ),
            ToolSpec(
                name="task.final_answer",
                action_type="final_answer",
                executor_family="task",
                description="Submit the final answer. Use only the exact answer requested, no explanation.",
                parameters=_object_schema(
                    {"answer": {"type": "string", "description": "Exact final answer."}},
                    required=["answer"],
                ),
            ),
            ToolSpec(
                name="mcp.chrome.snapshot",
                action_type="mcp_tool",
                executor_family="mcp",
                default_enabled=False,
                description="Chrome MCP-style call: get page URL, title, body text, and visible interactive elements.",
                parameters=_object_schema({}),
            ),
            ToolSpec(
                name="mcp.chrome.goto",
                action_type="mcp_tool",
                executor_family="mcp",
                default_enabled=False,
                description="Chrome MCP-style call: navigate the active browser page to a URL.",
                parameters=_object_schema(
                    {
                        "url": {"type": "string", "description": "Absolute URL to open."},
                        "timeout_ms": {"type": "integer", "description": "Navigation timeout."},
                    },
                    required=["url"],
                ),
            ),
            ToolSpec(
                name="mcp.chrome.click_selector",
                action_type="mcp_tool",
                executor_family="mcp",
                default_enabled=False,
                description="Chrome MCP-style call: click a CSS selector on the active page.",
                parameters=_object_schema(
                    {
                        "selector": {"type": "string", "description": "CSS selector to click."},
                        "timeout_ms": {"type": "integer", "description": "Action timeout."},
                    },
                    required=["selector"],
                ),
            ),
            ToolSpec(
                name="mcp.chrome.type_selector",
                action_type="mcp_tool",
                executor_family="mcp",
                default_enabled=False,
                description="Chrome MCP-style call: fill text into a CSS selector on the active page.",
                parameters=_object_schema(
                    {
                        "selector": {"type": "string", "description": "CSS selector to type into."},
                        "text": {"type": "string", "description": "Text to type."},
                        "timeout_ms": {"type": "integer", "description": "Action timeout."},
                    },
                    required=["selector", "text"],
                ),
            ),
            ToolSpec(
                name="mcp.chrome.get_text",
                action_type="mcp_tool",
                executor_family="mcp",
                default_enabled=False,
                description="Chrome MCP-style call: return visible text from the page or one selector.",
                parameters=_object_schema(
                    {
                        "selector": {
                            "type": "string",
                            "description": "Optional CSS selector. If omitted, returns page body text.",
                        },
                    },
                ),
            ),
            ToolSpec(
                name="mcp.chrome.evaluate",
                action_type="mcp_tool",
                executor_family="mcp",
                default_enabled=False,
                description="Chrome MCP-style call: evaluate JavaScript in the active page and return JSON-safe result.",
                parameters=_object_schema(
                    {
                        "script": {
                            "type": "string",
                            "description": "JavaScript expression or function body accepted by Playwright page.evaluate.",
                        },
                    },
                    required=["script"],
                ),
            ),
        ]
    )


class OpenAIToolAdapter:
    provider = "openai"

    def __init__(self, registry: ToolRegistry, addressing_modes: list[str] | None = None) -> None:
        self.registry = registry
        self.addressing_modes = list(addressing_modes or ["coordinate"])
        self._provider_to_canonical: dict[str, str] = {}

    def tool_payloads(self, specs: list[ToolSpec]) -> list[dict[str, Any]]:
        tools = []
        self._provider_to_canonical = {}
        for spec in specs:
            provider_name = _provider_tool_name(spec.name)
            self._provider_to_canonical[provider_name] = spec.name
            parameters = _provider_visible_schema(
                spec,
                _with_reasoning(spec.parameters),
                addressing_modes=self.addressing_modes,
            )
            parameters = _openai_compatible_schema(parameters)
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": provider_name,
                        "description": spec.description,
                        "parameters": parameters,
                    },
                }
            )
        return tools

    def parse_decision(self, response: Any, *, model: str) -> ToolCallDecision:
        choice = response.choices[0]
        message = choice.message
        tool_calls = list(getattr(message, "tool_calls", None) or [])
        usage = getattr(response, "usage", None)
        if not tool_calls:
            content = (getattr(message, "content", None) or "").strip()
            if content and "task.final_answer" in set(self._provider_to_canonical.values()):
                return ToolCallDecision(
                    provider=self.provider,
                    model=model,
                    tool_name="task.final_answer",
                    tool_args={"answer": content},
                    reasoning=content,
                    raw_provider_tool_name=None,
                    raw_response=_safe_model_dump(response),
                    finish_reason=getattr(choice, "finish_reason", None),
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                )
            raise ValueError("model did not return a tool call")

        call = tool_calls[0]
        function = call.function
        provider_name = function.name
        canonical_name = self._provider_to_canonical.get(provider_name)
        if canonical_name is None:
            raise ValueError(f"unknown provider tool call: {provider_name}")
        try:
            args = json.loads(function.arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"tool call arguments were not valid JSON: {exc}; raw={function.arguments!r}"
            ) from exc
        reasoning = str(args.get("reasoning") or (getattr(message, "content", None) or "") or "")
        return ToolCallDecision(
            provider=self.provider,
            model=model,
            tool_name=canonical_name,
            tool_args=args,
            reasoning=reasoning,
            raw_provider_tool_name=provider_name,
            raw_response=_safe_model_dump(response),
            finish_reason=getattr(choice, "finish_reason", None),
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )


class AnthropicToolAdapter:
    provider = "anthropic"

    def __init__(self, registry: ToolRegistry, addressing_modes: list[str] | None = None) -> None:
        self.registry = registry
        self.addressing_modes = list(addressing_modes or ["coordinate"])
        self._provider_to_canonical: dict[str, str] = {}

    def tool_payloads(self, specs: list[ToolSpec]) -> list[dict[str, Any]]:
        tools = []
        self._provider_to_canonical = {}
        for spec in specs:
            provider_name = _provider_tool_name(spec.name)
            self._provider_to_canonical[provider_name] = spec.name
            tools.append(
                {
                    "name": provider_name,
                    "description": spec.description,
                    "input_schema": _provider_visible_schema(
                        spec,
                        _with_reasoning(spec.parameters),
                        addressing_modes=self.addressing_modes,
                    ),
                }
            )
        return tools

    def parse_decision(self, response: Any, *, model: str) -> ToolCallDecision:
        content_blocks = list(getattr(response, "content", None) or [])
        usage = getattr(response, "usage", None)
        text_parts = [
            str(getattr(block, "text", ""))
            for block in content_blocks
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ]
        text = "\n".join(part for part in text_parts if part).strip()
        tool_block = next(
            (block for block in content_blocks if getattr(block, "type", None) == "tool_use"),
            None,
        )
        if tool_block is None:
            if text and "task.final_answer" in set(self._provider_to_canonical.values()):
                return ToolCallDecision(
                    provider=self.provider,
                    model=model,
                    tool_name="task.final_answer",
                    tool_args={"answer": text},
                    reasoning=text,
                    raw_provider_tool_name=None,
                    raw_response=_safe_model_dump(response),
                    finish_reason=getattr(response, "stop_reason", None),
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                )
            raise ValueError("model did not return a tool_use block")

        provider_name = str(getattr(tool_block, "name", ""))
        canonical_name = self._provider_to_canonical.get(provider_name)
        if canonical_name is None:
            raise ValueError(f"unknown provider tool call: {provider_name}")
        raw_input = getattr(tool_block, "input", None) or {}
        if not isinstance(raw_input, dict):
            raise ValueError(f"tool_use input was not an object: {raw_input!r}")
        reasoning = str(raw_input.get("reasoning") or text or "")
        return ToolCallDecision(
            provider=self.provider,
            model=model,
            tool_name=canonical_name,
            tool_args=dict(raw_input),
            reasoning=reasoning,
            raw_provider_tool_name=provider_name,
            raw_response=_safe_model_dump(response),
            finish_reason=getattr(response, "stop_reason", None),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


def _provider_tool_name(name: str) -> str:
    return name.replace(".", "__")


def _with_reasoning(parameters: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(parameters))
    properties = updated.setdefault("properties", {})
    properties.setdefault(
        "reasoning",
        {
            "type": "string",
            "description": "Brief rationale for this tool call, if useful.",
        },
    )
    return updated


def _openai_compatible_schema(parameters: dict[str, Any]) -> dict[str, Any]:
    """Render the registry schema into OpenAI's supported function subset.

    AgentLens keeps richer canonical schemas where useful. OpenAI function
    parameters reject top-level combinators such as oneOf, so provider adapters
    strip those API-incompatible hints while preserving the actual properties.
    Runtime tool gating and action validation still enforce executable actions.
    """

    updated = json.loads(json.dumps(parameters))
    for key in ("oneOf", "anyOf", "allOf", "not", "const"):
        updated.pop(key, None)
    return updated


def _provider_visible_schema(
    spec: ToolSpec,
    parameters: dict[str, Any],
    *,
    addressing_modes: list[str],
) -> dict[str, Any]:
    """Hide target-addressing fields unavailable in the current observation mode."""

    updated = json.loads(json.dumps(parameters))
    properties = updated.get("properties")
    if not isinstance(properties, dict):
        return updated

    target_fields = {"x", "y", "bid", "selector", "mark"}
    if not target_fields.intersection(properties):
        return updated

    modes = set(addressing_modes or ["coordinate"])
    allowed: set[str] = set()
    if "coordinate" in modes:
        allowed.update({"x", "y"})
    if "bid" in modes or "axtree" in modes:
        allowed.add("bid")
    if "selector" in modes or "css" in modes:
        allowed.add("selector")
    if "mark" in modes or "set_of_marks" in modes:
        allowed.add("mark")

    for field in target_fields - allowed:
        properties.pop(field, None)

    required = [item for item in updated.get("required", []) if item in properties]
    if spec.action_type in {"click", "double_click", "move"} and {"x", "y"}.issubset(properties):
        required = _unique_required([*required, "x", "y"])
    updated["required"] = required
    return updated


def _unique_required(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        result.append(item)
        seen.add(item)
    return result


def _target_props() -> dict[str, Any]:
    return {
        "x": {"type": "number", "description": "Viewport x coordinate."},
        "y": {"type": "number", "description": "Viewport y coordinate."},
        "bid": {"type": "string", "description": "AXTree element id."},
        "selector": {"type": "string", "description": "CSS selector."},
        "mark": {"type": "string", "description": "Set-of-marks label."},
    }


def _string_array(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": description,
    }


def _object_schema(
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required or []),
        "additionalProperties": False,
    }


def _targeted_object_schema(
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
) -> dict[str, Any]:
    schema = _object_schema({**_target_props(), **properties}, required=required)
    schema["oneOf"] = [
        {"required": ["x", "y"]},
        {"required": ["bid"]},
        {"required": ["selector"]},
        {"required": ["mark"]},
    ]
    return schema


def _safe_model_dump(value: Any) -> dict[str, Any] | None:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return None
