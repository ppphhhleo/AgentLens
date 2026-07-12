import sys
from pathlib import Path

from agentlens.models.gui_vs_cli_chatgpt import (
    GUI_SCREEN_ONLY_POLICY,
    GuiVsCliChatGPTModel,
    GuiVsCliClaudeModel,
    GuiVsCliGeminiModel,
    gui_vs_cli_actions_to_computer_actions,
)
from agentlens.schemas import ModelConfig


def test_gui_vs_cli_pyautogui_actions_are_preserved() -> None:
    actions = gui_vs_cli_actions_to_computer_actions(
        ["import pyautogui\npyautogui.click(10, 20)"],
        thought="click the sort control",
    )

    assert len(actions) == 1
    assert actions[0].type == "desktop_pyautogui"
    assert "pyautogui.click" in (actions[0].code or "")


def test_gui_vs_cli_done_becomes_final_answer() -> None:
    actions = gui_vs_cli_actions_to_computer_actions(["DONE"], thought="Mazda GLC")

    assert len(actions) == 1
    assert actions[0].type == "final_answer"
    assert actions[0].answer == "Mazda GLC"


def test_gui_vs_cli_prompt_uses_gui_screen_only_policy_by_default() -> None:
    model = GuiVsCliChatGPTModel(
        ModelConfig(id="m", provider="openai", name="gpt-5.4", extra={})
    )

    prompt = model._build_task_prompt("Finish the task")

    assert GUI_SCREEN_ONLY_POLICY in prompt
    assert "<USER_TASK>\nFinish the task\n</USER_TASK>" in prompt


def test_gui_vs_cli_backend_names_are_distinct() -> None:
    assert GuiVsCliChatGPTModel.backend_name == "gui_vs_cli_chatgpt"
    assert GuiVsCliClaudeModel.backend_name == "gui_vs_cli_claude"
    assert GuiVsCliGeminiModel.backend_name == "gui_vs_cli_gemini"


def test_gui_vs_cli_claude_ignores_text_on_drag_action() -> None:
    third_party_root = Path(__file__).resolve().parents[1] / "third_party" / "gui-vs-cli"
    sys.path.insert(0, str(third_party_root))
    try:
        from agents.claude_agent import ClaudeAgent

        agent = ClaudeAgent(model="dummy", screen_size=(1920, 1080))
        code = agent._parse_actions_from_tool_call(
            {
                "input": {
                    "action": "left_click_drag",
                    "coordinate": [200, 100],
                    "start_coordinate": [100, 50],
                    "text": "unexpected provider annotation",
                }
            }
        )

        assert "pyautogui.moveTo(150, 75" in code
        assert "pyautogui.dragTo(300, 150" in code
    finally:
        try:
            sys.path.remove(str(third_party_root))
        except ValueError:
            pass


def test_gui_vs_cli_claude_tolerates_cursor_position_action() -> None:
    third_party_root = Path(__file__).resolve().parents[1] / "third_party" / "gui-vs-cli"
    sys.path.insert(0, str(third_party_root))
    try:
        from agents.claude_agent import ClaudeAgent

        agent = ClaudeAgent(model="dummy", screen_size=(1920, 1080))
        code = agent._parse_actions_from_tool_call(
            {"input": {"action": "cursor_position"}}
        )

        assert code == "WAIT"
    finally:
        try:
            sys.path.remove(str(third_party_root))
        except ValueError:
            pass
