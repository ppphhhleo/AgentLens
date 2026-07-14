import pytest
from pydantic import ValidationError

from agentlens.harnesses.tool_gating import ToolSet
from agentlens.schemas import ToolHarnessConfig, ToolHarnessTier


def test_no_gui_tool_only_is_first_class_tier() -> None:
    harness = ToolHarnessConfig(
        id="nogui",
        runner="screenshot_react",
        tier="no_gui_tool_only",
        tools=[
            "web.openai_search",
            "code.run_python",
            "code.shell",
            "files.read",
            "files.write",
            "task.final_answer",
        ],
        extra={"input_modes": ["axtree"]},
    )

    assert harness.tier == ToolHarnessTier.NO_GUI_TOOL_ONLY


@pytest.mark.parametrize("tier", ["cli_only", "no_gui_tool_only"])
def test_cli_only_rejects_gui_tools(tier: str) -> None:
    with pytest.raises(ValidationError, match="must not expose browser\\.\\*"):
        ToolHarnessConfig(
            id="nogui",
            runner="screenshot_react",
            tier=tier,
            tools=["browser.screenshot", "code.shell", "task.final_answer"],
            extra={"input_modes": ["axtree"]},
        )


@pytest.mark.parametrize("tier", ["cli_only", "no_gui_tool_only"])
def test_cli_only_rejects_visual_input_modes(tier: str) -> None:
    with pytest.raises(ValidationError, match="visual input modes"):
        ToolHarnessConfig(
            id="nogui",
            runner="screenshot_react",
            tier=tier,
            tools=["code.shell", "task.final_answer"],
            extra={"input_modes": ["screenshot"]},
        )


@pytest.mark.parametrize("tier", ["cli_only", "no_gui_tool_only"])
def test_cli_only_requires_explicit_non_visual_input_modes(tier: str) -> None:
    with pytest.raises(ValidationError, match="extra\\.input_modes"):
        ToolHarnessConfig(
            id="nogui",
            runner="screenshot_react",
            tier=tier,
            tools=["code.shell", "task.final_answer"],
        )


def test_gui_only_accepts_individual_and_batched_direct_manipulation() -> None:
    harness = ToolHarnessConfig(
        id="gui",
        runner="desktop_react",
        tier="gui_only",
        tools=["computer.batch", "desktop.click", "desktop.type", "task.final_answer"],
    )
    toolset = ToolSet.from_harness(harness)

    assert harness.tier == ToolHarnessTier.GUI_ONLY
    assert toolset.is_allowed("desktop_click")
    assert toolset.is_allowed("desktop_keypress")


def test_gui_only_rejects_programmatic_tools() -> None:
    with pytest.raises(ValidationError, match="direct-manipulation desktop tools"):
        ToolHarnessConfig(
            id="gui",
            runner="desktop_react",
            tier="gui_only",
            tools=["computer.batch", "code.shell", "task.final_answer"],
        )


def test_full_sandbox_accepts_gui_batch_and_programmatic_tools() -> None:
    harness = ToolHarnessConfig(
        id="full",
        runner="desktop_react",
        tier="full_sandbox",
        tools=[
            "computer.batch",
            "desktop.click",
            "code.run_python",
            "code.shell",
            "files.read",
            "files.write",
            "task.final_answer",
        ],
    )

    assert harness.tier == ToolHarnessTier.FULL_SANDBOX


def test_computer_use_accepts_gui_batch_and_programmatic_tools() -> None:
    harness = ToolHarnessConfig(
        id="computer",
        runner="desktop_react",
        tier="computer_use",
        tools=["computer.batch", "desktop.click", "code.shell", "task.final_answer"],
    )

    assert harness.tier == ToolHarnessTier.COMPUTER_USE


def test_cli_only_is_canonical_non_visual_tier() -> None:
    harness = ToolHarnessConfig(
        id="cli",
        runner="screenshot_react",
        tier="cli_only",
        tools=["code.run_python", "code.shell", "files.read", "task.final_answer"],
        extra={"input_modes": ["axtree"]},
    )

    assert harness.tier == ToolHarnessTier.CLI_ONLY


def test_computer_batch_requires_desktop_runner() -> None:
    with pytest.raises(ValidationError, match="computer.batch requires"):
        ToolHarnessConfig(
            id="wrong-runner",
            runner="screenshot_react",
            tier="full_sandbox",
            tools=["computer.batch", "task.final_answer"],
        )
