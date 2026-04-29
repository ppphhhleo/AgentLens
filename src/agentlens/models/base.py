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
    """Per-step observation. Now mode-aware: any combination of
    `screenshot_path`, `axtree_text`, and `mark_registry` may be set.

    The model wrapper (`OpenAIVisionModel._build_messages`) reads which
    modalities are populated and constructs the prompt accordingly:
        - screenshot_path set    → include image
        - axtree_text   set    → append the AXTree text block
        - mark_registry set    → include the mark→bid count in prompt

    For backward compatibility the field name remains
    `ScreenshotObservation`; we add a `Observation` alias below.
    """

    step_index: int
    url: str
    viewport: dict[str, int]
    # Visual modality (optional now)
    screenshot_path: Path | None = None
    # AXTree modality (optional)
    axtree_text: str | None = None
    # Set-of-marks modality (optional): mapping mark_id → bid
    mark_registry: dict[str, str] | None = None
    # Out-of-band tool output (web_search / run_python / shell / files):
    tool_output_since_last_step: str | None = None


# Forward-compat alias — preferred name going forward.
Observation = ScreenshotObservation


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
