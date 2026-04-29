"""ScreenshotReactAgent + MockAgent — concrete AgentActor implementations.

Both wrap the existing screenshot ReAct loop without modifying it. The
agent owns no Playwright resources directly; the adapter passes the
page / sandbox / log_action callable in at construction.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agentlens.actions import ComputerAction
from agentlens.actors.agent_actor import (
    AgentObservation,
    AgentResponse,
    AgentState,
)
from agentlens.harnesses.browser_actions import (
    capture_screenshot_event,
    execute_action,
    format_action,
)
from agentlens.harnesses.screenshot_react_loop import run_screenshot_react_loop
from agentlens.harnesses.tool_gating import ToolSet, tool_name_for
from agentlens.models.base import build_model
from agentlens.schemas import (
    ModelConfig,
    TrajectoryEvent,
    TrajectoryEventType,
)


def _augment_goal_with_user_feedback(goal: str, user_messages: list[str]) -> str:
    """Append cumulative user feedback to the agent's goal.

    Mirrors what the prior `_augment_goal` in turns.py did, kept here so
    the AgentActor owns its own prompt-construction logic and the
    orchestrator stays generic.
    """
    if not user_messages:
        return goal
    feedback_block = "\n".join(f"- (user feedback) {m}" for m in user_messages)
    sep = "" if goal.endswith("\n") else "\n"
    return (
        f"{goal}{sep}\n"
        "USER FEEDBACK FROM PRIOR TURNS — you MUST address these:\n"
        f"{feedback_block}\n"
    )


class ScreenshotReactAgent:
    """AgentActor implementation that drives the screenshot ReAct loop.

    Resources (Playwright page, optional AIO Sandbox session, screenshot
    directory, model wrapper) are passed at construction. The agent
    re-uses them across turns — the orchestrator just calls `.act()`.
    """

    def __init__(
        self,
        *,
        model_config: ModelConfig,
        toolset: ToolSet,
        page,
        sandbox=None,
        max_steps: int = 12,
        log_action: Callable[[str], None] | None = None,
    ) -> None:
        self.model_config = model_config
        self.toolset = toolset
        self.model = build_model(model_config, toolset=toolset)
        self.page = page
        self.sandbox = sandbox
        self.max_steps = max_steps
        self.log_action = log_action

    def get_init_state(self, *, observation: AgentObservation) -> AgentState:
        return AgentState(
            cumulative_user_messages=list(observation.user_messages),
            history=[],
        )

    def act(
        self,
        *,
        observation: AgentObservation,
        state: AgentState,
    ) -> AgentResponse:
        screenshot_dir = Path(observation.extra.get("screenshot_dir", "screenshots"))
        run_id = str(observation.extra.get("run_id", "agent"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        goal = _augment_goal_with_user_feedback(
            observation.task_goal, observation.user_messages
        )
        answer, events = run_screenshot_react_loop(
            page=self.page,
            model=self.model,
            goal=goal,
            max_steps=self.max_steps,
            screenshot_dir=screenshot_dir,
            run_id=run_id,
            toolset=self.toolset,
            sandbox=self.sandbox,
            log_action=self.log_action,
        )
        new_state = state.model_copy(
            update={"cumulative_user_messages": list(observation.user_messages)}
        )
        return AgentResponse(answer=answer, events=events, state=new_state)


class MockAgent:
    """Replays `task.extra.mock_actions` in order.

    Used by smoke configs (no real model). Same AgentActor interface so
    the orchestrator/adapter doesn't need a special path for mocks.
    """

    def __init__(
        self,
        *,
        mock_actions: list[Any],
        mock_answer_fallback: str,
        page,
        toolset: ToolSet,
        log_action: Callable[[str], None] | None = None,
    ) -> None:
        self.mock_actions = mock_actions
        self.mock_answer_fallback = mock_answer_fallback
        self.page = page
        self.toolset = toolset
        self.log_action = log_action

    def get_init_state(self, *, observation: AgentObservation) -> AgentState:
        return AgentState(
            cumulative_user_messages=list(observation.user_messages),
            history=[],
        )

    def act(
        self,
        *,
        observation: AgentObservation,
        state: AgentState,
    ) -> AgentResponse:
        screenshot_dir = Path(observation.extra.get("screenshot_dir", "screenshots"))
        run_id = str(observation.extra.get("run_id", "mock"))
        task_goal = observation.task_goal
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        events: list[TrajectoryEvent] = [
            capture_screenshot_event(
                page=self.page,
                screenshot_dir=screenshot_dir,
                step_index=0,
                goal=task_goal,
            )
        ]
        answer: str | None = None
        for step_index, raw in enumerate(self.mock_actions, start=1):
            action = ComputerAction.from_raw(raw)
            self._log(f"[{run_id} step={step_index}] {format_action(action)}")
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.MODEL_MESSAGE,
                    step_index=step_index,
                    data={
                        "thought": f"Mock model requests '{action.type}'.",
                        "action": action.model_dump(mode="json"),
                        "tool_name": tool_name_for(action),
                        "mock": True,
                    },
                )
            )
            allowed, gating_msg = self.toolset.gate_action(action)
            if not allowed:
                self._log(f"[{run_id} step={step_index}] gating: {gating_msg}")
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.GATING_VIOLATION,
                        step_index=step_index,
                        data={
                            "action": action.model_dump(mode="json"),
                            "tool_name": tool_name_for(action),
                            "message": gating_msg,
                        },
                    )
                )
                continue
            if action.type == "final_answer":
                answer = action.answer
                break
            err = execute_action(self.page, action)
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.BROWSER_ACTION,
                    step_index=step_index,
                    data={"action": action.model_dump(mode="json"), "error": err},
                )
            )
            events.append(
                capture_screenshot_event(
                    page=self.page,
                    screenshot_dir=screenshot_dir,
                    step_index=step_index,
                    goal=task_goal,
                )
            )

        # Fallback: if no final_answer, surface the configured mock_answer.
        if answer is None:
            answer = self.mock_answer_fallback
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.MODEL_MESSAGE,
                    step_index=len(events),
                    data={
                        "thought": "Mock model returned fallback final answer.",
                        "action": {"type": "final_answer", "answer": answer},
                        "mock": True,
                    },
                )
            )

        new_state = state.model_copy(
            update={"cumulative_user_messages": list(observation.user_messages)}
        )
        return AgentResponse(answer=answer, events=events, state=new_state)

    def _log(self, msg: str) -> None:
        if self.log_action is not None:
            self.log_action(msg)
