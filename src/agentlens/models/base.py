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
    # Optional text block surfaced from out-of-band tools (web_search,
    # future shell/code tools). Persisted only for one observation —
    # the loop clears it after building this step's user message.
    tool_output_since_last_step: str | None = None


class ChatModel(Protocol):
    """Vision-capable chat model that emits ComputerActions for the ReAct loop."""

    def step(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> ModelStep: ...


def build_model(config: ModelConfig, toolset=None) -> ChatModel:
    """Construct a ChatModel from a ModelConfig.

    `toolset` is an agentlens.harnesses.tool_gating.ToolSet (kept untyped
    here to avoid an import cycle). Models use it to render the prompt's
    action schema so prompt advertising and runtime gating stay in sync.
    """
    if config.provider == "openai":
        from agentlens.models.openai_vision import OpenAIVisionModel

        return OpenAIVisionModel(config, toolset=toolset)

    raise ValueError(
        f"unsupported model provider '{config.provider}' for real screenshot ReAct loop "
        "(expected 'openai'); use provider='local' name='mock_screenshot_react' for mock runs"
    )
