from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from agentlens.actions import ComputerAction
from agentlens.schemas import TrajectoryEvent, TrajectoryEventType

GUI_LAUNCH_COMMANDS = {
    "blender",
    "weka",
}


def capture_desktop_screenshot_event(
    sandbox,
    screenshot_dir: Path,
    step_index: int,
    goal: str | None,
    *,
    name_suffix: str = "",
) -> TrajectoryEvent:
    """Capture the virtual desktop from inside the sandbox container."""
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{name_suffix.lstrip('_')}" if name_suffix else ""
    host_path = screenshot_dir / f"step_{step_index:03d}{suffix}.png"
    remote_path = f"/tmp/agentlens_desktop_step_{step_index:03d}{suffix}.png"
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
            "screenshot_source": "virtual_desktop",
            "coordinate_frame": "desktop_screen",
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
    if action.type == "desktop_launch_app":
        result = _launch_desktop_app(sandbox, action.app or "")
        return result.output, result.error
    if action.type == "desktop_shell":
        cmd = action.cmd or ""
        safe_cmd = _detached_gui_command(cmd)
        if safe_cmd:
            result = sandbox.shell(safe_cmd, timeout_sec=5)
            output = result.output
            if result.ok:
                output = (
                    output.rstrip()
                    + f"\n[agentlens] Detached foreground GUI command: {cmd!r}\n"
                ).lstrip()
            return output, result.error
        result = sandbox.shell(cmd, timeout_sec=60)
        return result.output, result.error
    if action.type == "desktop_click":
        button = {"left": 1, "middle": 2, "right": 3}.get(action.button, 1)
        cmd = f"xdotool mousemove {float(action.x or 0):.0f} {float(action.y or 0):.0f} click {button}"
        result = sandbox.shell(cmd, timeout_sec=10)
        return result.output, _desktop_tool_error(result, "xdotool")
    if action.type == "desktop_double_click":
        button = {"left": 1, "middle": 2, "right": 3}.get(action.button, 1)
        cmd = (
            f"xdotool mousemove {float(action.x or 0):.0f} {float(action.y or 0):.0f} "
            f"click --repeat 2 --delay 120 {button}"
        )
        result = sandbox.shell(cmd, timeout_sec=10)
        return result.output, _desktop_tool_error(result, "xdotool")
    if action.type == "desktop_move":
        cmd = f"xdotool mousemove {float(action.x or 0):.0f} {float(action.y or 0):.0f}"
        result = sandbox.shell(cmd, timeout_sec=10)
        return result.output, _desktop_tool_error(result, "xdotool")
    if action.type == "desktop_scroll":
        cmd = _scroll_command(action)
        result = sandbox.shell(cmd, timeout_sec=10)
        return result.output, _desktop_tool_error(result, "xdotool")
    if action.type == "desktop_drag":
        cmd = _drag_command(action)
        result = sandbox.shell(cmd, timeout_sec=20)
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
    if action.type == "desktop_double_click":
        return f"desktop_double_click x={action.x} y={action.y} button={action.button}"
    if action.type == "desktop_move":
        return f"desktop_move x={action.x} y={action.y}"
    if action.type == "desktop_scroll":
        return f"desktop_scroll x={action.x} y={action.y} scroll_x={action.scroll_x} scroll_y={action.scroll_y}"
    if action.type == "desktop_drag":
        return f"desktop_drag path={[(p.x, p.y) for p in action.path]}"
    if action.type == "desktop_type":
        return f"desktop_type text={action.text!r}"
    if action.type == "desktop_keypress":
        return f"desktop_keypress keys={action.keys}"
    if action.type == "desktop_launch_app":
        return f"desktop_launch_app app={action.app!r}"
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


def _scroll_command(action: ComputerAction) -> str:
    parts: list[str] = []
    if action.x is not None and action.y is not None:
        parts.append(f"mousemove {float(action.x):.0f} {float(action.y):.0f}")
    parts.extend(_wheel_clicks(action.scroll_y, negative_button=4, positive_button=5))
    parts.extend(_wheel_clicks(action.scroll_x, negative_button=6, positive_button=7))
    if not parts or (len(parts) == 1 and parts[0].startswith("mousemove")):
        parts.append("sleep 0.1")
    return "xdotool " + " ".join(parts)


def _wheel_clicks(delta: float, *, negative_button: int, positive_button: int) -> list[str]:
    if not delta:
        return []
    button = positive_button if delta > 0 else negative_button
    repeats = max(1, min(10, int(abs(delta) / 100) or 1))
    return [f"click {button}" for _ in range(repeats)]


def _drag_command(action: ComputerAction) -> str:
    first = action.path[0]
    parts = [f"mousemove {first.x:.0f} {first.y:.0f}", "mousedown 1"]
    for point in action.path[1:]:
        parts.append(f"mousemove {point.x:.0f} {point.y:.0f}")
    parts.append("mouseup 1")
    return "xdotool " + " ".join(parts)


def _launch_desktop_app(sandbox, app: str):
    command = _detached_gui_command(app) or _detached_command(app)
    return sandbox.shell(command, timeout_sec=5)


def _detached_gui_command(cmd: str) -> str | None:
    stripped = cmd.strip()
    if not stripped:
        return None
    try:
        parts = shlex.split(stripped)
    except ValueError:
        return None
    if not parts:
        return None
    if parts[0] in GUI_LAUNCH_COMMANDS:
        return _detached_command(stripped)
    if (
        parts[:2] == ["java", "-jar"]
        and len(parts) >= 3
        and parts[2].endswith("/weka.jar")
    ):
        return _detached_command(stripped)
    return None


def _detached_command(cmd: str) -> str:
    quoted_cmd = shlex.quote(cmd)
    log_path = shlex.quote(f"/tmp/agentlens_launch_{_safe_launch_name(cmd)}.log")
    return f"nohup bash -lc {quoted_cmd} >{log_path} 2>&1 & echo $!"


def _safe_launch_name(cmd: str) -> str:
    try:
        first = shlex.split(cmd)[0]
    except (IndexError, ValueError):
        first = "app"
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in first) or "app"


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
