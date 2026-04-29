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
def list_configs(path: Path = Path("configs/experiments")) -> None:
    """List experiment YAML files."""
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
    output_dir: Path = Path("agentlens_results/mock_summary"),
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
        Path("agentlens_results/run_plan.json"),
        "--output",
        help="Where to write dry-run plan JSON.",
    ),
) -> None:
    """Run or dry-run an AgentLens experiment config."""
    from agentlens.adapters.browsergym_direct import BrowserGymDirectAdapter, BrowserGymDirectRunPlan
    from agentlens.adapters.screenshot_react import ScreenshotReactAdapter, ScreenshotReactRunPlan
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

    if all(isinstance(plan, BrowserGymDirectRunPlan) for plan in plans):
        result = BrowserGymDirectAdapter().run_many(plans)
        report_dir = plans[0].output_dir / "browsergym_direct_summary"
    elif all(isinstance(plan, ScreenshotReactRunPlan) for plan in plans):
        result = ScreenshotReactAdapter().run_many(
            plans,
            log_action=typer.echo if log_actions else None,
        )
        report_dir = plans[0].output_dir / "screenshot_react_summary"
    else:
        raise typer.BadParameter(
            "mixed or unsupported execution plans; use --dry-run to inspect plans"
        )

    report_paths = write_all_reports(result, report_dir)
    typer.echo(f"Executed {len(result.run_results)} run(s).")
    for report_path in report_paths:
        typer.echo(str(report_path))


if __name__ == "__main__":
    app()
