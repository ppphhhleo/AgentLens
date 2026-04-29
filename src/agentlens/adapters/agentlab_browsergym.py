from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from agentlens.schemas import (
    ExperimentConfig,
    MemoryHarnessConfig,
    ModelConfig,
    RunConfig,
    TaskConfig,
    ToolHarnessConfig,
    ToolHarnessTier,
)


class ResolvedRunPlan(BaseModel):
    """Concrete executable unit after expanding config references, seeds, and trials."""

    experiment_id: str
    run_id: str
    adapter: Literal["agentlab_browsergym"]
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    output_dir: Path
    raw_output_dir: Path
    max_steps: int | None = None
    tags: list[str] = Field(default_factory=list)
    status: Literal["ready", "dry_run_only"] = "ready"
    notes: list[str] = Field(default_factory=list)


class AgentLabBrowserGymAdapter:
    """Adapter for AgentLab-managed BrowserGym tasks."""

    adapter_id = "agentlab_browsergym"

    def build_run_plans(
        self,
        config: ExperimentConfig,
        run_ids: set[str] | None = None,
        max_runs: int | None = None,
    ) -> list[ResolvedRunPlan]:
        models = {item.id: item for item in config.models}
        tool_harnesses = {item.id: item for item in config.tool_harnesses}
        memory_harnesses = {item.id: item for item in config.memory_harnesses}
        tasks = {item.id: item for item in config.tasks}
        plans: list[ResolvedRunPlan] = []

        for run in config.runs:
            if run_ids is not None and run.id not in run_ids:
                continue

            model = models[run.model]
            tool_harness = tool_harnesses[run.tool_harness]
            memory_harness = memory_harnesses[run.memory_harness]
            task = tasks[run.task]
            self._validate_supported(run, tool_harness, task)

            for seed in run.seeds:
                for trial in range(1, run.trials + 1):
                    notes = self._notes_for_plan(memory_harness, task)
                    plans.append(
                        ResolvedRunPlan(
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
                            raw_output_dir=run.output_dir / "agentlab_raw",
                            max_steps=run.max_steps,
                            tags=run.tags,
                            status="dry_run_only" if memory_harness.kind != "none" else "ready",
                            notes=notes,
                        )
                    )

                    if max_runs is not None and len(plans) >= max_runs:
                        return plans

        return plans

    def run(self, plan: ResolvedRunPlan) -> None:
        raise NotImplementedError(
            "Real AgentLab execution is not implemented yet. Use --dry-run to inspect plans."
        )

    def _validate_supported(
        self,
        run: RunConfig,
        tool_harness: ToolHarnessConfig,
        task: TaskConfig,
    ) -> None:
        if tool_harness.runner != "agentlab":
            raise ValueError(
                f"run '{run.id}' uses runner '{tool_harness.runner}', expected 'agentlab'"
            )
        if tool_harness.tier != ToolHarnessTier.BROWSER_ONLY:
            raise ValueError(
                f"run '{run.id}' uses tier '{tool_harness.tier}', expected 'browser_only'"
            )
        if task.benchmark != "browsergym":
            raise ValueError(
                f"run '{run.id}' uses benchmark '{task.benchmark}', expected 'browsergym'"
            )

    def _notes_for_plan(
        self,
        memory_harness: MemoryHarnessConfig,
        task: TaskConfig,
    ) -> list[str]:
        notes: list[str] = []
        if memory_harness.kind != "none":
            notes.append(
                "Memory harness is resolved, but real AgentLab memory injection is not wired yet."
            )
        if task.task_id == "browsergym/openended":
            notes.append(
                "Open-ended BrowserGym task may need a custom runner; AgentLab make_study usually "
                "expects registered benchmark names."
            )
        return notes

