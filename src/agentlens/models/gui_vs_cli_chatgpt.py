from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from agentlens.actions import ComputerAction
from agentlens.models.base import ModelStep, ScreenshotObservation
from agentlens.schemas import ModelConfig


class GuiVsCliChatGPTModel:
    """Adapter for the gui-vs-cli paper's ChatGPTAgent structure.

    The upstream agent receives a task instruction plus screenshot, calls the
    OpenAI Responses API native computer tool, converts native computer actions
    into pyautogui snippets, and chains turns with `previous_response_id`.
    AgentLens executes those snippets as `desktop_pyautogui` actions so the
    trajectory preserves the paper-faithful action representation.
    """

    def __init__(self, config: ModelConfig, toolset=None) -> None:
        self.config = config
        self.model_name = config.name
        self._agent = None

    def step(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> ModelStep:
        if observation.screenshot_path is None:
            raise ValueError("gui_vs_cli_chatgpt backend requires a desktop screenshot")
        if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENAI_BASE_URL"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Put it in .env at the repo root or export it."
            )
        if self._agent is None:
            self._agent = self._build_agent()
        if not history:
            self._agent.reset()

        screenshot_bytes = Path(observation.screenshot_path).read_bytes()
        thought, raw_actions = self._agent.predict(goal, {"screenshot": screenshot_bytes})
        actions = gui_vs_cli_actions_to_computer_actions(raw_actions, thought)
        raw_response = {
            "gui_vs_cli_actions": raw_actions,
            "provider_response": _sanitize_response(getattr(self._agent, "last_raw_response", None)),
        }
        return ModelStep(
            thought=thought,
            action=actions[0],
            actions=actions,
            raw_response=json.dumps(raw_response, ensure_ascii=False),
            extra={
                "model": self.model_name,
                "interaction_backend": "gui_vs_cli_chatgpt",
                "paper_agent": "third_party/gui-vs-cli/agents/chatgpt_agent.py",
                "raw_pyautogui_actions": raw_actions,
                "provider_tool_calls": _extract_computer_calls(
                    getattr(self._agent, "last_raw_response", None)
                ),
            },
        )

    def _build_agent(self):
        third_party_root = _third_party_gui_vs_cli_root()
        if not third_party_root.exists():
            raise RuntimeError(
                "third_party/gui-vs-cli is missing. Clone rebeccaz4/gui-vs-cli into "
                "third_party/gui-vs-cli before using interaction_backend='gui_vs_cli_chatgpt'."
            )
        root_str = str(third_party_root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        try:
            from agents.chatgpt_agent import ChatGPTAgent
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"failed to import gui-vs-cli ChatGPTAgent: {exc}") from exc

        extra = self.config.extra or {}
        screen_size = extra.get("screen_size") or [
            int(extra.get("display_width", 1600)),
            int(extra.get("display_height", 900)),
        ]
        return ChatGPTAgent(
            model=self.model_name,
            api_backend=extra.get("api_backend", "openai"),
            base_url=os.environ.get("OPENAI_BASE_URL") or extra.get("base_url"),
            platform=extra.get("platform", "ubuntu"),
            environment=extra.get("computer_environment", "linux"),
            reasoning_effort=extra.get("reasoning_effort", "medium"),
            reasoning_summary=extra.get("reasoning_summary", "concise"),
            truncation=extra.get("truncation", "auto"),
            max_tokens=self.config.max_output_tokens,
            temperature=extra.get("temperature") if extra.get("send_temperature") else None,
            screen_size=(int(screen_size[0]), int(screen_size[1])),
            max_steps=int(extra.get("max_steps", 400)),
            password=extra.get("password", "password"),
        )


def gui_vs_cli_actions_to_computer_actions(
    raw_actions: list[str],
    thought: str = "",
) -> list[ComputerAction]:
    actions: list[ComputerAction] = []
    for raw in raw_actions:
        token = raw.strip().upper()
        if token == "DONE":
            actions.append(ComputerAction(type="final_answer", answer=thought.strip()))
        elif token == "FAIL":
            actions.append(ComputerAction(type="final_answer", answer=thought.strip() or "[INFEASIBLE]"))
        elif token == "WAIT":
            actions.append(ComputerAction(type="desktop_wait", ms=1000))
        else:
            actions.append(ComputerAction(type="desktop_pyautogui", code=raw))
    return actions or [ComputerAction(type="desktop_wait", ms=1000)]


def _third_party_gui_vs_cli_root() -> Path:
    return Path(__file__).resolve().parents[3] / "third_party" / "gui-vs-cli"


def _extract_computer_calls(raw_response: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in _as_dict(raw_response).get("output", []) or []:
        if isinstance(item, dict) and item.get("type") == "computer_call":
            calls.append(_sanitize_response(item))
    return calls


def _sanitize_response(value: Any) -> Any:
    value = _as_plain(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            if key == "image_url" and isinstance(child, str) and child.startswith("data:image/"):
                out[key] = "<image>"
            else:
                out[key] = _sanitize_response(child)
        return out
    if isinstance(value, list):
        return [_sanitize_response(item) for item in value]
    return value


def _as_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    if isinstance(value, list):
        return [_as_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _as_plain(child) for key, child in value.items()}
    return value


def _as_dict(value: Any) -> dict[str, Any]:
    plain = _as_plain(value)
    return plain if isinstance(plain, dict) else {}
