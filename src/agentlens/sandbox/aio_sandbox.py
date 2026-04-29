"""AIO Sandbox lifecycle wrapper.

One context manager spins a single sandbox container, exposes the bundled
Chromium via CDP for our screenshot ReAct loop, and exposes Jupyter / shell
/ filesystem methods for the new multi-tool actions.

Same container hosts both the agent (CDP) and any future human runner
(noVNC at /vnc/index.html) — see docs/multi-tool-and-sessions.md.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "ghcr.io/agent-infra/sandbox:latest"
DEFAULT_HOST_PORT = 8080
CONTAINER_PORT = 8080
HEALTH_TIMEOUT_SEC = 60
HEALTH_POLL_INTERVAL_SEC = 1.0


@dataclass
class CodeResult:
    """Outcome of a Jupyter / shell / file call."""

    ok: bool
    output: str
    error: str = ""
    extra: dict[str, Any] | None = None


def _have_docker() -> bool:
    return shutil.which("docker") is not None


def ensure_image(image: str = DEFAULT_IMAGE) -> None:
    """Pull the AIO Sandbox image if it's not present locally."""
    if not _have_docker():
        raise RuntimeError("docker is not on PATH; install Docker Desktop and start it")
    have = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
    )
    if have.returncode == 0:
        return
    logger.info("pulling AIO Sandbox image %s (one-time, ~3-5 GB)...", image)
    pull = subprocess.run(["docker", "pull", image])
    if pull.returncode != 0:
        raise RuntimeError(f"failed to pull {image}")


class AIOSandboxSession:
    """Context manager for one AIO Sandbox container.

    Usage:
        with AIOSandboxSession() as session:
            cdp_url = session.cdp_url
            session.run_python("print(2+2)")
            session.shell("ls")
            session.write_file("/tmp/x", "hi")
            text = session.read_file("/tmp/x")

    On entry: starts the container, waits until the REST API is healthy,
    creates an `agent_sandbox.Sandbox` SDK client, and stashes the CDP
    URL of the bundled Chromium.

    On exit: stops + removes the container.
    """

    def __init__(
        self,
        *,
        image: str = DEFAULT_IMAGE,
        host_port: int = DEFAULT_HOST_PORT,
        container_name: str | None = None,
        env: dict[str, str] | None = None,
        autopull: bool = True,
    ) -> None:
        self.image = image
        self.host_port = host_port
        self.container_name = container_name or f"agentlens-sandbox-{int(time.time() * 1000)}"
        self.env = env or {}
        self.autopull = autopull
        self.base_url = f"http://localhost:{host_port}"
        self.client = None  # agent_sandbox.Sandbox; lazily set in __enter__
        self.cdp_url: str | None = None
        self.home_dir: str | None = None
        self._started = False

    # ---- lifecycle ----------------------------------------------------

    def __enter__(self) -> AIOSandboxSession:
        if self.autopull:
            ensure_image(self.image)
        self._docker_run()
        try:
            self._wait_until_healthy()
            self._open_client()
        except Exception:
            self._docker_stop()
            raise
        self._started = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._started:
            self._docker_stop()

    def _docker_run(self) -> None:
        cmd = [
            "docker", "run", "-d",
            "--rm",
            "--name", self.container_name,
            "-p", f"{self.host_port}:{CONTAINER_PORT}",
        ]
        for k, v in self.env.items():
            cmd.extend(["-e", f"{k}={v}"])
        cmd.append(self.image)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"docker run failed: {result.stderr.strip() or result.stdout.strip()}"
            )

    def _docker_stop(self) -> None:
        subprocess.run(
            ["docker", "stop", self.container_name],
            capture_output=True,
            timeout=30,
        )

    def _wait_until_healthy(self) -> None:
        url = f"{self.base_url}/v1/sandbox"
        deadline = time.time() + HEALTH_TIMEOUT_SEC
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if 200 <= resp.status < 400:
                        return
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError) as e:
                last_err = e
            except Exception as e:  # noqa: BLE001 - container booting; keep polling
                last_err = e
            time.sleep(HEALTH_POLL_INTERVAL_SEC)
        raise RuntimeError(
            f"AIO Sandbox container {self.container_name!r} did not become healthy "
            f"within {HEALTH_TIMEOUT_SEC}s: last error {last_err!r}"
        )

    def _open_client(self) -> None:
        try:
            from agent_sandbox import Sandbox
        except ImportError as exc:
            raise RuntimeError(
                "agent_sandbox SDK is not installed; run `pip install agent-sandbox`"
            ) from exc
        self.client = Sandbox(base_url=self.base_url)
        # Cache home dir + CDP url once
        try:
            ctx = self.client.sandbox.get_context()
            # SandboxResponse exposes home_dir at the top level; .data is a
            # human-readable summary string, not a struct.
            self.home_dir = (
                getattr(ctx, "home_dir", None)
                or getattr(getattr(ctx, "data", None), "home_dir", None)
                or "/home/gem"
            )
        except Exception:  # noqa: BLE001 - non-fatal; default home dir
            self.home_dir = "/home/gem"
        try:
            info = self.client.browser.get_info()
            self.cdp_url = getattr(getattr(info, "data", info), "cdp_url", None)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"could not fetch CDP url from sandbox: {exc!r}"
            ) from exc
        if not self.cdp_url:
            raise RuntimeError("AIO Sandbox returned no CDP url")

    # ---- multi-tool methods -------------------------------------------
    # All methods return CodeResult; never raise on tool errors so the
    # agent can see + recover.

    def run_python(self, code: str) -> CodeResult:
        try:
            r = self.client.jupyter.execute_code(code=code)
        except Exception as exc:  # noqa: BLE001
            return CodeResult(ok=False, output="", error=f"{type(exc).__name__}: {exc}")
        data = getattr(r, "data", r)
        outputs = getattr(data, "outputs", []) or []
        stdout, errtext = _format_jupyter_outputs(outputs)
        status = getattr(data, "status", "") or ""
        ok = (status == "ok") and not errtext
        return CodeResult(
            ok=ok,
            output=stdout,
            error=errtext,
            extra={
                "kernel_status": status,
                "execution_count": getattr(data, "execution_count", None),
                "session_id": getattr(data, "session_id", None),
            },
        )

    def shell(self, cmd: str, timeout_sec: int = 30) -> CodeResult:
        try:
            r = self.client.shell.exec_command(command=cmd, timeout=timeout_sec)
        except Exception as exc:  # noqa: BLE001
            return CodeResult(ok=False, output="", error=f"{type(exc).__name__}: {exc}")
        data = getattr(r, "data", r)
        output = getattr(data, "output", "") or ""
        exit_code = getattr(data, "exit_code", None)
        err = "" if exit_code == 0 else (getattr(data, "stderr", "") or "")
        return CodeResult(
            ok=(exit_code == 0),
            output=str(output),
            error=str(err),
            extra={"exit_code": exit_code, "session_id": getattr(data, "session_id", None)},
        )

    def read_file(self, path: str) -> CodeResult:
        try:
            r = self.client.file.read_file(file=path)
        except Exception as exc:  # noqa: BLE001
            return CodeResult(ok=False, output="", error=f"{type(exc).__name__}: {exc}")
        data = getattr(r, "data", r)
        content = (
            getattr(data, "content", None)
            or getattr(data, "text", None)
            or getattr(data, "file_content", None)
            or ""
        )
        return CodeResult(ok=True, output=str(content))

    def write_file(self, path: str, text: str) -> CodeResult:
        try:
            self.client.file.write_file(file=path, content=text)
        except Exception as exc:  # noqa: BLE001
            return CodeResult(ok=False, output="", error=f"{type(exc).__name__}: {exc}")
        return CodeResult(ok=True, output=f"wrote {len(text)} chars to {path}")


def _format_jupyter_outputs(outputs) -> tuple[str, str]:
    """Walk a JupyterOutput list, return (stdout_concat, error_text)."""
    stdout_parts: list[str] = []
    error_parts: list[str] = []
    for o in outputs:
        ot = getattr(o, "output_type", "") or ""
        if ot == "stream":
            text = getattr(o, "text", "") or ""
            if getattr(o, "name", "") == "stderr":
                error_parts.append(text)
            else:
                stdout_parts.append(text)
        elif ot in ("execute_result", "display_data"):
            data = getattr(o, "data", {}) or {}
            if isinstance(data, dict) and "text/plain" in data:
                stdout_parts.append(data["text/plain"])
        elif ot == "error":
            ename = getattr(o, "ename", "") or ""
            evalue = getattr(o, "evalue", "") or ""
            tb = getattr(o, "traceback", []) or []
            error_parts.append(f"{ename}: {evalue}\n" + "\n".join(tb))
    return ("".join(stdout_parts), "".join(error_parts))


def _safe_to_dict(obj: Any) -> dict | None:
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if isinstance(obj, dict):
            return obj
    except Exception:  # noqa: BLE001
        pass
    return None
