from __future__ import annotations

import shlex
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

from agentlens.evals.aggregate import aggregate_results
from agentlens.evals.base import ExperimentResult, SingleRunResult
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
from agentlens.validators.answers import validate_answer


class DesktopReactRunPlan(BaseModel):
    experiment_id: str
    run_id: str
    adapter: Literal["desktop_react"]
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    output_dir: Path
    max_steps: int = 8
    tags: list[str] = Field(default_factory=list)
    status: Literal["ready", "dry_run_only"] = "ready"
    notes: list[str] = Field(default_factory=list)


class DesktopReactAdapter:
    """Desktop-app ReAct adapter for Ubuntu/AIO-sandbox style GUI tasks."""

    adapter_id = "desktop_react"

    def build_run_plans(
        self,
        config: ExperimentConfig,
        run_ids: set[str] | None = None,
        max_runs: int | None = None,
    ) -> list[DesktopReactRunPlan]:
        models = {item.id: item for item in config.models}
        tool_harnesses = {item.id: item for item in config.tool_harnesses}
        memory_harnesses = {item.id: item for item in config.memory_harnesses}
        tasks = {item.id: item for item in config.tasks}
        plans: list[DesktopReactRunPlan] = []
        for run in config.runs:
            if run_ids is not None and run.id not in run_ids:
                continue
            model = models[run.model]
            tool_harness = tool_harnesses[run.tool_harness]
            memory_harness = memory_harnesses[run.memory_harness]
            task = tasks[run.task]
            self._validate_supported(run.id, model, tool_harness)
            for seed in run.seeds:
                for trial in range(1, run.trials + 1):
                    plans.append(
                        DesktopReactRunPlan(
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
                            max_steps=run.max_steps or 8,
                            tags=run.tags,
                            notes=[
                                f"Desktop ReAct real run with provider={model.provider} name={model.name}.",
                                f"sandbox_image={tool_harness.extra.get('sandbox_image')}",
                            ],
                        )
                    )
                    if max_runs is not None and len(plans) >= max_runs:
                        return plans
        return plans

    def run_many(
        self,
        plans: list[DesktopReactRunPlan],
        log_action: Callable[[str], None] | None = None,
    ) -> ExperimentResult:
        return aggregate_results(
            plans[0].experiment_id if plans else "empty",
            [self.run(plan, log_action=log_action) for plan in plans],
        )

    def run(
        self,
        plan: DesktopReactRunPlan,
        log_action: Callable[[str], None] | None = None,
    ) -> SingleRunResult:
        from agentlens.harnesses.desktop_react_loop import run_desktop_react_loop
        from agentlens.sandbox import AIOSandboxSession

        started_at = datetime.now(UTC)
        artifact_dir = self._trajectory_dir(plan)
        screenshot_dir = artifact_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        harness_extra = plan.tool_harness.extra
        sandbox_env = {
            str(key): str(value)
            for key, value in dict(harness_extra.get("sandbox_env") or {}).items()
        }
        screen_size = harness_extra.get("screen_size") or (
            plan.model.extra or {}
        ).get("screen_size", [1920, 1080])
        if not isinstance(screen_size, (list, tuple)) or len(screen_size) != 2:
            screen_size = [1920, 1080]
        sandbox_env.setdefault("DISPLAY_WIDTH", str(int(screen_size[0])))
        sandbox_env.setdefault("DISPLAY_HEIGHT", str(int(screen_size[1])))
        sandbox_cm = AIOSandboxSession(
            image=harness_extra.get("sandbox_image", "ghcr.io/agent-infra/sandbox:latest"),
            host_port=int(harness_extra.get("sandbox_port", 8080)),
            env=sandbox_env,
            shm_size=harness_extra.get("sandbox_shm_size", "2g"),
            cap_add=list(harness_extra.get("sandbox_cap_add", ["SYS_ADMIN"])),
            security_opt=list(harness_extra.get("sandbox_security_opt", ["seccomp=unconfined"])),
            watch_paths=list(harness_extra.get("sandbox_watch_paths", ["/home/gem", "/tmp", "/home/gem/Downloads"])),
            reuse_existing=bool(harness_extra.get("reuse_existing_sandbox", False)),
            keep_open_seconds=int(harness_extra.get("keep_sandbox_open_seconds", 0)),
        )
        with sandbox_cm as sandbox:
            launch_cmd = _desktop_start_command(plan)
            if launch_cmd:
                launch = sandbox.shell(str(launch_cmd), timeout_sec=10)
                self._log(log_action, f"[{plan.run_id}] desktop_start_cmd ok={launch.ok} err={launch.error[:120]!r}")
                settle_ms = int(harness_extra.get("settle_ms", 0) or 0)
                if settle_ms > 0:
                    time.sleep(settle_ms / 1000)
                if plan.task.start_url and bool(harness_extra.get("maximize_window", True)):
                    maximized = sandbox.shell(_maximize_active_window_command(), timeout_sec=10)
                    self._log(
                        log_action,
                        f"[{plan.run_id}] desktop_maximize_window "
                        f"ok={maximized.ok} err={maximized.error[:120]!r}",
                    )
                if plan.task.start_url and bool(harness_extra.get("force_start_url", True)):
                    nav = sandbox.shell(_force_start_url_command(plan.task.start_url), timeout_sec=10)
                    self._log(
                        log_action,
                        f"[{plan.run_id}] desktop_force_start_url ok={nav.ok} err={nav.error[:120]!r}",
                    )
                    if settle_ms > 0:
                        time.sleep(settle_ms / 1000)
                if plan.task.start_url and bool(
                    harness_extra.get("require_browser_ready", True)
                ):
                    ready, observed_url = _wait_for_browser_ready(
                        sandbox,
                        plan.task.start_url,
                        timeout_s=float(harness_extra.get("browser_ready_timeout_s", 30)),
                    )
                    self._log(
                        log_action,
                        f"[{plan.run_id}] desktop_browser_ready "
                        f"ok={ready} url={observed_url!r}",
                    )
                    if not ready:
                        raise RuntimeError(
                            "browser did not reach the task website before the acting loop; "
                            f"expected={plan.task.start_url!r}, observed={observed_url!r}"
                        )
                    ready_settle_ms = int(
                        harness_extra.get("browser_ready_settle_ms", 1500) or 0
                    )
                    if ready_settle_ms > 0:
                        time.sleep(ready_settle_ms / 1000)
            toolset = ToolSet.from_harness(plan.tool_harness)
            model_config = plan.model.model_copy(
                update={
                    "extra": {
                        **(plan.model.extra or {}),
                        "input_modes": list(harness_extra.get("input_modes", ["screenshot"])),
                        "addressing_modes": list(harness_extra.get("addressing_modes", ["coordinate"])),
                        "parallel_tool_calls": bool(harness_extra.get("parallel_tool_calls", False)),
                        "max_actions_per_round": int(harness_extra.get("max_actions_per_round", 1)),
                    }
                },
                deep=True,
            )
            model = build_model(model_config, toolset=toolset)
            answer, events = run_desktop_react_loop(
                sandbox=sandbox,
                model=model,
                goal=plan.task.goal or "",
                max_steps=plan.max_steps,
                screenshot_dir=screenshot_dir,
                run_id=f"{plan.run_id}.t{plan.trial}",
                toolset=toolset,
                intervention_config=harness_extra.get("intervention"),
                model_max_attempts=int(harness_extra.get("model_max_attempts", 3)),
                model_retry_sleep_s=float(harness_extra.get("model_retry_sleep_s", 1.0)),
                max_actions_per_round=int(harness_extra.get("max_actions_per_round", 1)),
                viewport={
                    "width": int(screen_size[0]),
                    "height": int(screen_size[1]),
                },
                log_action=log_action,
            )

        screenshot_paths = [
            path
            for event in events
            if event.event_type == TrajectoryEventType.SCREENSHOT
            for path in event.artifact_paths
        ]
        success, score, validation_message = validate_answer(
            answer,
            plan.task,
            final_url=None,
            screenshot_paths=screenshot_paths,
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
                    "adapter": self.adapter_id,
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
                tool_calls=self._count_action_events(events),
                extra={
                    "desktop_actions": self._count_tool_calls(events),
                    "max_actions_per_round": int(harness_extra.get("max_actions_per_round", 1)),
                    "screenshot_source": str(
                        harness_extra.get("screenshot_source", "virtual_desktop")
                    ),
                    "coordinate_frame": str(
                        harness_extra.get("coordinate_frame", "desktop_screen")
                    ),
                },
            ),
            artifact_dir=artifact_dir,
        )
        self._write_trajectory(trajectory)
        return SingleRunResult(
            trajectory=trajectory,
            score=score,
            metrics={
                "score": score,
                "success": success,
                "duration_ms": trajectory.metrics.duration_ms,
                "steps": trajectory.metrics.steps,
                "tool_calls": trajectory.metrics.tool_calls,
            },
        )

    def _trajectory_dir(self, plan: DesktopReactRunPlan) -> Path:
        return plan.output_dir / "trajectories" / trajectory_case_slug(plan)

    def _write_trajectory(self, trajectory: Trajectory) -> None:
        from agentlens.reports.trajectory_viewer import write_trajectory_viewer

        trajectory.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = trajectory.artifact_dir / "trajectory.json"
        path.write_text(trajectory.model_dump_json(indent=2), encoding="utf-8")
        write_trajectory_viewer(path)

    def _validate_supported(
        self,
        run_id: str,
        model: ModelConfig,
        tool_harness: ToolHarnessConfig,
    ) -> None:
        if tool_harness.runner != "desktop_react":
            raise ValueError(f"run '{run_id}' expected runner desktop_react")
        if tool_harness.tier not in {
            ToolHarnessTier.GUI_ONLY,
            ToolHarnessTier.COMPUTER_USE,
            ToolHarnessTier.FULL_SANDBOX,
        }:
            raise ValueError("desktop_react requires tier='gui_only' or 'computer_use'")
        if model.provider not in {"openai", "anthropic", "gemini"}:
            raise ValueError("desktop_react currently supports OpenAI, Anthropic, or Gemini models")
        if not model.vision:
            raise ValueError("desktop_react requires a vision-capable model")

    @staticmethod
    def _count_model_steps(events: list[TrajectoryEvent]) -> int:
        return sum(1 for event in events if event.event_type == TrajectoryEventType.MODEL_MESSAGE and "action" in event.data)

    @staticmethod
    def _count_action_events(events: list[TrajectoryEvent]) -> int:
        return sum(1 for event in events if event.event_type in {TrajectoryEventType.TOOL_CALL, TrajectoryEventType.BROWSER_ACTION})

    @staticmethod
    def _count_tool_calls(events: list[TrajectoryEvent]) -> int:
        return sum(1 for event in events if event.event_type == TrajectoryEventType.TOOL_CALL)

    @staticmethod
    def _sum_tokens(events: list[TrajectoryEvent], key: str) -> int | None:
        total = 0
        seen = False
        for event in events:
            value = event.data.get(key)
            if isinstance(value, int):
                seen = True
                total += value
        return total if seen else None

    @staticmethod
    def _log(log_action: Callable[[str], None] | None, message: str) -> None:
        if log_action is not None:
            log_action(message)


def _desktop_start_command(plan: DesktopReactRunPlan) -> str | None:
    if plan.task.extra and plan.task.extra.get("desktop_start_cmd"):
        return str(plan.task.extra["desktop_start_cmd"])
    template = plan.tool_harness.extra.get("desktop_start_cmd_template")
    if template and plan.task.start_url:
        return str(template).format(start_url=shlex.quote(plan.task.start_url))
    return None


def _force_start_url_command(start_url: str) -> str:
    cdp_script = (
        "import json,sys,urllib.parse,urllib.request; "
        "base='http://127.0.0.1:9222'; "
        "url=sys.argv[1]; "
        "req=urllib.request.Request(base+'/json/new?'+urllib.parse.quote(url,safe=''), "
        "method='PUT'); "
        "target=json.load(urllib.request.urlopen(req,timeout=5)); "
        "target_id=str(target.get('id','')); "
        "assert target_id; "
        "urllib.request.urlopen(urllib.request.Request("
        "base+'/json/activate/'+target_id,method='PUT'),timeout=5).read()"
    )
    cdp_command = f"python3 -c {shlex.quote(cdp_script)} {shlex.quote(start_url)}"
    quoted_url = shlex.quote(start_url)
    gui_fallback = _desktop_user_command(
        f"{_activate_browser_window_script()} && "
        "xdotool key --clearmodifiers ctrl+l && "
        f"xdotool type --clearmodifiers -- {quoted_url} && "
        "xdotool key --clearmodifiers Return"
    )
    return f"({cdp_command}) || ({gui_fallback})"


def _maximize_active_window_command() -> str:
    return _desktop_user_command(
        f"{_activate_browser_window_script()} && "
        "(wmctrl -i -r \"$wid\" -b add,maximized_vert,maximized_horz "
        "|| xdotool key --clearmodifiers alt+F10)"
    )


def _activate_browser_window_script() -> str:
    return (
        "wid=$(xdotool search --onlyvisible --class "
        "'(google-chrome|chromium|Google-chrome)' 2>/dev/null | tail -n 1); "
        "[ -n \"$wid\" ] || wid=$(xdotool search --onlyvisible --name "
        "'(Chrome|Chromium)' 2>/dev/null | tail -n 1); "
        "[ -n \"$wid\" ] && xdotool windowactivate --sync \"$wid\""
    )


def _desktop_user_command(script: str) -> str:
    quoted_script = shlex.quote(script)
    return (
        'if [ "$(id -u)" -eq 0 ]; then '
        'runuser -u gem -- env HOME=/home/gem DISPLAY="${DISPLAY:-:99.0}" '
        f"sh -lc {quoted_script}; "
        "else "
        'env HOME="${HOME:-/home/gem}" DISPLAY="${DISPLAY:-:99.0}" '
        f"sh -lc {quoted_script}; "
        "fi"
    )


def _wait_for_browser_ready(
    sandbox,
    start_url: str,
    *,
    timeout_s: float,
) -> tuple[bool, str]:
    deadline = time.monotonic() + max(1.0, timeout_s)
    command = _browser_target_check_command(start_url)
    last_url = ""
    stable_matches = 0
    while time.monotonic() < deadline:
        result = sandbox.shell(command, timeout_sec=5)
        observed_url = (result.output or "").strip().splitlines()
        if observed_url:
            current_url = observed_url[-1]
            if result.ok:
                stable_matches = stable_matches + 1 if current_url == last_url else 1
                if stable_matches >= 2:
                    return True, current_url
            else:
                stable_matches = 0
            last_url = current_url
        time.sleep(1)
    return False, last_url


def _browser_target_check_command(start_url: str) -> str:
    script = (
        "import json,sys,urllib.parse,urllib.request; "
        "expected=sys.argv[1]; expected_host=urllib.parse.urlsplit(expected).netloc; "
        "targets=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list', timeout=3)); "
        "urls=[str(item.get('url','')) for item in targets if item.get('type')=='page']; "
        "valid=[url for url in urls if url and not url.startswith('chrome-error://') "
        "and (not expected_host or urllib.parse.urlsplit(url).netloc==expected_host)]; "
        "print(valid[0] if valid else (urls[0] if urls else '')); "
        "raise SystemExit(0 if valid else 1)"
    )
    return f"python3 -c {shlex.quote(script)} {shlex.quote(start_url)}"
