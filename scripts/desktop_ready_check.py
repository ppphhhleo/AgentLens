#!/usr/bin/env python3
"""Exercise desktop task setup without constructing or calling an LLM.

This check intentionally uses the same sandbox bootstrap path as
``DesktopReactAdapter``: optional fresh browser profile, task launch,
browser readiness, and an initial virtual-desktop screenshot.  It is useful
for validating a task/image pair before a paid trajectory collection run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from agentlens.adapters.desktop_react import (
    DesktopReactAdapter,
    _build_desktop_sandbox_session,
    _desktop_start_command,
    _fresh_browser_profile_command,
    _force_start_url_command,
    _maximize_active_window_command,
    _wait_for_browser_ready,
)
from agentlens.harnesses.desktop_actions import capture_desktop_screenshot_event
from agentlens.schemas import load_experiment_config
from agentlens.trajectory_paths import trajectory_case_slug


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Experiment YAML using desktop_react.")
    parser.add_argument("--run-id", required=True, help="One configured run ID to check.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Readiness artifact directory. Defaults under the run output directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = load_experiment_config(args.config)
    plans = DesktopReactAdapter().build_run_plans(config, run_ids={args.run_id}, max_runs=1)
    if len(plans) != 1:
        raise SystemExit(f"expected exactly one desktop run plan for {args.run_id!r}, found {len(plans)}")
    plan = plans[0]
    harness_extra = plan.tool_harness.extra
    artifact_dir = args.output_dir or (
        plan.output_dir / "readiness" / trajectory_case_slug(plan)
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = artifact_dir / "initial.png"
    result_path = artifact_dir / "readiness.json"
    started_at = datetime.now(UTC)

    sandbox_env = {
        str(key): str(value)
        for key, value in dict(harness_extra.get("sandbox_env") or {}).items()
    }
    screen_size = harness_extra.get("screen_size") or (plan.model.extra or {}).get(
        "screen_size", [1920, 1080]
    )
    sandbox_env.setdefault("DISPLAY_WIDTH", str(int(screen_size[0])))
    sandbox_env.setdefault("DISPLAY_HEIGHT", str(int(screen_size[1])))
    result: dict[str, object] = {
        "ready_check_only": True,
        "experiment_id": config.id,
        "run_id": plan.run_id,
        "task_id": plan.task.id,
        "start_url": plan.task.start_url,
        "tool_harness": plan.tool_harness.id,
        "screen_size": list(screen_size),
        "browser_profile_reset": {
            "requested": bool(harness_extra.get("fresh_browser_profile_per_run", False)),
            "performed": False,
        },
        "started_at": started_at.isoformat(),
    }

    try:
        with _build_desktop_sandbox_session(plan, sandbox_env) as sandbox:
            if result["browser_profile_reset"]["requested"]:  # type: ignore[index]
                reset = sandbox.shell(_fresh_browser_profile_command(), timeout_sec=15)
                result["browser_profile_reset"] = {  # type: ignore[index]
                    "requested": True,
                    "performed": bool(reset.ok),
                    "error": reset.error or None,
                }
                if not reset.ok:
                    raise RuntimeError(reset.error or reset.output)

            launch_command = _desktop_start_command(plan)
            if launch_command:
                launch = sandbox.shell(launch_command, timeout_sec=10)
                result["launch"] = {"ok": launch.ok, "error": launch.error or None}
                if not launch.ok:
                    raise RuntimeError(launch.error or launch.output)
                settle_ms = int(harness_extra.get("settle_ms", 0) or 0)
                if settle_ms:
                    time.sleep(settle_ms / 1000)

            if plan.task.start_url and bool(harness_extra.get("maximize_window", True)):
                maximized = sandbox.shell(_maximize_active_window_command(), timeout_sec=10)
                result["maximize_window"] = {
                    "ok": maximized.ok,
                    "error": maximized.error or None,
                }

            if plan.task.start_url and bool(harness_extra.get("force_start_url", True)):
                launch_ready, launch_url = _wait_for_browser_ready(
                    sandbox,
                    plan.task.start_url,
                    timeout_s=float(harness_extra.get("launch_url_grace_s", 4)),
                )
                if not launch_ready:
                    navigation = sandbox.shell(
                        _force_start_url_command(plan.task.start_url), timeout_sec=10
                    )
                    result["force_start_url"] = {
                        "attempted": True,
                        "ok": navigation.ok,
                        "prior_url": launch_url,
                        "error": navigation.error or None,
                    }
                    if not navigation.ok:
                        raise RuntimeError(navigation.error or navigation.output)
                    settle_ms = int(harness_extra.get("settle_ms", 0) or 0)
                    if settle_ms:
                        time.sleep(settle_ms / 1000)
                else:
                    result["force_start_url"] = {
                        "attempted": False,
                        "ok": True,
                        "prior_url": launch_url,
                    }

            if plan.task.start_url and bool(harness_extra.get("require_browser_ready", True)):
                ready, observed_url = _wait_for_browser_ready(
                    sandbox,
                    plan.task.start_url,
                    timeout_s=float(harness_extra.get("browser_ready_timeout_s", 30)),
                )
                result["browser_ready"] = {"ok": ready, "observed_url": observed_url}
                if not ready:
                    raise RuntimeError(
                        "browser did not reach task website "
                        f"expected={plan.task.start_url!r} observed={observed_url!r}"
                    )
                settle_ms = int(harness_extra.get("browser_ready_settle_ms", 1500) or 0)
                if settle_ms:
                    time.sleep(settle_ms / 1000)

            screenshot = capture_desktop_screenshot_event(
                sandbox,
                artifact_dir,
                0,
                plan.task.goal,
                viewport={"width": int(screen_size[0]), "height": int(screen_size[1])},
            )
            if not screenshot.artifact_paths:
                raise RuntimeError(screenshot.data.get("error") or "initial screenshot capture failed")
            captured_path = screenshot.artifact_paths[0]
            if captured_path != screenshot_path:
                captured_path.replace(screenshot_path)
            result["initial_screenshot"] = str(screenshot_path.name)
            result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["error"] = str(exc)
    finally:
        completed_at = datetime.now(UTC)
        result["completed_at"] = completed_at.isoformat()
        result["elapsed_seconds"] = round((completed_at - started_at).total_seconds(), 2)
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(result_path)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
