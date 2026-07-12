"""Shared OpenAI authentication and Codex OAuth protocol adapter.

Codex OAuth uses an internal ChatGPT backend, not the public OpenAI API.  Keep
all reference-derived constants and protocol translation in this module.
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import stat
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from openai import OpenAI

AuthMode = Literal["api_key", "codex_oauth"]
CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
REFRESH_SKEW_SECONDS = 300


class CodexOAuthError(RuntimeError):
    pass


class CodexOAuthCapabilityError(CodexOAuthError):
    pass


def resolve_auth_mode(override: str | None = None) -> AuthMode:
    value = override or os.environ.get("AGENTLENS_OPENAI_AUTH_MODE") or "api_key"
    if value not in {"api_key", "codex_oauth"}:
        raise ValueError(
            "OpenAI auth mode must be 'api_key' or 'codex_oauth' "
            f"(got {value!r})"
        )
    return value  # type: ignore[return-value]


def codex_auth_path() -> Path:
    configured = os.environ.get("AGENTLENS_CODEX_AUTH_FILE")
    if configured:
        return Path(configured).expanduser()
    home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return home / "auth.json"


def resolve_helper_model(model: str | None, *, fallback_env: str | None = None) -> str:
    if model:
        return model
    if fallback_env and os.environ.get(fallback_env):
        return os.environ[fallback_env]
    value = os.environ.get("AGENTLENS_CODEX_MODEL")
    if value:
        return value
    raise CodexOAuthError(
        "Codex OAuth requires an explicit model or AGENTLENS_CODEX_MODEL; "
        "AgentLens does not guess volatile Codex model aliases."
    )


def build_openai_client(*, auth_mode: str | None = None, model: str | None = None) -> Any:
    mode = resolve_auth_mode(auth_mode)
    if mode == "api_key":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Put it in .env at the repo root or export it."
            )
        return OpenAI(api_key=key, base_url=os.environ.get("OPENAI_BASE_URL"))
    return CodexChatClient(model=model)


def _jwt_claims(token: str | None) -> dict[str, Any]:
    try:
        payload = (token or "").split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - malformed token becomes a safe auth error
        return {}


def _token_fields(data: dict[str, Any]) -> dict[str, Any]:
    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else data
    access = tokens.get("access_token") or tokens.get("accessToken")
    refresh = tokens.get("refresh_token") or tokens.get("refreshToken")
    claims = _jwt_claims(access)
    id_claims = _jwt_claims(tokens.get("id_token") or tokens.get("idToken"))
    auth_claims = claims.get("https://api.openai.com/auth", {})
    auth_claims = auth_claims if isinstance(auth_claims, dict) else {}
    id_auth_claims = id_claims.get("https://api.openai.com/auth", {})
    id_auth_claims = id_auth_claims if isinstance(id_auth_claims, dict) else {}
    account = (
        tokens.get("account_id")
        or data.get("account_id")
        or claims.get("chatgpt_account_id")
        or auth_claims.get("chatgpt_account_id")
        or id_claims.get("chatgpt_account_id")
        or id_auth_claims.get("chatgpt_account_id")
    )
    return {"access_token": access, "refresh_token": refresh, "account_id": account,
            "expires_at": claims.get("exp")}


def _read_auth(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("root is not an object")
    except FileNotFoundError as exc:
        raise CodexOAuthError(f"Codex login not found at {path}. Run `codex login`.") from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise CodexOAuthError(f"Codex login at {path} is unreadable. Run `codex login`.") from exc
    fields = _token_fields(raw)
    if not fields["access_token"] or not fields["refresh_token"] or not fields["account_id"]:
        raise CodexOAuthError(f"Codex login at {path} is incomplete. Run `codex login`.")
    return raw, fields


def _request_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            value = json.loads(response.read())
            return value if isinstance(value, dict) else {}
    except urllib.error.HTTPError as exc:
        raise CodexOAuthError(f"Codex authentication request failed with HTTP {exc.code}.") from exc
    except (OSError, ValueError) as exc:
        raise CodexOAuthError("Codex authentication request failed.") from exc


def _persist_auth(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _refresh(path: Path, *, force: bool = False) -> dict[str, Any]:
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        os.chmod(lock_path, stat.S_IRUSR | stat.S_IWUSR)
        fcntl.flock(lock, fcntl.LOCK_EX)
        raw, fields = _read_auth(path)  # another process may already have refreshed
        if not force and fields.get("expires_at", 0) > time.time() + REFRESH_SKEW_SECONDS:
            return fields
        refreshed = _request_json(TOKEN_URL, {
            "client_id": CODEX_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": fields["refresh_token"],
        }, {"Content-Type": "application/json"})
        tokens = raw.setdefault("tokens", {}) if isinstance(raw.get("tokens"), dict) else raw
        for key in ("access_token", "refresh_token", "id_token"):
            if refreshed.get(key):
                tokens[key] = refreshed[key]
        _persist_auth(path, raw)
        return _token_fields(raw)


def load_codex_credentials(*, force_refresh: bool = False) -> dict[str, Any]:
    path = codex_auth_path()
    _raw, fields = _read_auth(path)
    if force_refresh or fields.get("expires_at", 0) <= time.time() + REFRESH_SKEW_SECONDS:
        return _refresh(path, force=force_refresh)
    return fields


def _content_parts(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    result = []
    for part in content or []:
        if part.get("type") in {"text", "input_text"}:
            result.append({"type": "input_text", "text": part.get("text", "")})
        elif part.get("type") in {"image_url", "input_image"}:
            image = part.get("image_url", part.get("image_url"))
            url = image.get("url") if isinstance(image, dict) else image
            detail = image.get("detail", "auto") if isinstance(image, dict) else "auto"
            result.append({"type": "input_image", "image_url": url, "detail": detail})
    return result


def chat_to_responses(kwargs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    instructions, items = [], []
    for message in kwargs.get("messages", []):
        role, content = message.get("role"), message.get("content")
        if role in {"system", "developer"}:
            instructions.extend(p.get("text", "") for p in _content_parts(content))
        elif role == "assistant" and message.get("tool_calls"):
            if content:
                items.append({"role": "assistant", "content": _content_parts(content)})
            for call in message["tool_calls"]:
                fn = call["function"]
                items.append({"type": "function_call", "call_id": call["id"],
                              "name": fn["name"], "arguments": fn.get("arguments", "{}")})
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": message.get("tool_call_id"),
                          "output": content if isinstance(content, str) else json.dumps(content)})
        else:
            items.append({"role": role, "content": _content_parts(content)})
    tools = []
    for tool in kwargs.get("tools", []) or []:
        fn = tool.get("function", tool)
        tools.append({"type": "function", "name": fn["name"],
                      "description": fn.get("description", ""),
                      "parameters": fn.get("parameters", {}), "strict": fn.get("strict", False)})
    body: dict[str, Any] = {"model": kwargs["model"], "input": items, "stream": True,
                            "store": False}
    if instructions:
        body["instructions"] = "\n\n".join(instructions)
    if tools:
        body["tools"] = tools
    if "tool_choice" in kwargs:
        choice = kwargs["tool_choice"]
        body["tool_choice"] = ({"type": "function", "name": choice["function"]["name"]}
                               if isinstance(choice, dict) and "function" in choice else choice)
    if "parallel_tool_calls" in kwargs:
        body["parallel_tool_calls"] = kwargs["parallel_tool_calls"]
    fmt = kwargs.get("response_format")
    if fmt:
        body["text"] = {"format": fmt}
    omitted = [key for key in ("temperature", "max_tokens", "max_completion_tokens") if key in kwargs]
    return body, omitted


def _parse_sse(raw: bytes, fallback_model: str, omitted: list[str]) -> Any:
    text, calls, response, finish = [], {}, {}, "stop"
    for line in raw.decode(errors="replace").splitlines():
        if not line.startswith("data:") or line[5:].strip() == "[DONE]":
            continue
        try:
            event = json.loads(line[5:].strip())
        except ValueError:
            continue
        typ = event.get("type", "")
        if typ == "response.output_text.delta":
            text.append(event.get("delta", ""))
        elif typ == "response.output_item.added" and event.get("item", {}).get("type") == "function_call":
            item = event["item"]
            calls[item.get("id", item.get("call_id"))] = dict(item)
        elif typ == "response.function_call_arguments.delta":
            key = event.get("item_id")
            calls.setdefault(key, {"id": key, "arguments": ""})
            calls[key]["arguments"] = calls[key].get("arguments", "") + event.get("delta", "")
        elif typ == "response.output_item.done" and event.get("item", {}).get("type") == "function_call":
            item = event["item"]
            key = item.get("id", item.get("call_id"))
            calls[key] = {**calls.get(key, {}), **item}
        elif typ in {"response.completed", "response.incomplete"}:
            response = event.get("response", {})
            finish = "length" if typ.endswith("incomplete") else ("tool_calls" if calls else "stop")
    if not text:
        for item in response.get("output", []) or []:
            if item.get("type") == "message":
                text.extend(block.get("text", "") for block in item.get("content", [])
                            if block.get("type") in {"output_text", "text"})
            elif item.get("type") == "function_call":
                calls[item.get("id", item.get("call_id"))] = item
    tool_calls = [SimpleNamespace(id=c.get("call_id") or c.get("id"), type="function",
                   function=SimpleNamespace(name=c.get("name"), arguments=c.get("arguments", "{}")))
                  for c in calls.values()]
    usage = response.get("usage", {}) or {}
    message = SimpleNamespace(content="".join(text) or None, tool_calls=tool_calls or None)
    result = SimpleNamespace(
        id=response.get("id"), model=response.get("model", fallback_model),
        choices=[SimpleNamespace(message=message, finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=usage.get("input_tokens"),
                              completion_tokens=usage.get("output_tokens"),
                              total_tokens=usage.get("total_tokens")),
        agentlens_telemetry={"omitted_unsupported_parameters": omitted},
    )
    return result


class _ChatCompletions:
    def __init__(self, owner: "CodexChatClient") -> None: self.owner = owner
    def create(self, **kwargs: Any) -> Any: return self.owner._create(**kwargs)


class CodexChatClient:
    def __init__(self, *, model: str | None = None) -> None:
        self.default_model = model
        self.chat = SimpleNamespace(completions=_ChatCompletions(self))

    def _create(self, **kwargs: Any) -> Any:
        kwargs["model"] = resolve_helper_model(kwargs.get("model") or self.default_model)
        body, omitted = chat_to_responses(kwargs)
        for retry in range(2):
            credentials = load_codex_credentials(force_refresh=retry == 1)
            request = urllib.request.Request(CODEX_RESPONSES_URL, data=json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {credentials['access_token']}",
                         "ChatGPT-Account-Id": credentials["account_id"],
                         "Content-Type": "application/json", "Accept": "text/event-stream",
                         "OpenAI-Beta": "responses=experimental",
                         "originator": "agentlens"}, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    return _parse_sse(response.read(), body["model"], omitted)
            except urllib.error.HTTPError as exc:
                if exc.code == 401 and retry == 0:
                    continue
                raise CodexOAuthError(f"Codex response failed with HTTP {exc.code}.") from exc
            except OSError as exc:
                raise CodexOAuthError("Codex response request failed.") from exc
        raise CodexOAuthError("Codex authentication failed. Run `codex login`.")
