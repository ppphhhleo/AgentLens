from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from agentlens.models.base import ModelStep, ScreenshotObservation
from agentlens.models.openai_tool_call import SYSTEM_PROMPT_TEMPLATE
from agentlens.schemas import ModelConfig
from agentlens.tools.registry import GeminiToolAdapter, default_tool_registry


class GeminiToolCallModel:
    """Gemini model using API-registered function tools."""

    def __init__(self, config: ModelConfig, toolset=None) -> None:
        self.config = config
        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
            or os.environ.get("google_ai_studio_api_key")
        )
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Put it in .env at the repo root or export it."
            )
        self.client = genai.Client(api_key=api_key)
        self.model_name = config.name
        self.temperature = config.temperature
        self.max_output_tokens = config.max_output_tokens or 1024
        self.input_modes = list((config.extra or {}).get("input_modes", ["screenshot"]))
        self.addressing_modes = list((config.extra or {}).get("addressing_modes", ["coordinate"]))
        self.parallel_tool_calls = bool((config.extra or {}).get("parallel_tool_calls", False))
        self.max_actions_per_round = max(1, int((config.extra or {}).get("max_actions_per_round", 1)))

        from agentlens.harnesses.tool_gating import ToolSet

        if toolset is None:
            toolset = ToolSet(allowed=frozenset())
        self.toolset = toolset
        self.registry = default_tool_registry()
        self.provider_adapter = GeminiToolAdapter(
            self.registry,
            addressing_modes=self.addressing_modes,
        )
        if toolset.is_unrestricted:
            self.tool_specs = self.registry.specs_for_tool_names([])
        else:
            self.tool_specs = self.registry.specs_for_tool_names(
                sorted(toolset.allowed),
                strict=True,
            )
        self.tools = self.provider_adapter.tool_payloads(self.tool_specs)
        if not self.tools:
            raise ValueError("Gemini tool-call backend has no available tools for this harness")

    def step(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> ModelStep:
        system_prompt, contents = self._build_contents(
            goal=goal,
            observation=observation,
            history=history,
        )
        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        )
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=self.tools,
                tool_config=tool_config,
                max_output_tokens=self.max_output_tokens,
                temperature=self.temperature,
            ),
        )
        decisions = self.provider_adapter.parse_decisions(response, model=self.model_name)
        action_groups = [self.registry.to_actions(decision) for decision in decisions]
        actions = [action for group in action_groups for action in group]
        primary = decisions[0]
        return ModelStep(
            thought=primary.reasoning,
            action=actions[0],
            actions=actions,
            raw_response=json.dumps([decision.to_record() for decision in decisions], ensure_ascii=False),
            prompt_tokens=primary.input_tokens,
            completion_tokens=primary.output_tokens,
            extra={
                "model": getattr(response, "model_version", self.model_name),
                "finish_reason": primary.finish_reason,
                "interaction_backend": "tool_call",
                "provider_tool_call": primary.to_record(),
                "provider_tool_calls": [decision.to_record() for decision in decisions],
                "provider_action_group_sizes": [len(group) for group in action_groups],
                "ordered_action_batch": any(
                    decision.tool_name == "computer.batch" for decision in decisions
                ),
                "parallel_tool_calls": self.parallel_tool_calls,
            },
        )

    def _build_contents(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> tuple[str, list[Any]]:
        history_lines = []
        for i, past in enumerate(history, start=1):
            action_parts = []
            provider_calls = (past.extra or {}).get("provider_tool_calls") or []
            if provider_calls:
                for j, provider_call in enumerate(provider_calls, start=1):
                    action_parts.append(
                        f"{j}. tool={provider_call.get('tool_name')!r} "
                        f"args={provider_call.get('tool_args') or {}}"
                    )
            else:
                for j, action in enumerate(past.action_list(), start=1):
                    action_json = action.model_dump(
                        mode="json",
                        exclude_none=True,
                        exclude_defaults=True,
                    )
                    action_parts.append(f"{j}. tool={action_json.get('type')!r} args={action_json}")
            history_lines.append(
                f"Round {i}: " + "; ".join(action_parts) + f" reasoning={past.thought!r}"
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
            action_policy=self._action_policy(),
        )
        parts: list[Any] = [user_text]
        if observation.screenshot_path is not None and "screenshot" in self.input_modes:
            parts.append(self._image_part(observation.screenshot_path))
        return system_prompt, parts

    def _context_description(self) -> str:
        modes = set(self.input_modes)
        if "screenshot" in modes and "axtree" in modes:
            return "You receive a screenshot and an interactive-element tree each step."
        if "screenshot" in modes or "set_of_marks" in modes:
            return "You receive a screenshot each step."
        if "axtree" in modes:
            return "You receive an interactive-element tree and tool outputs. No screenshot is provided."
        return "You receive textual context and tool outputs. No screenshot is provided."

    def _action_policy(self) -> str:
        batch_note = ""
        if "computer.batch" in self.toolset.allowed:
            batch_note = (
                " computer.batch may contain a short ordered sequence of direct-manipulation "
                "actions when no intermediate screenshot is needed."
            )
        if self.parallel_tool_calls and self.max_actions_per_round > 1:
            return (
                f"You may call up to {self.max_actions_per_round} tools in one step "
                "when they are a short, safe sequence that does not require inspecting "
                "intermediate results. Use one tool call when the next action depends on "
                f"what changes on screen.{batch_note}"
            )
        return f"Use exactly one registered tool call per step.{batch_note}"

    @staticmethod
    def _image_part(path: Path) -> types.Part:
        suffix = path.suffix.casefold()
        mime_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
