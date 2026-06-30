from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from agentlens.actions import ComputerAction
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType

# Mouse-action modifier key aliases. OpenAI computer-use emits uppercase names;
# Playwright wants Capitalized. Anything not in this map falls through unchanged
# so single characters and special keys still work.
_MODIFIER_MAP = {
    "shift": "Shift",
    "ctrl": "Control",
    "control": "Control",
    "alt": "Alt",
    "option": "Alt",
    "meta": "Meta",
    "cmd": "Meta",
    "command": "Meta",
    "super": "Meta",
    "win": "Meta",
}


def _modifier_key(name: str) -> str:
    return _MODIFIER_MAP.get(name.casefold(), name)


@contextmanager
def _held_modifiers(page, keys: list[str] | None):
    """Hold the given modifier keys for the duration of the with-block."""
    held: list[str] = [_modifier_key(k) for k in (keys or [])]
    for k in held:
        try:
            page.keyboard.down(k)
        except Exception:  # noqa: BLE001 - best effort; downstream action will still try
            pass
    try:
        yield
    finally:
        for k in reversed(held):
            try:
                page.keyboard.up(k)
            except Exception:  # noqa: BLE001
                pass

# Settle delay after each action so the page can finish layout/animation
# before the next screenshot. Smaller = smoother live experience.
DEFAULT_POST_ACTION_SETTLE_MS = 0
DEFAULT_HOVER_SETTLE_MS = 600

OVERLAY_INIT_JS = """
(() => {
  if (window.__agentlens_overlay_ready) return;
  window.__agentlens_overlay_ready = true;
  const style = document.createElement('style');
  style.textContent = `
    @keyframes agentlens-pulse {
      0%   { transform: scale(0.4); opacity: 1; }
      100% { transform: scale(2.2); opacity: 0; }
    }
    .agentlens-marker {
      position: fixed;
      width: 36px; height: 36px;
      border: 3px solid #ff3b30;
      border-radius: 50%;
      pointer-events: none;
      z-index: 2147483647;
      animation: agentlens-pulse 1.0s ease-out forwards;
    }
    .agentlens-hint {
      position: fixed;
      right: 16px;
      bottom: 16px;
      max-width: min(420px, calc(100vw - 32px));
      padding: 12px 14px;
      background: rgba(20, 24, 31, 0.94);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 8px;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.28);
      font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      pointer-events: none;
      z-index: 2147483647;
    }
  `;
  document.head.appendChild(style);
  window.__agentlens_show = (x, y, color) => {
    const m = document.createElement('div');
    m.className = 'agentlens-marker';
    m.style.left = (x - 18) + 'px';
    m.style.top  = (y - 18) + 'px';
    if (color) m.style.borderColor = color;
    document.body.appendChild(m);
    setTimeout(() => m.remove(), 1000);
  };
  window.__agentlens_hint = (text, ms) => {
    const old = document.querySelector('.agentlens-hint');
    if (old) old.remove();
    const h = document.createElement('div');
    h.className = 'agentlens-hint';
    h.textContent = String(text || '');
    document.body.appendChild(h);
    setTimeout(() => h.remove(), ms || 4500);
  };
})();
"""


def show_marker(page, x: float | None, y: float | None, color: str = "#ff3b30") -> None:
    """Draw a pulsing circle at (x, y) on the page. Best-effort, never raises.

    The overlay JS is registered via context.add_init_script so it auto-runs on
    every page load — we only need to call __agentlens_show here. One CDP
    round-trip per action instead of two.
    """
    if x is None or y is None:
        return
    try:
        page.evaluate(
            "([x, y, c]) => window.__agentlens_show && window.__agentlens_show(x, y, c)",
            [x, y, color],
        )
    except Exception:  # noqa: BLE001 - overlay is best-effort
        pass


def show_hint(page, text: str, *, ms: int = 4500) -> None:
    """Display a transient AgentLens hint on the active page."""
    if not text:
        return
    try:
        page.evaluate(
            "([text, ms]) => window.__agentlens_hint && window.__agentlens_hint(text, ms)",
            [text, ms],
        )
    except Exception:  # noqa: BLE001 - overlay is best-effort
        pass


def _resolve_target_locator(page, action: ComputerAction):
    """Return (locator, marker_xy) for actions targeted by bid/selector/mark.

    Returns (None, None) if the action targets coordinates (we keep the
    current x,y dispatch for those).
    """
    if action.bid:
        loc = page.locator(f"[bid='{action.bid}']").first
        return loc, _bbox_center(loc)
    if action.selector:
        loc = page.locator(action.selector).first
        return loc, _bbox_center(loc)
    if action.mark:
        # mark→bid registry is per-page; agents using marks must inject it
        # via context.add_init_script before calling execute_action.
        bid = page.evaluate(
            "(m) => (window.__agentlens_marks && window.__agentlens_marks[m]) || null",
            action.mark,
        )
        if not bid:
            return None, None
        loc = page.locator(f"[bid='{bid}']").first
        return loc, _bbox_center(loc)
    return None, None


def _bbox_center(locator):
    """Best-effort center coords for an element — for the overlay marker."""
    try:
        bb = locator.bounding_box()
        if bb:
            return (bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
    except Exception:  # noqa: BLE001
        pass
    return None


def _click_locator(locator, *, button: str, timeout: int = 5000) -> None:
    """Click a locator with actionability checks, then fall back to force.

    The normal click is more faithful to what a user can do. The forced
    fallback keeps compatibility with custom-styled controls where the real
    input is visually covered by a label/toggle shell.
    """
    try:
        locator.click(button=button, timeout=timeout)
    except Exception:  # noqa: BLE001 - fallback is intentional for custom controls
        locator.click(button=button, timeout=10000, force=True)


def _dblclick_locator(locator, *, button: str, timeout: int = 5000) -> None:
    try:
        locator.dblclick(button=button, timeout=timeout)
    except Exception:  # noqa: BLE001
        locator.dblclick(button=button, timeout=10000, force=True)


def execute_action(page, action: ComputerAction) -> str | None:
    """Execute one ComputerAction against a Playwright page. Returns error string or None."""
    try:
        # Target resolution happens once: bid/selector/mark all flow through
        # a Playwright Locator; coordinates take the legacy mouse path.
        target_locator, target_xy = _resolve_target_locator(page, action)

        match action.type:
            case "screenshot":
                return None
            case "click":
                if target_locator is not None:
                    if target_xy is not None:
                        show_marker(page, *target_xy, "#ff3b30")
                    with _held_modifiers(page, action.keys):
                        _click_locator(target_locator, button=_playwright_button(action.button))
                else:
                    show_marker(page, action.x, action.y, "#ff3b30")
                    with _held_modifiers(page, action.keys):
                        page.mouse.click(
                            action.x, action.y, button=_playwright_button(action.button)
                        )
            case "double_click":
                if target_locator is not None:
                    if target_xy is not None:
                        show_marker(page, *target_xy, "#ff9500")
                    with _held_modifiers(page, action.keys):
                        _dblclick_locator(target_locator, button=_playwright_button(action.button))
                else:
                    show_marker(page, action.x, action.y, "#ff9500")
                    with _held_modifiers(page, action.keys):
                        page.mouse.dblclick(
                            action.x, action.y, button=_playwright_button(action.button)
                        )
            case "scroll":
                if target_locator is not None and target_xy is not None:
                    show_marker(page, *target_xy, "#34c759")
                    target_locator.scroll_into_view_if_needed(timeout=5000)
                else:
                    show_marker(page, action.x, action.y, "#34c759")
                    page.mouse.move(action.x, action.y)
                with _held_modifiers(page, action.keys):
                    page.evaluate(
                        "(delta) => window.scrollBy(delta.scrollX, delta.scrollY)",
                        {"scrollX": action.scroll_x, "scrollY": action.scroll_y},
                    )
            case "type":
                # If a target is specified, focus + fill it; else dispatch
                # raw keyboard typing into whatever's currently focused.
                if target_locator is not None:
                    target_locator.fill(action.text or "", timeout=10000)
                elif action.x is not None and action.y is not None:
                    show_marker(page, action.x, action.y, "#007aff")
                    page.mouse.click(action.x, action.y)
                    page.keyboard.type(action.text or "")
                else:
                    page.keyboard.type(action.text or "")
            case "wait":
                page.wait_for_timeout(action.ms or 1000)
            case "move":
                if target_locator is not None and target_xy is not None:
                    show_marker(page, *target_xy, "#5ac8fa")
                    target_locator.hover(timeout=5000)
                else:
                    show_marker(page, action.x, action.y, "#5ac8fa")
                    with _held_modifiers(page, action.keys):
                        page.mouse.move(action.x, action.y)
                page.wait_for_timeout(DEFAULT_HOVER_SETTLE_MS)
            case "keypress":
                for key in action.keys:
                    page.keyboard.press(_normalize_key(key))
            case "drag":
                first, *rest = action.path
                show_marker(page, first.x, first.y, "#af52de")
                with _held_modifiers(page, action.keys):
                    page.mouse.move(first.x, first.y)
                    page.mouse.down()
                    for point in rest:
                        page.mouse.move(point.x, point.y)
                    page.mouse.up()
            case "goto":
                if action.url:
                    page.goto(action.url, wait_until="domcontentloaded")
            case "back":
                page.go_back(wait_until="domcontentloaded")
            case "forward":
                page.go_forward(wait_until="domcontentloaded")
            case "reload":
                page.reload(wait_until="domcontentloaded")
            case "final_answer":
                return None
        # Let layout/animations settle before the next screenshot.
        if DEFAULT_POST_ACTION_SETTLE_MS > 0:
            page.wait_for_timeout(DEFAULT_POST_ACTION_SETTLE_MS)
        return None
    except Exception as exc:  # noqa: BLE001 - action errors belong in trajectory data.
        return f"{type(exc).__name__}: {exc}"


def capture_screenshot_event(
    page,
    screenshot_dir: Path,
    step_index: int,
    goal: str | None,
    *,
    name_suffix: str = "",
) -> TrajectoryEvent:
    """Capture viewport screenshot to step_NNN[<suffix>].png.

    Use `name_suffix` (e.g. "_marks") when there are MULTIPLE captures
    in the same step (e.g. set-of-marks pre-action vs unmarked
    post-action) — keeps the post-action capture from overwriting the
    pre-action one.
    """
    suffix = f"_{name_suffix.lstrip('_')}" if name_suffix else ""
    screenshot_path = screenshot_dir / f"step_{step_index:03d}{suffix}.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    return TrajectoryEvent(
        event_type=TrajectoryEventType.SCREENSHOT,
        step_index=step_index,
        data={
            "url": page.url,
            "viewport": page.viewport_size,
            "goal": goal,
            "kind": name_suffix.lstrip("_") or "post_action",
            "screenshot_source": "browser_viewport",
            "coordinate_frame": "browser_viewport",
        },
        artifact_paths=[screenshot_path],
    )


def _target_str(action: ComputerAction) -> str:
    """Human-readable target spec for log lines."""
    if action.bid:
        return f"bid={action.bid!r}"
    if action.selector:
        return f"selector={action.selector!r}"
    if action.mark:
        return f"mark={action.mark!r}"
    return f"x={action.x} y={action.y}"


def format_action(action: ComputerAction) -> str:
    mods = f" mods={action.keys}" if action.keys and action.type != "keypress" else ""
    match action.type:
        case "click" | "double_click":
            return f"{action.type} {_target_str(action)} button={action.button}{mods}"
        case "scroll":
            return (
                f"scroll {_target_str(action)} "
                f"scroll_x={action.scroll_x} scroll_y={action.scroll_y}{mods}"
            )
        case "type":
            tgt = f"target={_target_str(action)} " if action.bid or action.selector or action.mark else ""
            return f"type {tgt}text={action.text!r}"
        case "wait":
            return f"wait ms={action.ms or 1000}"
        case "move":
            return f"move {_target_str(action)}{mods}"
        case "keypress":
            return f"keypress keys={action.keys}"
        case "drag":
            return f"drag points={len(action.path)}{mods}"
        case "screenshot":
            return "screenshot"
        case "goto":
            return f"goto url={action.url!r}"
        case "back":
            return "back"
        case "forward":
            return "forward"
        case "reload":
            return "reload"
        case "web_search":
            return f"web_search query={action.query!r}"
        case "run_python":
            return f"run_python code=({len(action.code or '')} chars)"
        case "shell":
            return f"shell cmd={action.cmd!r}"
        case "read_file":
            return f"read_file file_path={action.file_path!r}"
        case "write_file":
            return f"write_file file_path={action.file_path!r} content=({len(action.content or '')} chars)"
        case "mcp_tool":
            return f"mcp_tool name={action.mcp_tool!r} args={action.mcp_args!r}"
        case "final_answer":
            return f"final_answer answer={action.answer!r}"


def _playwright_button(button: str) -> str:
    if button in {"left", "right", "middle"}:
        return button
    return "left"


def _normalize_key(key: str) -> str:
    key_map = {
        "enter": "Enter",
        "return": "Enter",
        "space": " ",
        "tab": "Tab",
        "escape": "Escape",
        "esc": "Escape",
        "backspace": "Backspace",
        "delete": "Delete",
        "home": "Home",
        "end": "End",
        "pageup": "PageUp",
        "page_up": "PageUp",
        "page down": "PageDown",
        "pagedown": "PageDown",
        "page_down": "PageDown",
        "arrowup": "ArrowUp",
        "arrow_up": "ArrowUp",
        "up": "ArrowUp",
        "arrowdown": "ArrowDown",
        "arrow_down": "ArrowDown",
        "down": "ArrowDown",
        "arrowleft": "ArrowLeft",
        "arrow_left": "ArrowLeft",
        "left": "ArrowLeft",
        "arrowright": "ArrowRight",
        "arrow_right": "ArrowRight",
        "right": "ArrowRight",
    }
    return key_map.get(key.casefold(), key)
