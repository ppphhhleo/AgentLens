from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import anthropic

from agentlens.models.base import ModelStep, ScreenshotObservation
from agentlens.models.openai_tool_call import SYSTEM_PROMPT_TEMPLATE
from agentlens.schemas import ModelConfig
from agentlens.tools.registry import (
    AnthropicToolAdapter,
    default_tool_registry,
)


class AnthropicToolCallModel:
    """Claude Messages API model using API-registered client tools."""

    def __init__(self, config: ModelConfig, toolset=None) -> None:
        self.config = config
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Put it in .env at the repo root or export it."
            )
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if os.environ.get("ANTHROPIC_BASE_URL"):
            client_kwargs["base_url"] = os.environ["ANTHROPIC_BASE_URL"]
        self.client = anthropic.Anthropic(**client_kwargs)
        self.model_name = config.name
        self.temperature = config.temperature
        self.max_output_tokens = config.max_output_tokens or 1024
        self.input_modes = list((config.extra or {}).get("input_modes", ["screenshot"]))

        from agentlens.harnesses.tool_gating import ToolSet

        if toolset is None:
            toolset = ToolSet(allowed=frozenset())
        self.toolset = toolset
        self.registry = default_tool_registry()
        self.provider_adapter = AnthropicToolAdapter(self.registry)
        if toolset.is_unrestricted:
            self.tool_specs = self.registry.specs_for_tool_names([])
        else:
            self.tool_specs = self.registry.specs_for_tool_names(
                sorted(toolset.allowed),
                strict=True,
            )
        self.tools = self.provider_adapter.tool_payloads(self.tool_specs)
        if not self.tools:
            raise ValueError("Claude tool-call backend has no available tools for this harness")

    def step(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> ModelStep:
        system_prompt, messages = self._build_messages(
            goal=goal,
            observation=observation,
            history=history,
        )
        response = self.client.messages.create(
            model=self.model_name,
            system=system_prompt,
            messages=messages,
            tools=self.tools,
            tool_choice={"type": "auto"},
            max_tokens=self.max_output_tokens,
            temperature=self.temperature,
        )
        decision = self.provider_adapter.parse_decision(response, model=self.model_name)
        action = self.registry.to_action(decision)
        return ModelStep(
            thought=decision.reasoning,
            action=action,
            raw_response=json.dumps(decision.to_record(), ensure_ascii=False),
            prompt_tokens=decision.input_tokens,
            completion_tokens=decision.output_tokens,
            extra={
                "model": getattr(response, "model", self.model_name),
                "finish_reason": decision.finish_reason,
                "interaction_backend": "tool_call",
                "provider_tool_call": decision.to_record(),
            },
        )

    def _build_messages(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> tuple[str, list[dict[str, Any]]]:
        history_lines = []
        for i, past in enumerate(history, start=1):
            action_json = past.action.model_dump(
                mode="json",
                exclude_none=True,
                exclude_defaults=True,
            )
            provider_call = (past.extra or {}).get("provider_tool_call") or {}
            tool_name = provider_call.get("tool_name") or action_json.get("type")
            history_lines.append(
                f"Step {i}: tool={tool_name!r} args={action_json} reasoning={past.thought!r}"
            )
        history_block = "\n".join(history_lines) if history_lines else "(none)"

        tool_block = ""
        if observation.tool_output_since_last_step:
            tool_block = (
                "\nTool output from your previous action:\n"
                f"{observation.tool_output_since_last_step}\n"
            )

        axtree_block = ""
        if observation.axtree_text:
            axtree_block = (
                "\nInteractive-element tree. Use bid values when helpful:\n"
                f"{observation.axtree_text}\n"
            )

        mark_block = ""
        if observation.mark_registry:
            sample = ", ".join(list(observation.mark_registry.keys())[:8])
            mark_block = (
                f"\nSet-of-marks labels visible in the screenshot: {sample}. "
                "Use mark labels when helpful.\n"
            )

        step_budget = ""
        if observation.max_steps is not None:
            step_budget = (
                f"Step {observation.step_index}. "
                "Continue until the task is complete, then call final_answer.\n"
            )

        modality_note = ""
        if observation.screenshot_path is None and observation.axtree_text:
            modality_note = "No screenshot is provided this step; operate from the element tree and tool output.\n"
        elif observation.screenshot_path is not None and observation.axtree_text:
            modality_note = "A screenshot and element tree are both provided; prefer bid for reliable element targeting.\n"

        user_text = (
            f"Current URL: {observation.url}\n"
            f"Viewport: {observation.viewport}\n"
            f"{step_budget}"
            f"Prior tool calls:\n{history_block}\n"
            f"{axtree_block}"
            f"{mark_block}"
            f"{tool_block}"
            f"{modality_note}"
            "\nInspect the current context and choose the next tool call."
        )

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            goal=goal,
            context_description=self._context_description(),
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        if observation.screenshot_path is not None and "screenshot" in self.input_modes:
            content.append(self._image_block(observation.screenshot_path))
        return system_prompt, [{"role": "user", "content": content}]

    def _context_description(self) -> str:
        modes = set(self.input_modes)
        if "screenshot" in modes and "axtree" in modes:
            return "You receive a screenshot and an interactive-element tree each step."
        if "screenshot" in modes or "set_of_marks" in modes:
            return "You receive a screenshot each step."
        if "axtree" in modes:
            return "You receive an interactive-element tree and tool outputs. No screenshot is provided."
        return "You receive textual context and tool outputs. No screenshot is provided."

    @staticmethod
    def _image_block(path: Path) -> dict[str, Any]:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        suffix = path.suffix.casefold()
        media_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        }
