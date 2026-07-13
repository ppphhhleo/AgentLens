"""SimulatedFinalJudge — LLM-driven user actor for one-shot final-answer review.

Single intervention point: when the agent finishes (final_answer or
max_steps reached). Produces an `accept` or `reject` `UserAction` based
on the goal, the agent's answer, and the last few screenshots.

This is functionally similar to `validators/webjudge.py` but lives on
the *actor* axis, not the *validator* axis. The split matters because
extending to multi-turn dialogue / human user only changes the actor —
the validator is unchanged.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from agentlens.actors.base import UserAction, UserObservation
from agentlens.harnesses.tool_gating import (
    UserToolSet,
    render_user_action_schema,
    user_tool_name_for,
)
from agentlens.schemas import ModelConfig, UserActionType, UserHarnessConfig
from agentlens.openai_provider import build_openai_client

DEFAULT_MAX_SCREENSHOTS = 3
JUDGE_DEFAULT_PERSONA = (
    "You are a strict reviewer evaluating an autonomous agent's final answer. "
    "Be fair but not lenient: only ACCEPT if the answer is clearly correct AND "
    "supported by the screenshots. REJECT if the answer is wrong, unsupported, "
    "or the agent gave up without engaging with the task."
)


class SimulatedFinalJudge:
    def __init__(
        self,
        *,
        harness: UserHarnessConfig,
        judge_model: ModelConfig,
        max_screenshots: int = DEFAULT_MAX_SCREENSHOTS,
    ) -> None:
        self.harness = harness
        self.model = judge_model
        self.max_screenshots = max_screenshots
        self.toolset = UserToolSet.from_harness(harness)
        # Action schema in the prompt is dynamically rendered from the
        # harness's allowed user-actions; never advertises tools the
        # gate would reject.
        self.action_schema = render_user_action_schema(self.toolset)
        self._persona = harness.persona or JUDGE_DEFAULT_PERSONA

        self.client = build_openai_client(
            auth_mode=judge_model.auth_mode, model=judge_model.name
        )

    def observe(self, observation: UserObservation) -> UserAction:
        # If the agent never produced an answer, fall back to a hard reject
        # without burning a model call — that's the unambiguous signal.
        if observation.final_answer is None:
            return UserAction(
                type=UserActionType.REJECT,
                text="No final_answer was emitted by the agent.",
            )

        messages = self._build_messages(observation)
        kwargs: dict[str, Any] = {
            "model": self.model.name,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if self._uses_completion_tokens_param():
            kwargs["max_completion_tokens"] = self.model.max_output_tokens or 400
        else:
            kwargs["max_tokens"] = self.model.max_output_tokens or 400
            kwargs["temperature"] = self.model.temperature
        try:
            resp = self.client.chat.completions.create(**kwargs)
            raw = (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - judge errors must not crash run
            return UserAction(
                type=UserActionType.REJECT,
                text=f"judge call failed: {type(exc).__name__}: {exc}",
                extra={"judge_error": True},
            )

        action = self._parse_decision(raw)
        # Gate the parsed action against the harness's allow-list.
        if not self.toolset.is_allowed(action.type.value):
            # Force-coerce to no_intervention if the judge produced a
            # disallowed action; the orchestrator records this so the
            # gating leak is visible.
            return UserAction(
                type=UserActionType.NO_INTERVENTION,
                text=f"judge emitted disallowed action {action.type.value!r}",
                extra={"original": action.model_dump(mode="json")},
            )
        return action

    # ---- helpers ------------------------------------------------------

    def _build_messages(self, obs: UserObservation) -> list[dict[str, Any]]:
        system = (
            f"{self._persona}\n\n"
            "You will see the task, the agent's final answer, the agent's last\n"
            "screenshot(s), and a brief action history.\n\n"
            "Respond ONLY with a single JSON object:\n"
            '{ "type": "accept" | "reject" | "no_intervention",\n'
            '  "text": "<short reason grounded in the screenshots>" }\n\n'
            "Allowed action types in this run:\n"
            f"{self.action_schema}\n"
        )
        history_block = (
            "\n".join(f"- {a}" for a in obs.agent_action_summary)
            if obs.agent_action_summary
            else "(no actions recorded)"
        )
        user_text = (
            f"TASK:\n{obs.task_goal}\n\n"
            f"FINAL URL: {obs.final_url or '(not captured)'}\n\n"
            f"AGENT'S FINAL ANSWER:\n{obs.final_answer or '(no answer)'}\n\n"
            f"ACTION HISTORY (most recent {len(obs.agent_action_summary)} steps):\n"
            f"{history_block}\n\n"
            f"SCREENSHOTS: {len(self._sample_screenshots(obs))} key frames in order."
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for path in self._sample_screenshots(obs):
            content.append(
                {"type": "image_url", "image_url": {"url": _data_url(path)}}
            )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]

    def _sample_screenshots(self, obs: UserObservation) -> list[Path]:
        if not obs.screenshot_paths:
            return []
        if len(obs.screenshot_paths) <= self.max_screenshots:
            return list(obs.screenshot_paths)
        # take first + last + (cap-2) from the tail (last few frames are
        # what reflect the final state, where judgment usually lands).
        cap = self.max_screenshots
        head = obs.screenshot_paths[:1]
        tail = obs.screenshot_paths[-(cap - 1):] if cap > 1 else []
        chosen: list[Path] = []
        for p in head + tail:
            if p not in chosen:
                chosen.append(p)
        return chosen

    def _parse_decision(self, raw: str) -> UserAction:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        decoder = json.JSONDecoder()
        try:
            data, _ = decoder.raw_decode(text)
        except json.JSONDecodeError:
            return UserAction(
                type=UserActionType.NO_INTERVENTION,
                text=f"judge returned non-JSON: {raw[:160]!r}",
                extra={"judge_parse_error": True},
            )
        if not isinstance(data, dict):
            return UserAction(type=UserActionType.NO_INTERVENTION, text="non-dict response")

        atype_str = str(data.get("type", "")).lower().strip()
        try:
            atype = UserActionType(atype_str)
        except ValueError:
            return UserAction(
                type=UserActionType.NO_INTERVENTION,
                text=f"unknown user action type: {atype_str!r}",
            )
        text_val = data.get("text") or data.get("reason") or ""
        # accept/no_intervention don't strictly require text, but we record it
        return UserAction(
            type=atype,
            text=str(text_val) if text_val else None,
            extra={"tool_name": user_tool_name_for(atype.value)},
        )

    def _uses_completion_tokens_param(self) -> bool:
        name = self.model.name.lower()
        return name.startswith(("gpt-5", "o1", "o3", "o4"))


def _data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
