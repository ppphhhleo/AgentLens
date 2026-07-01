from __future__ import annotations

import json
import os
import re
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
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-2: #f9fafc;
      --text: #171a1f;
      --muted: #677080;
      --line: #dfe4ec;
      --line-strong: #c9d1dc;
      --accent: #2563eb;
      --ok: #168a4a;
      --bad: #d23f31;
      --code: #f3f5f8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        linear-gradient(180deg, #ffffff 0, var(--bg) 18rem),
        var(--bg);
      color: var(--text);
      font: 13px/1.42 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      padding: .75rem 1rem;
      background: rgba(255, 255, 255, .92);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 1.05rem; letter-spacing: 0; }}
    a {{ color: var(--accent); text-decoration: none; }}
    .source {{
      color: var(--muted);
      margin-top: .2rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .run-nav {{
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      margin-top: .45rem;
    }}
    .run-nav a, .badge {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: .16rem .42rem;
      background: var(--panel-2);
      color: var(--text);
      font-size: .76rem;
    }}
    main {{ max-width: 1400px; margin: 0 auto; padding: .75rem; }}
    .run {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      overflow: hidden;
      margin-bottom: .75rem;
      box-shadow: 0 14px 34px rgba(28, 38, 57, .08);
    }}
    .run-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: .75rem;
      padding: .65rem .75rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    .run-head h2 {{
      font-size: 1.04rem;
      letter-spacing: 0;
      line-height: 1.2;
    }}
    .run-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: .3rem;
      justify-content: flex-end;
    }}
    .meta-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: .25rem .7rem;
      padding: .45rem .75rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }}
    .metric {{
      display: inline-flex;
      align-items: baseline;
      gap: .32rem;
      min-width: max-content;
      color: var(--text);
    }}
    .metric span {{ color: var(--muted); font-size: .72rem; }}
    .metric strong {{ font-size: .82rem; }}
    .goal {{
      margin: .65rem .75rem .55rem;
      padding: .45rem .55rem;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel-2);
      white-space: pre-wrap;
    }}
    .tool-map {{
      margin: .55rem .75rem;
      padding: .5rem;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel-2);
    }}
    .tool-map > summary {{
      cursor: pointer;
      color: var(--text);
      font-weight: 700;
      list-style-position: inside;
    }}
    .tool-map > summary span {{
      color: var(--muted);
      font-weight: 450;
      margin-left: .4rem;
      font-size: .76rem;
    }}
    .tool-map-head {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: baseline;
      margin: .55rem 0 .45rem;
    }}
    .tool-map-title {{ font-weight: 700; letter-spacing: 0; }}
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
      width: .55rem;
      height: .55rem;
      border-radius: 999px;
      display: inline-block;
      background: var(--kind-color, var(--line));
    }}
    .tool-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(3rem, 1fr));
      gap: .22rem;
    }}
    .tool-cell {{
      min-height: 2.65rem;
      border: 1px solid color-mix(in srgb, var(--kind-color, var(--line)) 54%, var(--line));
      border-radius: 6px;
      padding: .25rem .3rem;
      background: #fff;
      color: var(--text);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: .2rem;
    }}
    .tool-cell:hover {{
      outline: 2px solid color-mix(in srgb, var(--kind-color) 70%, white);
      outline-offset: 1px;
    }}
    .tool-step {{ color: var(--muted); font-size: .68rem; }}
    .tool-label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 750;
      font-size: .76rem;
    }}
    .tool-sub {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: .68rem;
    }}
    .step-log {{
      display: grid;
      gap: .45rem;
    }}
    .step-triplet {{
      border: 1px solid var(--line);
      border-left: 3px solid var(--kind-color, var(--line-strong));
      border-radius: 7px;
      background: #fff;
      overflow: hidden;
    }}
    .step-triplet-head {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: .35rem;
      padding: .34rem .45rem;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--kind-color, var(--line)) 7%, white);
    }}
    .step-triplet-head strong {{
      color: var(--kind-color, var(--text));
    }}
    .triplet-grid {{
      display: grid;
      grid-template-columns: minmax(170px, .78fr) minmax(220px, 1fr) minmax(220px, 1fr);
      gap: .45rem;
      padding: .45rem;
    }}
    .triplet-cell {{
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: .4rem;
      background: var(--panel-2);
    }}
    .triplet-cell h4 {{
      margin: 0 0 .28rem;
      color: var(--muted);
      font-size: .68rem;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    .triplet-cell p {{
      margin: 0;
      color: var(--text);
      font-size: .76rem;
    }}
    .triplet-shot {{
      display: block;
      max-width: 100%;
      max-height: 130px;
      object-fit: contain;
      border: 1px solid var(--line);
      border-radius: 5px;
      background: #fff;
    }}
    .triplet-meta {{
      color: var(--muted);
      font-size: .7rem;
      margin-top: .3rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .kind-browser {{ --kind-color: #0ea5e9; }}
    .kind-desktop {{ --kind-color: #475569; }}
    .kind-code {{ --kind-color: #d97706; }}
    .kind-file {{ --kind-color: #8b5cf6; }}
    .kind-web {{ --kind-color: #059669; }}
    .kind-model {{ --kind-color: #64748b; }}
    .kind-screenshot {{ --kind-color: #94a3b8; }}
    .kind-validation {{ --kind-color: #16a34a; }}
    .kind-error {{ --kind-color: #dc2626; }}
    .kind-final {{ --kind-color: #db2777; }}
    .kind-other {{ --kind-color: #737373; }}
    .action-click {{ --kind-color: #0ea5e9; }}
    .action-double_click {{ --kind-color: #06b6d4; }}
    .action-scroll {{ --kind-color: #16a34a; }}
    .action-keypress {{ --kind-color: #f59e0b; }}
    .action-type {{ --kind-color: #8b5cf6; }}
    .action-move {{ --kind-color: #6366f1; }}
    .action-drag {{ --kind-color: #ef4444; }}
    .action-wait {{ --kind-color: #64748b; }}
    .action-screenshot {{ --kind-color: #94a3b8; }}
    .action-goto {{ --kind-color: #059669; }}
    .action-back, .action-forward, .action-reload {{ --kind-color: #0f766e; }}
    .action-final_answer {{ --kind-color: #db2777; }}
    .action-run_python, .action-shell {{ --kind-color: #d97706; }}
    .action-read_file, .action-write_file {{ --kind-color: #8b5cf6; }}
    .action-web_search {{ --kind-color: #059669; }}
    .action-mcp_tool {{ --kind-color: #7c3aed; }}
    .action-desktop_screenshot {{ --kind-color: #94a3b8; }}
    .action-desktop_click {{ --kind-color: #0284c7; }}
    .action-desktop_double_click {{ --kind-color: #0891b2; }}
    .action-desktop_scroll {{ --kind-color: #15803d; }}
    .action-desktop_move {{ --kind-color: #4f46e5; }}
    .action-desktop_drag {{ --kind-color: #dc2626; }}
    .action-desktop_type {{ --kind-color: #7c3aed; }}
    .action-desktop_keypress {{ --kind-color: #d97706; }}
    .action-desktop_launch_app {{ --kind-color: #0f766e; }}
    .action-desktop_pyautogui {{ --kind-color: #475569; }}
    .action-desktop_shell {{ --kind-color: #b45309; }}
    .action-desktop_wait {{ --kind-color: #64748b; }}
    .action-pyautogui_wait {{ --kind-color: #64748b; }}
    .action-pyautogui_click {{ --kind-color: #0284c7; }}
    .action-pyautogui_double_click {{ --kind-color: #0891b2; }}
    .action-pyautogui_drag {{ --kind-color: #dc2626; }}
    .action-pyautogui_move {{ --kind-color: #4f46e5; }}
    .action-pyautogui_type {{ --kind-color: #7c3aed; }}
    .action-pyautogui_keypress {{ --kind-color: #d97706; }}
    .action-pyautogui_hotkey {{ --kind-color: #d97706; }}
    .action-pyautogui_screenshot {{ --kind-color: #94a3b8; }}
    .action-pyautogui_script {{ --kind-color: #475569; }}
    .round-index {{
      position: sticky;
      top: 3.9rem;
      z-index: 4;
      margin: 0 .75rem .55rem;
      padding: .45rem;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: rgba(255, 255, 255, .95);
      backdrop-filter: blur(10px);
    }}
    .round-index-head {{
      display: flex;
      justify-content: space-between;
      gap: .7rem;
      color: var(--muted);
      font-size: .74rem;
      margin: 0 .1rem .35rem;
    }}
    .round-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: .3rem .65rem;
      color: var(--muted);
      font-size: .7rem;
      margin: 0 .15rem .4rem;
    }}
    .round-legend span {{
      display: inline-flex;
      align-items: center;
      gap: .25rem;
    }}
    .round-links {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(4.05rem, 1fr));
      gap: .2rem;
      max-height: 6.4rem;
      overflow: auto;
      padding-right: .15rem;
    }}
    .round-link {{
      display: flex;
      min-width: 0;
      align-items: center;
      justify-content: space-between;
      gap: .25rem;
      border: 1px solid color-mix(in srgb, var(--kind-color) 34%, var(--line));
      border-left: 3px solid var(--kind-color, var(--accent));
      border-radius: 6px;
      padding: .2rem .3rem;
      background: #fff;
      color: var(--text);
      font-size: .72rem;
    }}
    .round-link:hover {{ background: color-mix(in srgb, var(--kind-color) 8%, white); }}
    .round-link strong {{ font-size: .72rem; }}
    .round-link span {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
    }}
    .timeline {{ padding: 0 .75rem .75rem; }}
    .event {{
      --round-color: var(--kind-color, var(--accent));
      scroll-margin-top: 15rem;
      border: 1px solid var(--line);
      border-left: 3px solid var(--line);
      border-radius: 8px;
      margin: 0 0 .55rem;
      background: var(--panel);
      overflow: hidden;
    }}
    .event.interesting {{ border-left-color: var(--round-color, var(--accent)); }}
    .event-head {{
      display: flex;
      gap: .35rem;
      flex-wrap: wrap;
      align-items: center;
      padding: .38rem .52rem;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--round-color, var(--accent)) 7%, white);
    }}
    .event-type {{ color: var(--round-color, var(--accent)); font-weight: 750; }}
    .event-title {{ min-width: 5.8rem; }}
    .timestamp {{ color: var(--muted); font-size: .78rem; }}
    .event-body {{
      display: grid;
      grid-template-columns: minmax(260px, 40%) minmax(320px, 1fr);
      gap: .55rem;
      padding: .5rem;
    }}
    .screenshot {{
      position: relative;
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 7px;
      overflow: hidden;
    }}
    .screenshot img {{
      display: block;
      width: 100%;
      max-height: 330px;
      height: auto;
      object-fit: contain;
    }}
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
      min-height: 5rem;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 7px;
      background: var(--panel-2);
    }}
    .details {{
      min-width: 0;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: .5rem;
    }}
    .round-summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(7.8rem, 1fr));
      gap: .28rem;
      margin-bottom: .42rem;
    }}
    .round-stat {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: .28rem .35rem;
      background: var(--panel-2);
      min-width: 0;
    }}
    .round-stat span {{
      display: block;
      color: var(--muted);
      font-size: .66rem;
    }}
    .round-stat strong {{
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: .76rem;
    }}
    .event-note {{
      color: var(--muted);
      font-size: .75rem;
      margin-top: .35rem;
    }}
    .thought {{
      white-space: pre-wrap;
      margin: .22rem 0 .4rem;
      max-height: 7.8rem;
      overflow: auto;
    }}
    pre {{
      max-height: 12rem;
      overflow: auto;
      margin: .3rem 0 0;
      padding: .5rem;
      border-radius: 7px;
      background: var(--code);
      border: 1px solid var(--line);
      color: #1f2937;
      font-size: .74rem;
    }}
    details {{ margin-top: .4rem; }}
    summary {{ cursor: pointer; color: var(--accent); }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    @media (max-width: 900px) {{
      .run-head, .event-body {{ grid-template-columns: 1fr; }}
      .triplet-grid {{ grid-template-columns: 1fr; }}
      .round-index {{ position: static; }}
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
    event_cards = _render_compact_timeline(
        events,
        output_path=output_path,
        action_by_step=action_by_step,
    )
    metrics = traj.get("metrics") or {}
    task = traj.get("task") or {}
    model = traj.get("model") or {}
    tool_harness = traj.get("tool_harness") or {}
    memory_harness = traj.get("memory_harness") or {}
    success = metrics.get("success")
    success_class = "ok" if success else "bad"
    goal = task.get("goal") or _first_goal(events) or ""
    viewpoint = _trajectory_viewpoint(traj)

    metric_cards = {
        "score": metrics.get("score"),
        "success": success,
        "rounds": metrics.get("steps"),
        "executed actions": metrics.get("tool_calls"),
        "viewpoint": viewpoint.get("source"),
        "frame": viewpoint.get("frame"),
        "size": viewpoint.get("size"),
        "duration": _format_duration_ms(metrics.get("duration_ms")),
        "tokens": _format_token_pair(metrics.get("tokens_input"), metrics.get("tokens_output")),
        "cost": metrics.get("cost_usd"),
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
    <div class="run-badges">
      <span class="badge">model: {escape(str(model.get("name") or model.get("id") or ""))}</span>
      <span class="badge">tools: {escape(str(tool_harness.get("tier") or tool_harness.get("id") or ""))}</span>
      <span class="badge">memory: {escape(str(memory_harness.get("kind") or memory_harness.get("id") or ""))}</span>
    </div>
  </div>
  <div class="meta-grid">{metric_html}</div>
  {_render_goal(goal)}
  {_render_round_index(events)}
  {_render_tool_map(events, output_path=output_path)}
  <div class="timeline">{event_cards}</div>
</section>"""


def _render_compact_timeline(
    events: list[dict[str, Any]],
    *,
    output_path: Path,
    action_by_step: dict[int, dict[str, Any]],
) -> str:
    by_step: dict[int, list[dict[str, Any]]] = {}
    tail_events: list[dict[str, Any]] = []
    for event in events:
        step = event.get("step_index")
        if isinstance(step, int):
            by_step.setdefault(step, []).append(event)
        elif event.get("event_type") in {"validation_event", "gating_violation"}:
            tail_events.append(event)

    cards: list[str] = []
    for step in sorted(by_step):
        step_events = by_step[step]
        model_event = next(
            (event for event in step_events if event.get("event_type") == "model_message"),
            None,
        )
        if model_event is None:
            continue
        cards.append(
            _render_round_card(
                model_event,
                step_events=step_events,
                output_path=output_path,
                marker_action=action_by_step.get(step),
            )
        )

    for event in tail_events:
        cards.append(
            _render_event(event, output_path=output_path, action_by_step=action_by_step)
        )
    return "\n".join(cards)


def _render_round_card(
    model_event: dict[str, Any],
    *,
    step_events: list[dict[str, Any]],
    output_path: Path,
    marker_action: dict[str, Any] | None,
) -> str:
    data = model_event.get("data") or {}
    step = model_event.get("step_index")
    screenshots = [
        event for event in step_events if event.get("event_type") == "screenshot"
    ]
    browser_events = [
        event for event in step_events if event.get("event_type") == "browser_action"
    ]
    tool_events = [event for event in step_events if event.get("event_type") == "tool_call"]
    intervention_events = [
        event for event in step_events if event.get("event_type") == "user_intervention"
    ]
    screenshot_event = screenshots[-1] if screenshots else model_event
    action_summary = _round_action_summary(data)
    action_kind = _action_kind(_first_action_from_event(model_event))
    tool_names = [
        name
        for name in (data.get("tool_names") or [])
        if isinstance(name, str) and not name.startswith("browser.")
    ]
    tool_badges = "".join(_badge(name) for name in tool_names)
    if intervention_events:
        tool_badges += _badge(f"{len(intervention_events)} warning(s)")

    event_id = _event_anchor(model_event)
    return f"""<article class="event interesting {escape(action_kind)}" id="{escape(event_id)}">
  <div class="event-head">
    <span class="event-type event-title">Round {escape(_short(step))}</span>
    <span class="badge">{escape(action_summary)}</span>
    {tool_badges}
    <span class="timestamp">{escape(str(model_event.get("timestamp", "")))}</span>
  </div>
  <div class="event-body">
    <div>
    {_render_screenshot(screenshot_event, output_path=output_path, marker_action=marker_action)}
    </div>
    <div class="details">{_render_round_details(model_event, browser_events, tool_events, intervention_events)}</div>
  </div>
</article>"""


def _render_round_details(
    model_event: dict[str, Any],
    browser_events: list[dict[str, Any]],
    tool_events: list[dict[str, Any]],
    intervention_events: list[dict[str, Any]],
) -> str:
    data = model_event.get("data") or {}
    pieces: list[str] = []
    pieces.append(_render_round_summary(model_event, browser_events, tool_events, intervention_events))
    thought = data.get("thought") or data.get("reasoning")
    if thought:
        pieces.append(f"<strong>Reasoning</strong><div class=\"thought\">{escape(str(thought))}</div>")

    actions = data.get("actions") or ([data.get("action")] if data.get("action") else [])
    if actions:
        pieces.append(
            "<strong>Actions</strong>"
            f"<pre>{escape(chr(10).join(_format_action_line(action) for action in actions if action))}</pre>"
        )

    errors = [
        (event.get("data") or {}).get("error")
        for event in browser_events + tool_events
        if (event.get("data") or {}).get("error")
    ]
    if errors:
        pieces.append(f"<strong>Error</strong><pre>{escape(chr(10).join(map(str, errors)))}</pre>")

    if intervention_events:
        messages = [
            (event.get("data") or {}).get("message")
            for event in intervention_events
            if (event.get("data") or {}).get("message")
        ]
        pieces.append(
            "<strong>Warnings</strong>"
            f"<pre>{escape(chr(10).join(messages) or str(len(intervention_events)))}</pre>"
        )

    raw_bundle = {
        "model_event": model_event,
        "browser_events": browser_events,
        "tool_events": tool_events,
        "intervention_events": intervention_events,
    }
    pieces.append(
        f"<details><summary>Raw round events</summary><pre>{escape(_json(raw_bundle))}</pre></details>"
    )
    return "\n".join(pieces)


def _render_round_summary(
    model_event: dict[str, Any],
    browser_events: list[dict[str, Any]],
    tool_events: list[dict[str, Any]],
    intervention_events: list[dict[str, Any]],
) -> str:
    data = model_event.get("data") or {}
    actions = data.get("actions") or ([data.get("action")] if data.get("action") else [])
    action_text = _round_action_summary(data)
    error_count = sum(
        1
        for event in browser_events + tool_events
        if (event.get("data") or {}).get("error")
    )
    stats = [
        ("action", action_text),
        ("executed actions", len(browser_events) + len(tool_events)),
        ("tool calls", len(tool_events)),
        ("warnings", len(intervention_events)),
        ("errors", error_count),
    ]
    if actions:
        stats.insert(1, ("first target", _format_action_line(actions[0])))
    cells = "\n".join(
        f'<div class="round-stat"><span>{escape(label)}</span><strong>{escape(_short(value, 90))}</strong></div>'
        for label, value in stats
    )
    return f'<section class="round-summary">{cells}</section>'


def _round_action_summary(data: dict[str, Any]) -> str:
    actions = data.get("actions") or ([data.get("action")] if data.get("action") else [])
    labels = [_action_label(action) for action in actions if isinstance(action, dict)]
    if not labels:
        return "model"
    if len(labels) <= 3:
        return " + ".join(labels)
    return " + ".join(labels[:3]) + f" + {len(labels) - 3} more"


def _format_action_line(action: dict[str, Any]) -> str:
    label = _action_label(action)
    detail = _action_detail(action)
    return f"{label} | {detail}" if detail else label


def _format_duration_ms(value: Any) -> str | None:
    if value is None:
        return None
    try:
        seconds = float(value) / 1000
    except (TypeError, ValueError):
        return str(value)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = int(round(seconds % 60))
    return f"{minutes}m {remainder}s"


def _format_token_pair(tokens_input: Any, tokens_output: Any) -> str | None:
    if tokens_input is None and tokens_output is None:
        return None
    return f"{_compact_number(tokens_input)} in / {_compact_number(tokens_output)} out"


def _compact_number(value: Any) -> str:
    if value is None:
        return "0"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if abs(number) >= 1_000:
        return f"{number / 1_000:.1f}k"
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}"


def _trajectory_viewpoint(traj: dict[str, Any]) -> dict[str, str | None]:
    metrics_extra = (traj.get("metrics") or {}).get("extra") or {}
    harness_extra = (traj.get("tool_harness") or {}).get("extra") or {}
    first_screenshot = next(
        (
            event
            for event in traj.get("events") or []
            if event.get("event_type") == "screenshot"
        ),
        {},
    )
    screenshot_data = first_screenshot.get("data") or {}
    viewport = (
        screenshot_data.get("viewport")
        or harness_extra.get("viewport")
        or (traj.get("model") or {}).get("extra", {}).get("screen_size")
    )
    return {
        "source": str(
            metrics_extra.get("screenshot_source")
            or harness_extra.get("screenshot_source")
            or screenshot_data.get("screenshot_source")
            or ""
        )
        or None,
        "frame": str(
            metrics_extra.get("coordinate_frame")
            or harness_extra.get("coordinate_frame")
            or screenshot_data.get("coordinate_frame")
            or ""
        )
        or None,
        "size": _viewport_size(viewport),
    }


def _viewport_size(value: Any) -> str | None:
    if isinstance(value, dict):
        width = value.get("width")
        height = value.get("height")
        if width and height:
            return f"{width}x{height}"
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return f"{value[0]}x{value[1]}"
    return None


ACTION_LABELS = {
    "screenshot": "browser.screenshot",
    "click": "browser.click",
    "double_click": "browser.double_click",
    "scroll": "browser.scroll",
    "type": "browser.type",
    "wait": "browser.wait",
    "move": "browser.move",
    "keypress": "browser.keypress",
    "drag": "browser.drag",
    "goto": "browser.goto",
    "back": "browser.back",
    "forward": "browser.forward",
    "reload": "browser.reload",
    "web_search": "web.search",
    "run_python": "code.run_python",
    "shell": "code.shell",
    "read_file": "files.read",
    "write_file": "files.write",
    "mcp_tool": "mcp.tool",
    "desktop_screenshot": "desktop.screenshot",
    "desktop_click": "desktop.click",
    "desktop_double_click": "desktop.double_click",
    "desktop_scroll": "desktop.scroll",
    "desktop_move": "desktop.move",
    "desktop_drag": "desktop.drag",
    "desktop_type": "desktop.type",
    "desktop_keypress": "desktop.keypress",
    "desktop_launch_app": "desktop.launch_app",
    "desktop_pyautogui": "desktop.pyautogui",
    "desktop_shell": "desktop.shell",
    "desktop_wait": "desktop.wait",
    "final_answer": "task.final_answer",
}


def _action_label(action: dict[str, Any] | None) -> str:
    if not action:
        return "model"
    action_type = str(action.get("type") or "action")
    if action_type == "desktop_pyautogui":
        return _pyautogui_label(action.get("code") or "")
    return ACTION_LABELS.get(action_type, action_type)


def _action_detail(action: dict[str, Any]) -> str:
    action_type = action.get("type")
    if action_type == "desktop_pyautogui":
        return _pyautogui_detail(action.get("code") or "")

    fields: list[str] = []
    if action.get("x") is not None and action.get("y") is not None:
        fields.append(f"x={action.get('x')} y={action.get('y')}")
    if action.get("button") and action.get("button") != "left":
        fields.append(f"button={action.get('button')}")
    if action.get("scroll_x"):
        fields.append(f"scroll_x={action.get('scroll_x')}")
    if action.get("scroll_y"):
        fields.append(f"scroll_y={action.get('scroll_y')}")
    if action.get("keys"):
        fields.append(f"keys={'+'.join(map(str, action.get('keys') or []))}")
    if action.get("path"):
        fields.append(f"path={_short(_json(action.get('path')), 110)}")
    if action.get("text"):
        fields.append(f"text={_short(action.get('text'), 80)}")
    if action.get("url"):
        fields.append(f"url={_short(action.get('url'), 90)}")
    if action.get("query"):
        fields.append(f"query={_short(action.get('query'), 90)}")
    if action.get("cmd"):
        fields.append(f"cmd={_short(action.get('cmd'), 100)}")
    if action.get("code"):
        fields.append(f"code={_short(_single_line(action.get('code')), 120)}")
    if action.get("file_path"):
        fields.append(f"file={_short(action.get('file_path'), 90)}")
    if action.get("content"):
        fields.append(f"content={_short(action.get('content'), 80)}")
    if action.get("mcp_tool"):
        fields.append(f"tool={action.get('mcp_tool')}")
    if action.get("mcp_args"):
        fields.append(f"args={_short(_json(action.get('mcp_args')), 90)}")
    if action.get("app"):
        fields.append(f"app={action.get('app')}")
    if action.get("ms"):
        fields.append(f"ms={action.get('ms')}")
    if action.get("answer"):
        fields.append(f"answer={_short(action.get('answer'), 120)}")
    return " | ".join(fields)


def _pyautogui_label(code: str) -> str:
    kind = _pyautogui_kind(code)
    return f"pyautogui.{kind}"


def _pyautogui_detail(code: str) -> str:
    text = _single_line(code)
    hotkey = re.search(r"pyautogui\.hotkey\(([^)]*)\)", code)
    if hotkey:
        return f"keys={_clean_py_args(hotkey.group(1))}"
    press = re.search(r"pyautogui\.(?:press|keyDown|keyUp)\(([^)]*)\)", code)
    if press:
        return f"key={_clean_py_args(press.group(1))}"
    move = re.search(r"pyautogui\.moveTo\(([^)]*)\)", code)
    if move:
        return f"target={_clean_py_args(move.group(1))}"
    click = re.search(r"pyautogui\.(?:click|doubleClick)\(([^)]*)\)", code)
    if click:
        args = _clean_py_args(click.group(1))
        return f"args={args}" if args else _short(text, 120)
    typed = re.search(r"pyautogui\.(?:typewrite|write)\((.+?)(?:,\s*interval=|\))", code, re.S)
    if typed:
        return f"text={_short(_clean_py_args(typed.group(1)), 120)}"
    sleep = re.search(r"time\.sleep\(([^)]*)\)", code)
    if sleep:
        return f"seconds={_clean_py_args(sleep.group(1))}"
    return _short(text, 140)


def _pyautogui_kind(code: str) -> str:
    if "time.sleep" in code:
        return "wait"
    if "pyautogui.hotkey" in code:
        return "hotkey"
    if re.search(r"pyautogui\.(?:press|keyDown|keyUp)\(", code):
        return "keypress"
    if "pyautogui.typewrite" in code or "pyautogui.write" in code:
        return "type"
    if "pyautogui.doubleClick" in code:
        return "double_click"
    if "pyautogui.dragTo" in code or "pyautogui.dragRel" in code:
        return "drag"
    if "pyautogui.click" in code:
        return "click"
    if "pyautogui.scroll" in code or "pyautogui.hscroll" in code:
        return "scroll"
    if "pyautogui.moveTo" in code or "pyautogui.moveRel" in code:
        return "move"
    if "pyautogui.screenshot" in code:
        return "screenshot"
    return "script"


def _clean_py_args(value: str) -> str:
    return _short(
        value.replace("'", "").replace('"', "").replace("\n", " ").strip(),
        140,
    )


def _single_line(value: Any) -> str:
    return " ".join(str(value).strip().split())


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
  <div class="event-head">
    <span class="event-type event-title">{escape(event_type)}</span>
    <span class="badge">step {escape(_short(step))}</span>
    {_badge(tool_name) if tool_name else ""}
    <span class="timestamp">{escape(str(event.get("timestamp", "")))}</span>
  </div>
  <div class="event-body">
    <div>
    {screenshot_html}
    </div>
    <div class="details">{details_html}</div>
  </div>
</article>"""


def _render_round_index(events: list[dict[str, Any]]) -> str:
    round_events = [
        event for event in events if event.get("event_type") == "model_message"
    ]
    if not round_events:
        return ""
    links = "\n".join(_render_round_link(event) for event in round_events)
    legend = _render_round_action_legend(round_events)
    return f"""<section class="round-index">
  <div class="round-index-head">
    <strong>Rounds</strong>
    <span>{len(round_events)} model step(s)</span>
  </div>
  {legend}
  <div class="round-links">{links}</div>
</section>"""


def _render_round_link(event: dict[str, Any]) -> str:
    data = event.get("data") or {}
    step = event.get("step_index")
    action = data.get("action") if isinstance(data.get("action"), dict) else None
    actions = data.get("actions") if isinstance(data.get("actions"), list) else None
    if action is None and actions:
        action = next((item for item in actions if isinstance(item, dict)), None)
    kind = _action_kind(action)
    label = _round_action_summary(data)
    return f"""<a class="round-link {escape(kind)}" href="#{escape(_event_anchor(event))}" title="{escape(label)}">
  <strong>{escape(_short(step))}</strong>
  <span>{escape(_short(label, 28))}</span>
</a>"""


def _render_round_action_legend(round_events: list[dict[str, Any]]) -> str:
    seen: list[str] = []
    for event in round_events:
        action = _first_action_from_event(event)
        action_label = _action_label(action)
        if action_label not in seen:
            seen.append(action_label)
    if not seen:
        return ""
    items = "\n".join(
        f'<span class="{escape(_action_kind_for_label(label))}"><i class="dot"></i>{escape(label)}</span>'
        for label in seen
    )
    return f'<div class="round-legend">{items}</div>'


def _render_tool_map(events: list[dict[str, Any]], *, output_path: Path) -> str:
    rows = "\n".join(
        _render_step_triplet(step, step_events, output_path=output_path)
        for step, step_events in _events_by_step(events).items()
    )
    if not rows:
        return ""
    rounds = sum(1 for event in events if event.get("event_type") == "model_message")
    return f"""<details class="tool-map">
  <summary>Raw Step Log <span>{len(events)} records grouped into observation / thought / action across {rounds} round(s)</span></summary>
  <div class="tool-map-head">
    <div>
      <div class="tool-map-title">Raw Step Log</div>
      <div class="event-note">Each row groups the raw records for one step: observed screen state, model thought, then requested/executed action.</div>
    </div>
  </div>
  <div class="step-log">{rows}</div>
</details>"""


def _events_by_step(events: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        step = event.get("step_index")
        if isinstance(step, int):
            grouped.setdefault(step, []).append(event)
    return dict(sorted(grouped.items()))


def _render_step_triplet(
    step: int, step_events: list[dict[str, Any]], *, output_path: Path
) -> str:
    model_event = next(
        (event for event in step_events if event.get("event_type") == "model_message"),
        None,
    )
    action_event = next(
        (
            event
            for event in step_events
            if event.get("event_type") in {"browser_action", "tool_call"}
        ),
        None,
    )
    screenshot_event = next(
        (
            event
            for event in reversed(step_events)
            if event.get("event_type") == "screenshot"
        ),
        None,
    )
    validation_event = next(
        (
            event
            for event in step_events
            if event.get("event_type") in {"validation_event", "gating_violation"}
        ),
        None,
    )
    anchor_event = model_event or action_event or screenshot_event or step_events[0]
    action = _first_action_from_event(model_event or action_event or {})
    kind = _action_kind(action)
    action_label = _round_action_summary((model_event or {}).get("data") or {})
    if action_label == "model" and action:
        action_label = str(action.get("type") or "action")
    return f"""<section class="step-triplet {escape(kind)}" id="step-{escape(_short(step))}">
  <div class="step-triplet-head">
    <strong>Step {escape(_short(step))}</strong>
    <a class="badge" href="#{escape(_event_anchor(anchor_event))}">round card</a>
    <span class="badge">{escape(action_label)}</span>
    <span class="source">{len(step_events)} raw record(s)</span>
  </div>
  <div class="triplet-grid">
    {_render_triplet_observation(screenshot_event, output_path=output_path)}
    {_render_triplet_thought(model_event)}
    {_render_triplet_action(model_event, action_event, validation_event)}
  </div>
</section>"""


def _render_triplet_observation(
    screenshot_event: dict[str, Any] | None, *, output_path: Path
) -> str:
    if screenshot_event is None:
        return _triplet_cell("Observation", '<p>No screenshot record for this step.</p>')
    data = screenshot_event.get("data") or {}
    image_paths = [
        path
        for path in screenshot_event.get("artifact_paths") or []
        if str(path).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]
    if image_paths:
        image_src = _relative_artifact_src(image_paths[0], output_path=output_path)
        shot = f'<img class="triplet-shot" src="{escape(image_src)}" loading="lazy">'
    else:
        shot = "<p>No screenshot artifact.</p>"
    meta = _triplet_meta(
        [
            ("url", data.get("url")),
            ("kind", data.get("kind")),
            ("viewpoint", data.get("screenshot_source")),
            ("frame", data.get("coordinate_frame")),
            ("size", _viewport_size(data.get("viewport"))),
            ("remote", data.get("remote_path")),
        ]
    )
    return _triplet_cell("Observation", shot + meta)


def _render_triplet_thought(model_event: dict[str, Any] | None) -> str:
    if model_event is None:
        return _triplet_cell("Thought", '<p>No model thought for this step.</p>')
    data = model_event.get("data") or {}
    thought = data.get("thought") or data.get("reasoning")
    if not thought:
        return _triplet_cell("Thought", '<p>No thought text recorded.</p>')
    return _triplet_cell("Thought", f"<p>{escape(_short_block(thought, 900))}</p>")


def _render_triplet_action(
    model_event: dict[str, Any] | None,
    action_event: dict[str, Any] | None,
    validation_event: dict[str, Any] | None,
) -> str:
    if validation_event is not None:
        data = validation_event.get("data") or {}
        validation_meta = _triplet_meta(
            [
                ("validation", data.get("success", data.get("ok"))),
                ("answer", data.get("answer")),
                ("message", data.get("message")),
            ]
        )
    else:
        validation_meta = ""

    actions = ((model_event or {}).get("data") or {}).get("actions")
    if not isinstance(actions, list):
        action = _first_action_from_event(model_event or action_event or {})
        actions = [action] if action else []
    lines = [
        _format_action_line(action)
        for action in actions
        if isinstance(action, dict)
    ]
    if not lines:
        body = "<p>No action recorded.</p>"
        if validation_meta:
            body += validation_meta
        return _triplet_cell("Action", body)
    execution_data = (action_event or {}).get("data") or {}
    status = "executed"
    if execution_data.get("error"):
        status = f"error: {_short(execution_data.get('error'), 160)}"
    elif action_event is None:
        status = "not executed in this step"
    body = f"<pre>{escape(chr(10).join(lines))}</pre>"
    body += _triplet_meta([("execution", status)])
    body += validation_meta
    return _triplet_cell("Action", body)


def _triplet_cell(label: str, body: str) -> str:
    return f'<section class="triplet-cell"><h4>{escape(label)}</h4>{body}</section>'


def _triplet_meta(items: list[tuple[str, Any]]) -> str:
    parts = [
        f"{label}: {_short(value, 160)}"
        for label, value in items
        if value not in (None, "")
    ]
    if not parts:
        return ""
    return f'<div class="triplet-meta">{escape(" | ".join(parts))}</div>'


def _event_tool_label(event: dict[str, Any]) -> tuple[str, str, str]:
    event_type = str(event.get("event_type", "event"))
    data = event.get("data") or {}
    action = _first_action_from_event(event)
    tool_name = data.get("tool_name") or _tool_name_from_action(action)

    if event_type == "model_message":
        return "decision", _action_label(action), _action_kind(action)
    if event_type == "screenshot":
        return "screenshot", str(data.get("url") or ""), "kind-screenshot"
    if event_type == "validation_event":
        ok = data.get("success", data.get("ok", ""))
        return "validation", f"success={ok}", "kind-validation"
    if event_type == "gating_violation":
        return "gating", str(tool_name or "blocked"), "kind-error"
    if event_type == "browser_action":
        return "executed", _action_label(action), _action_kind(action)
    if event_type == "tool_call":
        kind = _action_kind(action) if action else _tool_kind_class(str(tool_name or ""))
        return str(tool_name or "tool"), _tool_subtitle(data), kind
    if event_type == "user_intervention":
        return "user", str(data.get("action") or data.get("decision") or ""), "kind-other"
    if tool_name:
        return str(tool_name), _tool_subtitle(data), _tool_kind_class(str(tool_name))
    return event_type, "", "kind-other"


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
    if tool_name.startswith("desktop."):
        return "desktop"
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


def _first_action_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    data = event.get("data") or {}
    action = data.get("action")
    if isinstance(action, dict):
        return action
    actions = data.get("actions")
    if isinstance(actions, list):
        return next((item for item in actions if isinstance(item, dict)), None)
    return None


def _action_kind(action: dict[str, Any] | None) -> str:
    if not action:
        return "kind-model"
    action_type = action.get("type")
    if not action_type:
        return "kind-model"
    if action_type == "desktop_pyautogui":
        return f"action-pyautogui_{_pyautogui_kind(action.get('code') or '')}"
    safe = "".join(
        char if char.isalnum() or char in {"_", "-"} else "_"
        for char in str(action_type).lower()
    )
    return f"action-{safe}"


def _action_kind_for_label(label: str) -> str:
    if label.startswith("pyautogui."):
        return f"action-pyautogui_{_css_token(label.split('.', 1)[1])}"
    raw_type = next(
        (action_type for action_type, display in ACTION_LABELS.items() if display == label),
        None,
    )
    if raw_type:
        return f"action-{_css_token(raw_type)}"
    return f"action-{_css_token(label)}"


def _css_token(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"_", "-"} else "_"
        for char in str(value).lower()
    )


def _tool_kind_class(tool_name: str) -> str:
    return f"kind-{_kind_for_tool(tool_name)}"


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
    if action_type == "mcp_tool":
        return f"mcp.{action.get('mcp_tool') or 'tool'}"
    if str(action_type).startswith("desktop_"):
        return "desktop." + str(action_type).removeprefix("desktop_")
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
