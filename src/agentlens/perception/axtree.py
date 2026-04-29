"""AXTree perception — extract a textual accessibility tree the agent
can read in lieu of (or alongside) a screenshot.

We inject `bid` attributes on interactive DOM elements so the agent can
reference them by stable id (`bid="a23"`), and emit a compact serialized
tree the model can parse.

This is **self-contained**: no BrowserGym dependency. We assign our own
sequential bids on each snapshot. Bids are stable within a step but may
shift across steps if the DOM changes — that matches how BrowserGym's
GenericAgent works.
"""
from __future__ import annotations

from dataclasses import dataclass

# JS that walks the DOM, tags interactive elements with sequential `bid`
# attributes, and returns a compact serialized list. Roles + names come
# from accessible attributes (aria-label, label, text content, alt).
_BID_AND_AXTREE_JS = r"""
(() => {
  const INTERACTIVE_SELECTOR = [
    'a[href]',
    'button',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    'summary',
    '[role="button"]',
    '[role="link"]',
    '[role="checkbox"]',
    '[role="radio"]',
    '[role="switch"]',
    '[role="tab"]',
    '[role="menuitem"]',
    '[role="combobox"]',
    '[role="textbox"]',
    '[role="searchbox"]',
    '[role="option"]',
    '[contenteditable]:not([contenteditable="false"])',
    '[tabindex]:not([tabindex="-1"])',
    'label[for]',
    'details',
  ].join(',');

  // Some interactive elements are visually masked by custom CSS (e.g. native
  // checkboxes hidden behind styled labels) but still functional when clicked
  // via Playwright. Always surface them so the agent can target them by bid.
  const alwaysSurface = (el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'checkbox' || t === 'radio') return true;
    }
    const role = el.getAttribute('role');
    if (role === 'checkbox' || role === 'radio' || role === 'switch') return true;
    return false;
  };

  const visible = (el) => {
    if (!el) return false;
    if (alwaysSurface(el)) return true;
    const cs = window.getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  const truncate = (s, n) => {
    if (!s) return '';
    s = String(s).replace(/\s+/g, ' ').trim();
    return s.length > n ? s.slice(0, n) + '…' : s;
  };

  const accessibleName = (el) => {
    // For inputs masked by a visible label, prefer the label text — that's
    // what the user actually reads on the page.
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
      const labels = el.labels;
      if (labels && labels.length) {
        const txt = Array.from(labels).map(l => l.textContent || '').join(' ').trim();
        if (txt) return txt;
      }
    }
    return (
      el.getAttribute('aria-label') ||
      el.getAttribute('alt') ||
      (el.tagName === 'IMG' ? el.getAttribute('alt') : '') ||
      el.getAttribute('title') ||
      el.getAttribute('placeholder') ||
      (el.labels && el.labels[0] && el.labels[0].textContent) ||
      el.textContent ||
      el.value ||
      ''
    );
  };

  const tagRole = (el) => {
    if (el.hasAttribute('role')) return el.getAttribute('role');
    const t = el.tagName.toLowerCase();
    if (t === 'a') return 'link';
    if (t === 'button') return 'button';
    if (t === 'input') {
      const type = (el.getAttribute('type') || 'text').toLowerCase();
      if (['checkbox', 'radio', 'submit', 'button', 'reset'].includes(type)) return type;
      return 'textbox';
    }
    if (t === 'select') return 'combobox';
    if (t === 'textarea') return 'textbox';
    if (t === 'summary') return 'summary';
    if (t === 'details') return 'group';
    if (t === 'label') return 'label';
    return t;
  };

  // Clear stale bids first so re-snapshots don't accumulate.
  for (const el of document.querySelectorAll('[bid^="a"]')) {
    el.removeAttribute('bid');
  }

  const allCandidates = Array.from(document.querySelectorAll(INTERACTIVE_SELECTOR)).filter(visible);

  // Many UIs hide the native checkbox/radio behind a styled label. The
  // click handler is typically on the label (or a descendant span), and
  // clicking the bare hidden input does NOT trigger custom toggle code.
  // So: when a checkbox/radio has an associated label that is ALSO a
  // candidate, drop the input — surface only the label, but render it
  // with checkbox semantics + the input's checked state.
  const inputToLabel = new Map();
  for (const el of allCandidates) {
    if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA' && el.tagName !== 'SELECT') continue;
    const labels = el.labels;
    if (labels && labels.length) {
      // Pick the first label that's a candidate (visible + already in set).
      for (const lab of labels) {
        if (allCandidates.includes(lab)) {
          inputToLabel.set(el, lab);
          break;
        }
      }
    }
  }
  const labelToInput = new Map();
  for (const [inp, lab] of inputToLabel.entries()) labelToInput.set(lab, inp);

  const elements = allCandidates.filter(el => !inputToLabel.has(el));

  const lines = [];
  let counter = 0;
  for (const el of elements) {
    counter++;
    const bid = 'a' + counter;
    el.setAttribute('bid', bid);

    // If this element is a label wrapping a checkbox/radio, render it
    // with the input's role + checked state (better signal to the agent
    // that this is a toggle).
    const associatedInput = labelToInput.get(el);
    const effectiveEl = associatedInput || el;

    const role = tagRole(effectiveEl);
    const name = truncate(accessibleName(el), 80);  // label's own text reads better
    const value = effectiveEl.value !== undefined && effectiveEl.value !== '' ? truncate(effectiveEl.value, 50) : '';
    const isCheckable = (
      effectiveEl.type === 'checkbox' || effectiveEl.type === 'radio' ||
      effectiveEl.getAttribute('role') === 'checkbox' ||
      effectiveEl.getAttribute('role') === 'radio' ||
      effectiveEl.getAttribute('role') === 'switch'
    );
    const checked = isCheckable ? (effectiveEl.checked ?? effectiveEl.getAttribute('aria-checked') ?? null) : null;
    const disabled = el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';

    let line = `[${bid}] ${role}`;
    if (name) line += ` "${name}"`;
    const attrs = [];
    if (value && !isCheckable) attrs.push(`value="${value}"`);
    if (checked !== null) attrs.push(`checked=${checked}`);
    if (disabled) attrs.push('disabled');
    if (el.tagName === 'A' && el.getAttribute('href')) {
      attrs.push(`href="${truncate(el.getAttribute('href'), 60)}"`);
    }
    if (attrs.length) line += ` (${attrs.join(', ')})`;
    lines.push(line);
  }

  return {
    text: lines.join('\n'),
    bid_count: counter,
    title: document.title,
    url: location.href,
  };
})()
"""


@dataclass
class AXTreeSnapshot:
    """One snapshot of the page's interactive surface."""

    text: str            # serialized AXTree-ish list
    bid_count: int       # how many interactive elements got tagged
    url: str
    title: str

    def is_empty(self) -> bool:
        return self.bid_count == 0


def snapshot_axtree(page, *, max_lines: int = 200) -> AXTreeSnapshot:
    """Tag interactive elements with bid attrs + return a serialized tree.

    Idempotent: calling it again clears prior bids and re-numbers. Caller
    is responsible for any retention semantics across steps.

    `max_lines` truncates the serialized text — for very busy pages we
    cut to the top N elements (in DOM order) to keep prompt size sane.
    """
    try:
        result = page.evaluate(_BID_AND_AXTREE_JS)
    except Exception as exc:  # noqa: BLE001 - never crash the agent on perception errors
        return AXTreeSnapshot(
            text=f"[axtree extraction failed: {type(exc).__name__}: {exc}]",
            bid_count=0,
            url=page.url,
            title="",
        )
    text = str(result.get("text", "") or "")
    if max_lines > 0 and text.count("\n") + 1 > max_lines:
        head = "\n".join(text.splitlines()[:max_lines])
        text = head + f"\n... (truncated; {result.get('bid_count', 0)} total elements)"
    return AXTreeSnapshot(
        text=text,
        bid_count=int(result.get("bid_count", 0) or 0),
        url=str(result.get("url", "") or page.url),
        title=str(result.get("title", "") or ""),
    )
