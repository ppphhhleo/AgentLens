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
    assert "bid" in parameters["properties"]
