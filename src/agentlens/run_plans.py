from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agentlens.schemas import ExperimentConfig, MemoryScope, ToolHarnessConfig

RunPlan = Any


def build_run_plans(
    config: ExperimentConfig,
    run_id: str | None = None,
    max_runs: int | None = None,
    snapshot_name: str | None = None,
) -> list[RunPlan]:
    """Build executable run plans from an experiment config.

    Each invocation gets its own snapshot folder under each run's
    `output_dir`, so re-running never overwrites prior trajectories or
    reports. The snapshot folder defaults to a UTC timestamp; pass
    `snapshot_name` to override.
    """
    if snapshot_name is None:
        snapshot_name = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")

    run_ids = {run_id} if run_id else None
    tool_harnesses = {item.id: item for item in config.tool_harnesses}
    plans: list[RunPlan] = []

    for run in config.runs:
        if run_ids is not None and run.id not in run_ids:
            continue

        tool_harness = tool_harnesses[run.tool_harness]
        scoped_config = config.model_copy(update={"runs": [run]})
        if tool_harness.runner == "agentlab":
            from agentlens.adapters.agentlab_browsergym import AgentLabBrowserGymAdapter

            adapter = AgentLabBrowserGymAdapter()
            plans.extend(adapter.build_run_plans(scoped_config, max_runs=max_runs))
        elif tool_harness.runner == "browsergym_direct":
            from agentlens.adapters.browsergym_direct import BrowserGymDirectAdapter

            adapter = BrowserGymDirectAdapter()
            plans.extend(adapter.build_run_plans(scoped_config, max_runs=max_runs))
        elif tool_harness.runner == "screenshot_react":
            from agentlens.adapters.screenshot_react import ScreenshotReactAdapter

            adapter = ScreenshotReactAdapter()
            plans.extend(adapter.build_run_plans(scoped_config, max_runs=max_runs))
        elif tool_harness.runner == "browsergym_bridge":
            from agentlens.adapters.browsergym_bridge import BrowserGymBridgeAdapter

            adapter = BrowserGymBridgeAdapter()
            plans.extend(adapter.build_run_plans(scoped_config, max_runs=max_runs))
        else:
            raise ValueError(f"unsupported runner for run '{run.id}': {tool_harness.runner}")

        if max_runs is not None and len(plans) >= max_runs:
            plans = plans[:max_runs]
            break

    if run_id and not plans:
        raise ValueError(f"run id not found or produced no plans: {run_id}")

    # Stamp every plan's output dir with a per-invocation snapshot folder.
    # All downstream consumers (adapter trajectory dirs, CLI report dirs,
    # dry-run JSON) inherit this automatically.
    plans = [_with_snapshot_dir(plan, snapshot_name) for plan in plans]
    return plans


def _with_snapshot_dir(plan: RunPlan, snapshot_name: str) -> RunPlan:
    update = {"output_dir": plan.output_dir / snapshot_name}
    if hasattr(plan, "raw_output_dir"):
        # Re-derive raw_output_dir under the snapshot too.
        original = plan.raw_output_dir
        update["raw_output_dir"] = plan.output_dir / snapshot_name / original.name
    notes = list(getattr(plan, "notes", []) or [])
    notes.append(f"snapshot={snapshot_name}")
    update["notes"] = notes
    return plan.model_copy(update=update, deep=True)


def write_run_plan_json(plans: list[RunPlan], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [plan.model_dump(mode="json") for plan in plans]
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def with_live_mode(plans: list[RunPlan]) -> list[RunPlan]:
    """Return copies of run plans with headed browser mode enabled."""
    live_plans: list[RunPlan] = []
    for plan in plans:
        live_tool_harness = _tool_harness_with_headless(plan.tool_harness, headless=False)
        live_plans.append(
            plan.model_copy(
                update={
                    "tool_harness": live_tool_harness,
                    "notes": [*plan.notes, "Live mode enabled: browser headless=false."],
                },
                deep=True,
            )
        )
    return live_plans


def _tool_harness_with_headless(
    tool_harness: ToolHarnessConfig,
    headless: bool,
) -> ToolHarnessConfig:
    extra = dict(tool_harness.extra)
    extra["headless"] = headless
    return tool_harness.model_copy(update={"extra": extra}, deep=True)


def group_plans_by_scope(plans: list[RunPlan]) -> list[list[RunPlan]]:
    """Group plans into session batches by their memory_harness.scope.

    Grouping rules:
        NONE | IN_TASK            -> one group per plan (no sharing)
        CROSS_TRIAL               -> grouped by task.id (all trials of one task)
        CROSS_TASK_SAME_SITE      -> grouped by urlparse(task.start_url).netloc
        CROSS_BENCHMARK           -> one group containing all plans

    All plans in this batch must share the same memory scope. Mixing scopes
    in one CLI invocation is rejected (split into separate invocations).
    """
    if not plans:
        return []

    scopes = {p.memory_harness.scope for p in plans}
    if len(scopes) > 1:
        raise ValueError(
            f"plans have mixed memory scopes {scopes}; "
            "split into separate invocations or use a single memory harness"
        )
    scope = next(iter(scopes))

    if scope in (MemoryScope.NONE, MemoryScope.IN_TASK):
        return [[p] for p in plans]

    groups: dict[str, list[RunPlan]] = defaultdict(list)
    for p in plans:
        if scope == MemoryScope.CROSS_TRIAL:
            key = p.task.id
        elif scope == MemoryScope.CROSS_TASK_SAME_SITE:
            host = urlparse(p.task.start_url or "").netloc
            key = host or p.task.id
        elif scope == MemoryScope.CROSS_BENCHMARK:
            key = "__all__"
        else:
            key = p.task.id  # unknown scope -> per-task fallback
        groups[key].append(p)
    return list(groups.values())
