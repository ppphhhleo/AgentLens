"""OpenAI native web search via the Responses API.

Wraps `client.responses.create(..., tools=[{"type": "web_search"}])` so the
agent can call it as a single `web_search` ComputerAction. The synthesized
answer (and optional source URLs) are returned as a text block which the
loop injects into the agent's next observation.

This is the same web search GPT Atlas uses under the hood.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI

DEFAULT_SEARCH_MODEL = os.environ.get("OPENAI_SEARCH_MODEL", "gpt-5.4")
DEFAULT_MAX_CHARS = 2000


@dataclass
class WebSearchResult:
    query: str
    text: str
    sources: list[dict]
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


def openai_web_search(
    query: str,
    *,
    model: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> WebSearchResult:
    """Call OpenAI Responses API with the built-in web_search tool.

    Never raises — errors are encoded in `WebSearchResult.error`.
    """
    model = model or DEFAULT_SEARCH_MODEL
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return WebSearchResult(
            query=query, text="", sources=[], model=model,
            error="OPENAI_API_KEY not set",
        )

    client = OpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL"))
    try:
        r = client.responses.create(
            model=model,
            input=query,
            tools=[{"type": "web_search"}],
        )
    except Exception as exc:  # noqa: BLE001 - return error to caller
        return WebSearchResult(
            query=query, text="", sources=[], model=model,
            error=f"{type(exc).__name__}: {exc}",
        )

    text = (r.output_text or "").strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"

    sources: list[dict] = []
    for item in (r.output or []):
        if getattr(item, "type", None) == "message":
            for block in getattr(item, "content", []) or []:
                for ann in getattr(block, "annotations", []) or []:
                    if getattr(ann, "type", None) == "url_citation":
                        sources.append({
                            "url": getattr(ann, "url", ""),
                            "title": getattr(ann, "title", ""),
                        })

    usage = getattr(r, "usage", None)
    return WebSearchResult(
        query=query,
        text=text,
        sources=sources[:8],
        model=model,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
    )


def format_for_observation(result: WebSearchResult) -> str:
    """Render a WebSearchResult as a compact text block for the next user message."""
    if result.error:
        return f"[web_search('{result.query}') failed: {result.error}]"
    body = result.text or "(no text returned)"
    src_block = ""
    if result.sources:
        srcs = "\n".join(
            f"  - {s.get('title') or s.get('url') or ''}: {s.get('url') or ''}"
            for s in result.sources
        )
        src_block = f"\nSources:\n{srcs}"
    return f"[web_search results for {result.query!r}]\n{body}{src_block}"
