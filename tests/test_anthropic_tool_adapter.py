from __future__ import annotations

from types import SimpleNamespace

from agentlens.tools.registry import AnthropicToolAdapter, default_tool_registry


def test_anthropic_tool_payloads_use_provider_tool_names() -> None:
    registry = default_tool_registry()
    adapter = AnthropicToolAdapter(registry)

    payloads = adapter.tool_payloads([registry.get("browser.click")])

    assert payloads[0]["name"] == "browser__click"
    assert payloads[0]["input_schema"]["properties"]["reasoning"]["type"] == "string"


def test_anthropic_tool_use_response_maps_to_canonical_tool() -> None:
    registry = default_tool_registry()
    adapter = AnthropicToolAdapter(registry)
    adapter.tool_payloads([registry.get("browser.click"), registry.get("task.final_answer")])
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="I should click the filter."),
            SimpleNamespace(
                type="tool_use",
                name="browser__click",
                input={"x": 100, "y": 200, "reasoning": "Open the filter."},
            ),
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8),
        model_dump=lambda mode="json": {"id": "msg_test"},
    )

    decision = adapter.parse_decision(response, model="claude-test")

    assert decision.provider == "anthropic"
    assert decision.tool_name == "browser.click"
    assert decision.raw_provider_tool_name == "browser__click"
    assert decision.tool_args["x"] == 100
    assert decision.reasoning == "Open the filter."
    assert decision.input_tokens == 12
    assert decision.output_tokens == 8


def test_anthropic_right_click_alias_maps_to_desktop_click() -> None:
    registry = default_tool_registry()
    adapter = AnthropicToolAdapter(registry)
    adapter.tool_payloads([registry.get("desktop.click")])
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="I should open the context menu."),
            SimpleNamespace(
                type="tool_use",
                name="desktop__right_click",
                input={"x": "352, 107", "reasoning": "Open the context menu."},
            ),
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8),
        model_dump=lambda mode="json": {"id": "msg_right_click"},
    )

    decision = adapter.parse_decision(response, model="claude-test")
    action = registry.to_action(decision)

    assert decision.tool_name == "desktop.click"
    assert decision.raw_provider_tool_name == "desktop__right_click"
    assert decision.tool_args["button"] == "right"
    assert action.type == "desktop_click"
    assert action.button == "right"
    assert action.x == 352
    assert action.y == 107


def test_anthropic_text_response_can_fallback_to_final_answer() -> None:
    registry = default_tool_registry()
    adapter = AnthropicToolAdapter(registry)
    adapter.tool_payloads([registry.get("task.final_answer")])
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Mazda GLC")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=20, output_tokens=3),
        model_dump=lambda mode="json": {"id": "msg_final"},
    )

    decision = adapter.parse_decision(response, model="claude-test")

    assert decision.tool_name == "task.final_answer"
    assert decision.tool_args == {"answer": "Mazda GLC"}
