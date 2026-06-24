from __future__ import annotations

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
