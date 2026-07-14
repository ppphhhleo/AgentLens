"""Generate AgentLens experiment configs from agent-reward-bench data.

Reads ARB task IDs, metadata (WHEN categories), and scans trajectory
directories to produce experiment YAML configs for ARB judge evaluation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


_ARB_DATA_DIR: Path | None = None


def _find_arb_data_dir() -> Path:
    global _ARB_DATA_DIR
    if _ARB_DATA_DIR is not None:
        return _ARB_DATA_DIR

    candidates = [
        Path(__file__).resolve().parents[4] / "agent-reward-bench" / "agent_reward_bench" / "data",
    ]

    try:
        import agent_reward_bench

        pkg_dir = Path(agent_reward_bench.__file__).parent
        candidates.insert(0, pkg_dir / "data")
    except ImportError:
        pass

    for candidate in candidates:
        if candidate.is_dir():
            _ARB_DATA_DIR = candidate
            return candidate

    raise FileNotFoundError(
        "Cannot find agent_reward_bench/data directory. "
        "Install agent-reward-bench or ensure it is in the workspace."
    )


def _load_when_metadata() -> dict[str, dict[str, str]]:
    """Load WHEN (time_dependency) and difficulty from assistantbench.csv."""
    data_dir = _find_arb_data_dir()
    csv_path = data_dir / "assistantbench.csv"
    if not csv_path.exists():
        return {}

    metadata: dict[str, dict[str, str]] = {}
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task_name = row.get("task_name", "")
            metadata[task_name] = {
                "when": row.get("time_dependency", ""),
                "difficulty": row.get("difficulty", ""),
            }
    return metadata


def _load_splits() -> dict[str, str]:
    """Load task_id -> split mapping from splits.csv."""
    data_dir = _find_arb_data_dir()
    csv_path = data_dir / "splits.csv"
    if not csv_path.exists():
        return {}

    splits: dict[str, str] = {}
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            splits[row.get("task_id", "")] = row.get("split", "")
    return splits


def _load_task_ids(benchmark: str) -> list[str]:
    """Load task IDs for a benchmark from its task_ids.json file."""
    data_dir = _find_arb_data_dir()

    name_map = {
        "webarena_100": "webarena.task_ids.json",
        "webarena": "webarena.task_ids.json",
        "visualwebarena_100": "visualwebarena.task_ids.json",
        "visualwebarena": "visualwebarena.task_ids.json",
        "workarena_l2": "workarena_l2.task_ids.json",
    }

    json_file = name_map.get(benchmark)
    if json_file:
        path = data_dir / json_file
        if path.exists():
            with path.open() as f:
                return json.load(f)

    if benchmark == "assistantbench":
        metadata = _load_when_metadata()
        return list(metadata.keys())

    return []


def _scan_trajectories(
    base_dir: Path, benchmark_prefix: str
) -> dict[str, list[dict[str, str]]]:
    """Scan a trajectory directory for available cleaned JSONs.

    Returns a dict mapping task_id -> list of {agent, path} dicts.
    """
    results: dict[str, list[dict[str, str]]] = {}
    base_dir = Path(base_dir)

    if not base_dir.exists():
        return results

    for json_file in sorted(base_dir.rglob("*.json")):
        task_id = json_file.stem
        parts = json_file.relative_to(base_dir).parts
        agent = parts[1] if len(parts) >= 3 else "unknown"

        results.setdefault(task_id, []).append({
            "agent": agent,
            "path": str(json_file),
        })

    return results


def generate_arb_experiment_config(
    *,
    arb_benchmark: str,
    trajectory_base_dir: Path,
    judge_model: str = "gpt-4o-mini-2024-07-18",
    judge_provider: str = "openai",
    use_screenshot: bool = True,
    use_axtree: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Generate an ExperimentConfig dict for ARB judge evaluation."""
    benchmark_prefix = arb_benchmark.replace("_100", "")
    task_ids = _load_task_ids(arb_benchmark)
    when_metadata = _load_when_metadata()
    splits = _load_splits()

    trajectory_base_dir = Path(trajectory_base_dir)
    available = _scan_trajectories(trajectory_base_dir, benchmark_prefix)

    tasks: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    agents_seen: set[str] = set()
    count = 0

    for task_id in task_ids:
        full_task_id = (
            task_id
            if "." in task_id
            else f"{benchmark_prefix}.{task_id}"
        )

        traj_entries = available.get(full_task_id, [])
        if not traj_entries:
            traj_entries = available.get(task_id, [])

        if not traj_entries:
            continue

        for entry in traj_entries:
            agent = entry["agent"]
            agents_seen.add(agent)
            safe_agent = agent.replace("-", "_").replace(".", "_")[:40]
            safe_task = full_task_id.replace(".", "_")

            config_task_id = f"{safe_task}__{safe_agent}"
            run_id = f"judge_{config_task_id}"

            task_meta = when_metadata.get(full_task_id, {})
            when_value = task_meta.get("when") or None
            difficulty = task_meta.get("difficulty") or None
            split = splits.get(full_task_id, "")

            tasks.append({
                "id": config_task_id,
                "benchmark": "arb",
                "task_id": full_task_id,
                "answer_validator": "arb_judge",
                "extra": {
                    "who": agent,
                    "when": when_value,
                    "arb_benchmark": benchmark_prefix,
                    "trajectory_path": entry["path"],
                    "split": split,
                    "difficulty": difficulty,
                },
            })

            runs.append({
                "id": run_id,
                "model": "arb_judge_model",
                "tool_harness": "arb_judge_harness",
                "memory_harness": "no_memory",
                "task": config_task_id,
                "seeds": [0],
                "trials": 1,
                "max_steps": 0,
                "output_dir": f"agentlens_results/arb_{benchmark_prefix}_judge",
                "tags": ["arb", benchmark_prefix, "tool_usage"],
            })

            count += 1
            if limit and count >= limit:
                break

        if limit and count >= limit:
            break

    config: dict[str, Any] = {
        "schema_version": "0.1",
        "id": f"arb_{benchmark_prefix}_judge",
        "description": (
            f"ARB 4-dimensional LLM judge evaluation on {benchmark_prefix} "
            f"trajectories. Judge: {judge_model}. "
            f"Agents: {', '.join(sorted(agents_seen)) or 'auto-detected'}. "
            f"Tasks: {len(tasks)}."
        ),
        "models": [
            {
                "id": "arb_judge_model",
                "provider": judge_provider,
                "name": judge_model,
                "temperature": 0.0,
                "vision": use_screenshot,
                "max_output_tokens": 1024,
            }
        ],
        "tool_harnesses": [
            {
                "id": "arb_judge_harness",
                "runner": "arb_judge",
                "tier": "human",
                "tools": [],
                "extra": {
                    "use_screenshot": use_screenshot,
                    "use_axtree": use_axtree,
                },
            }
        ],
        "memory_harnesses": [
            {"id": "no_memory", "kind": "none", "scope": "none"}
        ],
        "tasks": tasks,
        "runs": runs,
    }

    return config
