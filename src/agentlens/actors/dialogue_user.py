"""SimulatedDialogueUser — multi-turn LLM-driven user with persona + goal.

Unlike `SimulatedFinalJudge` (one-shot reviewer), this user actor:
- Has a persona, a goal, and (optionally) private info / constraints
- Is invoked between agent turns
- Can `accept` (done), `reject` (give up), `send_message` (continue
  with feedback), or `request_clarification` (ask the agent something)
- Maintains memory of what they've said across turns

The orchestrator (`TurnBasedOrchestrator`) calls `observe(...)` after
each agent turn and routes the resulting UserAction.
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

DEFAULT_PERSONA = (
    "You are a thoughtful user collaborating with an autonomous browser agent.\n"
    "You have a goal and may have hidden preferences/constraints.\n"
    "Steer the agent toward what you actually want via concise feedback."
)

# Choose 1 first frame + 2 most-recent frames per turn — the user mostly
# cares about what state the agent ended in.
DEFAULT_MAX_SCREENSHOTS = 3


class SimulatedDialogueUser:
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
        self.action_schema = render_user_action_schema(self.toolset)

        self._persona = harness.persona or DEFAULT_PERSONA
        extra = harness.extra or {}
        self._user_goal = str(extra.get("user_goal", "") or "")
        self._private_info = str(extra.get("private_info", "") or "")

        # Multi-turn memory of (turn_index, what_we_said).
        self._history: list[tuple[int, UserAction]] = []

        self.client = build_openai_client(
            auth_mode=judge_model.auth_mode, model=judge_model.name
        )

    def observe(self, observation: UserObservation) -> UserAction:
        turn_index = int(observation.extra.get("turn_index", 1))
        max_turns = int(observation.extra.get("max_turns", 1))
        is_last_turn = turn_index >= max_turns

        # If agent never produced an answer and this is not the last turn,
        # request clarification rather than failing.
        if observation.final_answer is None and not is_last_turn:
            ua = UserAction(
                type=UserActionType.SEND_MESSAGE,
                text=(
                    "You did not produce a final_answer. Please continue and "
                    "emit final_answer when you have one."
                ),
            )
            self._history.append((turn_index, ua))
            return ua

        messages = self._build_messages(observation, is_last_turn=is_last_turn)
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
        except Exception as exc:  # noqa: BLE001
            ua = UserAction(
                type=UserActionType.REJECT,
                text=f"user model failed: {type(exc).__name__}: {exc}",
                extra={"user_error": True},
            )
            self._history.append((turn_index, ua))
            return ua

        action = self._parse_decision(raw, is_last_turn=is_last_turn)

        # Gate against allow-list.
        if not self.toolset.is_allowed(action.type.value):
            action = UserAction(
                type=UserActionType.NO_INTERVENTION,
                text=f"user emitted disallowed action {action.type.value!r}",
                extra={"original": action.model_dump(mode="json")},
            )
        self._history.append((turn_index, action))
        return action

    # ---- helpers ------------------------------------------------------

    def _build_messages(
        self, obs: UserObservation, *, is_last_turn: bool
    ) -> list[dict[str, Any]]:
        sys_lines = [self._persona.strip()]
        if self._user_goal:
            sys_lines.append(f"YOUR GOAL: {self._user_goal}")
        if self._private_info:
            sys_lines.append(
                f"YOUR PRIVATE INFO (only reveal if needed): {self._private_info}"
            )
        sys_lines.append(
            "After observing the agent's progress, decide what to do next.\n"
            "On the LAST turn you should choose accept or reject (no further\n"
            "feedback will be processed)."
        )
        sys_lines.append(
            "Respond ONLY with a single JSON object:\n"
            '{"type": "<accept|reject|send_message|request_clarification|no_intervention>",\n'
            ' "text": "<short message — required for reject/send_message/request_clarification>"}\n'
            "Allowed action types in this run:\n"
            f"{self.action_schema}\n"
        )
        if is_last_turn:
            sys_lines.append(
                "THIS IS THE LAST TURN. Choose accept or reject; "
                "no follow-up will be processed."
            )

        history_block = self._render_history()
        action_block = (
            "\n".join(f"- {a}" for a in obs.agent_action_summary)
            if obs.agent_action_summary
            else "(no actions recorded)"
        )
        user_text = (
            f"AGENT'S TASK: {obs.task_goal}\n\n"
            f"YOUR CONVERSATION HISTORY (most recent first):\n{history_block}\n\n"
            f"AGENT'S CURRENT FINAL ANSWER (this turn):\n"
            f"{obs.final_answer or '(no answer this turn)'}\n\n"
            f"AGENT ACTION HISTORY (recent {len(obs.agent_action_summary)} steps):\n"
            f"{action_block}\n\n"
            f"SCREENSHOTS: {len(self._sample_screenshots(obs))} frames in order."
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for path in self._sample_screenshots(obs):
            content.append(
                {"type": "image_url", "image_url": {"url": _data_url(path)}}
            )
        return [
            {"role": "system", "content": "\n\n".join(sys_lines)},
            {"role": "user", "content": content},
        ]

    def _render_history(self) -> str:
        if not self._history:
            return "(no prior user messages)"
        lines = []
        for turn, ua in self._history:
            lines.append(
                f"  turn {turn}: {ua.type.value} — {(ua.text or '')[:160]}"
            )
        return "\n".join(lines)

    def _sample_screenshots(self, obs: UserObservation) -> list[Path]:
        if not obs.screenshot_paths:
            return []
        if len(obs.screenshot_paths) <= self.max_screenshots:
            return list(obs.screenshot_paths)
        cap = self.max_screenshots
        head = obs.screenshot_paths[:1]
        tail = obs.screenshot_paths[-(cap - 1):] if cap > 1 else []
        chosen: list[Path] = []
        for p in head + tail:
            if p not in chosen:
                chosen.append(p)
        return chosen

    def _parse_decision(self, raw: str, *, is_last_turn: bool) -> UserAction:
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
                text=f"user returned non-JSON: {raw[:160]!r}",
            )
        if not isinstance(data, dict):
            return UserAction(
                type=UserActionType.NO_INTERVENTION, text="non-dict response"
            )
        atype_str = str(data.get("type", "")).lower().strip()
        try:
            atype = UserActionType(atype_str)
        except ValueError:
            return UserAction(
                type=UserActionType.NO_INTERVENTION,
                text=f"unknown user action type: {atype_str!r}",
            )
        text_val = data.get("text") or data.get("reason") or ""
        action = UserAction(
            type=atype,
            text=str(text_val) if text_val else None,
            extra={"tool_name": user_tool_name_for(atype.value)},
        )
        # On the last turn, coerce non-terminal actions to a verdict.
        if is_last_turn and atype not in (
            UserActionType.ACCEPT,
            UserActionType.REJECT,
            UserActionType.NO_INTERVENTION,
        ):
            return UserAction(
                type=UserActionType.REJECT,
                text=(
                    f"final turn reached without verdict; coerced to reject. "
                    f"(original: {atype.value} — {action.text or ''})"
                ),
                extra={"coerced_from": atype.value},
            )
        return action

    def _uses_completion_tokens_param(self) -> bool:
        name = self.model.name.lower()
        return name.startswith(("gpt-5", "o1", "o3", "o4"))


def _data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
