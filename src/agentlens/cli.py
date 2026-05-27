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
    from agentlens.adapters.browsergym_bridge import BrowserGymBridgeAdapter, BrowserGymBridgeRunPlan
    from agentlens.adapters.browsergym_direct import BrowserGymDirectAdapter, BrowserGymDirectRunPlan
    from agentlens.adapters.cocoabench import CocoaBenchAdapter, CocoaBenchRunPlan
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
    elif all(isinstance(plan, BrowserGymBridgeRunPlan) for plan in plans):
        result = BrowserGymBridgeAdapter().run_many(
            plans,
            log_action=typer.echo if log_actions else None,
        )
        report_dir = plans[0].output_dir / "browsergym_bridge_summary"
    elif all(isinstance(plan, CocoaBenchRunPlan) for plan in plans):
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


@app.command("human-run")
def human_run(
    path: Path,
    task_id: str = typer.Option(
        ..., "--task-id", help="ID of the task to run (from the YAML config)."
    ),
    output_dir: Path = typer.Option(
        Path("agentlens_results/human_runs"),
        "--output-dir",
        help="Directory for trajectory output.",
    ),
    timeout: int = typer.Option(
        600,
        "--timeout",
        help="Timeout in seconds for the human session.",
    ),
    screenshot_interval: float = typer.Option(
        5.0,
        "--screenshot-interval",
        help="Seconds between periodic screenshots.",
    ),
    log_actions: bool = typer.Option(
        True,
        "--log-actions",
        help="Print status messages during the session.",
    ),
) -> None:
    """Run a task for human interaction via VNC with trajectory recording.

    Opens a headed browser on DISPLAY=:99, injects a JS event recorder,
    and waits for the human to complete the task via the noVNC overlay.

    The human connects via noVNC at http://localhost:6080/vnc.html
    (forwarded via SSH tunnel) and interacts with the browser directly.

    Produces trajectory.json in the same format as agent runs, enabling
    direct comparison between human and agent browsing strategies.

    Requires: Xvfb + x11vnc + noVNC running on the server.
    Set DISPLAY=:99 before running.
    """
    import json
    import os
    from datetime import UTC, datetime

    from agentlens.actors.human_vnc import HumanVNCAgent
    from agentlens.harnesses.tool_gating import ToolSet
    from agentlens.schemas import (
        MemoryHarnessConfig,
        RunMetrics,
        Trajectory,
        TrajectoryEvent,
        TrajectoryEventType,
    )

    config = load_experiment_config(path)

    # Find the task
    task_config = None
    for t in config.tasks:
        if t.id == task_id:
            task_config = t
            break
    if task_config is None:
        available = [t.id for t in config.tasks]
        raise typer.BadParameter(
            f"task '{task_id}' not found. Available: {available}"
        )

    # Check DISPLAY
    display = os.environ.get("DISPLAY")
    if not display:
        typer.echo(
            "ERROR: DISPLAY not set. Run with DISPLAY=:99 "
            "(after starting Xvfb :99 -screen 0 1920x1080x24 &)",
            err=True,
        )
        raise typer.Exit(1)

    # Setup output directory
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    run_output_dir = output_dir / timestamp
    artifact_dir = run_output_dir / "trajectories" / f"human_{task_id}_session"
    screenshot_dir = artifact_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    log_fn = typer.echo if log_actions else None

    if log_fn:
        log_fn(f"[human-run] Task: {task_id}")
        log_fn(f"[human-run] Goal: {task_config.goal}")
        log_fn(f"[human-run] URL: {task_config.start_url}")
        log_fn(f"[human-run] Output: {artifact_dir}")
        log_fn(f"[human-run] Timeout: {timeout}s")
        log_fn("")
        log_fn("Connect via noVNC at: http://localhost:6080/vnc.html")
        log_fn("Complete the task and click 'Submit Answer & Finish' in the overlay.")
        log_fn("")

    # Find first tool harness for viewport config
    viewport = {"width": 1600, "height": 900}
    settle_ms = 2000
    if config.tool_harnesses:
        th = config.tool_harnesses[0]
        viewport = th.extra.get("viewport", viewport)
        settle_ms = int(th.extra.get("settle_ms", settle_ms))

    from playwright.sync_api import sync_playwright

    started_at = datetime.now(UTC)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=100)
        video_dir = artifact_dir / "video"
        video_dir.mkdir(parents=True, exist_ok=True)

        context = browser.new_context(
            viewport=viewport,
            record_video_dir=str(video_dir),
            record_video_size=viewport,
        )
        # Enable tracing
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = context.new_page()

        # Navigate to task URL
        start_url = task_config.start_url or "about:blank"
        if log_fn:
            log_fn(f"[human-run] Opening {start_url}")
        page.goto(start_url, wait_until="domcontentloaded")
        page.wait_for_timeout(settle_ms)

        # Build a minimal toolset (not used by human but needed by protocol)
        from agentlens.schemas import ToolHarnessConfig
        dummy_harness = ToolHarnessConfig(
            id="human_browser",
            runner="screenshot_react",
            tier="browser_only",
            tools=["task.final_answer"],
            prompt_version="screenshot_react_json_v1",
        )
        toolset = ToolSet.from_harness(dummy_harness)

        # Create and run the HumanVNCAgent
        agent = HumanVNCAgent(
            page=page,
            toolset=toolset,
            timeout_sec=timeout,
            screenshot_interval_sec=screenshot_interval,
            log_action=log_fn,
        )

        from agentlens.actors.agent_actor import AgentObservation
        obs = AgentObservation(
            task_goal=task_config.goal or "",
            user_messages=[],
            turn_index=1,
            max_turns=1,
            extra={
                "screenshot_dir": str(screenshot_dir),
                "run_id": f"human_{task_id}",
            },
        )
        init_state = agent.get_init_state(observation=obs)
        response = agent.act(observation=obs, state=init_state)

        # Save trace
        trace_path = artifact_dir / "trace.zip"
        context.tracing.stop(path=str(trace_path))

        final_url = page.url
        context.close()
        browser.close()

    completed_at = datetime.now(UTC)
    answer = response.answer

    # Validate
    from agentlens.validators.answers import validate_answer
    success, score, validation_message = validate_answer(
        answer, task_config, final_url=final_url
    )

    # Add validation event
    response.events.append(
        TrajectoryEvent(
            event_type=TrajectoryEventType.VALIDATION_EVENT,
            step_index=len(response.events),
            data={
                "success": success,
                "score": score,
                "message": validation_message,
                "answer": answer,
                "expected_answer": task_config.expected_answer,
                "answer_validator": task_config.answer_validator,
                "final_url": final_url,
            },
        )
    )

    if log_fn:
        log_fn(
            f"[human-run] validation success={success} "
            f"score={score} message={validation_message}"
        )

    # Build trajectory
    from agentlens.schemas import ModelConfig
    human_actions_count = response.state.extra.get("human_actions_count", 0)
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    trajectory = Trajectory(
        experiment_id="human_run",
        run_id=f"human_{task_id}",
        seed=0,
        trial=1,
        model=ModelConfig(
            id="human",
            provider="local",
            name="human_vnc",
            temperature=0.0,
            vision=True,
        ),
        tool_harness=dummy_harness,
        memory_harness=(
            config.memory_harnesses[0]
            if config.memory_harnesses
            else MemoryHarnessConfig(id="no_memory", kind="none", scope="none")
        ),
        task=task_config,
        started_at=started_at,
        completed_at=completed_at,
        events=response.events,
        metrics=RunMetrics(
            success=success,
            score=score,
            duration_ms=duration_ms,
            steps=human_actions_count,
            tokens_input=None,
            tokens_output=None,
            cost_usd=None,
            tool_calls=human_actions_count,
            extra={"source": "human"},
        ),
        artifact_dir=str(artifact_dir),
    )

    # Save trajectory
    traj_path = artifact_dir / "trajectory.json"
    traj_path.write_text(
        trajectory.model_dump_json(indent=2), encoding="utf-8"
    )

    if log_fn:
        log_fn(f"[human-run] Trajectory saved: {traj_path}")
        log_fn(f"[human-run] Trace saved: {trace_path}")
        log_fn(f"[human-run] Video dir: {video_dir}")
        log_fn(f"[human-run] Duration: {duration_ms}ms")
        log_fn(f"[human-run] Human actions: {human_actions_count}")

    # Generate trajectory viewer from the saved JSON
    try:
        from agentlens.reports.trajectory_viewer import write_trajectory_viewer
        viewer_path = write_trajectory_viewer(
            traj_path, run_output_dir / "human_trajectory_viewer.html"
        )
        typer.echo(str(viewer_path))
    except Exception:  # noqa: BLE001 - viewer is best-effort
        pass

    typer.echo(str(traj_path))


@app.command("import-online-mind2web")
def import_online_mind2web(
    output: Path = typer.Option(
        Path("configs/experiments/online_mind2web_screenshot_react.yaml"),
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
                "output_dir": "agentlens_results/online_mind2web_screenshot_react",
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
