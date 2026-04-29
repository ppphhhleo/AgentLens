from __future__ import annotations

from pathlib import Path

from agentlens.actions import ComputerAction
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType

# Settle delay after each action so the page can finish layout/animation
# before the next screenshot.
DEFAULT_POST_ACTION_SETTLE_MS = 600

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
})();
"""


def show_marker(page, x: float | None, y: float | None, color: str = "#ff3b30") -> None:
    """Draw a pulsing circle at (x, y) on the page. Best-effort, never raises."""
    if x is None or y is None:
        return
    try:
        page.evaluate(OVERLAY_INIT_JS)
        page.evaluate(
            "([x, y, c]) => window.__agentlens_show && window.__agentlens_show(x, y, c)",
            [x, y, color],
        )
    except Exception:  # noqa: BLE001 - overlay is best-effort
        pass


def execute_action(page, action: ComputerAction) -> str | None:
    """Execute one ComputerAction against a Playwright page. Returns error string or None."""
    try:
        match action.type:
            case "screenshot":
                return None
            case "click":
                show_marker(page, action.x, action.y, "#ff3b30")
                page.mouse.move(action.x, action.y)
                page.mouse.click(action.x, action.y, button=_playwright_button(action.button))
            case "double_click":
                show_marker(page, action.x, action.y, "#ff9500")
                page.mouse.move(action.x, action.y)
                page.mouse.dblclick(action.x, action.y, button=_playwright_button(action.button))
            case "scroll":
                show_marker(page, action.x, action.y, "#34c759")
                page.mouse.move(action.x, action.y)
                page.evaluate(
                    "(delta) => window.scrollBy(delta.scrollX, delta.scrollY)",
                    {"scrollX": action.scroll_x, "scrollY": action.scroll_y},
                )
            case "type":
                page.keyboard.type(action.text or "")
            case "wait":
                page.wait_for_timeout(action.ms or 1000)
            case "move":
                show_marker(page, action.x, action.y, "#5ac8fa")
                page.mouse.move(action.x, action.y)
            case "keypress":
                for key in action.keys:
                    page.keyboard.press(_normalize_key(key))
            case "drag":
                first, *rest = action.path
                show_marker(page, first.x, first.y, "#af52de")
                page.mouse.move(first.x, first.y)
                page.mouse.down()
                for point in rest:
                    page.mouse.move(point.x, point.y)
                page.mouse.up()
            case "final_answer":
                return None
        # Let layout/animations settle before the next screenshot.
        page.wait_for_timeout(DEFAULT_POST_ACTION_SETTLE_MS)
        return None
    except Exception as exc:  # noqa: BLE001 - action errors belong in trajectory data.
        return f"{type(exc).__name__}: {exc}"


def capture_screenshot_event(
    page,
    screenshot_dir: Path,
    step_index: int,
    goal: str | None,
) -> TrajectoryEvent:
    screenshot_path = screenshot_dir / f"step_{step_index:03d}.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    return TrajectoryEvent(
        event_type=TrajectoryEventType.SCREENSHOT,
        step_index=step_index,
        data={"url": page.url, "viewport": page.viewport_size, "goal": goal},
        artifact_paths=[screenshot_path],
    )


def format_action(action: ComputerAction) -> str:
    match action.type:
        case "click" | "double_click":
            return f"{action.type} x={action.x} y={action.y} button={action.button}"
        case "scroll":
            return (
                f"scroll x={action.x} y={action.y} "
                f"scroll_x={action.scroll_x} scroll_y={action.scroll_y}"
            )
        case "type":
            return f"type text={action.text!r}"
        case "wait":
            return f"wait ms={action.ms or 1000}"
        case "move":
            return f"move x={action.x} y={action.y}"
        case "keypress":
            return f"keypress keys={action.keys}"
        case "drag":
            return f"drag points={len(action.path)}"
        case "screenshot":
            return "screenshot"
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
    }
    return key_map.get(key.casefold(), key)
