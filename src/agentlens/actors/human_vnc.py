"""HumanVNCActor — replaces the LLM agent with a real human via VNC.

The human sees a Chromium browser via noVNC (or native VNC) and
directly interacts with the page. A JavaScript event recorder
(human_event_recorder.js) injected into the page captures every
click, scroll, keystroke, and navigation event.

When the human clicks "Submit Answer & Finish" in the overlay, the
actor collects all recorded events, converts them to TrajectoryEvent
objects, and returns via the AgentActor protocol — making the human
trajectory directly comparable to any LLM agent trajectory.

Usage::

    agentlens human-run configs/experiments/domsteer_human.yaml \\
        --task-id tf_discretize_toggle

The human connects via noVNC at http://localhost:6080/vnc.html
(forwarded via SSH tunnel from EC2).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from agentlens.actions import ComputerAction
from agentlens.actors.agent_actor import (
    AgentObservation,
    AgentResponse,
    AgentState,
)
from agentlens.harnesses.browser_actions import capture_screenshot_event
from agentlens.harnesses.tool_gating import ToolSet
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType

logger = logging.getLogger(__name__)

# Load the JS event recorder source once at import time.
_JS_RECORDER_PATH = Path(__file__).resolve().parent.parent / "harnesses" / "human_event_recorder.js"


def _load_recorder_js() -> str:
    return _JS_RECORDER_PATH.read_text(encoding="utf-8")


class HumanVNCAgent:
    """AgentActor that delegates control to a human via VNC.

    The human interacts with the browser through the Xvfb display.
    This actor monitors the page for the human's "done" signal
    (set by the injected JS overlay) and periodically captures
    screenshots for the trajectory record.
    """

    def __init__(
        self,
        *,
        page: Any,
        toolset: ToolSet,
        max_steps: int = 100,
        screenshot_interval_sec: float = 5.0,
        poll_interval_sec: float = 1.0,
        timeout_sec: float = 600.0,
        log_action: Callable[[str], None] | None = None,
    ) -> None:
        self.page = page
        self.toolset = toolset
        self.max_steps = max_steps
        self.screenshot_interval_sec = screenshot_interval_sec
        self.poll_interval_sec = poll_interval_sec
        self.timeout_sec = timeout_sec
        self.log_action = log_action

    def get_init_state(self, *, observation: AgentObservation) -> AgentState:
        return AgentState(
            cumulative_user_messages=list(observation.user_messages),
        )

    def act(
        self,
        *,
        observation: AgentObservation,
        state: AgentState,
    ) -> AgentResponse:
        """Wait for the human to complete the task and collect their trajectory."""
        events: list[TrajectoryEvent] = []
        screenshot_dir = Path(observation.extra.get("screenshot_dir", "/tmp/screenshots"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        run_id = observation.extra.get("run_id", "human")

        # Inject the event recorder JS into the page
        recorder_js = _load_recorder_js()
        self.page.evaluate(recorder_js)
        self._log(f"[{run_id}] Human session started — waiting for interaction via VNC")
        self._log(f"[{run_id}] Connect to noVNC at http://localhost:6080/vnc.html")
        self._log(f"[{run_id}] Complete the task and click 'Submit Answer & Finish' in the overlay")

        # Take initial screenshot
        step_index = 0
        events.append(
            capture_screenshot_event(
                self.page, screenshot_dir, step_index, observation.task_goal
            )
        )
        self._log(
            f"[{run_id} step={step_index}] screenshot -> "
            f"{screenshot_dir / f'step_{step_index:03d}.png'}"
        )

        # Poll for completion
        start_time = time.monotonic()
        last_screenshot_time = start_time
        last_event_count = 0

        while True:
            elapsed = time.monotonic() - start_time

            # Check timeout
            if elapsed > self.timeout_sec:
                self._log(f"[{run_id}] Timeout after {self.timeout_sec}s")
                break

            # Check if human clicked "Submit"
            done = self.page.evaluate("window.__agentlens_human_done || false")
            if done:
                self._log(f"[{run_id}] Human submitted answer")
                break

            # Check for new events and capture periodic screenshots
            current_event_count = self.page.evaluate(
                "(window.__agentlens_human_events || []).length"
            )
            time_since_screenshot = time.monotonic() - last_screenshot_time

            if (
                current_event_count > last_event_count
                or time_since_screenshot >= self.screenshot_interval_sec
            ):
                step_index += 1
                events.append(
                    capture_screenshot_event(
                        self.page, screenshot_dir, step_index, observation.task_goal
                    )
                )
                if current_event_count > last_event_count:
                    self._log(
                        f"[{run_id} step={step_index}] screenshot "
                        f"(+{current_event_count - last_event_count} human actions)"
                    )
                last_screenshot_time = time.monotonic()
                last_event_count = current_event_count

            time.sleep(self.poll_interval_sec)

        # Collect all recorded events from the browser
        raw_events = self.page.evaluate("window.__agentlens_human_events || []")
        answer = self.page.evaluate("window.__agentlens_human_answer")

        # Take final screenshot
        step_index += 1
        events.append(
            capture_screenshot_event(
                self.page, screenshot_dir, step_index, observation.task_goal
            )
        )

        # Convert JS events to trajectory events
        for raw_event in raw_events:
            event_type = raw_event.get("type", "unknown")

            if event_type in ("click", "double_click"):
                # Create a browser action event for each click
                action = ComputerAction(
                    type=event_type,
                    x=raw_event.get("x"),
                    y=raw_event.get("y"),
                    button=raw_event.get("button", "left"),
                )
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.BROWSER_ACTION,
                        step_index=step_index,
                        data={
                            "source": "human",
                            "action": action.model_dump(mode="json"),
                            "timestamp": raw_event.get("timestamp"),
                            "elapsed_ms": raw_event.get("elapsed_ms"),
                            "target": {
                                "tag": raw_event.get("target_tag", ""),
                                "id": raw_event.get("target_id", ""),
                                "class": raw_event.get("target_class", ""),
                                "text": raw_event.get("target_text", ""),
                            },
                            "url": raw_event.get("url", ""),
                        },
                    )
                )
            elif event_type == "scroll":
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.BROWSER_ACTION,
                        step_index=step_index,
                        data={
                            "source": "human",
                            "action": {
                                "type": "scroll",
                                "scroll_x": raw_event.get("scroll_x", 0),
                                "scroll_y": raw_event.get("scroll_y", 0),
                            },
                            "timestamp": raw_event.get("timestamp"),
                            "elapsed_ms": raw_event.get("elapsed_ms"),
                            "url": raw_event.get("url", ""),
                        },
                    )
                )
            elif event_type == "type":
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.BROWSER_ACTION,
                        step_index=step_index,
                        data={
                            "source": "human",
                            "action": {
                                "type": "type",
                                "text": raw_event.get("text", ""),
                            },
                            "timestamp": raw_event.get("timestamp"),
                            "elapsed_ms": raw_event.get("elapsed_ms"),
                            "target": {
                                "tag": raw_event.get("target_tag", ""),
                                "id": raw_event.get("target_id", ""),
                                "name": raw_event.get("target_name", ""),
                            },
                            "url": raw_event.get("url", ""),
                        },
                    )
                )
            elif event_type == "keypress":
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.BROWSER_ACTION,
                        step_index=step_index,
                        data={
                            "source": "human",
                            "action": {
                                "type": "keypress",
                                "key": raw_event.get("key", ""),
                                "code": raw_event.get("code", ""),
                            },
                            "timestamp": raw_event.get("timestamp"),
                            "elapsed_ms": raw_event.get("elapsed_ms"),
                            "url": raw_event.get("url", ""),
                        },
                    )
                )
            elif event_type == "navigation":
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.BROWSER_ACTION,
                        step_index=step_index,
                        data={
                            "source": "human",
                            "action": {
                                "type": "goto",
                                "from_url": raw_event.get("from_url", ""),
                                "to_url": raw_event.get("to_url", ""),
                            },
                            "timestamp": raw_event.get("timestamp"),
                            "elapsed_ms": raw_event.get("elapsed_ms"),
                        },
                    )
                )
            elif event_type == "final_answer":
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.MODEL_MESSAGE,
                        step_index=step_index,
                        data={
                            "source": "human",
                            "thought": "Human submitted final answer via overlay",
                            "action": {
                                "type": "final_answer",
                                "answer": raw_event.get("answer", ""),
                            },
                            "tool_name": "task.final_answer",
                            "mock": False,
                        },
                    )
                )

        total_human_actions = len(raw_events)
        self._log(
            f"[{run_id}] Human session completed: "
            f"{total_human_actions} actions recorded, "
            f"answer={'yes' if answer else 'no'}"
        )

        return AgentResponse(
            answer=answer,
            events=events,
            state=AgentState(
                cumulative_user_messages=state.cumulative_user_messages,
                extra={
                    "human_actions_count": total_human_actions,
                    "raw_human_events": raw_events,
                },
            ),
        )

    def _log(self, msg: str) -> None:
        if self.log_action is not None:
            self.log_action(msg)
        logger.info(msg)
