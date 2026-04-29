"""Turn-based Orchestrator — coordinates the agent and user actor across turns.

A "turn" is one full agent.run() (which itself is a multi-step screenshot
ReAct loop until final_answer or max_steps). Between turns, the user
actor observes the trajectory so far and may emit:

  - accept           → stop, success
  - reject           → stop, failure
  - send_message /
    request_clarification
                     → continue: feedback is added to the agent's
                       goal for the next turn

Capped by `max_turns`. After the final turn the user gets one last
observe() and any verdict is recorded (no continuation past the cap).

Single-turn modes (e.g. `simulated_final_judge` with max_turns=1) are
the degenerate case: agent runs once, user observes once, done.

The agent loop, model wrapper, and validator are all unchanged — this
is purely a wrapper that calls them in a loop.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from agentlens.actors.agent_actor import AgentActor, AgentObservation
from agentlens.actors.base import UserAction, UserActor, UserObservation
from agentlens.schemas import (
    TaskConfig,
    TrajectoryEvent,
    TrajectoryEventType,
    UserActionType,
    UserHarnessConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    """Result of a complete orchestrator run across turns."""

    final_answer: str | None
    events: list[TrajectoryEvent]
    turns_completed: int
    terminated_reason: str  # "user_accepted" | "user_rejected" | "no_intervention" | "max_turns"
    last_user_action: UserAction | None = None
    user_messages: list[str] = field(default_factory=list)


class TurnBasedOrchestrator:
    """Drives turn-taking between agent and user actor.

    Both `agent_actor` and `user_actor` implement the symmetric actor
    contract — orchestrator never reaches into Playwright, OpenAI, or
    any per-implementation specifics. Pluggable on both sides.
    """

    def __init__(
        self,
        *,
        agent_actor: AgentActor,
        user_actor: UserActor,
        user_harness: UserHarnessConfig,
        max_turns: int,
        log_action: Callable[[str], None] | None = None,
    ) -> None:
        self.agent_actor = agent_actor
        self.user_actor = user_actor
        self.user_harness = user_harness
        self.max_turns = max(1, max_turns)
        self.log_action = log_action

    def run(
        self,
        *,
        task: TaskConfig,
        per_turn_screenshot_dir_fn: Callable[[int], Path],
        run_id: str,
    ) -> TurnResult:
        all_events: list[TrajectoryEvent] = []
        user_messages: list[str] = []
        last_answer: str | None = None
        last_user_action: UserAction | None = None
        terminated_reason = "max_turns"

        # Initialize agent state once at the start of the run.
        # Subsequent turns thread the state forward.
        bootstrap_obs = AgentObservation(
            task_goal=task.goal or "",
            user_messages=list(user_messages),
            turn_index=0,
            max_turns=self.max_turns,
        )
        agent_state = self.agent_actor.get_init_state(observation=bootstrap_obs)

        for turn_idx in range(1, self.max_turns + 1):
            self._log(
                f"[{run_id}] turn {turn_idx}/{self.max_turns} starting"
                + (f" with {len(user_messages)} prior user message(s)" if user_messages else "")
            )

            # Mark the turn boundary in the cumulative event log.
            all_events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.SESSION_BOUNDARY,
                    step_index=len(all_events),
                    data={
                        "kind": "agent_turn_start",
                        "turn_index": turn_idx,
                        "max_turns": self.max_turns,
                        "user_messages_so_far": list(user_messages),  # snapshot, not ref
                    },
                )
            )

            # Run one agent turn via the AgentActor protocol.
            screenshot_dir = per_turn_screenshot_dir_fn(turn_idx)
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            agent_obs = AgentObservation(
                task_goal=task.goal or "",
                user_messages=list(user_messages),
                turn_index=turn_idx,
                max_turns=self.max_turns,
                extra={
                    "screenshot_dir": str(screenshot_dir),
                    "run_id": f"{run_id}.t{turn_idx}",
                },
            )
            agent_resp = self.agent_actor.act(observation=agent_obs, state=agent_state)
            answer = agent_resp.answer
            turn_events = agent_resp.events
            agent_state = agent_resp.state
            all_events.extend(turn_events)
            last_answer = answer

            # User observes the cumulative state.
            screenshot_paths: list[Path] = []
            for ev in all_events:
                if ev.event_type == TrajectoryEventType.SCREENSHOT:
                    screenshot_paths.extend(ev.artifact_paths)
            action_summary: list[str] = []
            for ev in all_events:
                if ev.event_type == TrajectoryEventType.MODEL_MESSAGE:
                    a = (ev.data.get("action") or {}).get("type", "?")
                    action_summary.append(f"step{ev.step_index}: {a}")

            obs = UserObservation(
                task_goal=task.goal or "",
                final_answer=answer,
                final_url=None,  # not tracked across turns at this level
                screenshot_paths=screenshot_paths,
                agent_action_summary=action_summary[-30:],
                extra={
                    "turn_index": turn_idx,
                    "max_turns": self.max_turns,
                    "prior_user_messages": list(user_messages),
                },
            )
            # When there's no real user harness (mode='none' / NoOpUser),
            # skip the user observe call AND the trajectory event so
            # backward-compat single-actor runs stay clean.
            if self.user_harness.mode == "none":
                terminated_reason = "no_user_harness"
                break

            user_action = self.user_actor.observe(obs)
            last_user_action = user_action

            self._log(
                f"[{run_id}] turn {turn_idx} user -> {user_action.type.value}"
                + (f": {(user_action.text or '')[:140]!r}" if user_action.text else "")
            )
            all_events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.USER_INTERVENTION,
                    step_index=len(all_events),
                    data={
                        "user_harness_id": self.user_harness.id,
                        "mode": self.user_harness.mode,
                        "turn_index": turn_idx,
                        "max_turns": self.max_turns,
                        "action": user_action.model_dump(mode="json"),
                        "combine_with_validator": self.user_harness.combine_with_validator,
                    },
                )
            )

            # Decide whether to continue.
            if user_action.type == UserActionType.ACCEPT:
                terminated_reason = "user_accepted"
                break
            if user_action.type == UserActionType.REJECT:
                terminated_reason = "user_rejected"
                break
            if user_action.type in (
                UserActionType.SEND_MESSAGE,
                UserActionType.REQUEST_CLARIFICATION,
            ):
                if user_action.text:
                    user_messages.append(user_action.text)
                # fall through to next turn
                continue
            # NO_INTERVENTION: stop without an explicit verdict.
            terminated_reason = "no_intervention"
            break
        else:
            # for/else: ran all turns without break. terminated_reason stays "max_turns".
            pass

        return TurnResult(
            final_answer=last_answer,
            events=all_events,
            turns_completed=turn_idx,  # noqa: B023 - last value in the for is what we want
            terminated_reason=terminated_reason,
            last_user_action=last_user_action,
            user_messages=user_messages,
        )

    def _log(self, msg: str) -> None:
        if self.log_action is not None:
            self.log_action(msg)


# NOTE: goal augmentation with cumulative user feedback now lives inside
# the AgentActor (see screenshot_react_agent._augment_goal_with_user_feedback).
# Each agent style controls its own prompt-construction. The orchestrator
# only forwards the user_messages list — agents decide how to use it.
