"""ARB Judge adapter — post-hoc 4-dimensional evaluation of agent trajectories.

Unlike browser/desktop adapters that execute agents live, this adapter
loads pre-existing trajectories (from agent-reward-bench's cleaned JSON
format) and runs an LLM judge to produce Success, Side Effects,
Optimality, and Looping scores.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from agentlens.adapters.arb_trajectory_loader import (
    convert_arb_to_agentlens,
    extract_last_axtree,
    extract_last_screenshot_b64,
    extract_steps_for_judge,
    load_arb_trajectory,
)
from agentlens.evals.aggregate import aggregate_results
from agentlens.evals.base import ExperimentResult, SingleRunResult
from agentlens.schemas import (
    ExperimentConfig,
    MemoryHarnessConfig,
    ModelConfig,
    RunMetrics,
    TaskConfig,
    ToolHarnessConfig,
    Trajectory,
    TrajectoryEvent,
    TrajectoryEventType,
)
from agentlens.validators.arb_judge import judge_trajectory_arb


class ARBJudgeRunPlan(BaseModel):
    experiment_id: str
    run_id: str
    adapter: Literal["arb_judge"] = "arb_judge"
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    output_dir: Path
    max_steps: int = 0
    tags: list[str] = Field(default_factory=list)
    status: Literal["ready", "dry_run_only"] = "ready"
    notes: list[str] = Field(default_factory=list)


class ARBJudgeAdapter:
    """Evaluate pre-existing agent trajectories using ARB's LLM judge."""

    adapter_id = "arb_judge"

    def build_run_plans(
        self,
        config: ExperimentConfig,
        run_ids: set[str] | None = None,
        max_runs: int | None = None,
    ) -> list[ARBJudgeRunPlan]:
        models = {item.id: item for item in config.models}
        tool_harnesses = {item.id: item for item in config.tool_harnesses}
        memory_harnesses = {item.id: item for item in config.memory_harnesses}
        tasks = {item.id: item for item in config.tasks}
        plans: list[ARBJudgeRunPlan] = []

        for run in config.runs:
            if run_ids is not None and run.id not in run_ids:
                continue

            model = models[run.model]
            tool_harness = tool_harnesses[run.tool_harness]
            memory_harness = memory_harnesses[run.memory_harness]
            task = tasks[run.task]

            for seed in run.seeds:
                for trial in range(1, run.trials + 1):
                    plans.append(
                        ARBJudgeRunPlan(
                            experiment_id=config.id,
                            run_id=run.id,
                            seed=seed,
                            trial=trial,
                            model=model,
                            tool_harness=tool_harness,
                            memory_harness=memory_harness,
                            task=task,
                            output_dir=run.output_dir,
                            max_steps=run.max_steps or 0,
                            tags=run.tags,
                            notes=[
                                f"ARB judge on {task.extra.get('who', 'unknown')} "
                                f"trajectory for {task.task_id}",
                            ],
                        )
                    )
                    if max_runs is not None and len(plans) >= max_runs:
                        return plans
        return plans

    def run_many(
        self,
        plans: list[ARBJudgeRunPlan],
        log_action: Callable[[str], None] | None = None,
    ) -> ExperimentResult:
        run_results = [self.run(plan, log_action=log_action) for plan in plans]
        experiment_id = plans[0].experiment_id if plans else "empty"
        return aggregate_results(experiment_id, run_results)

    def run(
        self,
        plan: ARBJudgeRunPlan,
        log_action: Callable[[str], None] | None = None,
    ) -> SingleRunResult:
        started_at = datetime.now(UTC)

        trajectory_path = plan.task.extra.get("trajectory_path")
        if not trajectory_path:
            raise ValueError(
                f"task '{plan.task.id}' has no extra.trajectory_path"
            )

        trajectory_path = Path(trajectory_path)
        self._log(
            log_action,
            f"[{plan.run_id}] Loading trajectory from {trajectory_path}",
        )

        arb_dict = load_arb_trajectory(trajectory_path)
        steps = extract_steps_for_judge(arb_dict)
        goal = arb_dict.get("goal") or plan.task.goal or ""

        trajectory_dir = trajectory_path.parent if trajectory_path.exists() else None

        use_screenshot = plan.tool_harness.extra.get("use_screenshot", True)
        use_axtree = plan.tool_harness.extra.get("use_axtree", False)

        last_screenshot_b64 = None
        if use_screenshot:
            last_screenshot_b64 = extract_last_screenshot_b64(arb_dict, trajectory_dir)

        last_axtree = None
        if use_axtree:
            last_axtree = extract_last_axtree(arb_dict)

        self._log(
            log_action,
            f"[{plan.run_id}] Running ARB judge ({plan.model.name}) "
            f"on {len(steps)} steps — "
            f"WHO={plan.task.extra.get('who', '?')}, "
            f"WHEN={plan.task.extra.get('when', 'N/A')}",
        )

        judge_result = judge_trajectory_arb(
            goal=goal,
            steps=steps,
            last_screenshot_b64=last_screenshot_b64,
            last_axtree=last_axtree,
            judge_model=plan.model.name,
            judge_provider=plan.model.provider,
            use_screenshot=use_screenshot,
            use_axtree=use_axtree,
            invert_system_prompt=plan.tool_harness.extra.get(
                "invert_system_prompt", False
            ),
            temperature=plan.model.temperature,
            max_completion_tokens=plan.model.max_output_tokens or 1024,
        )

        completed_at = datetime.now(UTC)

        metrics = RunMetrics(
            success=judge_result.success,
            score=judge_result.score,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            steps=len(steps),
            cost_usd=judge_result.cost_usd,
            extra={
                "arb_success": judge_result.arb_success,
                "arb_side_effect": judge_result.arb_side_effect,
                "arb_optimality": judge_result.arb_optimality,
                "arb_looping": judge_result.arb_looping,
                "arb_reasoning": judge_result.reasoning,
                "arb_judge_model": judge_result.judge_model,
                "arb_judge_cost_usd": judge_result.cost_usd,
                "who": plan.task.extra.get("who"),
                "when": plan.task.extra.get("when"),
                "arb_benchmark": plan.task.extra.get("arb_benchmark"),
            },
        )

        judge_event = TrajectoryEvent(
            event_id=str(uuid4()),
            event_type=TrajectoryEventType.VALIDATION_EVENT,
            timestamp=completed_at,
            data={
                "validator": "arb_judge",
                "arb_success": judge_result.arb_success,
                "arb_side_effect": judge_result.arb_side_effect,
                "arb_optimality": judge_result.arb_optimality,
                "arb_looping": judge_result.arb_looping,
                "reasoning": judge_result.reasoning,
                "composite_score": judge_result.score,
            },
        )

        trajectory = convert_arb_to_agentlens(
            arb_dict,
            task_config=plan.task,
            judge_model_config=plan.model,
            tool_harness=plan.tool_harness,
            memory_harness=plan.memory_harness,
            experiment_id=plan.experiment_id,
            run_id=plan.run_id,
            seed=plan.seed,
            trial=plan.trial,
        )
        trajectory.completed_at = completed_at
        trajectory.metrics = metrics
        trajectory.events.append(judge_event)

        artifact_dir = self._trajectory_dir(plan)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        trajectory.artifact_dir = artifact_dir

        traj_path = artifact_dir / "trajectory.json"
        traj_path.write_text(
            trajectory.model_dump_json(indent=2),
            encoding="utf-8",
        )

        self._log(
            log_action,
            f"[{plan.run_id}] Done — "
            f"success={judge_result.arb_success}, "
            f"optimality={judge_result.arb_optimality}, "
            f"score={judge_result.score}",
        )

        return SingleRunResult(
            trajectory=trajectory,
            score=judge_result.score,
            metrics={
                "success": judge_result.success,
                "arb_optimality": judge_result.arb_optimality,
                "arb_side_effect": 1 if judge_result.arb_side_effect == "Yes" else 0,
                "arb_looping": 1 if judge_result.arb_looping == "Yes" else 0,
            },
        )

    def _trajectory_dir(self, plan: ARBJudgeRunPlan) -> Path:
        return (
            plan.output_dir
            / "raw"
            / "trajectories"
            / f"{plan.run_id}_seed{plan.seed}_trial{plan.trial}"
        )

    @staticmethod
    def _log(log_action: Callable[[str], None] | None, msg: str) -> None:
        if log_action:
            log_action(msg)
