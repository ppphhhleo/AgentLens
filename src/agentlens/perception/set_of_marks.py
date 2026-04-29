"""Set-of-Marks (SoM) — overlay numbered/letter labels on interactive
elements before screenshot capture, build a `mark → bid` registry the
agent can target by short ids.

Pattern used by `browser-use`, Anthropic's computer-use models, Apple's
Ferret-UI, etc. Agent sees a screenshot WITH visible labels and emits
e.g. `{"type": "click", "mark": "M3"}`. The dispatch layer (in
`browser_actions.py`) resolves `M3 → bid` via the page-side registry
window.__agentlens_marks (keyed by mark id) and clicks the
corresponding element.

Marks are added BEFORE the screenshot is taken and stripped right
after, so they don't pollute subsequent (non-marks) observations or
the agent's next-turn vision.
"""
from __future__ import annotations

from dataclasses import dataclass

# Inject mark labels on every element with a `bid` attribute that's
# inside the viewport. Returns a {mark_id: bid} map and stashes it on
# window.__agentlens_marks for action-dispatch lookups.
_INJECT_MARKS_JS = r"""
(() => {
  const COLORS = ['#ff3b30', '#34c759', '#5ac8fa', '#af52de', '#ff9500', '#ffcc00'];
  // Strip any prior marks first.
  for (const el of document.querySelectorAll('.agentlens-mark')) el.remove();

  const all = Array.from(document.querySelectorAll('[bid]'));
  const inViewport = all.filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0
        && r.bottom > 0 && r.right > 0
        && r.top < window.innerHeight
        && r.left < window.innerWidth;
  });

  const registry = {};
  let counter = 0;
  for (const el of inViewport) {
    counter++;
    const markId = 'M' + counter;
    const bid = el.getAttribute('bid');
    if (!bid) continue;
    registry[markId] = bid;

    const r = el.getBoundingClientRect();
    const color = COLORS[(counter - 1) % COLORS.length];

    // The mark badge: a small absolute-positioned div anchored at the
    // top-left of the element. pointer-events: none so it never
    // intercepts clicks.
    const badge = document.createElement('div');
    badge.className = 'agentlens-mark';
    badge.textContent = markId;
    badge.style.cssText = `
      position: fixed;
      left: ${Math.max(0, r.left - 2)}px;
      top:  ${Math.max(0, r.top - 18)}px;
      background: ${color};
      color: white;
      font: bold 14px/16px ui-monospace, Menlo, monospace;
      padding: 2px 6px;
      border-radius: 3px;
      z-index: 2147483646;
      pointer-events: none;
      white-space: nowrap;
      box-shadow: 0 0 0 2px rgba(0,0,0,0.6);
    `;

    // Outline ring around the element.
    const ring = document.createElement('div');
    ring.className = 'agentlens-mark';
    ring.style.cssText = `
      position: fixed;
      left: ${r.left}px;
      top:  ${r.top}px;
      width: ${r.width}px;
      height: ${r.height}px;
      box-sizing: border-box;
      border: 2px solid ${color};
      pointer-events: none;
      z-index: 2147483645;
    `;

    document.body.appendChild(ring);
    document.body.appendChild(badge);
  }

  window.__agentlens_marks = registry;
  return { count: counter, registry };
})()
"""

_STRIP_MARKS_JS = r"""
(() => {
  for (const el of document.querySelectorAll('.agentlens-mark')) el.remove();
  // Keep window.__agentlens_marks around — dispatch may still need it.
  return true;
})()
"""

_CLEAR_REGISTRY_JS = r"""
(() => { window.__agentlens_marks = {}; return true; })()
"""


@dataclass
class SetOfMarks:
    registry: dict[str, str]   # mark_id -> bid

    @property
    def count(self) -> int:
        return len(self.registry)


def inject_marks(page) -> SetOfMarks:
    """Inject mark badges + outlines onto every [bid] element in viewport.

    REQUIRES that `snapshot_axtree(page)` has already run this turn so
    that elements have `bid` attributes. Returns the mark→bid registry.
    """
    try:
        result = page.evaluate(_INJECT_MARKS_JS)
    except Exception:  # noqa: BLE001
        return SetOfMarks(registry={})
    return SetOfMarks(registry=dict(result.get("registry") or {}))


def strip_marks(page) -> None:
    """Remove the visible mark overlay. The registry stays on window for
    dispatch lookups (in case the agent's action references a mark)."""
    try:
        page.evaluate(_STRIP_MARKS_JS)
    except Exception:  # noqa: BLE001
        pass


def clear_registry(page) -> None:
    """Clear the page-side mark registry (call between turns)."""
    try:
        page.evaluate(_CLEAR_REGISTRY_JS)
    except Exception:  # noqa: BLE001
        pass
