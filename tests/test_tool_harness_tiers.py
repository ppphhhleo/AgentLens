import pytest
from pydantic import ValidationError

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


def test_no_gui_tool_only_rejects_gui_tools() -> None:
    with pytest.raises(ValidationError, match="browser\\.\\* or desktop\\.\\*"):
        ToolHarnessConfig(
            id="nogui",
            runner="screenshot_react",
            tier="no_gui_tool_only",
            tools=["browser.screenshot", "code.shell", "task.final_answer"],
            extra={"input_modes": ["axtree"]},
        )


def test_no_gui_tool_only_rejects_visual_input_modes() -> None:
    with pytest.raises(ValidationError, match="visual input modes"):
        ToolHarnessConfig(
            id="nogui",
            runner="screenshot_react",
            tier="no_gui_tool_only",
            tools=["code.shell", "task.final_answer"],
            extra={"input_modes": ["screenshot"]},
        )


def test_no_gui_tool_only_requires_explicit_non_visual_input_modes() -> None:
    with pytest.raises(ValidationError, match="extra\\.input_modes"):
        ToolHarnessConfig(
            id="nogui",
            runner="screenshot_react",
            tier="no_gui_tool_only",
            tools=["code.shell", "task.final_answer"],
        )
