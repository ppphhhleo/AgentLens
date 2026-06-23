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
