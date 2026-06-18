from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from agentlens.actions import ComputerAction


@dataclass
class MCPToolResult:
    ok: bool
    output: str
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def run_mcp_tool(action: ComputerAction, *, page=None) -> MCPToolResult:
    """Dispatch MCP-style browser tools.

    This is intentionally a small local backend rather than a full MCP stdio
    client. It gives the model MCP-shaped Chrome tools backed by the live
    Playwright page, so the proof-of-concept exercises real web navigation and
    DOM interaction while preserving the same registry/gating/trajectory path a
    true MCP server would use.

    Set AGENTLENS_MCP_ECHO=1 for local smoke tests that should succeed without
    launching a browser.
    """
    tool_name = action.mcp_tool or "mcp.unknown"
    args = dict(action.mcp_args or {})
    if os.environ.get("AGENTLENS_MCP_ECHO") == "1":
        payload = {"tool": tool_name, "args": args}
        return MCPToolResult(
            ok=True,
            output=f"[mcp echo]\n{json.dumps(payload, ensure_ascii=False)}",
            extra={"mode": "echo", "tool": tool_name, "args": args},
        )
    if page is None:
        return MCPToolResult(
            ok=False,
            output="",
            error=(
                f"MCP executor needs a browser page for {tool_name!r}. "
                "Pass the active Playwright page or set AGENTLENS_MCP_ECHO=1 "
                "for a no-browser smoke test."
            ),
            extra={"mode": "missing_page", "tool": tool_name, "args": args},
        )

    try:
        return _run_chrome_tool(page, tool_name, args)
    except Exception as exc:  # noqa: BLE001 - tool failures belong in trajectory data.
        return MCPToolResult(
            ok=False,
            output="",
            error=f"{type(exc).__name__}: {exc}",
            extra={"mode": "playwright", "tool": tool_name, "args": args},
        )


def _run_chrome_tool(page, tool_name: str, args: dict[str, Any]) -> MCPToolResult:
    if tool_name == "mcp.chrome.snapshot":
        payload = _snapshot_page(page)
        return _json_result(tool_name, payload)

    if tool_name == "mcp.chrome.goto":
        url = str(args.get("url") or "")
        page.goto(url, wait_until="domcontentloaded", timeout=int(args.get("timeout_ms") or 30000))
        payload = {"url": page.url, "title": _safe_title(page)}
        return _json_result(tool_name, payload)

    if tool_name == "mcp.chrome.click_selector":
        selector = str(args.get("selector") or "")
        locator = page.locator(selector).first
        locator.click(timeout=int(args.get("timeout_ms") or 10000))
        return _json_result(tool_name, {"selector": selector, "url": page.url})

    if tool_name == "mcp.chrome.type_selector":
        selector = str(args.get("selector") or "")
        text = str(args.get("text") or "")
        locator = page.locator(selector).first
        locator.fill(text, timeout=int(args.get("timeout_ms") or 10000))
        return _json_result(tool_name, {"selector": selector, "text_length": len(text), "url": page.url})

    if tool_name == "mcp.chrome.get_text":
        selector = args.get("selector")
        if selector:
            text = page.locator(str(selector)).first.inner_text(timeout=10000)
        else:
            text = page.locator("body").inner_text(timeout=10000)
        payload = {"selector": selector, "text": _truncate(text, 6000), "url": page.url}
        return _json_result(tool_name, payload)

    if tool_name == "mcp.chrome.evaluate":
        script = str(args.get("script") or "")
        value = page.evaluate(script)
        payload = {"result": _json_safe(value), "url": page.url}
        return _json_result(tool_name, payload, max_chars=8000)

    return MCPToolResult(
        ok=False,
        output="",
        error=(
            f"Unsupported MCP tool {tool_name!r}. Add it to agentlens.tools.mcp "
            "or remove it from the harness allow-list."
        ),
        extra={"mode": "unsupported", "tool": tool_name, "args": args},
    )


def format_for_observation(result: MCPToolResult) -> str:
    if result.error:
        return f"[mcp tool failed]\n{result.error}"
    return result.output or "[mcp tool returned no output]"


def _snapshot_page(page) -> dict[str, Any]:
    elements = page.evaluate(
        """() => {
          const candidates = Array.from(document.querySelectorAll(
            'a,button,input,select,textarea,[role="button"],[role="link"],[tabindex],summary'
          ));
          return candidates.slice(0, 80).map((el, index) => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '').trim();
            return {
              index,
              tag: el.tagName.toLowerCase(),
              role: el.getAttribute('role'),
              text: text.slice(0, 160),
              id: el.id || null,
              name: el.getAttribute('name'),
              type: el.getAttribute('type'),
              href: el.getAttribute('href'),
              selector_hint: selectorHint(el),
              visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
              bbox: {x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height)}
            };
          });

          function selectorHint(el) {
            if (el.id) return '#' + CSS.escape(el.id);
            const name = el.getAttribute('name');
            if (name) return el.tagName.toLowerCase() + '[name="' + CSS.escape(name) + '"]';
            const aria = el.getAttribute('aria-label');
            if (aria) return el.tagName.toLowerCase() + '[aria-label="' + CSS.escape(aria) + '"]';
            return el.tagName.toLowerCase();
          }
        }"""
    )
    return {
        "url": page.url,
        "title": _safe_title(page),
        "text": _truncate(page.locator("body").inner_text(timeout=10000), 4000),
        "elements": elements,
    }


def _safe_title(page) -> str:
    try:
        return page.title()
    except Exception:  # noqa: BLE001
        return ""


def _json_result(tool_name: str, payload: dict[str, Any], *, max_chars: int = 6000) -> MCPToolResult:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return MCPToolResult(
        ok=True,
        output=f"[{tool_name}]\n{_truncate(text, max_chars)}",
        extra={"mode": "playwright", "tool": tool_name},
    )


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)
