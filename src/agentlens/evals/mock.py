from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentlens.evals.aggregate import aggregate_results
from agentlens.evals.base import ExperimentResult, SingleRunResult
from agentlens.schemas import (
    ExperimentConfig,
    ModelConfig,
    RunMetrics,
    TaskConfig,
    ToolHarnessConfig,
    Trajectory,
    TrajectoryEvent,
    TrajectoryEventType,
)


def _index_by_id(items: list[ModelConfig] | list[ToolHarnessConfig] | list[TaskConfig]) -> dict[str, object]:
    return {item.id: item for item in items}


def make_mock_results(config: ExperimentConfig) -> ExperimentResult:
    """Create deterministic placeholder results from config for report pipeline testing."""
    models = _index_by_id(config.models)
    tool_harnesses = _index_by_id(config.tool_harnesses)
    memory_harnesses = {item.id: item for item in config.memory_harnesses}
    tasks = _index_by_id(config.tasks)
    run_results: list[SingleRunResult] = []

    for run in config.runs:
        for seed in run.seeds:
            for trial in range(1, run.trials + 1):
                started_at = datetime.now(UTC)
                completed_at = started_at + timedelta(seconds=30 + seed + trial)
                uses_memory = memory_harnesses[run.memory_harness].kind != "none"
                steps = 5 if uses_memory else 7
                score = 1.0

                trajectory = Trajectory(
                    experiment_id=config.id,
                    run_id=run.id,
                    seed=seed,
                    trial=trial,
                    model=models[run.model],
                    tool_harness=tool_harnesses[run.tool_harness],
                    memory_harness=memory_harnesses[run.memory_harness],
                    task=tasks[run.task],
                    started_at=started_at,
                    completed_at=completed_at,
                    events=[
                        TrajectoryEvent(
                            event_type=TrajectoryEventType.BROWSER_OBSERVATION,
                            step_index=0,
                            data={"mock": True, "url": tasks[run.task].start_url},
                        ),
                        TrajectoryEvent(
                            event_type=TrajectoryEventType.MODEL_MESSAGE,
                            step_index=1,
                            data={"mock": True, "content": "Plan the next browser action."},
                        ),
                        TrajectoryEvent(
                            event_type=TrajectoryEventType.VALIDATION_EVENT,
                            step_index=steps,
                            data={"mock": True, "success": True},
                        ),
                    ],
                    metrics=RunMetrics(
                        success=True,
                        score=score,
                        duration_ms=int((completed_at - started_at).total_seconds() * 1000),
                        steps=steps,
                        tokens_input=1000 + steps * 100,
                        tokens_output=250 + steps * 10,
                        cost_usd=0.01 + steps * 0.001,
                        tool_calls=steps,
                    ),
                )

                run_results.append(
                    SingleRunResult(
                        trajectory=trajectory,
                        score=score,
                        metrics={
                            "success": True,
                            "score": score,
                            "duration_ms": trajectory.metrics.duration_ms,
                            "steps": steps,
                            "tokens_input": trajectory.metrics.tokens_input,
                            "tokens_output": trajectory.metrics.tokens_output,
                            "cost_usd": trajectory.metrics.cost_usd,
                            "tool_calls": trajectory.metrics.tool_calls,
                        },
                        metadata={
                            "run_id": run.id,
                            "model": run.model,
                            "tool_harness": run.tool_harness,
                            "memory_harness": run.memory_harness,
                            "task": run.task,
                            "mock": True,
                        },
                    )
                )

    return aggregate_results(config.id, run_results)

