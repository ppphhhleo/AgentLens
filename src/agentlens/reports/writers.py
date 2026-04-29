from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agentlens.evals.base import ExperimentResult, SingleRunResult


def _json_default(value: Any) -> str:
    return str(value)


def write_summary_json(result: ExperimentResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "summary.json"
    path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return path


def write_summary_csv(result: ExperimentResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "summary.csv"
    fieldnames = [
        "experiment_id",
        "run_id",
        "trajectory_id",
        "model",
        "tool_harness",
        "memory_harness",
        "task",
        "seed",
        "trial",
        "success",
        "score",
        "duration_ms",
        "steps",
        "tokens_input",
        "tokens_output",
        "cost_usd",
        "tool_calls",
    ]

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for run_result in result.run_results:
            trajectory = run_result.trajectory
            writer.writerow(
                {
                    "experiment_id": trajectory.experiment_id,
                    "run_id": trajectory.run_id,
                    "trajectory_id": trajectory.trajectory_id,
                    "model": trajectory.model.id,
                    "tool_harness": trajectory.tool_harness.id,
                    "memory_harness": trajectory.memory_harness.id,
                    "task": trajectory.task.id,
                    "seed": trajectory.seed,
                    "trial": trajectory.trial,
                    "success": trajectory.metrics.success,
                    "score": trajectory.metrics.score,
                    "duration_ms": trajectory.metrics.duration_ms,
                    "steps": trajectory.metrics.steps,
                    "tokens_input": trajectory.metrics.tokens_input,
                    "tokens_output": trajectory.metrics.tokens_output,
                    "cost_usd": trajectory.metrics.cost_usd,
                    "tool_calls": trajectory.metrics.tool_calls,
                }
            )

    return path


def make_html_report(result: ExperimentResult) -> str:
    metric_rows = "\n".join(
        f"<tr><td>{name}</td><td>{value}</td></tr>" for name, value in sorted(result.metrics.items())
    )
    run_rows = "\n".join(_run_result_to_html_row(run_result) for run_result in result.run_results)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AgentLens Report - {result.experiment_id}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; line-height: 1.4; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>AgentLens Report</h1>
  <p><strong>Experiment:</strong> <code>{result.experiment_id}</code></p>
  <h2>Aggregate Metrics</h2>
  <table>
    <thead><tr><th>Metric</th><th>Value</th></tr></thead>
    <tbody>{metric_rows}</tbody>
  </table>
  <h2>Runs</h2>
  <table>
    <thead>
      <tr>
        <th>Run</th><th>Model</th><th>Tool Harness</th><th>Memory</th>
        <th>Task</th><th>Seed</th><th>Trial</th><th>Success</th><th>Score</th><th>Steps</th>
      </tr>
    </thead>
    <tbody>{run_rows}</tbody>
  </table>
</body>
</html>
"""


def write_html_report(result: ExperimentResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "report.html"
    path.write_text(make_html_report(result), encoding="utf-8")
    return path


def write_all_reports(result: ExperimentResult, output_dir: Path) -> list[Path]:
    from agentlens.reports.trajectory_viewer import write_trajectory_viewer

    paths = [
        write_summary_json(result, output_dir),
        write_summary_csv(result, output_dir),
        write_html_report(result, output_dir),
    ]

    raw_path = output_dir / "summary.raw.json"
    raw_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2, default=_json_default))
    paths.append(raw_path)
    paths.append(write_trajectory_viewer(paths[0]))
    return paths


def _run_result_to_html_row(run_result: SingleRunResult) -> str:
    trajectory = run_result.trajectory
    return (
        "<tr>"
        f"<td>{trajectory.run_id}</td>"
        f"<td>{trajectory.model.id}</td>"
        f"<td>{trajectory.tool_harness.id}</td>"
        f"<td>{trajectory.memory_harness.id}</td>"
        f"<td>{trajectory.task.id}</td>"
        f"<td>{trajectory.seed}</td>"
        f"<td>{trajectory.trial}</td>"
        f"<td>{trajectory.metrics.success}</td>"
        f"<td>{trajectory.metrics.score}</td>"
        f"<td>{trajectory.metrics.steps}</td>"
        "</tr>"
    )
