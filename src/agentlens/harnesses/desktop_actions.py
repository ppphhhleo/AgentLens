from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from agentlens.actions import ComputerAction
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType


def capture_desktop_screenshot_event(
    sandbox,
    screenshot_dir: Path,
    step_index: int,
    goal: str | None,
) -> TrajectoryEvent:
    """Capture the virtual desktop from inside the sandbox container."""
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    host_path = screenshot_dir / f"step_{step_index:03d}.png"
    remote_path = f"/tmp/agentlens_desktop_step_{step_index:03d}.png"
    result = sandbox.shell(_screenshot_command(remote_path), timeout_sec=15)
    if result.ok and _docker_cp_from_container(sandbox, remote_path, host_path):
        artifact_paths = [host_path]
        error = ""
    else:
        artifact_paths = []
        error = result.error or result.output or "desktop screenshot capture failed"
    return TrajectoryEvent(
        event_type=TrajectoryEventType.SCREENSHOT,
        step_index=step_index,
        data={
            "goal": goal,
            "kind": "desktop",
            "remote_path": remote_path,
            "error": error,
        },
        artifact_paths=artifact_paths,
    )


def execute_desktop_action(sandbox, action: ComputerAction) -> tuple[str, str]:
    """Execute one desktop action. Returns (output, error)."""
    if action.type == "desktop_screenshot":
        return "", ""
    if action.type == "desktop_wait":
        ms = action.ms or 1000
        result = sandbox.shell(f"sleep {max(ms, 0) / 1000:.3f}", timeout_sec=max(2, int(ms / 1000) + 2))
        return result.output, result.error
    if action.type == "desktop_shell":
        result = sandbox.shell(action.cmd or "", timeout_sec=60)
        return result.output, result.error
    if action.type == "desktop_click":
        button = {"left": 1, "middle": 2, "right": 3}.get(action.button, 1)
        cmd = f"xdotool mousemove {float(action.x or 0):.0f} {float(action.y or 0):.0f} click {button}"
        result = sandbox.shell(cmd, timeout_sec=10)
        return result.output, _desktop_tool_error(result, "xdotool")
    if action.type == "desktop_type":
        cmd = f"xdotool type --clearmodifiers -- {shlex.quote(action.text or '')}"
        result = sandbox.shell(cmd, timeout_sec=20)
        return result.output, _desktop_tool_error(result, "xdotool")
    if action.type == "desktop_keypress":
        keys = " ".join(shlex.quote(_xdotool_key(key)) for key in action.keys)
        result = sandbox.shell(f"xdotool key --clearmodifiers {keys}", timeout_sec=10)
        return result.output, _desktop_tool_error(result, "xdotool")
    return "", f"unsupported desktop action: {action.type}"


def format_desktop_action(action: ComputerAction) -> str:
    if action.type == "desktop_click":
        return f"desktop_click x={action.x} y={action.y} button={action.button}"
    if action.type == "desktop_type":
        return f"desktop_type text={action.text!r}"
    if action.type == "desktop_keypress":
        return f"desktop_keypress keys={action.keys}"
    if action.type == "desktop_shell":
        return f"desktop_shell cmd={action.cmd!r}"
    if action.type == "desktop_wait":
        return f"desktop_wait ms={action.ms or 1000}"
    if action.type == "desktop_screenshot":
        return "desktop_screenshot"
    return action.type


def _screenshot_command(remote_path: str) -> str:
    quoted = shlex.quote(remote_path)
    return (
        "set -e; "
        f"mkdir -p {shlex.quote(str(Path(remote_path).parent))}; "
        "if command -v gnome-screenshot >/dev/null 2>&1; then "
        f"gnome-screenshot -f {quoted}; "
        "elif command -v scrot >/dev/null 2>&1; then "
        f"scrot {quoted}; "
        "elif command -v import >/dev/null 2>&1; then "
        f"import -window root {quoted}; "
        "elif command -v xwd >/dev/null 2>&1 && command -v convert >/dev/null 2>&1; then "
        f"xwd -root -silent | convert xwd:- {quoted}; "
        "else "
        "echo 'no desktop screenshot tool found: install gnome-screenshot, scrot, imagemagick import, or xwd+convert' >&2; "
        "exit 127; "
        "fi"
    )


def _docker_cp_from_container(sandbox, remote_path: str, host_path: Path) -> bool:
    container_name = getattr(sandbox, "container_name", None)
    if not container_name:
        return False
    try:
        result = subprocess.run(
            ["docker", "cp", f"{container_name}:{remote_path}", str(host_path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return False
    return result.returncode == 0 and host_path.exists()


def _desktop_tool_error(result, tool_name: str) -> str:
    if result.ok:
        return ""
    err = result.error or result.output
    if "not found" in err or "command not found" in err:
        return f"{tool_name} is not installed in the desktop sandbox image"
    return err


def _xdotool_key(key: str) -> str:
    mapping = {
        "enter": "Return",
        "return": "Return",
        "escape": "Escape",
        "esc": "Escape",
        "ctrl": "ctrl",
        "control": "ctrl",
        "cmd": "Super",
        "command": "Super",
        "super": "Super",
        "alt": "alt",
        "shift": "shift",
        "space": "space",
        "tab": "Tab",
    }
    return mapping.get(key.casefold(), key)
