from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv


@dataclass
class LLMResult:
    provider: str
    model: str | None
    raw: str
    data: dict[str, Any]


def call_json_llm(
    prompt: str,
    *,
    provider: str = "auto",
    model: str | None = None,
    timeout_s: int = 180,
) -> LLMResult:
    """Call a local/API LLM and parse a JSON object response."""
    load_dotenv()
    resolved = _resolve_provider(provider)
    if resolved == "claude_cli":
        return _call_claude_cli(prompt, model=model, timeout_s=timeout_s)
    if resolved == "openai":
        return _call_openai(prompt, model=model)
    raise RuntimeError(f"unsupported LLM provider: {provider}")


def _resolve_provider(provider: str) -> str:
    if provider != "auto":
        return provider
    if shutil.which("claude"):
        return "claude_cli"
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("AGENTLENS_OPENAI_AUTH_MODE") == "codex_oauth":
        return "openai"
    raise RuntimeError(
        "no LLM provider available: install claude CLI, set OPENAI_API_KEY, "
        "or select AGENTLENS_OPENAI_AUTH_MODE=codex_oauth"
    )


def _call_claude_cli(prompt: str, *, model: str | None, timeout_s: int) -> LLMResult:
    cmd = ["claude", "-p", prompt]
    if model:
        cmd.extend(["--model", model])
    proc = subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
    )
    raw = proc.stdout.strip()
    return LLMResult(
        provider="claude_cli",
        model=model,
        raw=raw,
        data=_parse_json_object(raw),
    )


def _call_openai(prompt: str, *, model: str | None) -> LLMResult:
    from agentlens.openai_provider import build_openai_client, resolve_auth_mode, resolve_helper_model

    mode = resolve_auth_mode()
    if mode == "codex_oauth":
        model_name = resolve_helper_model(model, fallback_env="AGENTLENS_ANALYSIS_MODEL")
    else:
        model_name = model or os.environ.get("AGENTLENS_ANALYSIS_MODEL") or "gpt-5.4-nano"
    client = build_openai_client(auth_mode=mode, model=model_name)
    kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a trajectory-analysis assistant. Return only a valid JSON "
                    "object matching the requested schema. Do not use markdown fences."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    if model_name.lower().startswith(("gpt-5", "o1", "o3", "o4")):
        kwargs["max_completion_tokens"] = 6000
    else:
        kwargs["max_tokens"] = 6000
        kwargs["temperature"] = 0.0
    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""
    return LLMResult(
        provider="openai",
        model=response.model,
        raw=raw,
        data=_parse_json_object(raw),
    )


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    decoder = json.JSONDecoder()
    data, _end = decoder.raw_decode(text)
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON must be an object")
    return data
