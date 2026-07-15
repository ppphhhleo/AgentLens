"""Compatibility layer for GUI-vs-CLI desktop environments.

The GUI-vs-CLI project provisions a desktop through ``computer_env`` while
AgentLens desktop agents expect a small ``shell/read/write/screenshot``
surface.  This module adapts that environment without changing the agent loop,
which keeps agent type as the experimental variable rather than the desktop
runtime.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any

from agentlens.sandbox.aio_sandbox import CodeResult


class GuiSynthSandbox:
    """Expose a GUI-vs-CLI environment through AgentLens desktop operations."""

    def __init__(self, environment: Any) -> None:
        self._environment = environment

    def shell(self, command: str, timeout_sec: int = 30) -> CodeResult:
        try:
            result = self._environment.commands.run(command, timeout=timeout_sec)
            return CodeResult(
                ok=getattr(result, "exit_code", 0) == 0,
                output=str(getattr(result, "stdout", "") or ""),
                error=str(getattr(result, "stderr", "") or ""),
                extra={"exit_code": getattr(result, "exit_code", None)},
            )
        except Exception as exc:  # GUI-vs-CLI raises on non-zero command exits.
            return CodeResult(
                ok=False,
                output=str(getattr(exc, "stdout", "") or ""),
                error=str(getattr(exc, "stderr", "") or str(exc)),
                extra={"exception": type(exc).__name__},
            )

    def run_python(self, code: str) -> CodeResult:
        return self.shell(f"python3 -c {shlex.quote(code)}", timeout_sec=60)

    def read_file(self, path: str) -> CodeResult:
        try:
            content = self._environment.files.read(path, format="text")
            return CodeResult(ok=True, output=str(content))
        except Exception as exc:
            return CodeResult(ok=False, output="", error=str(exc))

    def write_file(self, path: str, text: str) -> CodeResult:
        try:
            self._environment.files.write(path, text)
            return CodeResult(ok=True, output=f"wrote {len(text)} chars to {path}")
        except Exception as exc:
            return CodeResult(ok=False, output="", error=str(exc))

    def screenshot(self) -> bytes:
        return self._environment.screenshot()


class GuiSynthSandboxSession:
    """Create one fresh GUI-vs-CLI desktop environment for an AgentLens run."""

    def __init__(
        self,
        *,
        app_name: str,
        task: dict[str, Any] | None,
        sandbox_timeout: int,
        run_id: str,
        docker_image: str,
        docker_platform: str,
        docker_shm_size: str,
        docker_ready_timeout: int,
    ) -> None:
        self.app_name = app_name
        self.task = task
        self.sandbox_timeout = sandbox_timeout
        self.run_id = run_id
        self.docker_image = docker_image
        self.docker_platform = docker_platform
        self.docker_shm_size = docker_shm_size
        self.docker_ready_timeout = docker_ready_timeout
        self._session: Any = None
        self._sandbox: GuiSynthSandbox | None = None

    def __enter__(self) -> GuiSynthSandbox:
        repo_root = Path(__file__).resolve().parents[3]
        third_party_root = repo_root / "third_party" / "gui-vs-cli"
        if not third_party_root.exists():
            raise RuntimeError(
                "gui_synth backend requires third_party/gui-vs-cli; clone it before running."
            )
        root = str(third_party_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        from evaluation.runtime.sandbox_session import setup_sandbox_session

        self._session = setup_sandbox_session(
            self.app_name,
            self.task,
            sandbox_timeout=self.sandbox_timeout,
            run_id=self.run_id,
            run_mode="gui",
            env_backend="docker",
            docker_image=self.docker_image,
            docker_platform=self.docker_platform,
            docker_shm_size=self.docker_shm_size,
            docker_ready_timeout=self.docker_ready_timeout,
        )
        self._sandbox = GuiSynthSandbox(self._session.sandbox)
        return self._sandbox

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._session is not None:
            self._session.sandbox.kill()
