"""Opt-in end-to-end smoke test for the reference-derived Codex OAuth backend.

Run for human inspection (this spends model quota):

    AGENTLENS_LIVE_CODEX_OAUTH=1 \
    AGENTLENS_OPENAI_AUTH_MODE=codex_oauth \
    AGENTLENS_CODEX_MODEL=<exact-model-id> \
      .venv/bin/pytest -s tests/test_codex_oauth_live.py

The test reuses ``codex login`` credentials. It intentionally checks that
built-in OpenAI web search is rejected: that native tool is not supported by
the ChatGPT Codex endpoint and must never fall back to ``OPENAI_API_KEY``.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import pytest

from agentlens.openai_provider import build_openai_client, resolve_helper_model
from agentlens.tools.openai_search import openai_web_search


# Use a real, tracked RGB screenshot. Some vision backends reject 1x1 images
# even when the PNG itself is valid, so a pixel fixture is not a useful smoke test.
VISION_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "examples/results/gpt54_datavoyager_smoke/trajectories/browser/screenshots/step_000.png"
)


def _vision_data_url() -> str:
    return "data:image/png;base64," + base64.b64encode(VISION_FIXTURE.read_bytes()).decode()


def _usage(response: Any) -> dict[str, int | None]:
    usage = response.usage
    return {
        "input": usage.prompt_tokens,
        "output": usage.completion_tokens,
        "total": usage.total_tokens,
    }


def _show(label: str, response: Any) -> None:
    choice = response.choices[0]
    calls = choice.message.tool_calls or []
    printable = {
        "model": response.model,
        "finish_reason": choice.finish_reason,
        "text": choice.message.content,
        "tool_calls": [
            {
                "id": call.id,
                "name": call.function.name,
                "arguments": call.function.arguments,
            }
            for call in calls
        ],
        "usage": _usage(response),
        "telemetry": response.agentlens_telemetry,
    }
    print(f"\n===== {label} =====")
    print(json.dumps(printable, indent=2, ensure_ascii=False))


@pytest.mark.skipif(
    os.environ.get("AGENTLENS_LIVE_CODEX_OAUTH") != "1",
    reason="set AGENTLENS_LIVE_CODEX_OAUTH=1 to spend quota on the Codex OAuth smoke test",
)
def test_live_codex_oauth_full_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise every supported adapter surface and print results for review."""
    monkeypatch.setenv("AGENTLENS_OPENAI_AUTH_MODE", "codex_oauth")
    model = resolve_helper_model(None)
    client = build_openai_client(auth_mode="codex_oauth", model=model)

    text_response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Answer concisely."},
            {"role": "user", "content": "Reply with exactly: codex oauth text ok"},
        ],
        temperature=0,
        max_completion_tokens=40,
    )
    _show("TEXT", text_response)
    assert "codex oauth text ok" in (text_response.choices[0].message.content or "").lower()
    assert text_response.usage.total_tokens is not None
    assert set(text_response.agentlens_telemetry["omitted_unsupported_parameters"]) == {
        "temperature",
        "max_completion_tokens",
    }

    image_response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Confirm the screenshot loaded and name one visible UI element.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": _vision_data_url(), "detail": "auto"},
                },
            ],
        }],
    )
    _show("IMAGE", image_response)
    assert image_response.choices[0].message.content

    json_response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": 'Return a JSON object with keys "ok" (true) and "mode" ("codex_oauth").',
        }],
        response_format={"type": "json_object"},
    )
    _show("JSON", json_response)
    parsed = json.loads(json_response.choices[0].message.content)
    assert parsed == {"ok": True, "mode": "codex_oauth"}

    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_weather",
                "description": "Look up weather for one city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lookup_time",
                "description": "Look up local time for one city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    ]
    tool_response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": (
                "Call both lookup_weather and lookup_time for Chicago now. "
                "Make both independent calls in parallel and do not answer from memory."
            ),
        }],
        tools=tools,
        tool_choice="required",
        parallel_tool_calls=True,
    )
    _show("PARALLEL TOOL CALLS", tool_response)
    calls = tool_response.choices[0].message.tool_calls or []
    assert {call.function.name for call in calls} == {"lookup_weather", "lookup_time"}
    for call in calls:
        json.loads(call.function.arguments)

    assistant_calls = [
        {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.function.name,
                "arguments": call.function.arguments,
            },
        }
        for call in calls
    ]
    outputs = {
        "lookup_weather": '{"temperature_f": 72, "conditions": "clear"}',
        "lookup_time": '{"local_time": "12:34 PM", "timezone": "America/Chicago"}',
    }
    followup_messages: list[dict[str, Any]] = [
        {"role": "user", "content": "Get Chicago weather and local time."},
        {"role": "assistant", "content": None, "tool_calls": assistant_calls},
    ]
    followup_messages.extend(
        {
            "role": "tool",
            "tool_call_id": call.id,
            "content": outputs[call.function.name],
        }
        for call in calls
    )
    followup_messages.append({
        "role": "user",
        "content": "Summarize both tool results in one sentence and make no more tool calls.",
    })
    tool_result_response = client.chat.completions.create(
        model=model,
        messages=followup_messages,
        tools=tools,
        tool_choice="none",
        parallel_tool_calls=True,
    )
    _show("TOOL RESULTS", tool_result_response)
    assert tool_result_response.choices[0].message.content
    assert not tool_result_response.choices[0].message.tool_calls

    # OAuth search is intentionally unsupported and must not inspect/use an API key.
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    search_result = openai_web_search("OpenAI Codex OAuth smoke test")
    print("\n===== NATIVE OPENAI WEB SEARCH CAPABILITY =====")
    print(json.dumps(search_result.__dict__, indent=2, ensure_ascii=False))
    assert search_result.error
    assert "does not support" in search_result.error

    total = sum(
        response.usage.total_tokens or 0
        for response in (
            text_response,
            image_response,
            json_response,
            tool_response,
            tool_result_response,
        )
    )
    print(f"\n===== SUMMARY =====\nAll supported live checks passed; reported tokens: {total}")
