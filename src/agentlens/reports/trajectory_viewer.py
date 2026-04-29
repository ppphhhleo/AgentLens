from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from typing import Any


def write_trajectory_viewer(input_path: Path, output_path: Path | None = None) -> Path:
    """Render a static HTML trajectory viewer from summary.json or trajectory.json."""
    input_path = input_path.expanduser().resolve()
    data = json.loads(input_path.read_text(encoding="utf-8"))
    trajectories = _extract_trajectories(data)
    if not trajectories:
        raise ValueError(f"no trajectories found in {input_path}")

    if output_path is None:
        output_path = input_path.with_name("trajectory_viewer.html")
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _render_page(trajectories, source_path=input_path, output_path=output_path),
        encoding="utf-8",
    )
    return output_path


def _extract_trajectories(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "events" in data and "run_id" in data:
        return [data]
    if "trajectory" in data and isinstance(data["trajectory"], dict):
        return [data["trajectory"]]
    if "run_results" in data and isinstance(data["run_results"], list):
        trajectories = []
        for run_result in data["run_results"]:
            if isinstance(run_result, dict) and isinstance(run_result.get("trajectory"), dict):
                trajectories.append(run_result["trajectory"])
        return trajectories
    return []


def _render_page(
    trajectories: list[dict[str, Any]], *, source_path: Path, output_path: Path
) -> str:
    run_nav = "\n".join(
        f'<a href="#run-{idx}">{escape(str(traj.get("run_id", f"run-{idx}")))}</a>'
        for idx, traj in enumerate(trajectories, start=1)
    )
    run_sections = "\n".join(
        _render_trajectory(traj, idx=idx, output_path=output_path)
        for idx, traj in enumerate(trajectories, start=1)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentLens Trajectory Viewer</title>
  <style>
    :root {{
      --bg: #11120f;
      --panel: #1b1d18;
      --panel-2: #24271f;
      --text: #f1f0e8;
      --muted: #a9aa9e;
      --line: #363a30;
      --accent: #f5b642;
      --ok: #79c267;
      --bad: #e3655b;
      --code: #0d0e0c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(245,182,66,.14), transparent 34rem),
        linear-gradient(135deg, #11120f 0%, #171913 55%, #0d0e0c 100%);
      color: var(--text);
      font: 14px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      padding: 1rem 1.5rem;
      background: rgba(17, 18, 15, .92);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 1.35rem; letter-spacing: -.02em; }}
    a {{ color: var(--accent); text-decoration: none; }}
    .source {{ color: var(--muted); margin-top: .25rem; }}
    .run-nav {{
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      margin-top: .75rem;
    }}
    .run-nav a, .badge {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: .2rem .55rem;
      background: var(--panel-2);
      color: var(--text);
      font-size: .8rem;
    }}
    main {{ max-width: 1500px; margin: 0 auto; padding: 1.25rem; }}
    .run {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(27,29,24,.88);
      overflow: hidden;
      margin-bottom: 1.25rem;
      box-shadow: 0 20px 60px rgba(0,0,0,.25);
    }}
    .run-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 1rem;
      padding: 1rem;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, rgba(245,182,66,.10), transparent);
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: .5rem;
      padding: 1rem;
      border-bottom: 1px solid var(--line);
    }}
    .metric {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: .7rem;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: .75rem; }}
    .goal {{
      margin: 0 1rem 1rem;
      padding: .8rem;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(0,0,0,.18);
      white-space: pre-wrap;
    }}
    .tool-map {{
      margin: 1rem;
      padding: .85rem;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(0,0,0,.20);
    }}
    .tool-map-head {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: baseline;
      margin-bottom: .65rem;
    }}
    .tool-map-title {{ font-weight: 800; letter-spacing: -.01em; }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: .4rem .75rem;
      color: var(--muted);
      font-size: .78rem;
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: .3rem;
    }}
    .dot {{
      width: .65rem;
      height: .65rem;
      border-radius: 999px;
      display: inline-block;
      background: var(--kind-color, var(--line));
    }}
    .tool-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(3.7rem, 1fr));
      gap: .35rem;
    }}
    .tool-cell {{
      min-height: 3.8rem;
      border: 1px solid color-mix(in srgb, var(--kind-color, var(--line)) 68%, var(--line));
      border-radius: 10px;
      padding: .4rem;
      background:
        linear-gradient(180deg, color-mix(in srgb, var(--kind-color, #333) 24%, transparent), transparent),
        rgba(0,0,0,.18);
      color: var(--text);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: .2rem;
    }}
    .tool-cell:hover {{
      outline: 2px solid var(--kind-color);
      outline-offset: 1px;
    }}
    .tool-step {{ color: var(--muted); font-size: .72rem; }}
    .tool-label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 750;
      font-size: .82rem;
    }}
    .tool-sub {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: .72rem;
    }}
    .kind-browser {{ --kind-color: #5db7de; }}
    .kind-code {{ --kind-color: #f5b642; }}
    .kind-file {{ --kind-color: #b391ff; }}
    .kind-web {{ --kind-color: #64d6a4; }}
    .kind-model {{ --kind-color: #d6d166; }}
    .kind-screenshot {{ --kind-color: #7d8794; }}
    .kind-validation {{ --kind-color: #79c267; }}
    .kind-error {{ --kind-color: #e3655b; }}
    .kind-final {{ --kind-color: #ff8ec7; }}
    .kind-other {{ --kind-color: #9ea39a; }}
    .timeline {{ padding: 1rem; }}
    .event {{
      display: grid;
      grid-template-columns: minmax(320px, 48%) minmax(320px, 1fr);
      gap: 1rem;
      border-left: 3px solid var(--line);
      margin-left: .5rem;
      padding: 0 0 1rem 1rem;
    }}
    .event.interesting {{ border-left-color: var(--accent); }}
    .event-head {{
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: .5rem;
    }}
    .event-type {{ color: var(--accent); font-weight: 700; }}
    .timestamp {{ color: var(--muted); font-size: .78rem; }}
    .screenshot {{
      position: relative;
      background: #000;
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
    }}
    .screenshot img {{ display: block; width: 100%; height: auto; }}
    .marker {{
      position: absolute;
      width: 20px;
      height: 20px;
      margin-left: -10px;
      margin-top: -10px;
      border: 3px solid var(--bad);
      border-radius: 50%;
      box-shadow: 0 0 0 8px rgba(227,101,91,.25);
      pointer-events: none;
    }}
    .empty-shot {{
      min-height: 8rem;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 12px;
      background: rgba(0,0,0,.16);
    }}
    .details {{
      min-width: 0;
      background: rgba(0,0,0,.18);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: .8rem;
    }}
    .thought {{ white-space: pre-wrap; margin: .4rem 0 .7rem; }}
    pre {{
      max-height: 24rem;
      overflow: auto;
      margin: .5rem 0 0;
      padding: .75rem;
      border-radius: 10px;
      background: var(--code);
      border: 1px solid #2b2e27;
      color: #e9eadf;
      font-size: .78rem;
    }}
    details {{ margin-top: .6rem; }}
    summary {{ cursor: pointer; color: var(--accent); }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    @media (max-width: 900px) {{
      .run-head, .event {{ grid-template-columns: 1fr; }}
      main {{ padding: .75rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AgentLens Trajectory Viewer</h1>
    <div class="source">Source: <code>{escape(str(source_path))}</code></div>
    <nav class="run-nav">{run_nav}</nav>
  </header>
  <main>{run_sections}</main>
</body>
</html>
"""


def _render_trajectory(traj: dict[str, Any], *, idx: int, output_path: Path) -> str:
    events = traj.get("events") or []
    action_by_step = _action_by_step(events)
    event_cards = "\n".join(
        _render_event(event, output_path=output_path, action_by_step=action_by_step)
        for event in events
    )
    metrics = traj.get("metrics") or {}
    task = traj.get("task") or {}
    model = traj.get("model") or {}
    tool_harness = traj.get("tool_harness") or {}
    memory_harness = traj.get("memory_harness") or {}
    success = metrics.get("success")
    success_class = "ok" if success else "bad"
    goal = task.get("goal") or _first_goal(events) or ""

    metric_cards = {
        "score": metrics.get("score"),
        "success": success,
        "steps": metrics.get("steps"),
        "tool calls": metrics.get("tool_calls"),
        "duration ms": metrics.get("duration_ms"),
        "tokens in": metrics.get("tokens_input"),
        "tokens out": metrics.get("tokens_output"),
        "cost usd": metrics.get("cost_usd"),
    }
    metric_html = "\n".join(
        f'<div class="metric"><span>{escape(label)}</span><strong class="{success_class if label == "success" else ""}">{escape(_short(value))}</strong></div>'
        for label, value in metric_cards.items()
        if value is not None
    )

    return f"""<section class="run" id="run-{idx}">
  <div class="run-head">
    <div>
      <h2>{escape(str(traj.get("run_id", f"run-{idx}")))}</h2>
      <div class="source">{escape(str(traj.get("experiment_id", "")))} · task={escape(str(task.get("id", "")))}</div>
    </div>
    <div>
      <span class="badge">model: {escape(str(model.get("name") or model.get("id") or ""))}</span>
      <span class="badge">tools: {escape(str(tool_harness.get("tier") or tool_harness.get("id") or ""))}</span>
      <span class="badge">memory: {escape(str(memory_harness.get("kind") or memory_harness.get("id") or ""))}</span>
    </div>
  </div>
  <div class="meta-grid">{metric_html}</div>
  {_render_tool_map(events)}
  {_render_goal(goal)}
  <div class="timeline">{event_cards}</div>
</section>"""


def _render_event(
    event: dict[str, Any],
    *,
    output_path: Path,
    action_by_step: dict[int, dict[str, Any]],
) -> str:
    event_type = str(event.get("event_type", "event"))
    data = event.get("data") or {}
    step = event.get("step_index")
    action = data.get("action") if isinstance(data.get("action"), dict) else None
    tool_name = data.get("tool_name") or _tool_name_from_action(action)
    marker_action = action_by_step.get(step) if isinstance(step, int) else None
    screenshot_html = _render_screenshot(event, output_path=output_path, marker_action=marker_action)
    details_html = _render_event_details(event)
    interesting = event_type in {
        "model_message",
        "tool_call",
        "browser_action",
        "validation_event",
        "gating_violation",
        "user_intervention",
    }
    event_id = _event_anchor(event)
    return f"""<article class="event {'interesting' if interesting else ''}" id="{escape(event_id)}">
  <div>
    <div class="event-head">
      <span class="event-type">{escape(event_type)}</span>
      <span class="badge">step {escape(_short(step))}</span>
      {_badge(tool_name) if tool_name else ""}
      <span class="timestamp">{escape(str(event.get("timestamp", "")))}</span>
    </div>
    {screenshot_html}
  </div>
  <div class="details">{details_html}</div>
</article>"""


def _render_tool_map(events: list[dict[str, Any]]) -> str:
    cells = "\n".join(_render_tool_cell(event) for event in events)
    if not cells:
        return ""
    legend = "\n".join(
        f'<span class="kind-{kind}"><i class="dot"></i>{label}</span>'
        for kind, label in [
            ("browser", "browser"),
            ("code", "code"),
            ("file", "files"),
            ("web", "web"),
            ("model", "model"),
            ("screenshot", "screenshot"),
            ("final", "final"),
            ("validation", "validation"),
            ("error", "error"),
        ]
    )
    return f"""<section class="tool-map">
  <div class="tool-map-head">
    <div class="tool-map-title">Tool / Action Timeline</div>
    <div class="legend">{legend}</div>
  </div>
  <div class="tool-strip">{cells}</div>
</section>"""


def _render_tool_cell(event: dict[str, Any]) -> str:
    label, sublabel, kind = _event_tool_label(event)
    step = event.get("step_index")
    return f"""<a class="tool-cell kind-{kind}" href="#{escape(_event_anchor(event))}" title="{escape(label + ' ' + sublabel)}">
  <span class="tool-step">step {escape(_short(step))}</span>
  <span class="tool-label">{escape(label)}</span>
  <span class="tool-sub">{escape(sublabel)}</span>
</a>"""


def _event_tool_label(event: dict[str, Any]) -> tuple[str, str, str]:
    event_type = str(event.get("event_type", "event"))
    data = event.get("data") or {}
    action = data.get("action") if isinstance(data.get("action"), dict) else None
    tool_name = data.get("tool_name") or _tool_name_from_action(action)

    if event_type == "model_message":
        action_type = action.get("type") if action else None
        return "model", str(action_type or "message"), "model"
    if event_type == "screenshot":
        return "screenshot", str(data.get("url") or ""), "screenshot"
    if event_type == "validation_event":
        ok = data.get("success", data.get("ok", ""))
        return "validation", f"success={ok}", "validation"
    if event_type == "gating_violation":
        return "gating", str(tool_name or "blocked"), "error"
    if event_type == "browser_action":
        action_type = action.get("type") if action else None
        return str(tool_name or "browser"), str(action_type or ""), "browser"
    if event_type == "tool_call":
        return str(tool_name or "tool"), _tool_subtitle(data), _kind_for_tool(str(tool_name or ""))
    if event_type == "user_intervention":
        return "user", str(data.get("action") or data.get("decision") or ""), "other"
    if tool_name:
        return str(tool_name), _tool_subtitle(data), _kind_for_tool(str(tool_name))
    return event_type, "", "other"


def _tool_subtitle(data: dict[str, Any]) -> str:
    if data.get("error"):
        return "error"
    action = data.get("action") if isinstance(data.get("action"), dict) else {}
    for key in ("query", "cmd", "file_path", "url", "answer"):
        value = action.get(key) or data.get(key)
        if value:
            return _short(value, 42)
    action_type = action.get("type")
    if action_type:
        return str(action_type)
    if data.get("ok") is not None:
        return f"ok={data.get('ok')}"
    return ""


def _kind_for_tool(tool_name: str) -> str:
    if tool_name.startswith("browser."):
        return "browser"
    if tool_name.startswith("code."):
        return "code"
    if tool_name.startswith("files."):
        return "file"
    if tool_name.startswith("web."):
        return "web"
    if tool_name == "task.final_answer":
        return "final"
    return "other"


def _event_anchor(event: dict[str, Any]) -> str:
    event_id = str(event.get("event_id") or "")
    if event_id:
        return f"event-{event_id}"
    return f"event-step-{_short(event.get('step_index'))}-{_short(event.get('event_type'))}"


def _render_screenshot(
    event: dict[str, Any], *, output_path: Path, marker_action: dict[str, Any] | None
) -> str:
    image_paths = [
        path
        for path in event.get("artifact_paths") or []
        if str(path).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]
    if not image_paths:
        return '<div class="empty-shot">No screenshot for this event</div>'

    image_src = _relative_artifact_src(image_paths[0], output_path=output_path)
    marker = ""
    if marker_action and marker_action.get("x") is not None and marker_action.get("y") is not None:
        viewport = (event.get("data") or {}).get("viewport") or {}
        width = viewport.get("width") or 1600
        height = viewport.get("height") or 900
        try:
            left = float(marker_action["x"]) / float(width) * 100
            top = float(marker_action["y"]) / float(height) * 100
            marker = f'<span class="marker" style="left:{left:.3f}%; top:{top:.3f}%"></span>'
        except (TypeError, ValueError, ZeroDivisionError):
            marker = ""
    return f'<div class="screenshot"><img src="{escape(image_src)}" loading="lazy">{marker}</div>'


def _render_event_details(event: dict[str, Any]) -> str:
    data = event.get("data") or {}
    pieces: list[str] = []
    thought = data.get("thought")
    if thought:
        pieces.append(f"<strong>Thought</strong><div class=\"thought\">{escape(str(thought))}</div>")

    for label, key in [
        ("URL", "url"),
        ("Output", "output"),
        ("Error", "error"),
        ("Answer", "answer"),
    ]:
        value = data.get(key)
        if value not in (None, ""):
            pieces.append(f"<strong>{label}</strong><pre>{escape(_short_block(value))}</pre>")

    action = data.get("action")
    if action:
        pieces.append(f"<strong>Action</strong><pre>{escape(_json(action))}</pre>")

    raw = data.get("raw_response")
    if raw:
        pieces.append(
            f"<details><summary>Raw model response</summary><pre>{escape(_short_block(raw, 6000))}</pre></details>"
        )

    remaining = {
        key: value
        for key, value in data.items()
        if key
        not in {
            "thought",
            "action",
            "raw_response",
            "url",
            "output",
            "error",
            "answer",
        }
    }
    if remaining:
        pieces.append(
            f"<details><summary>Event data</summary><pre>{escape(_json(remaining))}</pre></details>"
        )

    if not pieces:
        pieces.append("<span class=\"source\">No structured event details.</span>")
    return "\n".join(pieces)


def _action_by_step(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    actions: dict[int, dict[str, Any]] = {}
    for event in events:
        step = event.get("step_index")
        if not isinstance(step, int):
            continue
        data = event.get("data") or {}
        action = data.get("action")
        if isinstance(action, dict) and action.get("x") is not None and action.get("y") is not None:
            actions[step] = action
    return actions


def _first_goal(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        goal = (event.get("data") or {}).get("goal")
        if goal:
            return str(goal)
    return None


def _render_goal(goal: str) -> str:
    if not goal:
        return ""
    return f'<section class="goal"><strong>Goal</strong>\n{escape(goal)}</section>'


def _relative_artifact_src(path: str, *, output_path: Path) -> str:
    artifact = Path(path)
    if not artifact.is_absolute():
        artifact = Path.cwd() / artifact
    try:
        return Path(os.path.relpath(artifact, output_path.parent)).as_posix()
    except ValueError:
        return artifact.as_posix()


def _tool_name_from_action(action: dict[str, Any] | None) -> str | None:
    if not action:
        return None
    action_type = action.get("type")
    if not action_type:
        return None
    if action_type == "final_answer":
        return "task.final_answer"
    if action_type in {"run_python", "shell"}:
        return f"code.{action_type}"
    if action_type in {"read_file", "write_file"}:
        return f"files.{action_type}"
    if action_type == "web_search":
        return "web.openai_search"
    return f"browser.{action_type}"


def _badge(value: Any) -> str:
    return f'<span class="badge">{escape(_short(value))}</span>'


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _short(value: Any, limit: int = 120) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _short_block(value: Any, limit: int = 3000) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"
