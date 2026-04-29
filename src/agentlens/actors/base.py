"""User actors — the user side of the agent/user dual control.

Today's MVP supports two modes (declared in `UserHarnessConfig.mode`):

- `none`                  : NoOpUser (never intervenes)
- `simulated_final_judge` : LLM-driven judge that observes the agent's
                            final_answer once and emits accept / reject

Future modes (deferred):
- `dialogue`              : multi-turn back-and-forth (G5)
- `checkpoint`            : mid-stream periodic intervention
- `human_cli` / `human_vnc`: real human (G1)

The `Orchestrator` layer (currently inlined in the screenshot_react
adapter; will be extracted later) calls `actor.observe(...)` after the
agent loop and records the decision as a USER_INTERVENTION trajectory
event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, model_validator

from agentlens.schemas import ModelConfig, UserActionType, UserHarnessConfig


class UserAction(BaseModel):
    """One user-side decision. Symmetric in spirit to ComputerAction
    but with a much simpler surface (no coordinates / paths / files)."""

    type: UserActionType
    text: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> UserAction:
        if self.type in {UserActionType.REJECT, UserActionType.SEND_MESSAGE,
                         UserActionType.REQUEST_CLARIFICATION} and not self.text:
            raise ValueError(f"user action '{self.type}' requires text")
        return self


@dataclass
class UserObservation:
    """What the user gets to look at after the agent stops."""

    task_goal: str
    final_answer: str | None
    final_url: str | None
    screenshot_paths: list[Path] = field(default_factory=list)
    agent_action_summary: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class UserActor(Protocol):
    """Observes the agent's run and may emit a UserAction."""

    def observe(self, observation: UserObservation) -> UserAction: ...


class NoOpUser:
    """Never intervenes — used when `user_harness=none` or mode='none'."""

    def observe(self, observation: UserObservation) -> UserAction:
        return UserAction(type=UserActionType.NO_INTERVENTION)


def build_user_actor(
    harness: UserHarnessConfig,
    *,
    judge_model: ModelConfig | None = None,
) -> UserActor:
    """Construct a UserActor from a UserHarnessConfig.

    `judge_model` is the resolved ModelConfig referenced by the harness
    (caller looks it up from the experiment's models list).
    """
    if harness.mode == "none":
        return NoOpUser()
    if harness.mode == "simulated_final_judge":
        if judge_model is None:
            raise ValueError(
                f"user harness '{harness.id}' mode='simulated_final_judge' requires "
                "a judge_model (set user_harness.model to a ModelConfig.id)"
            )
        from agentlens.actors.simulated_judge import SimulatedFinalJudge
        return SimulatedFinalJudge(harness=harness, judge_model=judge_model)
    if harness.mode == "simulated_dialogue":
        if judge_model is None:
            raise ValueError(
                f"user harness '{harness.id}' mode='simulated_dialogue' requires "
                "a model (set user_harness.model to a ModelConfig.id)"
            )
        from agentlens.actors.dialogue_user import SimulatedDialogueUser
        return SimulatedDialogueUser(harness=harness, judge_model=judge_model)
    raise ValueError(f"unsupported user harness mode: {harness.mode!r}")
