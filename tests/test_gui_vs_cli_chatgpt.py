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
