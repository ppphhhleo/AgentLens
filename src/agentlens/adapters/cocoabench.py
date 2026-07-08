"""CocoaBench adapter.

Each CocoaBench task ships as a self-contained directory with:
  - task.yaml         : instruction text for the agent
  - test.py           : programmatic test(result) -> {passed, feedback, ...}
  - Dockerfile        : usually just `FROM ghcr.io/agent-infra/sandbox:latest`
  - docker-compose.yaml

Because the task's runtime image IS our AIO Sandbox base image (or a thin
extension of it), we reuse `AIOSandboxSession` to spin the container, then
run our standard screenshot ReAct loop on the bundled Chromium. After the
agent emits final_answer, we import the task's `test.py` and call its
`test(result)` function for the score.

Tasks may target external websites (e.g. vercel apps, public sites) — the
container just provides the agent's tool environment, not the website.

For MVP we use the stock `ghcr.io/agent-infra/sandbox:latest` image rather
than building each task's Dockerfile. Most CocoaBench tasks have no
real customization beyond the FROM line. Custom-image support can be a
later extension.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

import yaml
from pydantic import BaseModel, Field

from agentlens.evals.aggregate import aggregate_results
from agentlens.evals.base import ExperimentResult, SingleRunResult
from agentlens.harnesses.browser_actions import OVERLAY_INIT_JS
from agentlens.harnesses.eval_protocol import (
    goal_with_format_hint,
    prepare_answer_for_validator,
)
from agentlens.harnesses.screenshot_react_loop import run_screenshot_react_loop
from agentlens.harnesses.tool_gating import ToolSet
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
from agentlens.trajectory_paths import trajectory_case_slug


class CocoaBenchRunPlan(BaseModel):
    experiment_id: str
    run_id: str
    adapter: Literal["cocoabench"]
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    output_dir: Path
    raw_output_dir: Path
    max_steps: int = 30
    tags: list[str] = Field(default_factory=list)
    status: Literal["ready", "dry_run_only"] = "ready"
    notes: list[str] = Field(default_factory=list)


class CocoaBenchAdapter:
    """Screenshot ReAct loop on a CocoaBench task's container."""

    adapter_id = "cocoabench"

    def build_run_plans(
        self,
        config: ExperimentConfig,
        run_ids: set[str] | None = None,
        max_runs: int | None = None,
    ) -> list[CocoaBenchRunPlan]:
        models = {item.id: item for item in config.models}
        tool_harnesses = {item.id: item for item in config.tool_harnesses}
        memory_harnesses = {item.id: item for item in config.memory_harnesses}
        tasks = {item.id: item for item in config.tasks}
        plans: list[CocoaBenchRunPlan] = []

        for run in config.runs:
            if run_ids is not None and run.id not in run_ids:
                continue

            model = models[run.model]
            tool_harness = tool_harnesses[run.tool_harness]
            memory_harness = memory_harnesses[run.memory_harness]
            task = tasks[run.task]
            self._validate_supported(run.id, tool_harness, task)

            for seed in run.seeds:
                for trial in range(1, run.trials + 1):
                    plans.append(
                        CocoaBenchRunPlan(
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
                            raw_output_dir=run.output_dir / "cocoabench_raw",
                            max_steps=run.max_steps or 30,
                            tags=run.tags,
                            notes=[
                                f"CocoaBench task at {task.extra.get('task_dir')!r}",
                            ],
                        )
                    )
                    if max_runs is not None and len(plans) >= max_runs:
                        return plans
        return plans

    def run_many(
        self,
        plans: list[CocoaBenchRunPlan],
        log_action: Callable[[str], None] | None = None,
    ) -> ExperimentResult:
        run_results = [self.run(plan, log_action=log_action) for plan in plans]
        experiment_id = plans[0].experiment_id if plans else "empty"
        return aggregate_results(experiment_id, run_results)

    def run(
        self,
        plan: CocoaBenchRunPlan,
        log_action: Callable[[str], None] | None = None,
    ) -> SingleRunResult:
        from agentlens.sandbox import AIOSandboxSession
        from playwright.sync_api import sync_playwright

        started_at = datetime.now(UTC)
        artifact_dir = self._trajectory_dir(plan)
        screenshot_dir = artifact_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        task_dir = Path(plan.task.extra.get("task_dir", "")).expanduser()
        if not task_dir.is_dir():
            raise ValueError(
                f"task '{plan.task.id}' has no valid extra.task_dir "
                f"(got {task_dir!r})"
            )
        task_yaml = yaml.safe_load((task_dir / "task.yaml").read_text())
        instruction = task_yaml.get("instruction", "")
        if not instruction:
            raise ValueError(f"task.yaml in {task_dir} has empty instruction")
        # Stash the raw instruction in plan.task.goal so eval_protocol can
        # append any output_format_hint set on extra.
        task_with_goal = plan.task.model_copy(update={"goal": instruction}, deep=True)
        full_goal = goal_with_format_hint(task_with_goal)

        # Use stock AIO Sandbox image. CocoaBench Dockerfiles are typically
        # just `FROM ghcr.io/agent-infra/sandbox:latest`; custom-image build
        # support can come later.
        sandbox_image = plan.tool_harness.extra.get(
            "sandbox_image", "ghcr.io/agent-infra/sandbox:latest"
        )

        self._log(
            log_action,
            f"[{plan.run_id}] CocoaBench task {plan.task.id} "
            f"(dir={task_dir}); spinning sandbox...",
        )

        with AIOSandboxSession(image=sandbox_image) as sandbox:
            self._log(
                log_action,
                f"[{plan.run_id}] sandbox at {sandbox.base_url}; "
                f"cdp={sandbox.cdp_url}",
            )
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(sandbox.cdp_url)
                viewport = plan.tool_harness.extra.get(
                    "viewport", {"width": 1600, "height": 900}
                )
                context = browser.new_context(viewport=viewport)
                context.add_init_script(OVERLAY_INIT_JS)
                page = context.new_page()
                if bool(plan.tool_harness.extra.get("stealth", True)):
                    try:
                        from playwright_stealth import stealth_sync
                        stealth_sync(page)
                    except Exception:  # noqa: BLE001 - best-effort
                        pass

                start_url = plan.task.start_url or "about:blank"
                page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(
                    int(plan.tool_harness.extra.get("settle_ms", 2000))
                )

                toolset = ToolSet.from_harness(plan.tool_harness)
                model = build_model(plan.model, toolset=toolset)
                answer, events = run_screenshot_react_loop(
                    page=page,
                    model=model,
                    goal=full_goal,
                    max_steps=plan.max_steps,
                    screenshot_dir=screenshot_dir,
                    run_id=plan.run_id,
                    toolset=toolset,
                    sandbox=sandbox,
                    log_action=log_action,
                )
                final_url = page.url
                context.close()

        # Build a CocoaBench-shaped result for test.py.
        # The eval protocol (task.extra.answer_format) governs wrapping;
        # CocoaBench tasks should set answer_format=wrap_xml_answer.
        wrapped_answer = prepare_answer_for_validator(task_with_goal, answer) or ""
        conversation = _events_to_openai_conversation(events, instruction, wrapped_answer)
        test_input = {
            "task_result": wrapped_answer,
            "conversation": conversation,
            "status": "success" if answer else "failure",
        }

        try:
            test_module = _load_test_module(task_dir / "test.py")
            test_result = test_module.test(test_input)
        except Exception as exc:  # noqa: BLE001 - test.py errors should not crash run
            test_result = {
                "passed": False,
                "feedback": f"test.py raised: {type(exc).__name__}: {exc}",
                "details": {},
            }

        passed = bool(test_result.get("passed"))
        score = 1.0 if passed else 0.0
        feedback = str(test_result.get("feedback", ""))
        validation_message = f"CocoaBench test.py: passed={passed}; {feedback[:160]}"
        self._log(log_action, f"[{plan.run_id}] {validation_message}")

        events.append(
            TrajectoryEvent(
                event_type=TrajectoryEventType.VALIDATION_EVENT,
                step_index=1,
                data={
                    "success": passed,
                    "score": score,
                    "message": validation_message,
                    "answer": answer,
                    "wrapped_answer": wrapped_answer,
                    "final_url": final_url,
                    "test_result": test_result,
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
                success=passed,
                score=score,
                duration_ms=int((completed_at - started_at).total_seconds() * 1000),
                steps=sum(
                    1 for e in events if e.event_type == TrajectoryEventType.MODEL_MESSAGE
                ),
                tool_calls=sum(
                    1 for e in events if e.event_type == TrajectoryEventType.TOOL_CALL
                ),
            ),
            artifact_dir=artifact_dir,
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "trajectory.json").write_text(
            trajectory.model_dump_json(indent=2), encoding="utf-8"
        )

        return SingleRunResult(
            trajectory=trajectory,
            score=score,
            metrics={
                "success": passed,
                "score": score,
                "duration_ms": trajectory.metrics.duration_ms,
                "steps": trajectory.metrics.steps,
                "tool_calls": trajectory.metrics.tool_calls,
            },
            metadata={
                "run_id": plan.run_id,
                "adapter": plan.adapter,
                "task_dir": str(task_dir),
            },
        )

    def _trajectory_dir(self, plan: CocoaBenchRunPlan) -> Path:
        return plan.output_dir / "trajectories" / trajectory_case_slug(plan)

    def _log(self, log_action: Callable[[str], None] | None, message: str) -> None:
        if log_action is not None:
            log_action(message)

    def _validate_supported(
        self,
        run_id: str,
        tool_harness: ToolHarnessConfig,
        task: TaskConfig,
    ) -> None:
        if tool_harness.runner != "cocoabench":
            raise ValueError(
                f"run '{run_id}' uses runner '{tool_harness.runner}', expected 'cocoabench'"
            )
        if tool_harness.tier not in {
            ToolHarnessTier.BROWSER_FILES,
            ToolHarnessTier.FULL_SANDBOX,
        }:
            raise ValueError(
                f"run '{run_id}' uses tier '{tool_harness.tier}'; CocoaBench tasks "
                "require browser_files or full_sandbox"
            )
        if task.benchmark != "cocoabench":
            raise ValueError(
                f"run '{run_id}' task '{task.id}' has benchmark='{task.benchmark}', "
                "expected 'cocoabench'"
            )
        if not task.extra.get("task_dir"):
            raise ValueError(
                f"run '{run_id}' task '{task.id}' must set extra.task_dir to the "
                "CocoaBench task directory"
            )


# ---------- helpers ----------------------------------------------------


def _events_to_openai_conversation(
    events,
    instruction: str,
    final_wrapped_answer: str,
) -> list[dict[str, Any]]:
    """Build a minimal OpenAI-shaped conversation for test.py.

    CocoaBench's test.py walks `conversation` looking at assistant content
    and tool_calls (specifically `task_complete` with a `result` arg).
    For our screenshot ReAct trajectories we surface the per-step thought +
    the final_answer in the same shape.
    """
    convo: list[dict[str, Any]] = [
        {"role": "user", "content": instruction},
    ]
    for e in events:
        if e.event_type != TrajectoryEventType.MODEL_MESSAGE:
            continue
        data = e.data or {}
        thought = data.get("thought") or ""
        action = data.get("action") or {}
        if action.get("type") == "final_answer":
            convo.append(
                {
                    "role": "assistant",
                    "content": final_wrapped_answer or (action.get("answer") or thought),
                }
            )
        else:
            content_parts = []
            if thought:
                content_parts.append(thought)
            if action:
                content_parts.append(f"[action: {action.get('type','?')}]")
            convo.append({"role": "assistant", "content": "\n".join(content_parts)})
    return convo


def _load_test_module(test_py: Path):
    """Dynamically import a CocoaBench task's test.py.

    We use a unique module name per import so multiple tasks in one run
    don't collide in sys.modules.
    """
    if not test_py.exists():
        raise FileNotFoundError(f"missing test.py: {test_py}")
    mod_name = f"_cocoabench_test_{abs(hash(str(test_py)))}"
    spec = importlib.util.spec_from_file_location(mod_name, test_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not build module spec for {test_py}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module
