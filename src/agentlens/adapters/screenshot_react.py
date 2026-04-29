from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

from agentlens.actions import ComputerAction
from agentlens.evals.aggregate import aggregate_results
from agentlens.evals.base import ExperimentResult, SingleRunResult
from agentlens.harnesses.browser_actions import (
    capture_screenshot_event,
    execute_action,
    format_action,
)
from agentlens.harnesses.screenshot_react_loop import run_screenshot_react_loop
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
from agentlens.validators.answers import validate_answer

MOCK_MODEL_NAME = "mock_screenshot_react"


class ScreenshotReactRunPlan(BaseModel):
    """Concrete executable unit for screenshot-only ReAct runs (mock or real)."""

    experiment_id: str
    run_id: str
    adapter: Literal["screenshot_react"]
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    output_dir: Path
    raw_output_dir: Path
    max_steps: int = 1
    tags: list[str] = Field(default_factory=list)
    status: Literal["ready", "dry_run_only"] = "ready"
    notes: list[str] = Field(default_factory=list)


class ScreenshotReactAdapter:
    """Screenshot-only ReAct adapter: mock or real model-backed loop."""

    adapter_id = "screenshot_react"

    def build_run_plans(
        self,
        config: ExperimentConfig,
        run_ids: set[str] | None = None,
        max_runs: int | None = None,
    ) -> list[ScreenshotReactRunPlan]:
        models = {item.id: item for item in config.models}
        tool_harnesses = {item.id: item for item in config.tool_harnesses}
        memory_harnesses = {item.id: item for item in config.memory_harnesses}
        tasks = {item.id: item for item in config.tasks}
        plans: list[ScreenshotReactRunPlan] = []

        for run in config.runs:
            if run_ids is not None and run.id not in run_ids:
                continue

            model = models[run.model]
            tool_harness = tool_harnesses[run.tool_harness]
            memory_harness = memory_harnesses[run.memory_harness]
            task = tasks[run.task]
            self._validate_supported(run.id, model, tool_harness, memory_harness, task)

            is_mock = _is_mock_model(model)
            note = (
                "Screenshot ReAct mock run; uses configured mock_actions / mock_answer."
                if is_mock
                else f"Screenshot ReAct real run with provider={model.provider} name={model.name}."
            )

            for seed in run.seeds:
                for trial in range(1, run.trials + 1):
                    plans.append(
                        ScreenshotReactRunPlan(
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
                            raw_output_dir=run.output_dir / "screenshot_react_raw",
                            max_steps=run.max_steps or (1 if is_mock else 12),
                            tags=run.tags,
                            notes=[note],
                        )
                    )

                    if max_runs is not None and len(plans) >= max_runs:
                        return plans

        return plans

    def run_many(
        self,
        plans: list[ScreenshotReactRunPlan],
        log_action: Callable[[str], None] | None = None,
    ) -> ExperimentResult:
        run_results = [self.run(plan, log_action=log_action) for plan in plans]
        experiment_id = plans[0].experiment_id if plans else "empty"
        return aggregate_results(experiment_id, run_results)

    def run(
        self,
        plan: ScreenshotReactRunPlan,
        log_action: Callable[[str], None] | None = None,
    ) -> SingleRunResult:
        started_at = datetime.now(UTC)
        artifact_dir = self._trajectory_dir(plan)
        screenshot_dir = artifact_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            self._log(
                log_action,
                f"[{plan.run_id} seed={plan.seed} trial={plan.trial}] open {plan.task.start_url}",
            )
            headless = bool(plan.tool_harness.extra.get("headless", True))
            # slow_mo defaults to 0 — pacing comes from settle_ms + the model
            # API latency. Override per-config if you want explicit pacing.
            slow_mo = int(plan.tool_harness.extra.get("slow_mo_ms", 0))
            browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
            viewport = plan.tool_harness.extra.get(
                "viewport", {"width": 1600, "height": 900}
            )

            # Tracing's DOM-snapshot walk causes visible flicker in headed
            # mode, so default it OFF when live. Video screencast is much
            # lighter and useful for sharing/post-hoc review, so always on
            # by default. Both can be overridden per-config.
            tracing_enabled = bool(
                plan.tool_harness.extra.get("tracing", headless)
            )
            video_enabled = bool(
                plan.tool_harness.extra.get("record_video", True)
            )
            video_dir = artifact_dir / "video" if video_enabled else None
            if video_dir is not None:
                video_dir.mkdir(parents=True, exist_ok=True)

            context = browser.new_context(
                viewport=viewport,
                record_video_dir=str(video_dir) if video_dir else None,
                record_video_size=viewport if video_dir else None,
            )
            if tracing_enabled:
                context.tracing.start(screenshots=True, snapshots=True, sources=True)

            # Inject the action-marker overlay once per context so we don't
            # pay a CDP round-trip + sync script eval on every action.
            from agentlens.harnesses.browser_actions import OVERLAY_INIT_JS
            context.add_init_script(OVERLAY_INIT_JS)

            page = context.new_page()
            page.goto(plan.task.start_url or "about:blank", wait_until="domcontentloaded")
            page.wait_for_timeout(int(plan.tool_harness.extra.get("settle_ms", 1500)))

            if _is_mock_model(plan.model):
                answer, events = self._run_mock(plan, page, screenshot_dir, log_action)
            else:
                model = build_model(plan.model)
                answer, events = run_screenshot_react_loop(
                    page=page,
                    model=model,
                    goal=plan.task.goal or "",
                    max_steps=plan.max_steps,
                    screenshot_dir=screenshot_dir,
                    run_id=plan.run_id,
                    log_action=log_action,
                )

            final_url = page.url
            trace_path = artifact_dir / "trace.zip" if tracing_enabled else None
            if tracing_enabled:
                context.tracing.stop(path=str(trace_path))
            context.close()
            browser.close()
            self._log(
                log_action,
                f"[{plan.run_id}] artifacts: trajectory.json"
                + (f", trace={trace_path}" if trace_path else "")
                + (f", video_dir={video_dir}" if video_dir else ""),
            )

        if answer is None and _is_mock_model(plan.model):
            answer = str(plan.task.extra.get("mock_answer", ""))
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.MODEL_MESSAGE,
                    step_index=len(events),
                    data={
                        "thought": "Mock model returned fallback final answer.",
                        "action": {"type": "final_answer", "answer": answer},
                        "mock": True,
                    },
                )
            )

        # Collect screenshots (in step order) for vision-based validators.
        screenshot_paths: list[Path] = []
        for event in events:
            if event.event_type == TrajectoryEventType.SCREENSHOT:
                screenshot_paths.extend(event.artifact_paths)
        success, score, validation_message = validate_answer(
            answer,
            plan.task,
            final_url=final_url,
            screenshot_paths=screenshot_paths,
        )
        self._log(
            log_action,
            f"[{plan.run_id}] validation success={success} score={score} message={validation_message}",
        )
        events.append(
            TrajectoryEvent(
                event_type=TrajectoryEventType.VALIDATION_EVENT,
                step_index=1,
                data={
                    "success": success,
                    "score": score,
                    "message": validation_message,
                    "answer": answer,
                    "expected_answer": plan.task.expected_answer,
                    "answer_validator": plan.task.answer_validator,
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
                steps=self._count_model_steps(events),
                tokens_input=self._sum_tokens(events, "prompt_tokens"),
                tokens_output=self._sum_tokens(events, "completion_tokens"),
                tool_calls=self._count_browser_actions(events),
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
                "tokens_input": trajectory.metrics.tokens_input,
                "tokens_output": trajectory.metrics.tokens_output,
            },
            metadata={
                "run_id": plan.run_id,
                "adapter": plan.adapter,
                "mock": _is_mock_model(plan.model),
            },
        )

    def _run_mock(
        self,
        plan: ScreenshotReactRunPlan,
        page,
        screenshot_dir: Path,
        log_action: Callable[[str], None] | None,
    ) -> tuple[str | None, list[TrajectoryEvent]]:
        events: list[TrajectoryEvent] = []
        answer: str | None = None

        events.append(
            capture_screenshot_event(
                page=page, screenshot_dir=screenshot_dir, step_index=0, goal=plan.task.goal
            )
        )
        self._log(
            log_action,
            f"[{plan.run_id} step=0] screenshot -> {screenshot_dir / 'step_000.png'}",
        )

        for step_index, action in enumerate(self._mock_actions(plan), start=1):
            thought = self._mock_thought(action)
            self._log(log_action, f"[{plan.run_id} step={step_index}] {format_action(action)}")
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.MODEL_MESSAGE,
                    step_index=step_index,
                    data={
                        "thought": thought,
                        "action": action.model_dump(mode="json"),
                        "mock": True,
                    },
                )
            )

            if action.type == "final_answer":
                answer = action.answer
                break

            action_error = execute_action(page, action)
            if action_error:
                self._log(log_action, f"[{plan.run_id} step={step_index}] error: {action_error}")
            events.append(
                TrajectoryEvent(
                    event_type=TrajectoryEventType.BROWSER_ACTION,
                    step_index=step_index,
                    data={"action": action.model_dump(mode="json"), "error": action_error},
                )
            )
            events.append(
                capture_screenshot_event(
                    page=page,
                    screenshot_dir=screenshot_dir,
                    step_index=step_index,
                    goal=plan.task.goal,
                )
            )
            self._log(
                log_action,
                f"[{plan.run_id} step={step_index}] screenshot -> "
                f"{screenshot_dir / f'step_{step_index:03d}.png'}",
            )

        return answer, events

    def _mock_actions(self, plan: ScreenshotReactRunPlan) -> list[ComputerAction]:
        raw_actions = plan.task.extra.get("mock_actions")
        if raw_actions:
            return [ComputerAction.from_raw(raw_action) for raw_action in raw_actions]

        answer = str(plan.task.extra.get("mock_answer", ""))
        return [ComputerAction(type="final_answer", answer=answer)]

    def _mock_thought(self, action: ComputerAction) -> str:
        if action.type == "final_answer":
            return "Mock model returns the configured final answer after observing the screenshot."
        return f"Mock model requests computer action '{action.type}'."

    def _log(self, log_action: Callable[[str], None] | None, message: str) -> None:
        if log_action is not None:
            log_action(message)

    def _count_model_steps(self, events: list[TrajectoryEvent]) -> int:
        return sum(event.event_type == TrajectoryEventType.MODEL_MESSAGE for event in events)

    def _count_browser_actions(self, events: list[TrajectoryEvent]) -> int:
        return sum(event.event_type == TrajectoryEventType.BROWSER_ACTION for event in events)

    def _sum_tokens(self, events: list[TrajectoryEvent], key: str) -> int | None:
        total = 0
        seen = False
        for event in events:
            if event.event_type != TrajectoryEventType.MODEL_MESSAGE:
                continue
            value = event.data.get(key)
            if isinstance(value, int):
                total += value
                seen = True
        return total if seen else None

    def _trajectory_dir(self, plan: ScreenshotReactRunPlan) -> Path:
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
        if tool_harness.runner != "screenshot_react":
            raise ValueError(
                f"run '{run_id}' uses runner '{tool_harness.runner}', "
                "expected 'screenshot_react'"
            )
        if tool_harness.tier != ToolHarnessTier.BROWSER_ONLY:
            raise ValueError(
                f"run '{run_id}' uses tier '{tool_harness.tier}', expected 'browser_only'"
            )
        if memory_harness.kind != "none":
            raise ValueError(
                f"run '{run_id}' uses memory '{memory_harness.kind}', "
                "but screenshot_react adapter only supports no memory"
            )

        is_mock = _is_mock_model(model)
        if not is_mock and model.provider != "openai":
            raise ValueError(
                f"run '{run_id}' uses model '{model.id}' with provider '{model.provider}'; "
                "screenshot_react supports provider='local' name='mock_screenshot_react' "
                "(mock) or provider='openai' (real)"
            )
        if not is_mock and not model.vision:
            raise ValueError(
                f"run '{run_id}' uses non-vision model '{model.id}'; "
                "screenshot_react requires vision=true for real model runs"
            )

        if not task.start_url:
            raise ValueError(f"run '{run_id}' task '{task.id}' must define start_url")


def _is_mock_model(model: ModelConfig) -> bool:
    return model.provider == "local" and model.name == MOCK_MODEL_NAME
