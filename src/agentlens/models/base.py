from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from agentlens.actions import ComputerAction
from agentlens.schemas import ModelConfig


@dataclass
class ModelStep:
    """One model decision: thought + action + telemetry."""

    thought: str
    action: ComputerAction
    raw_response: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenshotObservation:
    step_index: int
    screenshot_path: Path
    url: str
    viewport: dict[str, int]


class ChatModel(Protocol):
    """Vision-capable chat model that emits ComputerActions for the ReAct loop."""

    def step(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> ModelStep: ...


def build_model(config: ModelConfig) -> ChatModel:
    """Construct a ChatModel from a ModelConfig."""
    if config.provider == "openai":
        from agentlens.models.openai_vision import OpenAIVisionModel

        return OpenAIVisionModel(config)

    raise ValueError(
        f"unsupported model provider '{config.provider}' for real screenshot ReAct loop "
        "(expected 'openai'); use provider='local' name='mock_screenshot_react' for mock runs"
    )
