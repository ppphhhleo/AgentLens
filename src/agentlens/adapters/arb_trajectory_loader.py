"""Load and convert agent-reward-bench trajectories for AgentLens evaluation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from agentlens.schemas import (
    ModelConfig,
    MemoryHarnessConfig,
    RunMetrics,
    TaskConfig,
    ToolHarnessConfig,
    Trajectory,
    TrajectoryEvent,
    TrajectoryEventType,
)


def load_arb_trajectory(path: Path) -> dict[str, Any]:
    """Load a cleaned ARB trajectory JSON file.

    Cleaned trajectories are produced by agent-reward-bench's
    ``scripts/convert_trajectories_to_json.py`` and contain:
    goal, steps (url/action/reasoning/axtree/screenshot_path), benchmark,
    agent, model, valid, summary_info, etc.
    """
    path = Path(path)
    with path.open("rb") as f:
        try:
            import orjson

            return orjson.loads(f.read())
        except ImportError:
            f.seek(0)
            return json.loads(f.read())


def convert_arb_to_agentlens(
    arb_dict: dict[str, Any],
    task_config: TaskConfig,
    judge_model_config: ModelConfig,
    tool_harness: ToolHarnessConfig,
    memory_harness: MemoryHarnessConfig,
    experiment_id: str,
    run_id: str,
    seed: int = 0,
    trial: int = 0,
) -> Trajectory:
    """Convert an ARB trajectory dict into an AgentLens Trajectory."""
    events: list[TrajectoryEvent] = []
    steps = arb_dict.get("steps", [])

    for i, step in enumerate(steps):
        events.append(
            TrajectoryEvent(
                event_id=str(uuid4()),
                event_type=TrajectoryEventType.TOOL_CALL,
                timestamp=datetime.now(UTC),
                step_index=i,
                data={
                    "action": step.get("action"),
                    "url": step.get("url"),
                    "reasoning": step.get("reasoning"),
                },
            )
        )

    cum_reward = (arb_dict.get("summary_info") or {}).get("cum_reward")
    metrics = RunMetrics(
        success=cum_reward is not None and cum_reward > 0.5,
        score=cum_reward,
        steps=len(steps),
        extra={
            "arb_agent": arb_dict.get("agent"),
            "arb_model": arb_dict.get("model"),
            "arb_benchmark": arb_dict.get("benchmark"),
            "arb_seed": arb_dict.get("seed"),
        },
    )

    return Trajectory(
        trajectory_id=str(uuid4()),
        experiment_id=experiment_id,
        run_id=run_id,
        seed=seed,
        trial=trial,
        model=judge_model_config,
        tool_harness=tool_harness,
        memory_harness=memory_harness,
        task=task_config,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        events=events,
        metrics=metrics,
    )


def extract_steps_for_judge(arb_dict: dict[str, Any]) -> list[dict[str, str]]:
    """Extract the step list in the format expected by ARB's judge templates."""
    return [
        {
            "url": step.get("url", ""),
            "action": step.get("action", ""),
            "reasoning": step.get("reasoning", ""),
        }
        for step in arb_dict.get("steps", [])
    ]


def extract_last_screenshot_b64(
    arb_dict: dict[str, Any],
    trajectory_dir: Path | None = None,
) -> str | None:
    """Get the last step's screenshot as a base64 data URI.

    If the trajectory JSON was produced from the original pickle
    trajectories, screenshot_path is an absolute path on the machine
    that ran the conversion.  We try several strategies:
    1. Absolute path from the JSON
    2. Relative to the provided trajectory_dir
    3. Return None if unavailable
    """
    steps = arb_dict.get("steps", [])
    if not steps:
        return None

    screenshot_path = steps[-1].get("screenshot_path")
    if not screenshot_path:
        return None

    candidates = [Path(screenshot_path)]
    if trajectory_dir:
        candidates.append(trajectory_dir / Path(screenshot_path).name)

    for path in candidates:
        if path.exists():
            try:
                from agent_reward_bench.judge.utils import image_to_base64

                return image_to_base64(path)
            except ImportError:
                import base64

                with open(path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                suffix = path.suffix.lower()
                mime = "image/png" if suffix == ".png" else "image/jpeg"
                return f"data:{mime};base64,{encoded}"

    return None


def extract_last_axtree(arb_dict: dict[str, Any]) -> str | None:
    """Get the last step's accessibility tree text."""
    steps = arb_dict.get("steps", [])
    if not steps:
        return None
    return steps[-1].get("axtree_pruned") or steps[-1].get("axtree")
