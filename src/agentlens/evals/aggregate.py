from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev

from agentlens.evals.base import ExperimentResult, SingleRunResult


def _as_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return None


def aggregate_results(
    experiment_id: str,
    run_results: list[SingleRunResult],
) -> ExperimentResult:
    """Aggregate single-run metrics into experiment-level metrics."""
    metric_values: dict[str, list[float]] = defaultdict(list)

    for result in run_results:
        if result.score is not None:
            metric_values["score"].append(result.score)

        for name, value in result.metrics.items():
            if name == "score" and result.score is not None:
                continue
            numeric_value = _as_number(value)
            if numeric_value is not None:
                metric_values[name].append(numeric_value)

    metrics: dict[str, float | int | bool | None] = {}
    for name, values in sorted(metric_values.items()):
        if not values:
            continue
        metrics[name] = mean(values)
        metrics[f"{name}:std"] = pstdev(values) if len(values) > 1 else 0.0
        metrics[f"{name}:n"] = len(values)

    return ExperimentResult(
        experiment_id=experiment_id,
        score=metrics.get("score"),
        metrics=metrics,
        run_results=run_results,
    )
