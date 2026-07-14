from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from agentlens.models.base import ModelStep, ScreenshotObservation
from agentlens.openai_provider import build_openai_client
from agentlens.schemas import ModelConfig
from agentlens.tools.registry import (
    OpenAIToolAdapter,
    default_tool_registry,
)


SYSTEM_PROMPT_TEMPLATE = """You are an autonomous agent operating inside a browser or sandboxed computer environment.
The application is already open and loaded. Complete the task using the available tools.

Task:
{goal}

{context_description}

{action_policy}
When you know the answer, call final_answer.
For final_answer, return only the exact answer requested: no explanation, no prefix, no markdown.
"""


class OpenAIToolCallModel:
    """OpenAI chat-completions model using API-registered tools.

    The prompt stays clean; tool availability is provided through the API tool
    registry and still gated by the runtime harness.
    """

    def __init__(self, config: ModelConfig, toolset=None) -> None:
        self.config = config
        self.client = build_openai_client(auth_mode=config.auth_mode, model=config.name)
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
        self.provider_adapter = OpenAIToolAdapter(
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
            raise ValueError("tool-call backend has no available tools for this harness")

    def step(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> ModelStep:
        messages = self._build_messages(goal=goal, observation=observation, history=history)
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "tools": self.tools,
            "tool_choice": "auto",
            "parallel_tool_calls": self.parallel_tool_calls,
        }
        if self._uses_completion_tokens_param():
            kwargs["max_completion_tokens"] = self.max_output_tokens
        else:
            kwargs["max_tokens"] = self.max_output_tokens
            kwargs["temperature"] = self.temperature

        response = self.client.chat.completions.create(**kwargs)
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
                "model": getattr(response, "model", self.model_name),
                "finish_reason": primary.finish_reason,
                "interaction_backend": "tool_call",
                "provider_tool_call": primary.to_record(),
                "provider_tool_calls": [decision.to_record() for decision in decisions],
                "provider_action_group_sizes": [len(group) for group in action_groups],
                "ordered_action_batch": any(
                    decision.tool_name == "computer.batch" for decision in decisions
                ),
                "parallel_tool_calls": self.parallel_tool_calls,
                "openai_provider_telemetry": getattr(
                    response, "agentlens_telemetry", {}
                ),
            },
        )

    def _build_messages(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> list[dict[str, Any]]:
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
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        if observation.screenshot_path is not None and "screenshot" in self.input_modes:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._image_to_data_url(observation.screenshot_path)},
                }
            )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

    def _uses_completion_tokens_param(self) -> bool:
        name = self.model_name.lower()
        return name.startswith(("gpt-5", "o1", "o3", "o4"))

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
    def _image_to_data_url(path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
