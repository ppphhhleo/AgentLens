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

SYSTEM_PROMPT_TEMPLATE = """You are an autonomous agent operating inside a web application. \
The application is already open and loaded in front of you. Navigate the interface to \
complete the task — do not ask the user for information that is available in the application.

Task: {goal}

You see one screenshot per step. Respond ONLY with a single JSON object:
{{
  "thought": "<short reasoning, 1-3 sentences>",
  "action": {{ ... one ComputerAction ... }}
}}

Action schema (pick exactly one per step):
- {{"type": "click", "x": int, "y": int, "button": "left"|"right"|"middle"}}
- {{"type": "double_click", "x": int, "y": int, "button": "left"}}
- {{"type": "scroll", "x": int, "y": int, "scroll_x": int, "scroll_y": int}}
- {{"type": "type", "text": "..."}}
- {{"type": "keypress", "keys": ["Enter"]}}
- {{"type": "wait", "ms": 1000}}
- {{"type": "move", "x": int, "y": int}}
- {{"type": "drag", "path": [{{"x": int, "y": int}}, ...]}}
- {{"type": "screenshot"}}
- {{"type": "final_answer", "answer": "..."}}

Rules:
- Coordinates are viewport pixels from the top-left of the screenshot.
- When you can answer the task, emit final_answer immediately; do not over-explore.
- The "answer" field of final_answer is your ANSWER to the task.
- Never wrap the JSON in markdown fences.
"""


class OpenAIVisionModel:
    """OpenAI chat-completions vision model returning strict JSON actions."""

    def __init__(self, config: ModelConfig) -> None:
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

        user_text = (
            f"Current URL: {observation.url}\n"
            f"Viewport: {observation.viewport}\n"
            f"Step index: {observation.step_index}\n"
            f"Prior steps:\n{history_block}\n\n"
            "Inspect the screenshot, then emit your next JSON action."
        )

        image_data_url = self._image_to_data_url(observation.screenshot_path)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(goal=goal)

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
