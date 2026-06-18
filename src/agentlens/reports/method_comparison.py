from __future__ import annotations

import base64
import json
import os
from html import escape
from pathlib import Path
from typing import Any

from agentlens.analysis.methods import analyze_trajectory_methods

GROUP_COLORS = {
    "Retrieval": "#6b5b3a",
    "Memory": "#6a5a3a",
    "Planning": "#2d4a6a",
    "Reasoning": "#5b4a8a",
    "Evaluate": "#1a5878",
    "Deciding": "#4a4a5a",
    "Grounding": "#8a4a6a",
    "Executing": "#2d5a3d",
    "Learning": "#8a3a4a",
    "Reflection": "#b8451a",
}


def write_method_comparison_report(
    trajectory_path: Path,
    output_dir: Path,
    *,
    state_diff_threshold: float = 8000.0,
    annotation_mode: str = "rule",
    llm_provider: str = "auto",
    llm_model: str | None = None,
) -> Path:
    """Run both methods and render a side-by-side static HTML report."""
    trajectory_path = trajectory_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    result = analyze_trajectory_methods(
        trajectory_path,
        output_dir,
        state_diff_threshold=state_diff_threshold,
        annotation_mode=annotation_mode,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    html_path = output_dir / "method_comparison.html"
    html_path.write_text(
        _render_html(trajectory_path, trajectory, result, html_path),
        encoding="utf-8",
    )
    return html_path


def _render_html(
    trajectory_path: Path,
    trajectory: dict[str, Any],
    result: dict[str, Any],
    html_path: Path,
) -> str:
    task = trajectory.get("task") or {}
    wang = result["wang"]
    actonomy = result["actonomy"]
    comparison_table = _render_per_turn_comparison(wang, actonomy, html_path)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentLens Method Comparison</title>
  <style>
    :root {{
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #222622;
      --muted: #697069;
      --line: #d8ded6;
      --wang: #2f6f82;
      --act: #8a4f22;
      --raw: #59623f;
      --code: #f0f2ed;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      padding: 16px 22px;
      background: rgba(247, 247, 244, .94);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(10px);
    }}
    h1 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 10px; font-size: 16px; }}
    h3 {{ margin: 0 0 8px; font-size: 14px; }}
    a {{ color: #235c73; }}
    .sub {{ color: var(--muted); margin-top: 4px; }}
    .grid {{
      display: grid;
      gap: 14px;
      padding: 14px;
    }}
    .full {{ grid-column: 1 / -1; }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      overflow: hidden;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 8px;
    }}
    .run-summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      margin-bottom: 8px;
    }}
    .summary-chip {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 9px;
      background: #fbfbf8;
      max-width: 100%;
      font-size: 12px;
    }}
    .summary-chip span:first-child {{
      color: var(--muted);
      font-weight: 650;
    }}
    .summary-chip strong {{
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    .summary-chip.status-ok {{ border-color: #9bc7a4; background: #f2faf3; }}
    .summary-chip.status-fail {{ border-color: #d8a29c; background: #fff5f3; }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: #fbfbf8;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .method-title {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
      margin-bottom: 10px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      color: white;
      background: var(--raw);
    }}
    .pill.wang {{ background: var(--wang); }}
    .pill.act {{ background: var(--act); }}
    .timeline {{
      display: grid;
      gap: 8px;
    }}
    .item {{
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 10px;
      background: #fbfbf8;
    }}
    .item-head {{
      display: flex;
      gap: 8px;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .summary {{ margin: 4px 0 8px; }}
    pre {{
      margin: 8px 0 0;
      padding: 8px;
      background: var(--code);
      border-radius: 6px;
      overflow: auto;
      white-space: pre-wrap;
      font-size: 12px;
    }}
    img {{
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      margin-top: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      text-align: left;
      vertical-align: top;
      padding: 7px 6px;
      border-bottom: 1px solid var(--line);
    }}
    th {{ color: var(--muted); font-weight: 650; }}
    .codes {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }}
    .code-chip {{
      border: 1px solid var(--line);
      background: #f7efe8;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 12px;
    }}
    .phase-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
      margin: 10px 0;
    }}
    .phase-card {{
      border-left: 4px solid var(--act);
      background: #fbf6f1;
      border-radius: 6px;
      padding: 8px 9px;
    }}
    .phase-card strong {{ display: block; }}
    .small {{ color: var(--muted); font-size: 12px; }}
    .cmp-wrap {{ overflow-x: auto; }}
    table.cmp {{
      min-width: 1450px;
      table-layout: fixed;
      font-size: 12px;
    }}
    table.cmp th {{
      background: #eeeeeb;
      color: #252925;
      font-size: 12px;
      padding: 7px 8px;
    }}
    table.cmp th .sub {{
      color: #858985;
      font-weight: 500;
    }}
    table.cmp th:nth-child(1) {{ width: 44px; }}
    table.cmp th:nth-child(2) {{ width: 150px; }}
    table.cmp th:nth-child(3) {{ width: 230px; }}
    table.cmp th:nth-child(4) {{ width: 260px; background: #eef4f0; }}
    table.cmp th:nth-child(5) {{ width: 470px; background: #f1eef6; }}
    table.cmp th:nth-child(6) {{ width: 310px; background: #eee9f6; }}
    table.cmp td {{
      border-bottom: 1px solid #ecefea;
      vertical-align: top;
      padding: 7px 8px;
    }}
    .raw-num {{
      color: #9a9f99;
      font: 700 13px ui-monospace, SFMono-Regular, Menlo, monospace;
      text-align: right;
    }}
    .screen-thumb {{
      width: 135px;
      display: block;
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 4px;
    }}
    .action-cell code {{
      display: block;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 11px;
      color: #3c413c;
      margin-top: 5px;
    }}
    .chip {{
      display: inline-block;
      color: white;
      background: var(--raw);
      border-radius: 999px;
      padding: 2px 8px;
      font: 700 11px ui-monospace, SFMono-Regular, Menlo, monospace;
      margin: 0 4px 4px 0;
    }}
    .chip.wang {{ background: var(--wang); }}
    .chip.act {{ background: #5b4a8a; }}
    .cmp-wang {{ background: #fbfdfc; }}
    .cmp-tags {{ background: #fdfcff; }}
    .cmp-phase {{ background: #f8f5fc; }}
    .continuation {{
      color: #c3c7c3;
      font-size: 18px;
      line-height: 1;
    }}
    .tag-row {{
      padding: 0 0 7px;
      margin: 0 0 7px;
      border-bottom: 1px dotted #e4e1e8;
    }}
    .tag-row:last-child {{
      margin-bottom: 0;
      border-bottom: 0;
    }}
    .tag-leaf {{
      color: #454945;
      margin-left: 4px;
    }}
    .tag-quote {{
      color: #777d77;
      font-style: italic;
      margin-top: 2px;
    }}
    .status-footer {{
      margin-top: 14px;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }}
    .status-footer .meta {{
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }}
    @media (max-width: 1000px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Per-Turn Method Alignment</h1>
    <div class="sub">{escape(str(task.get("id") or trajectory.get("run_id") or trajectory_path.name))}</div>
  </header>
  <main class="grid">
    <section class="card full">
      {_render_run_summary(trajectory, trajectory_path)}
      <p><strong>Goal:</strong> {escape(str(task.get("goal") or ""))}</p>
      {_render_mode_note(result.get("manifest", {}))}
      {comparison_table}
      {_render_finish_status(trajectory, result.get("manifest", {}))}
    </section>
  </main>
</body>
</html>"""


def _render_run_summary(trajectory: dict[str, Any], trajectory_path: Path) -> str:
    task = trajectory.get("task") or {}
    metrics = trajectory.get("metrics") or {}
    success = metrics.get("success")
    status_class = "status-ok" if success is True else "status-fail" if success is False else ""
    compact = [
        ("Task", _clean_task_label(task)),
        ("Model", _model_label(trajectory.get("model"), compact=True)),
        ("Harness", _harness_label(trajectory.get("tool_harness"), compact=True)),
        ("Outcome", f"{'success' if success is True else 'failed' if success is False else success} / {metrics.get('score')}"),
        ("Steps", metrics.get("steps")),
        ("Run", trajectory.get("run_id")),
    ]
    chips = "".join(
        _summary_chip(label, value, extra_class=status_class if label == "Outcome" else "")
        for label, value in compact
    )
    detail = (
        f"{task.get('benchmark') or ''}"
        f" | raw task: {task.get('id') or ''}"
        f" | benchmark task: {task.get('task_id') or ''}"
        f" | trajectory: {trajectory_path}"
    )
    return f'<div class="run-summary">{chips}</div><div class="small">{escape(detail)}</div>'


def _summary_chip(label: str, value: Any, *, extra_class: str = "") -> str:
    return (
        f'<span class="summary-chip {escape(extra_class)}">'
        f"<span>{escape(label)}</span><strong>{escape(str(value))}</strong></span>"
    )


def _render_mode_note(manifest: dict[str, Any]) -> str:
    llm = manifest.get("llm") or {}
    mode = llm.get("annotation_mode") or manifest.get("annotation_mode") or "rule"
    if mode == "llm":
        provider = llm.get("provider")
        model = llm.get("model")
        return (
            f'<p class="small"><strong>Current labels:</strong> LLM-refined using '
            f"{escape(str(provider))}"
            f"{' / ' + escape(str(model)) if model else ''}. Deterministic parsing still supplies the raw turns.</p>"
        )
    if mode == "llm_failed_rule_fallback":
        return (
            '<p class="small"><strong>Current labels:</strong> rule-based fallback; '
            f"LLM refinement failed: {escape(str(llm.get('error')))}</p>"
        )
    return (
        '<p class="small"><strong>Current labels:</strong> rule-based summaries from '
        "action type, target, and model thought. No LLM has rewritten these phase names yet.</p>"
    )


def _render_finish_status(trajectory: dict[str, Any], manifest: dict[str, Any]) -> str:
    metrics = trajectory.get("metrics") or {}
    task = trajectory.get("task") or {}
    llm = manifest.get("llm") or {}
    extra = metrics.get("extra") if isinstance(metrics.get("extra"), dict) else {}
    validation = _validation_event_data(trajectory)
    final_answer = validation.get("answer") if validation else _final_answer_from_events(trajectory)
    validation_message = validation.get("message") if validation else None
    last_model_error = _last_model_error(trajectory)
    success = metrics.get("success")
    outcome = "success" if success is True else "failed" if success is False else success
    return f"""<div class="status-footer">
      <h2>Task Finish Status</h2>
      <div class="meta">
        {_metric("Recorded outcome", outcome)}
        {_metric("Score", metrics.get("score"))}
        {_metric("Final answer", final_answer if final_answer is not None else "not emitted")}
        {_metric("Validation message", validation_message)}
        {_metric("Expected answer", task.get("expected_answer"))}
        {_metric("Validator", _validator_label(task, validation))}
        {_metric("Steps", metrics.get("steps"))}
        {_metric("Duration", _format_duration(metrics.get("duration_ms")))}
        {_metric("Tool calls", metrics.get("tool_calls"))}
        {_metric("Browser actions", extra.get("browser_actions"))}
        {_metric("IO tool calls", extra.get("io_tool_calls"))}
        {_metric("Analysis model", _analysis_model_label(llm))}
        {_metric("Last model error", last_model_error)}
      </div>
    </div>"""


def _validation_event_data(trajectory: dict[str, Any]) -> dict[str, Any]:
    for event in reversed(trajectory.get("events", [])):
        if event.get("event_type") == "validation_event":
            data = event.get("data")
            return data if isinstance(data, dict) else {}
    return {}


def _final_answer_from_events(trajectory: dict[str, Any]) -> str | None:
    for event in trajectory.get("events", []):
        data = event.get("data") or {}
        action = data.get("action") or {}
        if action.get("type") == "final_answer":
            answer = action.get("answer")
            return str(answer) if answer is not None else None
    return None


def _last_model_error(trajectory: dict[str, Any]) -> str | None:
    for event in reversed(trajectory.get("events", [])):
        if event.get("event_type") != "model_message":
            continue
        data = event.get("data") or {}
        error = data.get("error")
        if error:
            return _summarize_model_error(str(error))
    return None


def _summarize_model_error(error: str) -> str:
    if "RateLimitError" in error or "rate_limit_exceeded" in error:
        return "RateLimitError 429: token-per-minute limit reached before final_answer."
    if "model response was not valid JSON" in error:
        return "Invalid model response: expected JSON action but received empty/non-JSON content."
    return error


def _validator_label(task: dict[str, Any], validation: dict[str, Any]) -> str:
    pieces = [
        task.get("validator"),
        validation.get("answer_validator") or task.get("answer_validator"),
    ]
    return " / ".join(str(piece) for piece in pieces if piece)


def _clean_task_label(task: dict[str, Any]) -> str:
    task_id = str(task.get("id") or "")
    benchmark_task = str(task.get("task_id") or "")
    key = benchmark_task or task_id
    if key in {"datavoyager.most_fuel_efficient", "datavoyager_most_fuel_efficient"}:
        return "DataVoyager: most fuel-efficient car"
    if task_id == "domsteer_datavoyager_most_fuel_efficient":
        return "DataVoyager: most fuel-efficient car"
    if key in {"datavoyager.europe_100hp_4cyl_count", "datavoyager_europe_100hp_4cyl_count"}:
        return "DataVoyager: Europe <100hp, 4-cylinder count"
    if key in {"datavoyager.horsepower_range_by_origin", "datavoyager_horsepower_range_by_origin"}:
        return "DataVoyager: horsepower range by origin"
    if key in {"datavoyager.8_cylinder_characteristics", "datavoyager_8_cylinder_characteristics"}:
        return "DataVoyager: 8-cylinder characteristics"
    if key in {"tf_discretize_toggle", "tf_discretize_toggle_dialogue"}:
        return "TaskForm: discretize toggle"
    return task_id or benchmark_task


def _model_label(model: Any, *, compact: bool = False) -> str:
    if not isinstance(model, dict):
        return str(model or "")
    name = model.get("name") or model.get("id") or ""
    if compact:
        return str(name)
    provider = model.get("provider")
    local_id = model.get("id")
    pieces = [str(name)]
    if local_id and local_id != name:
        pieces.append(f"id={local_id}")
    if provider:
        pieces.append(str(provider))
    return " | ".join(piece for piece in pieces if piece)


def _harness_label(harness: Any, *, compact: bool = False) -> str:
    if not isinstance(harness, dict):
        return str(harness or "")
    if compact:
        return str(harness.get("tier") or harness.get("id") or "")
    return " / ".join(
        str(piece)
        for piece in (harness.get("id"), harness.get("tier"), harness.get("runner"))
        if piece
    )


def _analysis_model_label(llm: dict[str, Any]) -> str:
    if not llm:
        return "rule mode"
    provider = llm.get("provider")
    model = llm.get("model")
    mode = llm.get("annotation_mode")
    return " | ".join(str(piece) for piece in (mode, provider, model) if piece)


def _format_duration(duration_ms: Any) -> str:
    if not isinstance(duration_ms, (int, float)):
        return str(duration_ms or "")
    if duration_ms >= 1000:
        return f"{duration_ms / 1000:.1f}s"
    return f"{duration_ms}ms"


def _render_file_list(paths: dict[str, Path], html_path: Path) -> str:
    rows = []
    for name, path in sorted(paths.items()):
        rel = os.path.relpath(path, html_path.parent)
        rows.append(
            f"<tr><td>{escape(name)}</td><td><a href=\"{escape(rel)}\">{escape(rel)}</a></td></tr>"
        )
    return "<h3>Generated intermediate files</h3><table><tbody>" + "".join(rows) + "</tbody></table>"


def _render_wang_panel(wang: dict[str, Any], html_path: Path) -> str:
    summary = wang["summary"]
    items = []
    for step in wang["workflow_steps"]:
        segs = step.get("intermediate", {}).get("state_segments", [])
        items.append(
            f"""<div class="item">
              <div class="item-head">
                <span>W{step['workflow_step_id']} | {escape(step.get('title', step['phase']))} | steps {step['start_index']}-{step['end_index']}</span>
                <span>{escape(step['status'])}</span>
              </div>
              <h3>{escape(step.get('title', step['phase']))}</h3>
              <div class="summary">{escape(step['summary'])}</div>
              <div class="small"><strong>Goal:</strong> {escape(step['goal'])}</div>
              <pre>{escape(json.dumps(segs, indent=2, ensure_ascii=False))}</pre>
            </div>"""
        )
    return f"""
      <div class="meta">
        {_metric("Action nodes", summary["action_node_count"])}
        {_metric("State segments", summary["state_segment_count"])}
        {_metric("Workflow steps", summary["workflow_step_count"])}
      </div>
      <pre>{escape(summary["sequence_summary"])}</pre>
      <div class="timeline">{''.join(items)}</div>
    """


def _render_actonomy_panel(actonomy: dict[str, Any], html_path: Path) -> str:
    profile = actonomy["profile"]
    phase_cards = "".join(
        f"<div class=\"phase-card\"><strong>{escape(phase)}</strong><span>{count} session(s)</span></div>"
        for phase, count in sorted((profile.get("phase_counts") or {}).items())
    )
    sessions = []
    for session in actonomy["sessions"]:
        sessions.append(
            f"""<div class="item">
              <div class="item-head">
                <span>A{session['session_id']} | {escape(session.get('title', session['dominant_phase']))} | turns {session['start_turn']}-{session['end_turn']}</span>
                <span>{escape(session['dominant_action'])}</span>
              </div>
              <h3>{escape(session.get('title', session['dominant_phase']))}</h3>
              <div class="summary">{escape(session['summary'])}</div>
              <table>
                <tbody>
                  <tr><th>Phase counts</th><td><pre>{escape(json.dumps(session.get('phase_counts', {}), indent=2, ensure_ascii=False))}</pre></td></tr>
                  <tr><th>Action-type counts</th><td><pre>{escape(json.dumps(session.get('action_type_counts', {}), indent=2, ensure_ascii=False))}</pre></td></tr>
                  <tr><th>Taxonomy-code counts</th><td><pre>{escape(json.dumps(session['taxonomy_code_counts'], indent=2, ensure_ascii=False))}</pre></td></tr>
                </tbody>
              </table>
            </div>"""
        )
    rows = []
    for turn in actonomy["turns"]:
        chips = "".join(
            f"<span class=\"code-chip\">{escape(a['taxonomy_code'])} {escape(a['action'])}</span>"
            for a in turn["annotations"]
        )
        rows.append(
            f"""<tr>
              <td>T{turn['turn']}</td>
              <td>{escape(turn['headline'])}</td>
              <td><div class="codes">{chips}</div></td>
            </tr>"""
        )
    return f"""
      <div class="meta">
        {_metric("Turns", profile["turn_count"])}
        {_metric("Sessions", profile["session_count"])}
        {_metric("Annotations", profile["annotation_count"])}
      </div>
      <h3>Profile / Aggregation Summary</h3>
      <pre>{escape(profile["sequence_summary"])}</pre>
      <div class="phase-grid">{phase_cards}</div>
      <pre>{escape(json.dumps(profile.get("action_counts", {}), indent=2, ensure_ascii=False))}</pre>
      <h3>Aggregated Phases / Sessions</h3>
      <div class="timeline">{''.join(sessions)}</div>
      <h3>Turn-Level Codebook Assignments</h3>
      <table><thead><tr><th>Turn</th><th>Headline</th><th>Codes</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
    """


def _render_per_turn_comparison(
    wang: dict[str, Any],
    actonomy: dict[str, Any],
    html_path: Path,
) -> str:
    wang_by_step = _span_lookup(wang["workflow_steps"], "start_index", "end_index")
    act_turns = {turn["turn"]: turn for turn in actonomy["turns"]}
    act_by_turn = _span_lookup(actonomy["sessions"], "start_turn", "end_turn")
    rows = []
    for event in wang["canonical_events"]:
        step_idx = event["step_index"]
        turn = act_turns.get(step_idx)
        wang_step = wang_by_step.get(step_idx)
        act_session = act_by_turn.get(step_idx)
        rows.append(
            f"""<tr>
              <td class="raw-num">{step_idx}</td>
              <td>{_screen_thumb(event, html_path)}</td>
              <td class="action-cell">{_render_raw_action(event, turn)}</td>
              <td class="cmp-wang">{_render_wang_cell(step_idx, wang_step)}</td>
              <td class="cmp-tags">{_render_actonomy_tags(turn)}</td>
              <td class="cmp-phase">{_render_actonomy_phase_cell(step_idx, act_session)}</td>
            </tr>"""
        )
    return f"""<div class="cmp-wrap">
      <table class="cmp">
        <thead>
          <tr>
            <th>raw</th>
            <th>screen</th>
            <th>raw action <span class="sub">(tool call)</span></th>
            <th>Wang aggregation <span class="sub">workflow segment</span></th>
            <th>Act-onomy intermediate <span class="sub">per-turn cognitive tags</span></th>
            <th>Act-onomy aggregation <span class="sub">named phase</span></th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _span_lookup(records: list[dict[str, Any]], start_key: str, end_key: str) -> dict[int, dict[str, Any]]:
    out = {}
    for record in records:
        start = int(record[start_key])
        end = int(record[end_key])
        for idx in range(start, end + 1):
            out[idx] = record
    return out


def _screen_thumb(event: dict[str, Any], html_path: Path) -> str:
    screenshot = event.get("after_screenshot") or (event.get("screenshots") or [None])[-1]
    if not screenshot:
        return '<span class="small">no screenshot</span>'
    path = Path(str(screenshot))
    if not path.exists():
        return '<span class="small">missing screenshot</span>'
    src = _image_data_uri(path)
    return f'<img class="screen-thumb" src="{escape(src)}" alt="screen step {event["step_index"]}">'


def _image_data_uri(path: Path) -> str:
    suffix = path.suffix.casefold()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _render_raw_action(event: dict[str, Any], turn: dict[str, Any] | None) -> str:
    action_type = event.get("action_type") or "event"
    tool_name = event.get("tool_name") or action_type
    action_text = (turn or {}).get("action_surface") or event.get("action_text") or ""
    return (
        f'<span class="chip">{escape(str(tool_name))}</span>'
        f"<code>{escape(str(action_text))}</code>"
    )


def _render_wang_cell(step_idx: int, wang_step: dict[str, Any] | None) -> str:
    if not wang_step:
        return '<span class="small">unassigned</span>'
    if step_idx != wang_step["start_index"]:
        return '<span class="continuation">↳</span>'
    return (
        f'<span class="chip wang">W{wang_step["workflow_step_id"]}</span>'
        f"<strong>{escape(wang_step.get('title', wang_step['phase']))}</strong>"
        f'<div class="summary">{escape(wang_step["summary"])}</div>'
    )


def _render_actonomy_tags(turn: dict[str, Any] | None) -> str:
    if not turn:
        return '<span class="small">unassigned</span>'
    annotations = turn.get("annotations") or []
    if not annotations:
        return '<span class="small">no tags</span>'
    rows = []
    for annotation in annotations:
        group = annotation["action"]
        color = GROUP_COLORS.get(group, "#59623f")
        leaf = f"{annotation['subaction']} › {annotation['instance']}"
        evidence = annotation.get("evidence") or annotation.get("assignment_reason") or ""
        rows.append(
            f"""<div class="tag-row">
              <span class="chip" style="background:{escape(color)}">{escape(group)}</span>
              <span class="tag-leaf">{escape(leaf)}</span>
              <div class="tag-quote">“{escape(str(evidence))}”</div>
            </div>"""
        )
    return "".join(rows)


def _render_actonomy_phase_cell(step_idx: int, session: dict[str, Any] | None) -> str:
    if not session:
        return '<span class="small">unassigned</span>'
    if step_idx != session["start_turn"]:
        return '<span class="continuation">↳</span>'
    return (
        f'<span class="chip act">P{session["session_id"]}</span>'
        f"<strong>{escape(session.get('title', session['dominant_phase']))}</strong>"
        f'<div class="summary">{escape(session["summary"])}</div>'
    )


def _render_original_timeline(trajectory: dict[str, Any], html_path: Path) -> str:
    events_by_step: dict[int, list[dict[str, Any]]] = {}
    for event in trajectory.get("events", []):
        idx = event.get("step_index")
        if isinstance(idx, int):
            events_by_step.setdefault(idx, []).append(event)
    items = []
    for idx, events in sorted(events_by_step.items()):
        model = next((e for e in events if e.get("event_type") == "model_message"), None)
        screenshot = next((e for e in events if e.get("event_type") == "screenshot"), None)
        tool_or_action = next(
            (e for e in events if e.get("event_type") in {"browser_action", "tool_call", "validation_event"}),
            None,
        )
        thought = ((model or {}).get("data") or {}).get("thought") or ""
        action = (((model or {}).get("data") or {}).get("action")) or (
            ((tool_or_action or {}).get("data") or {}).get("action")
        )
        screenshot_html = ""
        if screenshot and screenshot.get("artifact_paths"):
            path = Path(str(screenshot["artifact_paths"][-1]))
            if path.exists():
                rel = os.path.relpath(path.resolve(), html_path.parent)
                screenshot_html = f"<img src=\"{escape(rel)}\" alt=\"screenshot step {idx}\">"
        items.append(
            f"""<div class="item" id="raw-{idx}">
              <div class="item-head">
                <span>Step {idx}</span>
                <span>{escape(', '.join(str(e.get('event_type')) for e in events))}</span>
              </div>
              <div>{escape(thought)}</div>
              <pre>{escape(json.dumps(action, indent=2, ensure_ascii=False)) if action else ''}</pre>
              {screenshot_html}
            </div>"""
        )
    return f"<div class=\"timeline\">{''.join(items)}</div>"


def _metric(label: str, value: Any) -> str:
    display = "" if value is None else str(value)
    return f"<div class=\"metric\"><span>{escape(label)}</span>{escape(display)}</div>"
