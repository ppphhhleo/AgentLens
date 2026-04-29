from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from agentlens.actions import ComputerAction
from agentlens.models.base import ModelStep, ScreenshotObservation
from agentlens.schemas import ModelConfig

# The action-schema bullet list is injected at runtime from the run's
# ToolSet, so the prompt only ever advertises tools the gate will accept.
SYSTEM_PROMPT_TEMPLATE = """You are an autonomous agent operating inside a web application. \
The application is already open and loaded in front of you. Navigate the interface to \
complete the task — do not ask the user for information that is available in the application.

Task: {goal}

You see one screenshot per step. Respond ONLY with a single JSON object:
{{
  "thought": "<short reasoning, 1-3 sentences>",
  "action": {{ ... one ComputerAction ... }}
}}

Action schema — pick EXACTLY ONE per step. ONLY these actions are available:
{action_schema}

Rules:
- Coordinates are viewport pixels from the top-left of the screenshot.
- For mouse actions, "keys" (optional) is a list of MODIFIERS held during the
  action: SHIFT, CTRL (or CONTROL), ALT, META (or CMD/COMMAND).
- For "keypress", "keys" is the list of keys to PRESS (e.g. ["Enter"], ["CTRL", "A"]).
- "scroll_x"/"scroll_y" may also be written "scrollX"/"scrollY".
- "drag.path" entries may be {{"x":.., "y":..}} objects or [x, y] arrays.
- When you can answer the task, emit final_answer immediately; do not over-explore.
- The "answer" field of final_answer is your ANSWER to the task.
- Never emit an action that is not in the schema above; it will be rejected.
- Never wrap the JSON in markdown fences.
"""


class OpenAIVisionModel:
    """OpenAI chat-completions vision model returning strict JSON actions."""

    def __init__(self, config: ModelConfig, toolset=None) -> None:
        self.config = config
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Put it in .env at the repo root or export it."
            )
        base_url = os.environ.get("OPENAI_BASE_URL")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = config.name
        self.temperature = config.temperature
        self.max_output_tokens = config.max_output_tokens or 1024
        # Lazy import to avoid cycles via models.base.build_model.
        from agentlens.harnesses.tool_gating import ToolSet, render_action_schema

        if toolset is None:
            toolset = ToolSet(allowed=frozenset())  # unrestricted
        self.toolset = toolset
        self.action_schema = render_action_schema(toolset)

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
            "response_format": {"type": "json_object"},
        }
        if self._uses_completion_tokens_param():
            kwargs["max_completion_tokens"] = self.max_output_tokens
        else:
            kwargs["max_tokens"] = self.max_output_tokens
            kwargs["temperature"] = self.temperature
        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        raw = choice.message.content or ""
        thought, action = self._parse_response(raw)

        usage = response.usage
        return ModelStep(
            thought=thought,
            action=action,
            raw_response=raw,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            extra={
                "model": response.model,
                "finish_reason": choice.finish_reason,
            },
        )

    def _build_messages(
        self,
        *,
        goal: str,
        observation: ScreenshotObservation,
        history: list[ModelStep],
    ) -> list[dict[str, Any]]:
        history_lines: list[str] = []
        for i, past in enumerate(history, start=1):
            history_lines.append(
                f"Step {i}: thought={past.thought!r} action={past.action.model_dump(mode='json')}"
            )
        history_block = "\n".join(history_lines) if history_lines else "(none)"

        tool_block = ""
        if observation.tool_output_since_last_step:
            tool_block = (
                f"\nTOOL OUTPUT FROM YOUR LAST ACTION (visible only this step):\n"
                f"{observation.tool_output_since_last_step}\n"
            )

        user_text = (
            f"Current URL: {observation.url}\n"
            f"Viewport: {observation.viewport}\n"
            f"Step index: {observation.step_index}\n"
            f"Prior steps:\n{history_block}\n"
            f"{tool_block}\n"
            "Inspect the screenshot (and tool output above, if any), then emit your next JSON action."
        )

        image_data_url = self._image_to_data_url(observation.screenshot_path)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            goal=goal, action_schema=self.action_schema
        )

        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ]

    def _uses_completion_tokens_param(self) -> bool:
        """gpt-5.x and o-series reject max_tokens + custom temperature."""
        name = self.model_name.lower()
        return name.startswith(("gpt-5", "o1", "o3", "o4"))

    @staticmethod
    def _image_to_data_url(path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _parse_response(raw: str) -> tuple[str, ComputerAction]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        # Use raw_decode so we tolerate trailing data (e.g. duplicate JSON object).
        decoder = json.JSONDecoder()
        try:
            data, _end = decoder.raw_decode(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"model response was not valid JSON: {exc}\nraw={raw!r}") from exc

        if not isinstance(data, dict) or "action" not in data:
            raise ValueError(f"model response missing 'action': {data!r}")

        thought = str(data.get("thought", "")).strip()
        action = ComputerAction.from_raw(data["action"])
        return thought, action
