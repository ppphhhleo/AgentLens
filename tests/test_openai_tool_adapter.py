from __future__ import annotations

from types import SimpleNamespace

from agentlens.actions import ComputerAction
from agentlens.models.base import ModelStep
from agentlens.tools.registry import OpenAIToolAdapter, default_tool_registry


def test_openai_tool_payload_strips_top_level_combinators() -> None:
    registry = default_tool_registry()
    adapter = OpenAIToolAdapter(registry)

    payload = adapter.tool_payloads([registry.get("browser.click")])[0]
    parameters = payload["function"]["parameters"]

    assert parameters["type"] == "object"
    assert "oneOf" not in parameters
    assert "reasoning" in parameters["properties"]
    assert "x" in parameters["properties"]
    assert "y" in parameters["properties"]
    assert "bid" not in parameters["properties"]
    assert "selector" not in parameters["properties"]
    assert "mark" not in parameters["properties"]
    assert parameters["required"] == ["x", "y"]


def test_openai_tool_payload_keeps_configured_target_modes() -> None:
    registry = default_tool_registry()
    adapter = OpenAIToolAdapter(registry, addressing_modes=["bid", "selector"])

    payload = adapter.tool_payloads([registry.get("browser.click")])[0]
    properties = payload["function"]["parameters"]["properties"]

    assert "x" not in properties
    assert "y" not in properties
    assert "bid" in properties
    assert "selector" in properties
    assert "mark" not in properties


def test_openai_adapter_parses_multiple_tool_calls() -> None:
    registry = default_tool_registry()
    adapter = OpenAIToolAdapter(registry)
    adapter.tool_payloads([registry.get("browser.click"), registry.get("browser.wait")])

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="browser__click",
                                arguments='{"x": 10, "y": 20, "reasoning": "click target"}',
                            )
                        ),
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="browser__wait",
                                arguments='{"ms": 500, "reasoning": "wait for UI"}',
                            )
                        ),
                    ],
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    )

    decisions = adapter.parse_decisions(response, model="test-model")

    assert [decision.tool_name for decision in decisions] == ["browser.click", "browser.wait"]
    assert decisions[0].tool_args["x"] == 10
    assert decisions[1].tool_args["ms"] == 500


def test_openai_adapter_maps_right_click_alias() -> None:
    registry = default_tool_registry()
    adapter = OpenAIToolAdapter(registry)
    adapter.tool_payloads([registry.get("desktop.click")])
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="desktop__right_click",
                                arguments='{"x": 10, "y": 20, "reasoning": "open menu"}',
                            )
                        ),
                    ],
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    )

    decision = adapter.parse_decision(response, model="test-model")
    action = registry.to_action(decision)

    assert decision.tool_name == "desktop.click"
    assert decision.tool_args["button"] == "right"
    assert action.type == "desktop_click"
    assert action.button == "right"


def test_model_step_action_list_defaults_to_primary_action() -> None:
    action = ComputerAction(type="wait", ms=100)
    assert ModelStep(thought="", action=action).action_list() == [action]


def test_computer_batch_expands_to_ordered_desktop_actions() -> None:
    registry = default_tool_registry()
    adapter = OpenAIToolAdapter(registry)
    payload = adapter.tool_payloads([registry.get("computer.batch")])[0]

    assert payload["function"]["name"] == "computer__batch"
    assert payload["function"]["parameters"]["properties"]["actions"]["maxItems"] == 20

    decision = SimpleNamespace(
        tool_name="computer.batch",
        tool_args={
            "actions": [
                {"type": "move", "x": 100, "y": 200},
                {"type": "left_click", "x": 100, "y": 200},
                {"type": "type", "text": "hello"},
                {"type": "keypress", "keys": ["CTRL", "S"]},
            ]
        },
    )

    actions = registry.to_actions(decision)

    assert [action.type for action in actions] == [
        "desktop_move",
        "desktop_click",
        "desktop_type",
        "desktop_keypress",
    ]
    assert actions[1].button == "left"
    assert actions[2].text == "hello"


def test_computer_batch_maps_native_scroll_aliases() -> None:
    registry = default_tool_registry()
    decision = SimpleNamespace(
        tool_name="computer.batch",
        tool_args={"actions": [{"type": "scroll", "x": 20, "y": 30, "deltaY": 450}]},
    )

    action = registry.to_actions(decision)[0]

    assert action.type == "desktop_scroll"
    assert action.scroll_y == 450
