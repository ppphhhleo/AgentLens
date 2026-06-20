from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentlens.analysis.canonical import load_trajectory, resolve_trajectory_paths
from agentlens.evaluators.method_features import evaluate_method_features
from agentlens.evaluators.outcome import evaluate_outcome
from agentlens.evaluators.trajectory_checks import evaluate_trajectory_checks


def evaluate_trajectory_bundle(
    trajectory_path: Path,
    output_dir: Path | None = None,
    *,
    config_path: Path | None = None,
    state_diff_threshold: float = 8000.0,
) -> dict[str, Any]:
    trajectory_path = trajectory_path.expanduser().resolve()
    trajectory = load_trajectory(trajectory_path)
    bundle = {
        "schema_version": "0.1",
        "trajectory_path": str(trajectory_path),
        "trajectory_id": trajectory.get("trajectory_id"),
        "run_id": trajectory.get("run_id"),
        "task_id": (trajectory.get("task") or {}).get("id"),
        "acting": {
            "model": trajectory.get("model"),
            "tool_harness": trajectory.get("tool_harness"),
            "memory_harness": trajectory.get("memory_harness"),
        },
        "evaluating": {
            "outcome": evaluate_outcome(trajectory, config_path=config_path),
            "trajectory": evaluate_trajectory_checks(trajectory),
            "methods": evaluate_method_features(
                trajectory_path,
                state_diff_threshold=state_diff_threshold,
            ),
        },
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "evaluation_bundle.json"
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        bundle["bundle_path"] = str(path)
    return bundle


def evaluate_trajectory_batch(
    inputs: list[Path],
    output_dir: Path,
    *,
    config_path: Path | None = None,
    state_diff_threshold: float = 8000.0,
) -> dict[str, Path]:
    trajectory_paths = resolve_trajectory_paths(inputs)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "evaluation_bundles.jsonl"
    summary_path = output_dir / "evaluation_summary.json"
    counts: dict[str, int] = {}
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for trajectory_path in trajectory_paths:
            bundle = evaluate_trajectory_bundle(
                trajectory_path,
                None,
                config_path=config_path,
                state_diff_threshold=state_diff_threshold,
            )
            handle.write(json.dumps(bundle, ensure_ascii=False) + "\n")
            for flag in bundle["evaluating"]["trajectory"].get("flags", []):
                counts[flag] = counts.get(flag, 0) + 1
    summary = {
        "trajectory_count": len(trajectory_paths),
        "flag_counts": dict(sorted(counts.items())),
        "outputs": {
            "bundles": str(jsonl_path),
            "summary": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"bundles": jsonl_path, "summary": summary_path}
