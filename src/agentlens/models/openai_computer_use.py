from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from agentlens.actions import ComputerAction
from agentlens.models.base import ModelStep, ScreenshotObservation
from agentlens.schemas import ModelConfig


GUI_OPERATOR_PROMPT = """You are operating a Linux desktop through its graphical interface.

Complete the user's task using only visible GUI operations such as clicking, dragging,
typing, scrolling, waiting, and keyboard shortcuts. Do not use shell commands, code
execution, direct filesystem edits, database edits, or hidden programmatic shortcuts.

The application or website may already be open. If the task needs a browser, use the
visible browser window. You can act without asking for confirmation.

When the task is complete and an answer is requested, respond with only the exact
answer. Do not add explanation, prefixes, or markdown.

Current date: {current_date}
"""


class OpenAIComputerUseModel:
    """OpenAI Responses API native computer-use model.

    This is intentionally separate from `OpenAIToolCallModel`.
    It mirrors the paper-style GUI setup: the model receives a clean GUI-only
    operator prompt and the native OpenAI `{"type": "computer"}` tool, not an
    AgentLens-rendered list of JSON function tools.
    """

    def __init__(self, config: ModelConfig, toolset=None) -> None:
        self.config = config
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Put it in .env at the repo root or export it."
            )
        self.client = OpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL"))
        self.model_name = config.name
        self.max_output_tokens = config.max_output_tokens
        self.reasoning_effort = (config.extra or {}).get("reasoning_effort")
        self.reasoning_summary = (config.extra or {}).get("reasoning_summary")
        self.truncation = (config.extra or {}).get("truncation", "auto")
        self.environment = (config.extra or {}).get("computer_environment", "linux")
        self.display_width = int((config.extra or {}).get("display_width", 1024))
        self.display_height = int((config.extra or {}).get("display_height", 768))
        self.previous_response_id: str | None = None
        self.pending_input_items: list[dict[str, Any]] = []

    def step(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> ModelStep:
        if observation.screenshot_path is None:
            raise ValueError("openai_computer backend requires a desktop screenshot")
        if not history:
            self.previous_response_id = None
            self.pending_input_items = []

        request_input = self._build_input(goal, observation.screenshot_path)
        response = self._create_response(request_input)
        self.previous_response_id = _get_field(response, "id")

        parsed = _parse_response(response)
        self.pending_input_items = parsed.pending_input_items
        actions = [_map_computer_action(item) for item in parsed.computer_actions]
        actions = [action for action in actions if action is not None]

        if not actions:
            if parsed.message_text:
                actions = [ComputerAction(type="final_answer", answer=parsed.message_text.strip())]
            else:
                # In the built-in computer loop, the absence of a computer_call means
                # the model is done. Continuing with previous_response_id plus a fresh
                # image is rejected by the Responses API.
                self.previous_response_id = None
                actions = [
                    ComputerAction(
                        type="final_answer",
                        answer=parsed.reasoning_text.strip() or "[NO_COMPUTER_ACTION]",
                    )
                ]

        usage = _get_field(response, "usage", {}) or {}
        raw_response = _model_dump(response)
        return ModelStep(
            thought=parsed.reasoning_text,
            action=actions[0],
            actions=actions,
            raw_response=json.dumps(_sanitize_response(raw_response), ensure_ascii=False),
            prompt_tokens=_get_field(usage, "input_tokens") or _get_field(usage, "prompt_tokens"),
            completion_tokens=_get_field(usage, "output_tokens") or _get_field(usage, "completion_tokens"),
            extra={
                "model": _get_field(response, "model", self.model_name),
                "interaction_backend": "openai_computer",
                "provider_tool_call": parsed.computer_calls[0] if parsed.computer_calls else None,
                "provider_tool_calls": parsed.computer_calls,
                "provider_computer_actions": parsed.computer_actions,
                "native_tool": self._computer_tool(),
            },
        )

    def _build_input(self, goal: str, screenshot_path: Path) -> list[dict[str, Any]]:
        image_url = self._image_to_data_url(screenshot_path)
        if self.previous_response_id and self.pending_input_items:
            request_input = []
            for item in self.pending_input_items:
                item_copy = dict(item)
                item_copy["output"] = {
                    "type": "computer_screenshot",
                    "image_url": image_url,
                    "detail": "original",
                }
                request_input.append(item_copy)
            return request_input

        return [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": goal}],
            }
        ]

    def _create_response(self, request_input: list[dict[str, Any]]) -> Any:
        request: dict[str, Any] = {
            "model": self.model_name,
            "instructions": GUI_OPERATOR_PROMPT.format(
                current_date=datetime.now().strftime("%A, %B %d, %Y")
            ),
            "input": request_input,
            "tools": [self._computer_tool()],
            "parallel_tool_calls": False,
            "truncation": self.truncation,
        }
        if self.reasoning_effort or self.reasoning_summary:
            request["reasoning"] = {
                key: value
                for key, value in {
                    "effort": self.reasoning_effort,
                    "summary": self.reasoning_summary,
                }.items()
                if value
            }
        if self.max_output_tokens:
            request["max_output_tokens"] = self.max_output_tokens
        if self.previous_response_id:
            request["previous_response_id"] = self.previous_response_id
        return self.client.responses.create(**request)

    def _computer_tool(self) -> dict[str, Any]:
        if "computer-use-preview" in self.model_name.lower():
            return {
                "type": "computer_use_preview",
                "display_width": self.display_width,
                "display_height": self.display_height,
                "environment": self.environment,
            }
        return {"type": "computer"}

    @staticmethod
    def _image_to_data_url(path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"


class _ParsedComputerResponse:
    def __init__(
        self,
        *,
        message_text: str,
        reasoning_text: str,
        computer_actions: list[dict[str, Any]],
        computer_calls: list[dict[str, Any]],
        pending_input_items: list[dict[str, Any]],
    ) -> None:
        self.message_text = message_text
        self.reasoning_text = reasoning_text
        self.computer_actions = computer_actions
        self.computer_calls = computer_calls
        self.pending_input_items = pending_input_items


def _parse_response(response: Any) -> _ParsedComputerResponse:
    messages: list[str] = []
    reasoning: list[str] = []
    computer_actions: list[dict[str, Any]] = []
    computer_calls: list[dict[str, Any]] = []
    pending_input_items: list[dict[str, Any]] = []

    for item in _get_field(response, "output", []) or []:
        item_type = _get_field(item, "type")
        if item_type == "message":
            text = _message_text(item)
            if text:
                messages.append(text)
        elif item_type == "reasoning":
            text = _reasoning_text(item)
            if text:
                reasoning.append(text)
        elif item_type == "computer_call":
            call_record = _model_dump(item)
            raw_actions = _get_field(item, "actions")
            if raw_actions is None:
                single = _get_field(item, "action")
                raw_actions = [single] if single is not None else []
            action_records = [_action_to_dict(action) for action in raw_actions]
            computer_actions.extend(action_records)
            computer_calls.append({**call_record, "agentlens_actions": action_records})

            call_id = _get_field(item, "call_id", "") or ""
            output_item: dict[str, Any] = {
                "type": "computer_call_output",
                "call_id": call_id,
                "output": {
                    "type": "computer_screenshot",
                    "image_url": "",
                    "detail": "original",
                },
            }
            pending_checks = _model_dump(_get_field(item, "pending_safety_checks", [])) or []
            if pending_checks:
                output_item["acknowledged_safety_checks"] = pending_checks
            pending_input_items.append(output_item)

    return _ParsedComputerResponse(
        message_text="\n".join(messages).strip(),
        reasoning_text="\n".join(reasoning + messages).strip(),
        computer_actions=computer_actions,
        computer_calls=computer_calls,
        pending_input_items=pending_input_items,
    )


def _map_computer_action(raw: dict[str, Any]) -> ComputerAction | None:
    action_type = raw.get("type")
    args = dict(raw.get("args") or {})
    if action_type == "click":
        return ComputerAction(
            type="desktop_click",
            x=args.get("x"),
            y=args.get("y"),
            button=_button(args.get("button")),
        )
    if action_type == "double_click":
        return ComputerAction(
            type="desktop_double_click",
            x=args.get("x"),
            y=args.get("y"),
            button=_button(args.get("button")),
        )
    if action_type == "move":
        return ComputerAction(type="desktop_move", x=args.get("x"), y=args.get("y"))
    if action_type == "drag":
        path = args.get("path")
        if not path and args.get("from") and args.get("to"):
            path = [args["from"], args["to"]]
        return ComputerAction(type="desktop_drag", path=path or [])
    if action_type == "scroll":
        return ComputerAction(
            type="desktop_scroll",
            x=args.get("x"),
            y=args.get("y"),
            scroll_x=_number(args.get("scroll_x") or args.get("delta_x") or args.get("deltaX")),
            scroll_y=_number(args.get("scroll_y") or args.get("delta_y") or args.get("deltaY")),
        )
    if action_type == "type":
        return ComputerAction(type="desktop_type", text=str(args.get("text", "")))
    if action_type == "keypress":
        keys = args.get("keys") or ([args.get("key")] if args.get("key") else [])
        if not isinstance(keys, list):
            keys = [keys]
        return ComputerAction(type="desktop_keypress", keys=[str(key) for key in keys])
    if action_type == "wait":
        return ComputerAction(type="desktop_wait", ms=int(args.get("ms") or 1000))
    if action_type == "screenshot":
        return ComputerAction(type="desktop_screenshot")
    return None


def _action_to_dict(action: Any) -> dict[str, Any]:
    raw = _model_dump(action)
    if isinstance(raw, dict):
        action_type = raw.get("type")
        args = {k: v for k, v in raw.items() if k != "type"}
        return {"type": action_type, "args": args}
    action_type = getattr(action, "type", None)
    args: dict[str, Any] = {}
    for attr in dir(action):
        if attr.startswith("_") or attr == "type":
            continue
        try:
            args[attr] = _model_dump(getattr(action, attr))
        except Exception:
            continue
    return {"type": action_type, "args": args}


def _message_text(item: Any) -> str:
    content = _get_field(item, "content", [])
    if isinstance(content, list):
        parts = []
        for part in content:
            if _get_field(part, "type") == "output_text":
                text = _get_field(part, "text", "")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def _reasoning_text(item: Any) -> str:
    summary = _get_field(item, "summary", [])
    if isinstance(summary, list):
        parts = []
        for part in summary:
            text = _get_field(part, "text", "")
            if text:
                parts.append(str(text))
        return "\n".join(parts)
    return str(summary or "")


def _get_field(value: Any, field: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    if isinstance(value, list):
        return [_model_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _model_dump(item) for key, item in value.items()}
    if hasattr(value, "__dict__"):
        return {
            key: _model_dump(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _sanitize_response(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_response(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_response(item) for item in value]
    return value


def _button(value: Any) -> str:
    if value in {"left", "right", "middle"}:
        return str(value)
    return "left"


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
