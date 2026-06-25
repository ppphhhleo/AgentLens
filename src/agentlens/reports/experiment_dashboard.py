from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from typing import Any

from agentlens.harnesses.tool_gating import ToolSet, render_action_schema
from agentlens.models.openai_tool_call import SYSTEM_PROMPT_TEMPLATE as TOOL_CALL_PROMPT_TEMPLATE
from agentlens.models.openai_vision import SYSTEM_PROMPT_TEMPLATE as LEGACY_JSON_PROMPT_TEMPLATE
from agentlens.reports.method_comparison import write_method_comparison_report
from agentlens.schemas import ExperimentConfig
from agentlens.validators.answers import validate_answer


def write_matrix_dashboard(
    config: ExperimentConfig,
    *,
    trajectory_root: Path,
    output_path: Path,
    report_root: Path,
    generate_reports: bool = False,
    annotation_mode: str = "llm",
    llm_provider: str = "openai",
    llm_model: str = "gpt-5.4-mini",
) -> Path:
    """Render a reusable model x task x harness dashboard for one experiment config."""
    trajectory_root = trajectory_root.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    report_root = report_root.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    trajectories = _latest_trajectories_by_run(trajectory_root)
    model_by_id = {model.id: model for model in config.models}
    task_by_id = {task.id: task for task in config.tasks}
    harness_by_id = {harness.id: harness for harness in config.tool_harnesses}

    cells = []
    for run in config.runs:
        trajectory_path = trajectories.get(run.id)
        report_path = None
        trajectory = None
        if trajectory_path is not None:
            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
            report_path = report_root / _safe_name(run.id) / "method_comparison.html"
            if generate_reports or not report_path.exists():
                if generate_reports:
                    write_method_comparison_report(
                        trajectory_path,
                        report_path.parent,
                        annotation_mode=annotation_mode,
                        llm_provider=llm_provider,
                        llm_model=llm_model,
                    )
        cells.append(
            {
                "run": run,
                "model": model_by_id[run.model],
                "task": task_by_id[run.task],
                "harness": harness_by_id[run.tool_harness],
                "trajectory_path": trajectory_path,
                "report_path": report_path if report_path and report_path.exists() else None,
                "trajectory": trajectory,
            }
        )

    output_path.write_text(
        _render_dashboard(
            config,
            cells,
            output_path=output_path,
            trajectory_root=trajectory_root,
            report_root=report_root,
            annotation_mode=annotation_mode,
            llm_provider=llm_provider,
            llm_model=llm_model,
        ),
        encoding="utf-8",
    )
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(
            {
                "experiment_id": config.id,
                "trajectory_root": str(trajectory_root),
                "report_root": str(report_root),
                "output_path": str(output_path),
                "generate_reports": generate_reports,
                "annotation_mode": annotation_mode,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "runs": [_cell_manifest(cell) for cell in cells],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return output_path


def _latest_trajectories_by_run(root: Path) -> dict[str, Path]:
    latest: dict[str, tuple[float, Path]] = {}
    for path in root.glob("**/trajectory.json"):
        try:
            trajectory = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run_id = trajectory.get("run_id")
        if not run_id:
            continue
        mtime = path.stat().st_mtime
        if run_id not in latest or mtime > latest[run_id][0]:
            latest[run_id] = (mtime, path)
    return {run_id: path for run_id, (_, path) in latest.items()}


def _render_dashboard(
    config: ExperimentConfig,
    cells: list[dict[str, Any]],
    *,
    output_path: Path,
    trajectory_root: Path,
    report_root: Path,
    annotation_mode: str,
    llm_provider: str,
    llm_model: str,
) -> str:
    models = list(config.models)
    harnesses = list(config.tool_harnesses)
    tasks = list(config.tasks)
    by_key = {
        (cell["task"].id, cell["model"].id, cell["harness"].id): cell
        for cell in cells
    }
    completed = sum(1 for cell in cells if cell.get("trajectory_path"))
    successes = sum(
        1
        for cell in cells
        if (((cell.get("trajectory") or {}).get("metrics") or {}).get("success") is True)
    )
    header_cols = "".join(
        f"<th>{escape(_task_label(task.id))}<br><span>{escape(task.task_id)}</span></th>"
        for task in tasks
    )
    rows = []
    for model in models:
        for harness in harnesses:
            row_cells = []
            for task in tasks:
                cell = by_key.get((task.id, model.id, harness.id))
                row_cells.append(_render_cell(cell, output_path))
            row_label = f"{model.name} / {_harness_short(harness)}"
            rows.append(
                f"""<tr>
              <th class="row-col">
                {_render_row_context(model, harness, row_label)}
              </th>
              {''.join(row_cells)}
            </tr>"""
            )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(config.id)} Dashboard</title>
  <style>
    :root {{
      --bg: #f7f7f4;
      --panel: #fff;
      --ink: #222622;
      --muted: #6d746d;
      --line: #d8ded6;
      --ok: #2f7b4f;
      --fail: #a64032;
      --missing: #8a8f89;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 18px 22px 12px;
      border-bottom: 1px solid var(--line);
      background: rgba(247,247,244,.94);
      position: sticky;
      top: 0;
      z-index: 5;
      backdrop-filter: blur(10px);
    }}
    h1 {{ margin: 0 0 6px; font-size: 22px; }}
    .small {{ color: var(--muted); font-size: 12px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
    .chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 9px;
      background: #fbfbf8;
      font-size: 12px;
    }}
    main {{ padding: 16px; }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }}
    table {{
      width: 100%;
      min-width: 1100px;
      border-collapse: collapse;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      border-right: 1px solid var(--line);
      padding: 9px;
      vertical-align: top;
      text-align: left;
    }}
    tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
    th:last-child, td:last-child {{ border-right: 0; }}
    thead th {{
      background: #eeeeeb;
      font-size: 12px;
      white-space: nowrap;
    }}
    thead th span {{ color: var(--muted); font-weight: 500; }}
    .row-col {{
      width: 260px;
      background: #fbfbf8;
      position: sticky;
      left: 0;
      z-index: 2;
    }}
    .row-col span {{
      display: block;
      color: var(--muted);
      font-weight: 400;
      margin-top: 4px;
    }}
    details {{
      margin-top: 7px;
      font-weight: 400;
    }}
    summary {{
      cursor: pointer;
      color: #235c73;
      font-size: 12px;
      font-weight: 650;
    }}
    .tool-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 5px;
    }}
    .tool-pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 6px;
      background: #f3f5f1;
      color: #333833;
      font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    pre.prompt-preview {{
      margin: 6px 0 0;
      max-height: 260px;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #f0f2ed;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      font: 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
      color: #2f352f;
    }}
    .cell-status {{
      display: inline-block;
      border-radius: 999px;
      color: white;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .ok {{ background: var(--ok); }}
    .fail {{ background: var(--fail); }}
    .missing {{ background: var(--missing); }}
    .cell-links {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }}
    .answer {{
      margin-top: 5px;
      padding-top: 5px;
      border-top: 1px dashed var(--line);
      color: #343934;
      overflow-wrap: anywhere;
    }}
    .answer span {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .02em;
    }}
    a {{ color: #235c73; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{ font-size: 11px; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(config.id)}</h1>
    <div class="small">Reusable matrix dashboard for generated trajectories and per-trajectory method reports.</div>
    <div class="chips">
      <span class="chip">conditions: {len(cells)}</span>
      <span class="chip">completed: {completed}/{len(cells)}</span>
      <span class="chip">successes: {successes}</span>
      <span class="chip">analysis: {escape(annotation_mode)} / {escape(llm_provider)} / {escape(llm_model)}</span>
    </div>
    <div class="small">trajectory root: <code>{escape(str(trajectory_root))}</code></div>
    <div class="small">report root: <code>{escape(str(report_root))}</code></div>
  </header>
  <main>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th class="row-col">Model / Harness</th>{header_cols}</tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
  </main>
</body>
</html>"""


def _render_cell(cell: dict[str, Any] | None, output_path: Path) -> str:
    if cell is None:
        return '<td><span class="cell-status missing">not planned</span></td>'
    trajectory = cell.get("trajectory") or {}
    metrics = trajectory.get("metrics") or {}
    trajectory_path = cell.get("trajectory_path")
    report_path = cell.get("report_path")
    if trajectory_path is None:
        return (
            '<td><span class="cell-status missing">missing</span>'
            f'<div class="small"><code>{escape(cell["run"].id)}</code></div></td>'
        )
    success = metrics.get("success")
    cls = "ok" if success is True else "missing"
    label = "success" if success is True else "recorded"
    answer = _final_answer(trajectory)
    answer_html = (
        f'<div class="answer"><span>answer</span><br>{escape(answer)}</div>'
        if answer
        else '<div class="answer"><span>answer</span><br><span class="small">none</span></div>'
    )
    current_validation = _current_validation(answer, cell["task"])
    current_html = ""
    if current_validation is not None:
        current_success, current_score, current_message = current_validation
        if current_success != success or current_score != metrics.get("score"):
            current_label = "success" if current_success is True else "recorded"
            current_html = (
                f'<div class="small">current validator: '
                f'{escape(current_label)} / {escape(str(current_score))} '
                f'({escape(current_message)})</div>'
            )
    links = [
        _link("trajectory", trajectory_path, output_path),
    ]
    if report_path:
        links.append(_link("analysis", report_path, output_path))
    return f"""<td>
      <span class="cell-status {cls}">{escape(label)}</span>
      <div>score {escape(str(metrics.get("score")))} | steps {escape(str(metrics.get("steps")))}</div>
      {answer_html}
      {current_html}
      <div class="small"><code>{escape(cell["run"].id)}</code></div>
      <div class="cell-links">{''.join(links)}</div>
    </td>"""


def _render_row_context(model: Any, harness: Any, row_label: str) -> str:
    tools = list(getattr(harness, "tools", []) or [])
    tool_html = "".join(f'<span class="tool-pill">{escape(tool)}</span>' for tool in tools)
    prompt = _initial_prompt_preview(model, harness)
    return f"""
      <strong>{escape(row_label)}</strong>
      <span>{escape(_harness_detail(harness))}</span>
      <details>
        <summary>tools ({len(tools)})</summary>
        <div class="tool-list">{tool_html}</div>
      </details>
      <details>
        <summary>initial prompt</summary>
        <pre class="prompt-preview">{escape(prompt)}</pre>
      </details>
    """


def _initial_prompt_preview(model: Any, harness: Any) -> str:
    toolset = ToolSet.from_harness(harness)
    addressing_modes = list((getattr(harness, "extra", {}) or {}).get("addressing_modes", ["coordinate"]))
    input_modes = list((getattr(harness, "extra", {}) or {}).get("input_modes", ["screenshot"]))
    model_extra = getattr(model, "extra", {}) or {}
    if model_extra.get("interaction_backend") == "tool_call":
        return TOOL_CALL_PROMPT_TEMPLATE.format(
            goal="[task goal inserted at runtime]",
            context_description=_context_description(input_modes),
            action_policy=_action_policy_preview(harness),
        )
    return LEGACY_JSON_PROMPT_TEMPLATE.format(
        goal="[task goal inserted at runtime]",
        action_schema=render_action_schema(toolset, addressing_modes),
        context_description=_context_description(input_modes),
    )


def _context_description(input_modes: list[str]) -> str:
    modes = set(input_modes)
    if "screenshot" in modes and "axtree" in modes:
        return "You see one screenshot and one interactive-element tree per step."
    if "screenshot" in modes or "set_of_marks" in modes:
        return "You see one screenshot per step."
    if "axtree" in modes:
        return "You see an interactive-element tree and any tool output per step. No screenshot is provided to you."
    return "You see textual context and any tool output per step. No screenshot is provided to you."


def _action_policy_preview(harness: Any) -> str:
    extra = getattr(harness, "extra", {}) or {}
    parallel = bool(extra.get("parallel_tool_calls", False))
    max_actions = max(1, int(extra.get("max_actions_per_round", 1)))
    if parallel and max_actions > 1:
        return (
            f"You may call up to {max_actions} tools in one step when they are "
            "a short, safe sequence that does not require inspecting intermediate "
            "results. Use one tool call when the next action depends on what "
            "changes on screen."
        )
    return "Use exactly one tool call per step."


def _link(label: str, path: Path, output_path: Path) -> str:
    rel = os.path.relpath(path.resolve(), output_path.parent)
    return f'<a href="{escape(rel)}">{escape(label)}</a>'


def _cell_manifest(cell: dict[str, Any]) -> dict[str, Any]:
    trajectory = cell.get("trajectory") or {}
    metrics = trajectory.get("metrics") or {}
    answer = _final_answer(trajectory)
    current_validation = _current_validation(answer, cell["task"])
    return {
        "run_id": cell["run"].id,
        "task": cell["task"].id,
        "model": cell["model"].name,
        "harness": cell["harness"].id,
        "harness_tier": cell["harness"].tier.value,
        "tools": list(cell["harness"].tools),
        "trajectory_path": str(cell["trajectory_path"]) if cell.get("trajectory_path") else None,
        "report_path": str(cell["report_path"]) if cell.get("report_path") else None,
        "success": metrics.get("success"),
        "score": metrics.get("score"),
        "steps": metrics.get("steps"),
        "final_answer": answer,
        "current_validation": {
            "success": current_validation[0],
            "score": current_validation[1],
            "message": current_validation[2],
        } if current_validation else None,
    }


def _final_answer(trajectory: dict[str, Any]) -> str | None:
    for event in trajectory.get("events", []):
        data = event.get("data") or {}
        action = data.get("action") or {}
        if action.get("type") == "final_answer":
            answer = action.get("answer")
            if answer is not None:
                return str(answer)
    return None


def _current_validation(answer: str | None, task: Any) -> tuple[bool | None, float | None, str] | None:
    if not answer:
        return None
    try:
        return validate_answer(answer, task)
    except Exception:
        return None


def _harness_short(harness: Any) -> str:
    return str(getattr(harness, "id", "") or "")


def _harness_detail(harness: Any) -> str:
    tier = getattr(getattr(harness, "tier", None), "value", None) or str(
        getattr(harness, "tier", "") or ""
    )
    tools = getattr(harness, "tools", []) or []
    return f"{tier}; {len(tools)} tools"


def _task_label(task_id: str) -> str:
    labels = {
        "datavoyager_most_fuel_efficient": "Most fuel-efficient car",
        "datavoyager_europe_100hp_4cyl_count": "Europe <100hp + 4 cylinders",
    }
    return labels.get(task_id, task_id)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
