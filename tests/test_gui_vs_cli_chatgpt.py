from agentlens.models.gui_vs_cli_chatgpt import gui_vs_cli_actions_to_computer_actions


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
