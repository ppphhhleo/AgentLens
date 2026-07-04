from __future__ import annotations

import ast
import json
import os
from html import escape
from pathlib import Path
from typing import Any


def write_gui_vs_cli_trajectory_viewer(
    input_path: Path, output_path: Path | None = None
) -> Path:
    """Render a static HTML viewer for gui-vs-cli list-format trajectories."""
    input_path = input_path.expanduser().resolve()
    steps = json.loads(input_path.read_text(encoding="utf-8"))
    if not _looks_like_gui_vs_cli_steps(steps):
        raise ValueError(f"not a gui-vs-cli step-list trajectory: {input_path}")

    if output_path is None:
        output_path = input_path.with_name("gui_vs_cli_trajectory_viewer.html")
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = _load_result(input_path.with_name("result.json"))
    output_path.write_text(
        _render_page(steps, result=result, source_path=input_path, output_path=output_path),
        encoding="utf-8",
    )
    return output_path


def _looks_like_gui_vs_cli_steps(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) for item in value)
        and any("screenshot_file" in item and "actions" in item for item in value)
    )


def _load_result(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _render_page(
    steps: list[dict[str, Any]],
    *,
    result: dict[str, Any],
    source_path: Path,
    output_path: Path,
) -> str:
    nav = "\n".join(_render_nav_link(step) for step in steps)
    cards = "\n".join(_render_step(step, output_path=output_path) for step in steps)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentLens GUI-vs-CLI Trajectory Viewer</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-2: #f9fafc;
      --text: #171a1f;
      --muted: #667085;
      --line: #dfe4ec;
      --accent: #2563eb;
      --ok: #168a4a;
      --bad: #d23f31;
      --code: #f3f5f8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #fff 0, var(--bg) 18rem), var(--bg);
      color: var(--text);
      font: 13px/1.42 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 8;
      padding: .8rem 1rem;
      background: rgba(255,255,255,.94);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 1.1rem; }}
    main {{ max-width: 1500px; margin: 0 auto; padding: .85rem; }}
    a {{ color: var(--accent); text-decoration: none; }}
    .source {{
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-top: .2rem;
    }}
    .summary {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      overflow: hidden;
      box-shadow: 0 14px 34px rgba(28, 38, 57, .08);
      margin-bottom: .75rem;
    }}
    .summary-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: .75rem;
      padding: .7rem .8rem;
      border-bottom: 1px solid var(--line);
    }}
    .summary-head h2 {{
      font-size: 1.05rem;
      overflow-wrap: anywhere;
    }}
    .badges {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: .35rem;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: .18rem .45rem;
      background: var(--panel-2);
      color: var(--text);
      font-size: .76rem;
      white-space: nowrap;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: .3rem .8rem;
      padding: .5rem .8rem;
      background: var(--panel-2);
    }}
    .metric span {{ color: var(--muted); margin-right: .25rem; }}
    .metric strong {{ font-weight: 780; }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    .step-nav {{
      position: sticky;
      top: 5.1rem;
      z-index: 5;
      display: flex;
      flex-wrap: wrap;
      gap: .32rem;
      padding: .45rem;
      margin-bottom: .65rem;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,.95);
      backdrop-filter: blur(10px);
    }}
    .step-nav a {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: .16rem .38rem;
      background: var(--panel-2);
      color: var(--text);
      font-size: .74rem;
    }}
    .timeline {{
      display: grid;
      gap: .7rem;
    }}
    .step {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      overflow: hidden;
      box-shadow: 0 10px 26px rgba(28, 38, 57, .06);
    }}
    .step-head {{
      display: flex;
      justify-content: space-between;
      gap: .7rem;
      align-items: center;
      padding: .48rem .65rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }}
    .step-head strong {{ font-size: .9rem; }}
    .step-body {{
      display: grid;
      grid-template-columns: minmax(320px, .9fr) minmax(360px, 1fr);
      gap: .65rem;
      padding: .65rem;
    }}
    .shot img {{
      display: block;
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    .details {{
      display: grid;
      gap: .55rem;
      min-width: 0;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }}
    .panel h3 {{
      padding: .38rem .5rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--muted);
      font-size: .72rem;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    .panel-body {{ padding: .5rem; }}
    .text-block {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
    pre {{
      max-height: 18rem;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: .55rem;
      border-radius: 7px;
      background: var(--code);
      border: 1px solid var(--line);
      color: #1f2937;
      font-size: .74rem;
    }}
    .action-click {{ --action-color: #0ea5e9; }}
    .action-double_click {{ --action-color: #06b6d4; }}
    .action-move {{ --action-color: #6366f1; }}
    .action-drag {{ --action-color: #ef4444; }}
    .action-scroll {{ --action-color: #16a34a; }}
    .action-type {{ --action-color: #8b5cf6; }}
    .action-keypress {{ --action-color: #f59e0b; }}
    .action-wait {{ --action-color: #64748b; }}
    .action-script {{ --action-color: #475569; }}
    .action-line {{
      border-left: 3px solid var(--action-color, var(--line));
      padding: .26rem .45rem;
      margin-bottom: .28rem;
      background: color-mix(in srgb, var(--action-color, var(--line)) 7%, white);
      border-radius: 6px;
    }}
    .action-line strong {{ color: var(--action-color, var(--text)); }}
    details {{ margin-top: .2rem; }}
    summary {{ cursor: pointer; color: var(--accent); }}
    @media (max-width: 900px) {{
      .summary-head, .step-body {{ grid-template-columns: 1fr; }}
      .badges {{ justify-content: flex-start; }}
      .step-nav {{ top: 4.7rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AgentLens GUI-vs-CLI Trajectory Viewer</h1>
    <div class="source">Source: <code>{escape(str(source_path))}</code></div>
  </header>
  <main>
    {_render_summary(source_path, steps, result)}
    <nav class="step-nav">{nav}</nav>
    <div class="timeline">{cards}</div>
  </main>
</body>
</html>
"""


def _render_summary(source_path: Path, steps: list[dict[str, Any]], result: dict[str, Any]) -> str:
    run_id = source_path.parent.name
    first_extra = (steps[0].get("extra") if steps else {}) or {}
    metrics = [
        ("score", result.get("score")),
        ("ok", result.get("ok")),
        ("checks", _checks(result)),
        ("steps", len(steps)),
        ("elapsed", _elapsed(result.get("elapsed_seconds"))),
    ]
    cells = "\n".join(
        f'<div class="metric"><span>{escape(label)}</span><strong class="{_ok_class(label, value)}">{escape(_short(value))}</strong></div>'
        for label, value in metrics
        if value is not None
    )
    return f"""<section class="summary">
  <div class="summary-head">
    <div>
      <h2>{escape(run_id)}</h2>
      <div class="source">task={escape(str(result.get("task_id", "")))} · app={escape(str(result.get("app", "")))}</div>
    </div>
    <div class="badges">
      <span class="badge">mode: Computer-agent (gui-vs-cli)</span>
      <span class="badge">agent: {escape(str(result.get("agent", "")))}</span>
      <span class="badge">model: {escape(str(first_extra.get("model", "")))}</span>
      <span class="badge">backend: {escape(str(first_extra.get("interaction_backend", "")))}</span>
    </div>
  </div>
  <div class="meta">{cells}</div>
</section>"""


def _render_nav_link(step: dict[str, Any]) -> str:
    labels = _step_action_labels(step)
    title = " + ".join(labels) if labels else "step"
    return f'<a href="#step-{escape(str(step.get("step")))}">{escape(str(step.get("step")))} · {escape(_short(title, 26))}</a>'


def _render_step(step: dict[str, Any], *, output_path: Path) -> str:
    labels = _step_action_labels(step)
    action_summary = " + ".join(labels) if labels else "no action"
    screenshot = _render_screenshot(step, output_path=output_path)
    reasoning = _reasoning_text(step)
    return f"""<article class="step" id="step-{escape(str(step.get("step")))}">
  <div class="step-head">
    <strong>Step {escape(str(step.get("step")))}</strong>
    <span class="badge">{escape(action_summary)}</span>
  </div>
  <div class="step-body">
    <div class="shot">{screenshot}</div>
    <div class="details">
      {_panel("Reasoning", f'<div class="text-block">{escape(reasoning or "No reasoning text recorded.")}</div>')}
      {_panel("Actions", _render_actions(step))}
      {_panel("Action Results", _render_action_results(step))}
      {_panel("Raw Provider Response", _render_raw_response(step))}
    </div>
  </div>
</article>"""


def _render_screenshot(step: dict[str, Any], *, output_path: Path) -> str:
    path = step.get("screenshot_file")
    if not path:
        return '<div class="text-block">No screenshot recorded.</div>'
    src = _relative_artifact_src(str(path), output_path=output_path)
    return f'<img src="{escape(src)}" loading="lazy" alt="step {escape(str(step.get("step")))} screenshot">'


def _render_actions(step: dict[str, Any]) -> str:
    actions = step.get("actions") or []
    if not actions:
        return '<div class="text-block">No action recorded.</div>'
    rows = []
    for action in actions:
        label, detail = _action_label_detail(action)
        rows.append(
            f'<div class="action-line action-{escape(_css_token(label))}"><strong>{escape(label)}</strong>'
            f'<pre>{escape(detail)}</pre></div>'
        )
    return "\n".join(rows)


def _render_action_results(step: dict[str, Any]) -> str:
    results = step.get("action_results") or []
    if not results:
        return '<div class="text-block">No action result recorded.</div>'
    return f"<pre>{escape(_json(results))}</pre>"


def _render_raw_response(step: dict[str, Any]) -> str:
    raw = step.get("raw_response")
    if not raw:
        return '<div class="text-block">No raw response recorded.</div>'
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return f"<pre>{escape(str(raw))}</pre>"
    return f"<details><summary>Open raw response</summary><pre>{escape(_json(parsed))}</pre></details>"


def _panel(title: str, body: str) -> str:
    return f'<section class="panel"><h3>{escape(title)}</h3><div class="panel-body">{body}</div></section>'


def _step_action_labels(step: dict[str, Any]) -> list[str]:
    labels = []
    for action in step.get("actions") or []:
        label, _ = _action_label_detail(action)
        if label not in labels:
            labels.append(label)
    return labels


def _action_label_detail(action: dict[str, Any]) -> tuple[str, str]:
    if action.get("type") != "desktop_pyautogui":
        return str(action.get("type") or "action"), _json(action)
    code = str(action.get("code") or "")
    label = _pyautogui_label(code)
    detail = _pyautogui_detail(code)
    return label, detail or code.strip()


def _pyautogui_label(code: str) -> str:
    if "time.sleep" in code:
        return "wait"
    if "pyautogui.click" in code:
        return "click"
    if "pyautogui.doubleClick" in code:
        return "double_click"
    if "pyautogui.dragTo" in code or "pyautogui.dragRel" in code:
        return "drag"
    if "pyautogui.moveTo" in code or "pyautogui.moveRel" in code:
        return "move"
    if "pyautogui.scroll" in code or "pyautogui.hscroll" in code:
        return "scroll"
    if "pyautogui.typewrite" in code or "pyautogui.write" in code:
        return "type"
    if "pyautogui.hotkey" in code or "pyautogui.press" in code:
        return "keypress"
    return "script"


def _pyautogui_detail(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code.strip()

    calls = []
    typed_chars = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if not isinstance(owner, ast.Name) or owner.id not in {"pyautogui", "time"}:
            continue
        name = node.func.attr
        args = [_ast_value(arg) for arg in node.args]
        if owner.id == "pyautogui" and name == "press" and len(args) == 1:
            typed_chars.append(args[0])
            continue
        if owner.id == "pyautogui" and name in {"typewrite", "write"} and args:
            calls.append(f"type text={args[0]}")
        elif owner.id == "pyautogui" and name == "hotkey":
            calls.append("keypress keys=" + "+".join(args))
        elif owner.id == "pyautogui" and name in {"click", "doubleClick", "moveTo", "moveRel", "dragTo", "dragRel"}:
            calls.append(f"{name} args=" + ", ".join(args))
        elif owner.id == "pyautogui" and name in {"scroll", "hscroll"}:
            calls.append(f"{name} amount=" + ", ".join(args))
        elif owner.id == "time" and name == "sleep":
            calls.append("wait seconds=" + ", ".join(args))
        else:
            calls.append(f"{owner.id}.{name}(" + ", ".join(args) + ")")

    if typed_chars:
        text = "".join("\n" if char == "enter" else char for char in typed_chars)
        calls.insert(0, "keypress/type sequence=" + text)
    return "\n".join(calls)


def _ast_value(node: ast.AST) -> str:
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return ast.unparse(node)
    return str(value)


def _reasoning_text(step: dict[str, Any]) -> str:
    if step.get("reasoning"):
        return str(step["reasoning"])
    raw = step.get("raw_response")
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return ""
    provider = parsed.get("provider_response") or {}
    pieces = []
    for item in provider.get("content") or []:
        text = item.get("thinking") or item.get("text")
        if text:
            pieces.append(str(text))
    return "\n\n".join(pieces)


def _checks(result: dict[str, Any]) -> str | None:
    passed = result.get("checks_passed")
    total = result.get("checks_total")
    if passed is None or total is None:
        return None
    return f"{passed}/{total}"


def _elapsed(value: Any) -> str | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{seconds:.1f}s"


def _ok_class(label: str, value: Any) -> str:
    if label != "ok":
        return ""
    return "ok" if value else "bad"


def _relative_artifact_src(path: str, *, output_path: Path) -> str:
    artifact = Path(path)
    if not artifact.is_absolute():
        artifact = output_path.parent / artifact
    try:
        return Path(os.path.relpath(artifact, output_path.parent)).as_posix()
    except ValueError:
        return artifact.as_uri()


def _css_token(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)


def _short(value: Any, limit: int = 120) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)
