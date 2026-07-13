from __future__ import annotations

import base64
import json
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentlens.openai_provider import (
    CodexOAuthError,
    _parse_sse,
    _persist_auth,
    _token_fields,
    chat_to_responses,
    codex_auth_path,
    resolve_auth_mode,
    resolve_helper_model,
)
from agentlens.schemas import ModelConfig
from agentlens.tools.openai_search import openai_web_search


def _jwt(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{encoded}.signature"


def test_auth_mode_resolution_and_model_precedence(monkeypatch):
    monkeypatch.delenv("AGENTLENS_OPENAI_AUTH_MODE", raising=False)
    assert resolve_auth_mode() == "api_key"
    monkeypatch.setenv("AGENTLENS_OPENAI_AUTH_MODE", "codex_oauth")
    assert resolve_auth_mode() == "codex_oauth"
    assert resolve_auth_mode("api_key") == "api_key"
    with pytest.raises(ValueError, match="auth mode"):
        resolve_auth_mode("password")
    with pytest.raises(ValidationError):
        ModelConfig(id="x", provider="openai", name="x", auth_mode="password")


def test_auth_path_and_helper_model(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENTLENS_CODEX_AUTH_FILE", "~/secret/auth.json")
    assert codex_auth_path() == tmp_path / "secret/auth.json"
    monkeypatch.setenv("AGENTLENS_CODEX_MODEL", "exact-model")
    assert resolve_helper_model(None) == "exact-model"
    assert resolve_helper_model("configured") == "configured"
    monkeypatch.delenv("AGENTLENS_CODEX_MODEL")
    with pytest.raises(CodexOAuthError, match="explicit model"):
        resolve_helper_model(None)


def test_official_token_shape_and_jwt_claims():
    token = _jwt({"exp": 123, "https://api.openai.com/auth": {"chatgpt_account_id": "acct"}})
    fields = _token_fields({"tokens": {"access_token": token, "refresh_token": "refresh"}})
    assert fields == {"access_token": token, "refresh_token": "refresh",
                      "account_id": "acct", "expires_at": 123}


def test_atomic_auth_persistence_is_owner_only(tmp_path: Path):
    path = tmp_path / "auth.json"
    _persist_auth(path, {"tokens": {"refresh_token": "secret"}, "unrelated": 1})
    assert json.loads(path.read_text())["unrelated"] == 1
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_protocol_conversion_and_unsupported_telemetry():
    body, omitted = chat_to_responses({
        "model": "exact",
        "messages": [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": [{"type": "text", "text": "look"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "click", "arguments": "{\"x\":1}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
        ],
        "tools": [{"type": "function", "function": {"name": "click", "description": "click",
                    "parameters": {"type": "object"}, "strict": True}}],
        "parallel_tool_calls": True,
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_completion_tokens": 100,
    })
    assert body["model"] == "exact"
    assert body["instructions"] == "rules"
    assert body["input"][0]["content"][1]["type"] == "input_image"
    assert body["input"][0]["content"][1]["detail"] == "auto"
    assert body["input"][-1]["type"] == "function_call_output"
    assert body["tools"][0]["strict"] is True
    assert body["parallel_tool_calls"] is True
    assert body["text"]["format"]["type"] == "json_object"
    assert omitted == ["temperature", "max_completion_tokens"]


def test_sse_assembly_text_tool_usage_and_model():
    events = [
        {"type": "response.output_text.delta", "delta": "hello"},
        {"type": "response.output_item.added", "item": {"type": "function_call", "id": "i1",
            "call_id": "c1", "name": "done", "arguments": ""}},
        {"type": "response.function_call_arguments.delta", "item_id": "i1", "delta": "{}"},
        {"type": "response.completed", "response": {"id": "r1", "model": "returned",
            "usage": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6}}},
    ]
    raw = "\n".join(f"data: {json.dumps(event)}" for event in events).encode()
    response = _parse_sse(raw, "fallback", ["temperature"])
    assert response.choices[0].message.content == "hello"
    assert response.choices[0].message.tool_calls[0].function.arguments == "{}"
    assert response.choices[0].finish_reason == "tool_calls"
    assert response.usage.total_tokens == 6
    assert response.model == "returned"
    assert response.agentlens_telemetry["omitted_unsupported_parameters"] == ["temperature"]


def test_web_search_rejects_oauth_without_api_key(monkeypatch):
    monkeypatch.setenv("AGENTLENS_OPENAI_AUTH_MODE", "codex_oauth")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = openai_web_search("query")
    assert "does not support" in (result.error or "")
