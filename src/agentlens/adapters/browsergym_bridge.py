"""BrowserGym bridge adapter.

Runs our screenshot ReAct loop (mock or real OpenAI model) inside a
BrowserGym task environment. We use BrowserGym for:
  - task instantiation (URL setup, fixture, environment seeding)
  - the ground-truth `task.validate(page, chat_messages)` reward

We use BrowserGym's `env.unwrapped.page` Playwright handle as the page
our screenshot loop operates on. We ignore the gym action space entirely.
"""
from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

from agentlens.evals.aggregate import aggregate_results
from agentlens.evals.base import ExperimentResult, SingleRunResult
from agentlens.harnesses.browser_actions import OVERLAY_INIT_JS
from agentlens.harnesses.screenshot_react_loop import run_screenshot_react_loop
from agentlens.harnesses.tool_gating import ToolSet, tool_name_for
from agentlens.models.base import build_model
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

MOCK_MODEL_NAME = "mock_screenshot_react"


class BrowserGymBridgeRunPlan(BaseModel):
    """Concrete executable unit for a screenshot ReAct loop on a BrowserGym task."""

    experiment_id: str
    run_id: str
    adapter: Literal["browsergym_bridge"]
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    output_dir: Path
    raw_output_dir: Path
    max_steps: int = 12
    tags: list[str] = Field(default_factory=list)
    status: Literal["ready", "dry_run_only"] = "ready"
    notes: list[str] = Field(default_factory=list)


class BrowserGymBridgeAdapter:
    """Screenshot ReAct loop running inside a BrowserGym task env."""

    adapter_id = "browsergym_bridge"

    def build_run_plans(
        self,
        config: ExperimentConfig,
        run_ids: set[str] | None = None,
        max_runs: int | None = None,
    ) -> list[BrowserGymBridgeRunPlan]:
        models = {item.id: item for item in config.models}
        tool_harnesses = {item.id: item for item in config.tool_harnesses}
        memory_harnesses = {item.id: item for item in config.memory_harnesses}
        tasks = {item.id: item for item in config.tasks}
        plans: list[BrowserGymBridgeRunPlan] = []

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
                        BrowserGymBridgeRunPlan(
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
                            raw_output_dir=run.output_dir / "browsergym_bridge_raw",
                            max_steps=run.max_steps or 15,
                            tags=run.tags,
                            notes=[
                                f"BrowserGym bridge: task={task.task_id} "
                                f"provider={model.provider} name={model.name}"
                            ],
                        )
                    )
                    if max_runs is not None and len(plans) >= max_runs:
                        return plans
        return plans

    def run_many(
        self,
        plans: list[BrowserGymBridgeRunPlan],
        log_action: Callable[[str], None] | None = None,
    ) -> ExperimentResult:
        run_results = [self.run(plan, log_action=log_action) for plan in plans]
        experiment_id = plans[0].experiment_id if plans else "empty"
        return aggregate_results(experiment_id, run_results)

    def run(
        self,
        plan: BrowserGymBridgeRunPlan,
        log_action: Callable[[str], None] | None = None,
    ) -> SingleRunResult:
        started_at = datetime.now(UTC)
        artifact_dir = self._trajectory_dir(plan)
        screenshot_dir = artifact_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Lazy gym imports so the CLI startup stays light and a missing
        # browsergym subpackage only fails when actually invoked.
        import gymnasium as gym

        env_id = self._gym_env_id(plan.task.task_id)
        self._import_browsergym_for(plan.task.task_id)

        headless = bool(plan.tool_harness.extra.get("headless", True))
        slow_mo = int(plan.tool_harness.extra.get("slow_mo_ms", 0))
        env_kwargs: dict = {
            "headless": headless,
            "slow_mo": slow_mo,
        }
        # MiniWoB and friends ship narrow viewports; let the user override.
        if "viewport" in plan.tool_harness.extra:
            env_kwargs["viewport"] = plan.tool_harness.extra["viewport"]

        self._log(
            log_action,
            f"[{plan.run_id} seed={plan.seed} trial={plan.trial}] gym.make {env_id}",
        )
        env = gym.make(env_id, **env_kwargs)
        obs, info = env.reset(seed=plan.seed)
        page = env.unwrapped.page

        # Inject the action overlay so live runs visualize what the agent does.
        try:
            page.context.add_init_script(OVERLAY_INIT_JS)
            page.evaluate(OVERLAY_INIT_JS)
        except Exception:  # noqa: BLE001 - overlay is best-effort
            pass

        goal = self._goal_text(obs) or plan.task.goal or ""
        self._log(log_action, f"[{plan.run_id}] goal: {goal!r}")

        toolset = ToolSet.from_harness(plan.tool_harness)
        events: list[TrajectoryEvent] = []
        answer: str | None = None
        if _is_mock_model(plan.model):
            mock_actions = plan.task.extra.get("mock_actions") or []
            from agentlens.actions import ComputerAction
            from agentlens.harnesses.browser_actions import (
                capture_screenshot_event,
                execute_action,
                format_action,
            )

            events.append(
                capture_screenshot_event(page, screenshot_dir, 0, goal)
            )
            self._log(log_action, f"[{plan.run_id} step=0] screenshot captured")

            for step_index, raw in enumerate(mock_actions, start=1):
                action = ComputerAction.from_raw(raw)
                self._log(log_action, f"[{plan.run_id} step={step_index}] {format_action(action)}")
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.MODEL_MESSAGE,
                        step_index=step_index,
                        data={
                            "thought": f"Mock action '{action.type}'.",
                            "action": action.model_dump(mode="json"),
                            "tool_name": tool_name_for(action),
                            "mock": True,
                        },
                    )
                )
                allowed, gating_msg = toolset.gate_action(action)
                if not allowed:
                    self._log(log_action, f"[{plan.run_id} step={step_index}] gating: {gating_msg}")
                    events.append(
                        TrajectoryEvent(
                            event_type=TrajectoryEventType.GATING_VIOLATION,
                            step_index=step_index,
                            data={
                                "action": action.model_dump(mode="json"),
                                "tool_name": tool_name_for(action),
                                "message": gating_msg,
                            },
                        )
                    )
                    continue
                if action.type == "final_answer":
                    answer = action.answer
                    break
                err = execute_action(page, action)
                events.append(
                    TrajectoryEvent(
                        event_type=TrajectoryEventType.BROWSER_ACTION,
                        step_index=step_index,
                        data={"action": action.model_dump(mode="json"), "error": err},
                    )
                )
                events.append(
                    capture_screenshot_event(page, screenshot_dir, step_index, goal)
                )
        else:
            model = build_model(plan.model, toolset=toolset)
            answer, events = run_screenshot_react_loop(
                page=page,
                model=model,
                goal=goal,
                max_steps=plan.max_steps,
                screenshot_dir=screenshot_dir,
                run_id=plan.run_id,
                toolset=toolset,
                log_action=log_action,
            )

        final_url = page.url
        # BrowserGym task validators inspect either DOM state, the chat
        # transcript, or both. We pass the agent's final_answer as a
        # synthetic assistant chat message so Q&A-style tasks
        # (AssistantBench, etc.) can read it; DOM-state tasks (MiniWoB)
        # ignore the messages. Empty answer -> empty list.
        chat_messages: list[dict] = []
        if answer is not None:
            chat_messages.append({"role": "assistant", "message": str(answer)})
        try:
            reward, done, val_msg, val_info = env.unwrapped.task.validate(
                page, chat_messages
            )
        except Exception as exc:  # noqa: BLE001
            reward, done, val_msg, val_info = 0.0, False, f"validate raised: {exc}", {}

        env.close()

        success = bool(reward and reward > 0)
        score = float(reward) if reward is not None else None
        validation_message = (
            f"BrowserGym task.validate -> reward={reward} done={done} msg={val_msg!r}"
        )
        self._log(log_action, f"[{plan.run_id}] {validation_message}")

        events.append(
            TrajectoryEvent(
                event_type=TrajectoryEventType.VALIDATION_EVENT,
                step_index=1,
                data={
                    "success": success,
                    "score": score,
                    "message": validation_message,
                    "answer": answer,
                    "browsergym_reward": reward,
                    "browsergym_done": done,
                    "browsergym_msg": val_msg,
                    "browsergym_info": val_info,
                    "final_url": final_url,
                },
            )
        )

        completed_at = datetime.now(UTC)
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
                steps=sum(
                    1 for e in events if e.event_type == TrajectoryEventType.MODEL_MESSAGE
                ),
                tool_calls=sum(
                    1 for e in events if e.event_type == TrajectoryEventType.BROWSER_ACTION
                ),
            ),
            artifact_dir=artifact_dir,
        )
        self._write_trajectory(trajectory)

        return SingleRunResult(
            trajectory=trajectory,
            score=score,
            metrics={
                "success": success,
                "score": score,
                "duration_ms": trajectory.metrics.duration_ms,
                "steps": trajectory.metrics.steps,
                "tool_calls": trajectory.metrics.tool_calls,
            },
            metadata={
                "run_id": plan.run_id,
                "adapter": plan.adapter,
                "browsergym_task": plan.task.task_id,
                "mock": _is_mock_model(plan.model),
            },
        )

    def _gym_env_id(self, task_id: str) -> str:
        # Accept both "miniwob.click-test" and "browsergym/miniwob.click-test"
        return task_id if task_id.startswith("browsergym/") else f"browsergym/{task_id}"

    def _import_browsergym_for(self, task_id: str) -> None:
        bare = task_id.split("/", 1)[-1]  # strip optional "browsergym/" prefix
        suite = bare.split(".", 1)[0]     # "miniwob.click-test" -> "miniwob"
        try:
            importlib.import_module(f"browsergym.{suite}")
        except ImportError as exc:
            raise RuntimeError(
                f"task suite browsergym.{suite} is not installed; "
                f"install browsergym[{suite}] or pick a different task"
            ) from exc

    def _goal_text(self, obs) -> str | None:
        if not isinstance(obs, dict):
            return None
        goal_obj = obs.get("goal_object") or []
        for item in goal_obj:
            if isinstance(item, dict) and item.get("type", "text") == "text":
                text = item.get("text")
                if text:
                    return str(text)
        # Fallback: BrowserGym sometimes exposes a flat "goal" field.
        goal = obs.get("goal")
        return str(goal) if goal else None

    def _log(self, log_action: Callable[[str], None] | None, message: str) -> None:
        if log_action is not None:
            log_action(message)

    def _trajectory_dir(self, plan: BrowserGymBridgeRunPlan) -> Path:
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
        if tool_harness.runner != "browsergym_bridge":
            raise ValueError(
                f"run '{run_id}' uses runner '{tool_harness.runner}', expected 'browsergym_bridge'"
            )
        if tool_harness.tier != ToolHarnessTier.BROWSER_ONLY:
            raise ValueError(
                f"run '{run_id}' uses tier '{tool_harness.tier}', expected 'browser_only'"
            )
        if memory_harness.kind != "none":
            raise ValueError(
                f"run '{run_id}' uses memory '{memory_harness.kind}', "
                "but browsergym_bridge only supports no memory"
            )
        is_mock = _is_mock_model(model)
        if not is_mock and model.provider != "openai":
            raise ValueError(
                f"run '{run_id}' uses model '{model.id}' with provider '{model.provider}'; "
                "browsergym_bridge supports provider='local' name='mock_screenshot_react' or provider='openai'"
            )
        if not is_mock and not model.vision:
            raise ValueError(
                f"run '{run_id}' uses non-vision model '{model.id}'; "
                "browsergym_bridge requires vision=true for real model runs"
            )
        if task.benchmark != "browsergym":
            raise ValueError(
                f"run '{run_id}' task '{task.id}' has benchmark='{task.benchmark}', "
                "expected 'browsergym'"
            )


def _is_mock_model(model: ModelConfig) -> bool:
    return model.provider == "local" and model.name == MOCK_MODEL_NAME
