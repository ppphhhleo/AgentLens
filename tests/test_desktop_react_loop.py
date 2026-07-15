from pathlib import Path
from types import SimpleNamespace

from agentlens.actions import ComputerAction
from agentlens.harnesses import desktop_react_loop
from agentlens.harnesses.tool_gating import ToolSet
from agentlens.models.base import ModelStep
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType


class _FakeModel:
    def __init__(self) -> None:
        self.observations = []

    def step(self, *, goal, observation, history):
        self.observations.append(observation)
        if len(self.observations) == 1:
            actions = [
                ComputerAction(type="desktop_move", x=100, y=200),
                ComputerAction(type="desktop_click", x=100, y=200),
            ]
            return ModelStep(
                thought="move and click",
                action=actions[0],
                actions=actions,
                extra={
                    "ordered_action_batch": True,
                    "provider_action_group_sizes": [2],
                    "provider_tool_calls": [
                        {
                            "tool_name": "computer.batch",
                            "tool_args": {
                                "actions": [
                                    {"type": "move", "x": 100, "y": 200},
                                    {"type": "left_click", "x": 100, "y": 200},
                                ]
                            },
                        }
                    ],
                },
            )
        return ModelStep(
            thought="done",
            action=ComputerAction(type="final_answer", answer="complete"),
        )


class _FakeSandbox:
    def __init__(self) -> None:
        self.commands = []

    def shell(self, command, timeout_sec=30):
        self.commands.append(command)
        return SimpleNamespace(ok=True, output=f"ran {len(self.commands)}", error="")


def test_ordered_batch_executes_all_actions_and_aggregates_results(monkeypatch, tmp_path) -> None:
    def fake_capture(_sandbox, screenshot_dir, step_index, _goal, **_kwargs):
        suffix = _kwargs.get("name_suffix")
        suffix = f"_{suffix}" if suffix else ""
        path = Path(screenshot_dir) / f"step_{step_index:03d}{suffix}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        return TrajectoryEvent(
            event_type=TrajectoryEventType.SCREENSHOT,
            step_index=step_index,
            artifact_paths=[path],
        )

    monkeypatch.setattr(
        desktop_react_loop,
        "capture_desktop_screenshot_event",
        fake_capture,
    )
    model = _FakeModel()
    sandbox = _FakeSandbox()

    answer, events = desktop_react_loop.run_desktop_react_loop(
        sandbox=sandbox,
        model=model,
        goal="test",
        max_steps=2,
        screenshot_dir=tmp_path,
        run_id="batch-test",
        toolset=ToolSet(allowed=frozenset({"computer.batch", "task.final_answer"})),
        max_actions_per_round=1,
    )

    assert answer == "complete"
    assert len(sandbox.commands) == 2
    assert "[desktop_move result]" in model.observations[1].tool_output_since_last_step
    assert "[desktop_click result]" in model.observations[1].tool_output_since_last_step

    tool_events = [event for event in events if event.event_type == TrajectoryEventType.TOOL_CALL]
    assert len(tool_events) == 2
    assert all(event.data["expanded_from_tool"] == "computer.batch" for event in tool_events)

    model_events = [
        event
        for event in events
        if event.event_type == TrajectoryEventType.MODEL_MESSAGE and "action" in event.data
    ]
    assert model_events[0].data["provider_action_group_sizes"] == [2]
    assert model_events[0].data["actions_in_round"] == 2

    screenshot_events = [
        event for event in events if event.event_type == TrajectoryEventType.SCREENSHOT
    ]
    assert screenshot_events[-1].step_index == 2
    assert screenshot_events[-1].data["terminal_state"] is True
    assert screenshot_events[-1].artifact_paths[0].name == "step_002_final.png"


def test_fresh_browser_profile_command_only_targets_browser_profile_paths() -> None:
    from agentlens.adapters.desktop_react import _fresh_browser_profile_command

    command = _fresh_browser_profile_command()

    assert "rm -rf" in command
    assert "/home/gem/.config/google-chrome" in command
    assert "/home/gem/.cache/google-chrome" in command
    assert "/home/gem/.config/chromium" in command
    assert "/home/gem/.cache/chromium" in command
    assert "install -d -o gem -g gem /home/gem/.config /home/gem/.cache" in command
