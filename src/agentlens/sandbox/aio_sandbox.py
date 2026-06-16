"""AIO Sandbox lifecycle wrapper.

One context manager spins a single sandbox container, exposes the bundled
Chromium via CDP for our screenshot ReAct loop, and exposes Jupyter / shell
/ filesystem methods for the new multi-tool actions.

Same container hosts both the agent (CDP) and any future human runner
(noVNC at /vnc/index.html) — see docs/multi-tool-and-sessions.md.
"""
from __future__ import annotations

import logging
import json
import shlex
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
HEALTH_TIMEOUT_SEC = 180
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
        shm_size: str | None = "2g",
        cap_add: list[str] | None = None,
        security_opt: list[str] | None = None,
        watch_paths: list[str] | None = None,
        autopull: bool = True,
        reuse_existing: bool = False,
        keep_open_seconds: int = 0,
    ) -> None:
        self.image = image
        self.host_port = host_port
        self.container_name = container_name or f"agentlens-sandbox-{int(time.time() * 1000)}"
        self.env = env or {}
        self.shm_size = shm_size
        # Chromium inside the AIO image can crash before opening CDP on EC2's
        # default Docker seccomp/capability profile. Keep these runtime knobs
        # configurable, but default to the settings validated on AWS.
        self.cap_add = cap_add if cap_add is not None else ["SYS_ADMIN"]
        self.security_opt = (
            security_opt if security_opt is not None else ["seccomp=unconfined"]
        )
        self.watch_paths = watch_paths
        self.autopull = autopull
        # If an AIO Sandbox is already healthy at host_port, attach to it
        # instead of starting our own container. Useful when the user has
        # a long-lived sandbox open for VNC inspection.
        self.reuse_existing = reuse_existing
        # If > 0, sleep this many seconds after the run completes BEFORE
        # docker-stop, so the user has time to open
        # http://localhost:<port>/vnc/index.html and inspect final state.
        self.keep_open_seconds = keep_open_seconds
        # Prefer IPv4 loopback. Some Docker Desktop/macOS combinations make
        # localhost alternate between IPv4/IPv6 during container boot, which
        # can surface as transient 502/timeout failures from the sandbox nginx.
        self.base_url = f"http://127.0.0.1:{host_port}"
        self.client = None  # agent_sandbox.Sandbox; lazily set in __enter__
        self.cdp_url: str | None = None
        self.home_dir: str | None = None
        self._started = False
        self._we_started_it = False  # only stop containers we ourselves spawned

    # ---- lifecycle ----------------------------------------------------

    def __enter__(self) -> AIOSandboxSession:
        if self.reuse_existing and self._is_healthy_now():
            # Attach to whatever's already running; don't pull/run our own.
            self._we_started_it = False
        else:
            if self.autopull:
                ensure_image(self.image)
            self._docker_run()
            self._we_started_it = True
        try:
            self._wait_until_healthy()
            self._open_client()
        except Exception:
            if self._we_started_it:
                self._docker_stop()
            raise
        self._started = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._started:
            return
        if self.keep_open_seconds > 0 and self._we_started_it:
            logger.info(
                "AIO Sandbox %s keeping open for %ds before stop "
                "(open http://localhost:%d/vnc/index.html?autoconnect=true to inspect)",
                self.container_name, self.keep_open_seconds, self.host_port,
            )
            time.sleep(self.keep_open_seconds)
        if self._we_started_it:
            self._docker_stop()

    def _is_healthy_now(self) -> bool:
        url = f"{self.base_url}/v1/sandbox"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return 200 <= resp.status < 400
        except Exception:  # noqa: BLE001
            return False

    def _docker_run(self) -> None:
        cmd = [
            "docker", "run", "-d",
            "--rm",
            "--name", self.container_name,
            "-p", f"{self.host_port}:{CONTAINER_PORT}",
        ]
        if self.shm_size:
            cmd.extend(["--shm-size", self.shm_size])
        for value in self.cap_add:
            cmd.extend(["--cap-add", value])
        for value in self.security_opt:
            cmd.extend(["--security-opt", value])
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
                with urllib.request.urlopen(url, timeout=10) as resp:
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
        last_exc: Exception | None = None
        for _ in range(30):
            try:
                info = self.client.browser.get_info()
                self.cdp_url = getattr(getattr(info, "data", info), "cdp_url", None)
                if self.cdp_url:
                    break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
            self.cdp_url = self._browser_cdp_url_http()
            if self.cdp_url:
                break
            time.sleep(1)
        if not self.cdp_url:
            raise RuntimeError(f"AIO Sandbox returned no CDP url; last error={last_exc!r}")

    def _browser_cdp_url_http(self) -> str | None:
        """Direct HTTP fallback for browser info.

        The generated SDK can raise when sandbox nginx briefly returns a
        non-JSON 502 during browser boot. The raw endpoint usually stabilizes a
        second later; this helper keeps startup tolerant without changing the
        public session API.
        """
        try:
            with urllib.request.urlopen(f"{self.base_url}/v1/browser/info", timeout=10) as resp:
                if not (200 <= resp.status < 400):
                    return None
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return None
        cdp_url = data.get("cdp_url")
        return str(cdp_url) if cdp_url else None

    # ---- multi-tool methods -------------------------------------------
    # All methods return CodeResult; never raise on tool errors so the
    # agent can see + recover.

    def run_python(self, code: str) -> CodeResult:
        r, exc = self._call_with_retries(lambda: self.client.jupyter.execute_code(code=code))
        if exc is not None:
            return self._docker_run_python(code, sdk_error=exc)
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
        r, exc = self._call_with_retries(
            lambda: self.client.shell.exec_command(command=cmd, timeout=timeout_sec)
        )
        if exc is not None:
            return self._docker_shell(cmd, timeout_sec=timeout_sec, sdk_error=exc)
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
        r, exc = self._call_with_retries(lambda: self.client.file.read_file(file=path))
        if exc is not None:
            return self._docker_read_file(path, sdk_error=exc)
        data = getattr(r, "data", r)
        content = (
            getattr(data, "content", None)
            or getattr(data, "text", None)
            or getattr(data, "file_content", None)
            or ""
        )
        return CodeResult(ok=True, output=str(content))

    def write_file(self, path: str, text: str) -> CodeResult:
        _, exc = self._call_with_retries(
            lambda: self.client.file.write_file(file=path, content=text)
        )
        if exc is not None:
            return self._docker_write_file(path, text, sdk_error=exc)
        return CodeResult(ok=True, output=f"wrote {len(text)} chars to {path}")

    def _call_with_retries(self, fn, *, attempts: int = 3, delay_sec: float = 0.5):
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                return fn(), None
            except Exception as exc:  # noqa: BLE001 - sandbox services boot independently
                last_exc = exc
                time.sleep(delay_sec)
        return None, last_exc

    def _docker_shell(
        self,
        cmd: str,
        *,
        timeout_sec: int = 30,
        sdk_error: Exception | None = None,
    ) -> CodeResult:
        try:
            result = subprocess.run(
                ["docker", "exec", self.container_name, "bash", "-lc", cmd],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except Exception as exc:  # noqa: BLE001
            return CodeResult(
                ok=False,
                output="",
                error=f"{type(exc).__name__}: {exc}; sdk_error={sdk_error!r}",
            )
        return CodeResult(
            ok=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            extra={
                "exit_code": result.returncode,
                "backend": "docker_exec",
                "sdk_error": repr(sdk_error) if sdk_error else None,
            },
        )

    def _docker_run_python(
        self,
        code: str,
        *,
        sdk_error: Exception | None = None,
    ) -> CodeResult:
        try:
            result = subprocess.run(
                ["docker", "exec", "-i", self.container_name, "python3", "-"],
                input=code,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            return CodeResult(
                ok=False,
                output="",
                error=f"{type(exc).__name__}: {exc}; sdk_error={sdk_error!r}",
            )
        return CodeResult(
            ok=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            extra={
                "exit_code": result.returncode,
                "backend": "docker_exec",
                "sdk_error": repr(sdk_error) if sdk_error else None,
            },
        )

    def _docker_read_file(
        self,
        path: str,
        *,
        sdk_error: Exception | None = None,
    ) -> CodeResult:
        return self._docker_shell(
            f"cat {shlex.quote(path)}",
            timeout_sec=10,
            sdk_error=sdk_error,
        )

    def _docker_write_file(
        self,
        path: str,
        text: str,
        *,
        sdk_error: Exception | None = None,
    ) -> CodeResult:
        quoted_path = shlex.quote(path)
        quoted_dir = shlex.quote(str(__import__("posixpath").dirname(path) or "."))
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    self.container_name,
                    "bash",
                    "-lc",
                    f"mkdir -p {quoted_dir} && cat > {quoted_path}",
                ],
                input=text,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            return CodeResult(
                ok=False,
                output="",
                error=f"{type(exc).__name__}: {exc}; sdk_error={sdk_error!r}",
            )
        return CodeResult(
            ok=result.returncode == 0,
            output=f"wrote {len(text)} chars to {path}" if result.returncode == 0 else result.stdout,
            error=result.stderr,
            extra={
                "exit_code": result.returncode,
                "backend": "docker_exec",
                "sdk_error": repr(sdk_error) if sdk_error else None,
            },
        )


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
