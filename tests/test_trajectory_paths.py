from pathlib import Path

from agentlens.adapters.desktop_react import DesktopReactRunPlan
from agentlens.schemas import (
    MemoryHarnessConfig,
    ModelConfig,
    TaskConfig,
    ToolHarnessConfig,
)
from agentlens.trajectory_paths import gui_vs_cli_case_slug, trajectory_case_slug


def test_trajectory_case_slug_uses_task_model_harness_seed_and_trial() -> None:
    plan = DesktopReactRunPlan(
        experiment_id="exp",
        run_id="dv_t3_grounded__opus48__agentlens_gui_toolcall",
        adapter="desktop_react",
        seed=0,
        trial=1,
        model=ModelConfig(
            id="claude_opus48_gui_toolcall",
            provider="anthropic",
            name="claude-opus-4-8",
            extra={"interaction_backend": "tool_call"},
        ),
        tool_harness=ToolHarnessConfig(
            id="desktop_gui_toolcall",
            runner="desktop_react",
            tier="full_sandbox",
        ),
        memory_harness=MemoryHarnessConfig(id="none", kind="none", scope="none"),
        task=TaskConfig(
            id="datavoyager_europe_hp_gt_100_four_cyl_grounded",
            benchmark="domsteer",
            task_id="datavoyager.europe_hp_gt_100_four_cyl",
            extra={
                "canonical_task": "datavoyager_europe_hp_gt_100_four_cyl",
                "prompt_variant": "grounded_procedure",
                "task_family": "visual_analytics",
            },
        ),
        output_dir=Path("runs/example"),
    )

    assert trajectory_case_slug(plan) == (
        "visual_analytics__datavoyager_europe_hp_gt_100_four_cyl__grounded__"
        "claude_opus48_gui_toolcall__desktop_gui_toolcall__seed0__trial1"
    )


def test_gui_vs_cli_case_slug_uses_app_task_prompt_model_and_agent() -> None:
    assert gui_vs_cli_case_slug(
        app="libreoffice_calc",
        task_id="calc_3d_quarterly_consolidation",
        prompt_style="grounded",
        model="claude-opus-4-8",
        agent_id="agentlens_gui_toolcall_opus48",
    ) == (
        "libreoffice_calc__calc_3d_quarterly_consolidation__grounded__"
        "claude_opus_4_8__agentlens_gui_toolcall_opus48"
    )
