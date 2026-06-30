from pathlib import Path

import typer
from dotenv import load_dotenv

from agentlens.schemas import load_experiment_config

app = typer.Typer(
    help="AgentLens MVP command line interface.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Run AgentLens commands."""
    load_dotenv()


@app.command()
def doctor() -> None:
    """Check that the AgentLens environment is importable."""
    typer.echo("AgentLens environment is ready.")


@app.command("validate-config")
def validate_config(path: Path) -> None:
    """Validate an AgentLens experiment YAML file."""
    config = load_experiment_config(path)
    typer.echo(
        f"Valid config '{config.id}': "
        f"{len(config.models)} model(s), "
        f"{len(config.tool_harnesses)} tool harness(es), "
        f"{len(config.memory_harnesses)} memory harness(es), "
        f"{len(config.tasks)} task(s), "
        f"{len(config.runs)} run spec(s)."
    )


@app.command("list-configs")
def list_configs(path: Path = Path("configs/batches")) -> None:
    """List batch YAML files."""
    if not path.exists():
        raise typer.BadParameter(f"config directory does not exist: {path}")

    config_paths = sorted([*path.glob("*.yaml"), *path.glob("*.yml")])
    if not config_paths:
        typer.echo(f"No config files found in {path}")
        return

    for config_path in config_paths:
        typer.echo(str(config_path))


@app.command()
def summarize(
    path: Path,
    output_dir: Path = Path("runs/mock_summary"),
) -> None:
    """Generate mock summary artifacts from an experiment config."""
    from agentlens.evals.mock import make_mock_results
    from agentlens.reports.writers import write_all_reports

    config = load_experiment_config(path)
    result = make_mock_results(config)
    report_paths = write_all_reports(result, output_dir)
    typer.echo(
        f"Wrote mock summary for '{config.id}' with "
        f"{len(result.run_results)} run result(s) to {output_dir}"
    )
    for report_path in report_paths:
        typer.echo(str(report_path))


@app.command("trajectory-viewer")
def trajectory_viewer(
    path: Path,
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Where to write the static HTML viewer. Defaults next to the input file.",
    ),
) -> None:
    """Generate a static HTML viewer from summary.json or trajectory.json."""
    from agentlens.reports.trajectory_viewer import write_trajectory_viewer

    viewer_path = write_trajectory_viewer(path, output)
    typer.echo(str(viewer_path))


@app.command("process-trajectories")
def process_trajectories_cmd(
    inputs: list[Path] = typer.Argument(
        ...,
        help="One or more trajectory.json files or directories containing trajectories.",
    ),
    output_dir: Path = typer.Option(
        Path("runs/trajectory_processing"),
        "--output-dir",
        "-o",
        help="Directory for workflow_steps.jsonl and summary files.",
    ),
    repeat_threshold: int = typer.Option(
        5,
        "--repeat-threshold",
        min=2,
        help="Consecutive same-action threshold for repeated-action loop labels.",
    ),
) -> None:
    """Aggregate raw trajectories into workflow steps and behavior labels."""
    from agentlens.analysis.trajectory_processing import process_trajectories

    paths = process_trajectories(
        inputs,
        output_dir,
        repeat_threshold=repeat_threshold,
    )
    typer.echo(f"Processed trajectories into {output_dir}")
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


@app.command("compare-trajectory-methods")
def compare_trajectory_methods_cmd(
    trajectory: Path = typer.Argument(..., help="A single trajectory.json file."),
    output_dir: Path = typer.Option(
        Path("runs/method_comparison"),
        "--output-dir",
        "-o",
        help="Directory for method outputs and the side-by-side HTML report.",
    ),
    state_diff_threshold: float = typer.Option(
        8000.0,
        "--state-diff-threshold",
        help="Wang-style state-difference segmentation threshold.",
    ),
    annotation_mode: str = typer.Option(
        "rule",
        "--annotation-mode",
        help="Analysis mode: 'rule' for deterministic labels or 'llm' for LLM-refined labels.",
    ),
    llm_provider: str = typer.Option(
        "auto",
        "--llm-provider",
        help="LLM provider for --annotation-mode llm: auto, claude_cli, or openai.",
    ),
    llm_model: str | None = typer.Option(
        None,
        "--llm-model",
        help="Optional provider model name, e.g. gpt-5.4-nano.",
    ),
) -> None:
    """Compare Wang-style and Act-onomy-style analyses for one trajectory."""
    from agentlens.reports.method_comparison import write_method_comparison_report

    html_path = write_method_comparison_report(
        trajectory,
        output_dir,
        state_diff_threshold=state_diff_threshold,
        annotation_mode=annotation_mode,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    typer.echo(str(html_path))


@app.command("evaluate-trajectory")
def evaluate_trajectory_cmd(
    trajectory: Path = typer.Argument(..., help="A single trajectory.json file."),
    output_dir: Path = typer.Option(
        Path("runs/evaluations/single"),
        "--output-dir",
        "-o",
        help="Directory for evaluation_bundle.json.",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        help="Optional experiment config for recomputing current outcome validators.",
    ),
    state_diff_threshold: float = typer.Option(
        8000.0,
        "--state-diff-threshold",
        help="Wang-style state-difference segmentation threshold.",
    ),
) -> None:
    """Evaluate a completed trajectory after acting has finished."""
    from agentlens.evaluators.bundle import evaluate_trajectory_bundle

    bundle = evaluate_trajectory_bundle(
        trajectory,
        output_dir,
        config_path=config_path,
        state_diff_threshold=state_diff_threshold,
    )
    typer.echo(bundle.get("bundle_path") or output_dir / "evaluation_bundle.json")


@app.command("evaluate-batch")
def evaluate_batch_cmd(
    inputs: list[Path] = typer.Argument(
        ...,
        help="Trajectory files or directories containing trajectory.json files.",
    ),
    output_dir: Path = typer.Option(
        Path("runs/evaluations/batch"),
        "--output-dir",
        "-o",
        help="Directory for evaluation_bundles.jsonl and summary.",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        help="Optional experiment config for recomputing current outcome validators.",
    ),
    state_diff_threshold: float = typer.Option(
        8000.0,
        "--state-diff-threshold",
        help="Wang-style state-difference segmentation threshold.",
    ),
) -> None:
    """Evaluate many completed trajectories after acting has finished."""
    from agentlens.evaluators.bundle import evaluate_trajectory_batch

    paths = evaluate_trajectory_batch(
        inputs,
        output_dir,
        config_path=config_path,
        state_diff_threshold=state_diff_threshold,
    )
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


@app.command("matrix-dashboard")
def matrix_dashboard_cmd(
    config_path: Path = typer.Argument(..., help="Experiment config defining the matrix."),
    trajectory_root: Path = typer.Option(
        Path("runs/gpt54_datavoyager_smoke/raw"),
        "--trajectory-root",
        help="Directory to scan for generated trajectory.json files.",
    ),
    output: Path = typer.Option(
        Path("runs/gpt54_datavoyager_smoke/dashboard/dashboard.html"),
        "--output",
        "-o",
        help="Where to write the reusable dashboard HTML.",
    ),
    report_root: Path = typer.Option(
        Path("runs/gpt54_datavoyager_smoke/analysis/method_comparison"),
        "--report-root",
        help="Directory for per-trajectory method-comparison reports.",
    ),
    generate_reports: bool = typer.Option(
        False,
        "--generate-reports/--no-generate-reports",
        help="Generate missing per-trajectory method-comparison reports.",
    ),
    annotation_mode: str = typer.Option(
        "llm",
        "--annotation-mode",
        help="Analysis mode for generated reports: rule or llm.",
    ),
    llm_provider: str = typer.Option(
        "openai",
        "--llm-provider",
        help="LLM provider for generated reports.",
    ),
    llm_model: str = typer.Option(
        "gpt-5.4-mini",
        "--llm-model",
        help="LLM model for generated reports.",
    ),
) -> None:
    """Render a reusable model x task x harness trajectory dashboard."""
    from agentlens.reports.experiment_dashboard import write_matrix_dashboard

    config = load_experiment_config(config_path)
    html_path = write_matrix_dashboard(
        config,
        trajectory_root=trajectory_root,
        output_path=output,
        report_root=report_root,
        generate_reports=generate_reports,
        annotation_mode=annotation_mode,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    typer.echo(str(html_path))


@app.command()
def run(
    path: Path,
    run_id: str | None = typer.Option(None, "--run-id", help="Only plan/run one run id."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve run plans without executing browser/model calls.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Execute supported no-model runners.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Run browser-backed adapters in headed mode so you can watch live.",
    ),
    log_actions: bool = typer.Option(
        False,
        "--log-actions",
        help="Print action and screenshot events while executing.",
    ),
    max_runs: int | None = typer.Option(
        None,
        "--max-runs",
        min=1,
        help="Limit expanded seed/trial plans.",
    ),
    output_path: Path = typer.Option(
        Path("runs/run_plan.json"),
        "--output",
        help="Where to write dry-run plan JSON.",
    ),
) -> None:
    """Run or dry-run an AgentLens experiment config."""
    from agentlens.reports.writers import write_all_reports
    from agentlens.run_plans import build_run_plans, with_live_mode, write_run_plan_json

    config = load_experiment_config(path)
    plans = build_run_plans(config, run_id=run_id, max_runs=max_runs)

    if dry_run:
        write_run_plan_json(plans, output_path)
        typer.echo(f"Resolved {len(plans)} run plan(s) for experiment '{config.id}'.")
        for plan in plans:
            typer.echo(
                f"- {plan.run_id} seed={plan.seed} trial={plan.trial} "
                f"model={plan.model.id} tool={plan.tool_harness.id} "
                f"memory={plan.memory_harness.id} task={plan.task.id} status={plan.status}"
            )
            for note in plan.notes:
                typer.echo(f"  note: {note}")
        typer.echo(f"Wrote dry-run plan to {output_path}")
        return

    if not execute:
        raise typer.BadParameter("real execution requires --execute; use --dry-run to inspect plans")

    if live:
        plans = with_live_mode(plans)
        typer.echo("Live mode enabled: launching headed browser windows.")

    adapters = {getattr(plan, "adapter", None) for plan in plans}
    if adapters == {"browsergym_direct"}:
        from agentlens.adapters.browsergym_direct import BrowserGymDirectAdapter

        result = BrowserGymDirectAdapter().run_many(plans)
        report_dir = plans[0].output_dir / "browsergym_direct_summary"
    elif adapters == {"screenshot_react"}:
        from agentlens.adapters.screenshot_react import ScreenshotReactAdapter

        result = ScreenshotReactAdapter().run_many(
            plans,
            log_action=typer.echo if log_actions else None,
        )
        report_dir = plans[0].output_dir / "summary"
    elif adapters == {"desktop_react"}:
        from agentlens.adapters.desktop_react import DesktopReactAdapter

        result = DesktopReactAdapter().run_many(
            plans,
            log_action=typer.echo if log_actions else None,
        )
        report_dir = plans[0].output_dir / "desktop_react_summary"
    elif adapters == {"browsergym_bridge"}:
        from agentlens.adapters.browsergym_bridge import BrowserGymBridgeAdapter

        result = BrowserGymBridgeAdapter().run_many(
            plans,
            log_action=typer.echo if log_actions else None,
        )
        report_dir = plans[0].output_dir / "browsergym_bridge_summary"
    elif adapters == {"cocoabench"}:
        from agentlens.adapters.cocoabench import CocoaBenchAdapter

        result = CocoaBenchAdapter().run_many(
            plans,
            log_action=typer.echo if log_actions else None,
        )
        report_dir = plans[0].output_dir / "cocoabench_summary"
    else:
        raise typer.BadParameter(
            "mixed or unsupported execution plans; use --dry-run to inspect plans"
        )

    report_paths = write_all_reports(result, report_dir)
    typer.echo(f"Executed {len(result.run_results)} run(s).")
    for report_path in report_paths:
        typer.echo(str(report_path))


@app.command("import-online-mind2web")
def import_online_mind2web(
    output: Path = typer.Option(
        Path("configs/batches/online_mind2web_screenshot_react.yaml"),
        "--output",
        help="Where to write the generated experiment config.",
    ),
    limit: int = typer.Option(5, "--limit", min=1, help="How many tasks to include."),
    offset: int = typer.Option(0, "--offset", min=0, help="Offset into the dataset."),
    level: str | None = typer.Option(
        None, "--level", help="Filter to easy|medium|hard. Default: any."
    ),
    model_id: str = typer.Option(
        "gpt-5.4", "--model", help="OpenAI vision model id used by the agent."
    ),
    judge_model: str = typer.Option(
        "gpt-4o", "--judge", help="OpenAI vision model id used by WebJudge."
    ),
    max_steps: int = typer.Option(25, "--max-steps", help="Step cap per task."),
) -> None:
    """Generate an AgentLens config from the Online-Mind2Web HF dataset.

    Requires HF_TOKEN in .env (gated dataset).
    """
    import yaml
    from datasets import load_dataset

    ds = load_dataset("osunlp/Online-Mind2Web", split="test")
    if level:
        ds = ds.filter(lambda ex: ex.get("level") == level)
    rows = list(ds)[offset : offset + limit]
    if not rows:
        raise typer.BadParameter(
            f"no tasks after offset={offset} limit={limit} level={level!r}"
        )

    tasks = []
    runs = []
    for row in rows:
        short_id = str(row["task_id"])[:12]
        task_id = f"om2w_{short_id}"
        run_id = f"{task_id}_{model_id.replace('.', '_').replace('-', '_')}"
        tasks.append(
            {
                "id": task_id,
                "benchmark": "online_mind2web",
                "task_id": row["task_id"],
                "goal": row["confirmed_task"],
                "start_url": row["website"],
                "capability_required": ["browser_ui", "web_navigation"],
                "validator": "webjudge",
                "answer_validator": "webjudge",
                "extra": {
                    "reference_length": row.get("reference_length"),
                    "level": row.get("level"),
                    "judge_model": judge_model,
                },
            }
        )
        runs.append(
            {
                "id": run_id,
                "model": "agent_model",
                "tool_harness": "screenshot_react_browser",
                "memory_harness": "no_memory",
                "task": task_id,
                "seeds": [0],
                "trials": 1,
                "max_steps": max_steps,
                "output_dir": "runs/online_mind2web_screenshot_react",
                "tags": ["online_mind2web", "gpt5"],
            }
        )

    config = {
        "schema_version": "0.1",
        "id": "online_mind2web_screenshot_react",
        "description": (
            f"Online-Mind2Web tasks generated from osunlp/Online-Mind2Web "
            f"(limit={limit} offset={offset} level={level or 'any'}). "
            f"Agent: {model_id}. WebJudge: {judge_model}."
        ),
        "models": [
            {
                "id": "agent_model",
                "provider": "openai",
                "name": model_id,
                "temperature": 0.0,
                "vision": True,
                "max_output_tokens": 1024,
            }
        ],
        "tool_harnesses": [
            {
                "id": "screenshot_react_browser",
                "runner": "screenshot_react",
                "tier": "browser_only",
                "tools": [
                    "browser.screenshot",
                    "browser.click",
                    "browser.double_click",
                    "browser.type",
                    "browser.scroll",
                    "browser.wait",
                    "browser.move",
                    "browser.keypress",
                    "browser.drag",
                    "browser.goto",
                    "browser.back",
                    "browser.forward",
                    "browser.reload",
                    "task.final_answer",
                ],
                "prompt_version": "screenshot_react_json_v1",
                "extra": {
                    "headless": True,
                    "settle_ms": 2000,
                    "viewport": {"width": 1600, "height": 900},
                },
            }
        ],
        "memory_harnesses": [{"id": "no_memory", "kind": "none", "scope": "none"}],
        "tasks": tasks,
        "runs": runs,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    typer.echo(
        f"Wrote {len(tasks)} task(s) to {output} (model={model_id}, judge={judge_model})"
    )


if __name__ == "__main__":
    app()
