from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from agentlens.evals.aggregate import aggregate_results
from agentlens.evals.base import ExperimentResult, SingleRunResult
from agentlens.schemas import (
    ExperimentConfig,
    MemoryHarnessConfig,
    ModelConfig,
    RunMetrics,
    TaskConfig,
    ToolHarnessConfig,
    ToolHarnessTier,
    Trajectory,
    TrajectoryEvent,
    TrajectoryEventType,
)


class BrowserGymDirectRunPlan(BaseModel):
    """Concrete executable unit for a direct BrowserGym scripted run."""

    experiment_id: str
    run_id: str
    adapter: Literal["browsergym_direct"]
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    output_dir: Path
    raw_output_dir: Path
    max_steps: int = 3
    tags: list[str] = Field(default_factory=list)
    status: Literal["ready", "dry_run_only"] = "ready"
    notes: list[str] = Field(default_factory=list)


class BrowserGymDirectAdapter:
    """Direct BrowserGym adapter for no-model scripted smoke runs."""

    adapter_id = "browsergym_direct"

    def build_run_plans(
        self,
        config: ExperimentConfig,
        run_ids: set[str] | None = None,
        max_runs: int | None = None,
    ) -> list[BrowserGymDirectRunPlan]:
        models = {item.id: item for item in config.models}
        tool_harnesses = {item.id: item for item in config.tool_harnesses}
        memory_harnesses = {item.id: item for item in config.memory_harnesses}
        tasks = {item.id: item for item in config.tasks}
        plans: list[BrowserGymDirectRunPlan] = []

        for run in config.runs:
            if run_ids is not None and run.id not in run_ids:
                continue

            model = models[run.model]
            tool_harness = tool_harnesses[run.tool_harness]
            memory_harness = memory_harnesses[run.memory_harness]
            task = tasks[run.task]
            self._validate_supported(run.id, model, tool_harness, memory_harness, task)

            for seed in run.seeds:
                for trial in range(1, run.trials + 1):
                    plans.append(
                        BrowserGymDirectRunPlan(
                            experiment_id=config.id,
                            run_id=run.id,
                            adapter=self.adapter_id,
                            seed=seed,
                            trial=trial,
                            model=model,
                            tool_harness=tool_harness,
                            memory_harness=memory_harness,
                            task=task,
                            output_dir=run.output_dir,
                            raw_output_dir=run.output_dir / "browsergym_direct_raw",
                            max_steps=run.max_steps or 3,
                            tags=run.tags,
                            notes=[
                                "Scripted BrowserGym direct run; no model/API call is used.",
                            ],
                        )
                    )

                    if max_runs is not None and len(plans) >= max_runs:
                        return plans

        return plans

    def run_many(self, plans: list[BrowserGymDirectRunPlan]) -> ExperimentResult:
        run_results = [self.run(plan) for plan in plans]
        experiment_id = plans[0].experiment_id if plans else "empty"
        return aggregate_results(experiment_id, run_results)

    def run(self, plan: BrowserGymDirectRunPlan) -> SingleRunResult:
        started_at = datetime.now(UTC)
        events: list[TrajectoryEvent] = []
        action_errors: list[str] = []
        steps = 0
        env = self._make_env(plan)

        try:
            obs, _info = env.reset(seed=plan.seed)
            events.append(self._observation_event(obs, step_index=0))

            scripted_actions = self._scripted_actions(plan.task, obs)
            for steps, action in enumerate(scripted_actions[: plan.max_steps], start=1):
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.BROWSER_ACTION,
                        step_index=steps,
                        data={"action": action},
                    )
                )
                obs, reward, terminated, truncated, info = env.step(action)
                error = obs.get("last_action_error") or ""
                if error:
                    action_errors.append(error)
                events.append(
                    self._observation_event(
                        obs,
                        step_index=steps,
                        extra={
                            "reward": reward,
                            "terminated": terminated,
                            "truncated": truncated,
                            "info": info,
                        },
                    )
                )
                if terminated or truncated:
                    break

        finally:
            env.close()

        completed_at = datetime.now(UTC)
        success = steps > 0 and not action_errors
        score = 1.0 if success else 0.0
        events.append(
            TrajectoryEvent(
                event_type=TrajectoryEventType.VALIDATION_EVENT,
                step_index=steps,
                data={"success": success, "action_errors": action_errors},
            )
        )
        trajectory = Trajectory(
            experiment_id=plan.experiment_id,
            run_id=plan.run_id,
            seed=plan.seed,
            trial=plan.trial,
            model=plan.model,
            tool_harness=plan.tool_harness,
            memory_harness=plan.memory_harness,
            task=plan.task,
            started_at=started_at,
            completed_at=completed_at,
            events=events,
            metrics=RunMetrics(
                success=success,
                score=score,
                duration_ms=int((completed_at - started_at).total_seconds() * 1000),
                steps=steps,
                tool_calls=steps,
            ),
            artifact_dir=self._trajectory_dir(plan),
        )
        self._write_trajectory(trajectory)

        return SingleRunResult(
            trajectory=trajectory,
            score=score,
            metrics={
                "success": success,
                "score": score,
                "duration_ms": trajectory.metrics.duration_ms,
                "steps": steps,
                "tool_calls": steps,
            },
            metadata={
                "run_id": plan.run_id,
                "adapter": plan.adapter,
                "scripted": True,
            },
        )

    def _make_env(self, plan: BrowserGymDirectRunPlan):
        import gymnasium as gym
        import browsergym.core  # noqa: F401 - registers browsergym/openended
        task_kwargs = dict(plan.task.extra.get("task_kwargs", {}))
        if plan.task.start_url:
            task_kwargs.setdefault("start_url", plan.task.start_url)

        return gym.make(
            plan.task.task_id,
            task_kwargs=task_kwargs or None,
            headless=bool(plan.tool_harness.extra.get("headless", True)),
        )

    def _scripted_actions(self, task: TaskConfig, obs: dict) -> list[str]:
        if actions := task.extra.get("scripted_actions"):
            return list(actions)

        if task.extra.get("scripted_policy") == "click_first_button":
            action = self._first_button_mouse_click(obs)
            return [action or "noop()"]

        return ["noop()"]

    def _first_button_bid(self, obs: dict) -> str | None:
        for node in obs.get("axtree_object", {}).get("nodes", []):
            role = node.get("role", {}).get("value")
            bid = node.get("browsergym_id")
            if role == "button" and bid:
                return str(bid)
        return None

    def _first_button_mouse_click(self, obs: dict) -> str | None:
        bid = self._first_button_bid(obs)
        if bid is None:
            return None

        properties = obs.get("extra_element_properties", {}).get(bid, {})
        bbox = properties.get("bbox")
        if not bbox:
            return f"click('{bid}')"

        x, y, width, height = bbox
        return f"mouse_click({x + width / 2:.1f}, {y + height / 2:.1f})"

    def _observation_event(
        self,
        obs: dict,
        step_index: int,
        extra: dict | None = None,
    ) -> TrajectoryEvent:
        data = {
            "url": obs.get("url"),
            "goal": obs.get("goal"),
            "last_action": obs.get("last_action"),
            "last_action_error": obs.get("last_action_error"),
            "focused_element_bid": obs.get("focused_element_bid"),
        }
        if extra:
            data.update(extra)
        return TrajectoryEvent(
            event_type=TrajectoryEventType.BROWSER_OBSERVATION,
            step_index=step_index,
            data=data,
        )

    def _trajectory_dir(self, plan: BrowserGymDirectRunPlan) -> Path:
        return (
            plan.output_dir
            / "trajectories"
            / f"{plan.run_id}_seed{plan.seed}_trial{plan.trial}"
        )

    def _write_trajectory(self, trajectory: Trajectory) -> Path:
        if trajectory.artifact_dir is None:
            raise ValueError("trajectory artifact_dir is required")
        trajectory.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = trajectory.artifact_dir / "trajectory.json"
        path.write_text(trajectory.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _validate_supported(
        self,
        run_id: str,
        model: ModelConfig,
        tool_harness: ToolHarnessConfig,
        memory_harness: MemoryHarnessConfig,
        task: TaskConfig,
    ) -> None:
        if tool_harness.runner != "browsergym_direct":
            raise ValueError(
                f"run '{run_id}' uses runner '{tool_harness.runner}', "
                "expected 'browsergym_direct'"
            )
        if tool_harness.tier != ToolHarnessTier.BROWSER_ONLY:
            raise ValueError(
                f"run '{run_id}' uses tier '{tool_harness.tier}', expected 'browser_only'"
            )
        if task.benchmark != "browsergym":
            raise ValueError(
                f"run '{run_id}' uses benchmark '{task.benchmark}', expected 'browsergym'"
            )
        if memory_harness.kind != "none":
            raise ValueError(
                f"run '{run_id}' uses memory '{memory_harness.kind}', "
                "but browsergym_direct smoke runner only supports no memory"
            )
        if model.provider != "local" or model.name != "scripted":
            raise ValueError(
                f"run '{run_id}' uses model '{model.id}', but browsergym_direct smoke runner "
                "only supports provider=local name=scripted"
            )
