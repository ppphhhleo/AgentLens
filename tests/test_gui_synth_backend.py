from __future__ import annotations

from agentlens.sandbox.gui_synth import GuiSynthSandbox


class _CommandResult:
    exit_code = 0
    stdout = "ok"
    stderr = ""


class _Commands:
    def run(self, command: str, timeout: int | None = None):
        assert command == "echo ready"
        assert timeout == 7
        return _CommandResult()


class _Files:
    def read(self, path: str, format: str = "text"):
        assert (path, format) == ("/tmp/example.txt", "text")
        return "contents"

    def write(self, path: str, content: str):
        assert (path, content) == ("/tmp/example.txt", "new contents")


class _Environment:
    commands = _Commands()
    files = _Files()

    @staticmethod
    def screenshot() -> bytes:
        return b"png"


def test_gui_synth_adapter_matches_desktop_operation_surface() -> None:
    sandbox = GuiSynthSandbox(_Environment())

    command = sandbox.shell("echo ready", timeout_sec=7)
    assert command.ok is True
    assert command.output == "ok"
    assert sandbox.read_file("/tmp/example.txt").output == "contents"
    assert sandbox.write_file("/tmp/example.txt", "new contents").ok is True
    assert sandbox.screenshot() == b"png"
