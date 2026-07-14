"""Extract and aggregate ARB 4-dimensional scores from trajectory metrics.

Provides WHO/WHEN grouping for post-hoc analysis and dashboard generation.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any


def evaluate_arb_dimensions(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Extract ARB 4-dimensional scores from a trajectory's metrics.extra."""
    extra = (trajectory.get("metrics") or {}).get("extra", {})
    task_extra = (trajectory.get("task") or {}).get("extra", {})

    return {
        "kind": "arb_dimensions",
        "success": extra.get("arb_success"),
        "side_effect": extra.get("arb_side_effect"),
        "optimality": extra.get("arb_optimality"),
        "looping": extra.get("arb_looping"),
        "reasoning": extra.get("arb_reasoning"),
        "judge_model": extra.get("arb_judge_model"),
        "composite_score": (trajectory.get("metrics") or {}).get("score"),
        "who": task_extra.get("who") or extra.get("who"),
        "when": task_extra.get("when") or extra.get("when"),
        "arb_benchmark": task_extra.get("arb_benchmark") or extra.get("arb_benchmark"),
        "split": task_extra.get("split"),
        "difficulty": task_extra.get("difficulty"),
    }


def aggregate_by_who(
    evaluations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Group evaluation results by WHO (agent model) and compute per-agent stats."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in evaluations:
        who = ev.get("who") or "unknown"
        groups[who].append(ev)

    return {who: _compute_group_stats(evals) for who, evals in sorted(groups.items())}


def aggregate_by_when(
    evaluations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Group evaluation results by WHEN (time_dependency) and compute stats."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in evaluations:
        when = ev.get("when")
        if when:
            groups[when].append(ev)

    return {when: _compute_group_stats(evals) for when, evals in sorted(groups.items())}


def aggregate_by_who_when(
    evaluations: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Cross-tabulate WHO x WHEN and compute stats per cell."""
    groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for ev in evaluations:
        who = ev.get("who") or "unknown"
        when = ev.get("when")
        if when:
            groups[who][when].append(ev)

    return {
        who: {
            when: _compute_group_stats(evals)
            for when, evals in sorted(when_groups.items())
        }
        for who, when_groups in sorted(groups.items())
    }


def _compute_group_stats(evals: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate statistics for a group of ARB evaluations."""
    n = len(evals)
    if n == 0:
        return {"n": 0}

    successes = [1 for e in evals if e.get("success") == "Successful"]
    side_effects = [1 for e in evals if e.get("side_effect") == "Yes"]
    looping = [1 for e in evals if e.get("looping") == "Yes"]
    optimalities = [
        e["optimality"] for e in evals
        if e.get("optimality") is not None and isinstance(e["optimality"], int)
    ]
    scores = [
        e["composite_score"] for e in evals
        if e.get("composite_score") is not None
    ]

    return {
        "n": n,
        "success_rate": len(successes) / n,
        "side_effect_rate": len(side_effects) / n,
        "looping_rate": len(looping) / n,
        "mean_optimality": mean(optimalities) if optimalities else None,
        "mean_composite_score": mean(scores) if scores else None,
    }
