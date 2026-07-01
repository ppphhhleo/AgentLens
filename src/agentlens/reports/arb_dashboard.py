"""ARB Evaluation Dashboard — static HTML report with WHO/WHEN breakdowns.

Generates a self-contained HTML dashboard showing ARB 4-dimensional
judge results sliced by agent model (WHO) and temporal stability (WHEN).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentlens.evaluators.arb_dimensions import (
    aggregate_by_when,
    aggregate_by_who,
    aggregate_by_who_when,
    evaluate_arb_dimensions,
)


def write_arb_dashboard(
    results_dir: Path,
    output_path: Path,
    *,
    title: str = "ARB Evaluation Dashboard",
) -> Path:
    """Generate a static HTML dashboard for ARB judge evaluation results."""
    results_dir = Path(results_dir)
    output_path = Path(output_path)

    evaluations = _load_evaluations(results_dir)
    who_stats = aggregate_by_who(evaluations)
    when_stats = aggregate_by_when(evaluations)
    who_when_stats = aggregate_by_who_when(evaluations)

    has_when = bool(when_stats)
    benchmarks = sorted({e.get("arb_benchmark", "") for e in evaluations if e.get("arb_benchmark")})

    html = _render_html(
        title=title,
        evaluations=evaluations,
        who_stats=who_stats,
        when_stats=when_stats,
        who_when_stats=who_when_stats,
        has_when=has_when,
        benchmarks=benchmarks,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _load_evaluations(results_dir: Path) -> list[dict[str, Any]]:
    """Load trajectory.json files from the results directory and extract ARB dimensions."""
    evaluations: list[dict[str, Any]] = []

    for traj_file in sorted(results_dir.rglob("trajectory.json")):
        try:
            trajectory = json.loads(traj_file.read_text(encoding="utf-8"))
            if (trajectory.get("task") or {}).get("benchmark") == "arb":
                ev = evaluate_arb_dimensions(trajectory)
                ev["trajectory_path"] = str(traj_file)
                ev["task_id"] = (trajectory.get("task") or {}).get("task_id", "")
                evaluations.append(ev)
        except (json.JSONDecodeError, KeyError):
            continue

    return evaluations


def _fmt_pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "—"


def _fmt_float(value: float | None, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}" if value is not None else "—"


def _color_cell(value: float | None, good_high: bool = True) -> str:
    if value is None:
        return ""
    if good_high:
        if value >= 0.7:
            return "background: #c6efce; color: #006100;"
        elif value >= 0.4:
            return "background: #ffeb9c; color: #9c6500;"
        else:
            return "background: #ffc7ce; color: #9c0006;"
    else:
        if value <= 0.3:
            return "background: #c6efce; color: #006100;"
        elif value <= 0.6:
            return "background: #ffeb9c; color: #9c6500;"
        else:
            return "background: #ffc7ce; color: #9c0006;"


def _render_stats_table(stats: dict[str, dict[str, Any]], row_label: str) -> str:
    rows = []
    for key, s in stats.items():
        n = s.get("n", 0)
        rows.append(f"""
        <tr>
            <td><strong>{key}</strong></td>
            <td>{n}</td>
            <td style="{_color_cell(s.get('success_rate'))}">{_fmt_pct(s.get('success_rate'))}</td>
            <td>{_fmt_float(s.get('mean_optimality'))}</td>
            <td style="{_color_cell(s.get('side_effect_rate'), good_high=False)}">{_fmt_pct(s.get('side_effect_rate'))}</td>
            <td style="{_color_cell(s.get('looping_rate'), good_high=False)}">{_fmt_pct(s.get('looping_rate'))}</td>
            <td>{_fmt_float(s.get('mean_composite_score'))}</td>
        </tr>""")

    return f"""
    <table>
        <thead>
            <tr>
                <th>{row_label}</th>
                <th>N</th>
                <th>Success Rate</th>
                <th>Mean Optimality (1-4)</th>
                <th>Side Effect Rate</th>
                <th>Looping Rate</th>
                <th>Composite Score</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>"""


def _render_who_when_heatmap(who_when_stats: dict[str, dict[str, dict[str, Any]]]) -> str:
    if not who_when_stats:
        return ""

    all_whens = sorted({w for whens in who_when_stats.values() for w in whens})
    if not all_whens:
        return ""

    header = "<th>Agent / WHEN</th>" + "".join(f"<th>{w}</th>" for w in all_whens)
    rows = []
    for who, whens in sorted(who_when_stats.items()):
        cells = []
        for w in all_whens:
            s = whens.get(w, {})
            rate = s.get("success_rate")
            cells.append(
                f'<td style="{_color_cell(rate)}">'
                f'{_fmt_pct(rate)} (n={s.get("n", 0)})</td>'
            )
        rows.append(f"<tr><td><strong>{who}</strong></td>{''.join(cells)}</tr>")

    return f"""
    <h2>WHO x WHEN Heatmap (Success Rate)</h2>
    <table>
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
    </table>"""


def _render_html(
    *,
    title: str,
    evaluations: list[dict[str, Any]],
    who_stats: dict[str, dict[str, Any]],
    when_stats: dict[str, dict[str, Any]],
    who_when_stats: dict[str, dict[str, dict[str, Any]]],
    has_when: bool,
    benchmarks: list[str],
) -> str:
    n_total = len(evaluations)
    n_success = sum(1 for e in evaluations if e.get("success") == "Successful")

    when_section = ""
    if has_when:
        when_section = f"""
    <h2>WHEN Breakdown (Temporal Stability)</h2>
    <p>WHEN categories from AssistantBench: <strong>Static</strong> (state doesn't change),
    <strong>Stable</strong> (changes gradually), <strong>Unlikely</strong> (may change but unlikely to affect solution).</p>
    {_render_stats_table(when_stats, "WHEN")}
    {_render_who_when_heatmap(who_when_stats)}"""

    detail_rows = []
    for ev in evaluations:
        detail_rows.append(f"""
        <tr>
            <td>{ev.get('task_id', '')}</td>
            <td>{ev.get('who', '')}</td>
            <td>{ev.get('when', '—')}</td>
            <td>{ev.get('success', '—')}</td>
            <td>{ev.get('optimality', '—')}</td>
            <td>{ev.get('side_effect', '—')}</td>
            <td>{ev.get('looping', '—')}</td>
            <td>{_fmt_float(ev.get('composite_score'))}</td>
        </tr>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           max-width: 1200px; margin: 0 auto; padding: 20px; background: #fafafa; }}
    h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
    h2 {{ color: #16213e; margin-top: 30px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; background: white;
             box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    th, td {{ border: 1px solid #e0e0e0; padding: 10px 14px; text-align: left; }}
    th {{ background: #16213e; color: white; font-weight: 600; }}
    tr:nth-child(even) {{ background: #f8f9fa; }}
    tr:hover {{ background: #e8eaf6; }}
    .summary {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
    .card {{ background: white; border-radius: 8px; padding: 20px; min-width: 180px;
             box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
    .card .value {{ font-size: 2em; font-weight: bold; color: #16213e; }}
    .card .label {{ color: #666; margin-top: 5px; }}
    details {{ margin: 10px 0; }}
    summary {{ cursor: pointer; font-weight: 600; color: #16213e; }}
</style>
</head>
<body>
    <h1>{title}</h1>
    <p>Benchmarks: <strong>{', '.join(benchmarks) or 'N/A'}</strong> |
       Generated from {n_total} trajectory evaluation(s)</p>

    <div class="summary">
        <div class="card">
            <div class="value">{n_total}</div>
            <div class="label">Total Evaluations</div>
        </div>
        <div class="card">
            <div class="value">{_fmt_pct(n_success / n_total if n_total else None)}</div>
            <div class="label">Overall Success Rate</div>
        </div>
        <div class="card">
            <div class="value">{len(who_stats)}</div>
            <div class="label">Agent Models (WHO)</div>
        </div>
        <div class="card">
            <div class="value">{len(when_stats) if has_when else '—'}</div>
            <div class="label">WHEN Categories</div>
        </div>
    </div>

    <h2>WHO Breakdown (Agent Models)</h2>
    {_render_stats_table(who_stats, "Agent (WHO)")}

    {when_section}

    <details>
        <summary>Per-Task Detail ({n_total} evaluations)</summary>
        <table>
            <thead>
                <tr>
                    <th>Task ID</th>
                    <th>WHO</th>
                    <th>WHEN</th>
                    <th>Success</th>
                    <th>Optimality</th>
                    <th>Side Effect</th>
                    <th>Looping</th>
                    <th>Composite</th>
                </tr>
            </thead>
            <tbody>{''.join(detail_rows)}</tbody>
        </table>
    </details>

    <p style="color: #999; margin-top: 30px; font-size: 0.85em;">
        Generated by AgentLens ARB Dashboard.
        Scoring: Success (binary), Side Effects (binary), Optimality (1-4 Likert), Looping (binary).
        Composite = success*0.4 + optimality_norm*0.3 + no_side_effect*0.15 + no_looping*0.15.
    </p>
</body>
</html>"""
