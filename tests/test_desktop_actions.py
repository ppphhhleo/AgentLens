from agentlens.actions import ComputerAction
from agentlens.harnesses.desktop_actions import _detached_gui_command, format_desktop_action


def test_detached_gui_command_detects_known_gui_apps() -> None:
    assert _detached_gui_command("blender") is not None
    assert _detached_gui_command("weka") is not None
    assert _detached_gui_command("java -jar /usr/share/java/weka.jar") is not None


def test_detached_gui_command_leaves_regular_shell_commands_alone() -> None:
    assert _detached_gui_command("ls /workspace/output") is None
    assert _detached_gui_command("python script.py") is None


def test_desktop_launch_action_formats() -> None:
    action = ComputerAction(type="desktop_launch_app", app="blender")
    assert format_desktop_action(action) == "desktop_launch_app app='blender'"


def test_desktop_native_gui_actions_format() -> None:
    drag = ComputerAction(
        type="desktop_drag",
        path=[{"x": 10, "y": 20}, {"x": 50, "y": 60}],
    )
    scroll = ComputerAction(type="desktop_scroll", x=100, y=200, scroll_y=300)

    assert format_desktop_action(drag) == "desktop_drag path=[(10.0, 20.0), (50.0, 60.0)]"
    assert format_desktop_action(scroll) == "desktop_scroll x=100.0 y=200.0 scroll_x=0 scroll_y=300.0"


def test_desktop_pyautogui_action_formats() -> None:
    action = ComputerAction(type="desktop_pyautogui", code="import pyautogui\npyautogui.click(10, 20)")

    assert format_desktop_action(action) == (
        "desktop_pyautogui code='import pyautogui pyautogui.click(10, 20)'"
    )
