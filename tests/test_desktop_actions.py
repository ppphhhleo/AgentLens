from types import SimpleNamespace

from agentlens.actions import ComputerAction
from agentlens.harnesses.desktop_actions import (
    _desktop_tool_error,
    _detached_gui_command,
    _pyautogui_command,
    format_desktop_action,
    execute_desktop_action,
)


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


def test_pyautogui_command_prefers_image_managed_interpreter() -> None:
    command = _pyautogui_command("pyautogui.click(10, 20)")

    assert "AGENTLENS_PYAUTOGUI_PYTHON" in command
    assert "/opt/agentlens-pyautogui/bin/python" in command
    assert 'runuser -u gem' in command


def test_desktop_tool_error_detects_traceback_even_when_transport_reports_ok() -> None:
    result = SimpleNamespace(
        ok=True,
        error="",
        output="Traceback (most recent call last):\nModuleNotFoundError: No module named 'pyautogui'",
    )

    assert _desktop_tool_error(result, "pyautogui") == (
        "pyautogui is not installed in the desktop sandbox image"
    )


def test_desktop_executor_supports_full_sandbox_programmatic_tools() -> None:
    class Sandbox:
        def run_python(self, code):
            return SimpleNamespace(output=f"python:{code}", error="")

        def shell(self, cmd, timeout_sec=30):
            return SimpleNamespace(output=f"shell:{cmd}", error="")

        def read_file(self, path):
            return SimpleNamespace(output=f"read:{path}", error="")

        def write_file(self, path, text):
            return SimpleNamespace(output=f"write:{path}:{text}", error="")

    sandbox = Sandbox()
    cases = [
        (ComputerAction(type="run_python", code="print(1)"), "python:print(1)"),
        (ComputerAction(type="shell", cmd="pwd"), "shell:pwd"),
        (ComputerAction(type="read_file", file_path="/tmp/a"), "read:/tmp/a"),
        (
            ComputerAction(type="write_file", file_path="/tmp/a", content="x"),
            "write:/tmp/a:x",
        ),
    ]

    for action, expected in cases:
        output, error = execute_desktop_action(sandbox, action)
        assert output == expected
        assert error == ""
