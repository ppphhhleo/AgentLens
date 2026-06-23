# AgentLens Handover

This file tracks big implementation milestones and replacement-sensitive
decisions. Update it whenever a major harness, task source, evaluator, image,
or analysis pipeline is replaced.

Task planning lives in `docs/task-registry.md`. Update that registry whenever
adding, replacing, retiring, or reprioritizing runnable or candidate tasks.

## 2026-06-20: Desktop POC And Post-Hoc Evaluation

Commit: `a225bbd Add desktop POC and trajectory evaluator pipeline`

What changed:

- Added `desktop_react` for desktop-app trajectories in the sandbox virtual computer.
- Added desktop tool actions: screenshot, click, type, keypress, shell, wait.
- Added post-hoc evaluator CLI:
  - `agentlens evaluate-trajectory`
  - `agentlens evaluate-batch`
- Evaluation bundles now keep:
  - `acting`
  - `evaluating.outcome`
  - `evaluating.trajectory`
  - `evaluating.methods.wang`
  - `evaluating.methods.actonomy`
- Added Workflow-GYM-style Unity smoke config:
  - `configs/experiments/workflow_desktop_poc.yaml`
- Added replaceable desktop image scaffold:
  - `docker/desktop-poc/`
- Added exact answers for the two additional Domsteer/DataVoyager task entries.

Validated:

- Local desktop POC generated trajectories and screenshots.
- AWS desktop POC generated trajectories and screenshots from
  `/home/ubuntu/AgentLens_desktop_poc`.
- The current generic desktop image does not install Unity; Unity outcome is
  intentionally `manual_pending`.

Important replacement note:

- Replacing `tool_harnesses[].extra.sandbox_image` with a Unity/Blender image is
  the next real Workflow-GYM milestone. When that happens, update this file with
  the image tag, installed application version, launch command, and evaluator.

## 2026-06-22: Weka And Blender Desktop App Smoke Tasks

What changed:

- Added Workflow-GYM-style desktop app smoke config:
  - `configs/experiments/workflow_desktop_apps_poc.yaml`
- Added replaceable app image scaffold:
  - `docker/desktop-apps-poc/`
  - image tag: `agentlens/desktop-apps-poc:latest`
  - installed apps: Weka, Blender, Java runtime
- Added prep script:
  - `scripts/prepare_workflow_desktop_apps_poc.sh`
  - prefers Dockerfile build;
  - falls back to run-plus-commit build on hosts where Docker's legacy builder
    stalls, while restoring the AIO sandbox entrypoint `/opt/gem/run.sh`.
- Registered tasks:
  - `workflowgym_weka_iris_smoke`
  - `workflowgym_blender_cube_smoke`

Validated:

- Local smoke generated two trajectories:
  - `agentlens_results/workflow_desktop_apps_poc/2026-06-22_07-24-14/`
- Local post-hoc evaluation bundles generated under:
  - `agentlens_results/evaluations/workflow_desktop_apps_poc/2026-06-22_07-24-14/`
- AWS smoke generated two trajectories from `/home/ubuntu/AgentLens_desktop_poc`
  and was synced back locally:
  - `agentlens_results/workflow_desktop_apps_poc/2026-06-22_07-48-38_aws/`
- AWS post-hoc evaluation bundles generated under:
  - `agentlens_results/evaluations/workflow_desktop_apps_poc/2026-06-22_07-48-38_aws/`

Important smoke finding:

- When the app is already launched by `desktop_start_cmd`, the agent may still
  call `desktop.shell` with GUI commands such as `weka` or `blender`. These
  foreground GUI processes can block the shell tool. Short-term mitigation is
  to avoid telling the model to launch already-started GUI apps; longer-term
  fix is to make desktop shell execution safer for GUI commands, such as
  detached launch helpers or timeout/kill handling.

## Current Practical Commands

Prepare desktop POC locally or on AWS:

```bash
scripts/prepare_workflow_desktop_poc.sh
```

Prepare Weka/Blender desktop app POC locally or on AWS:

```bash
scripts/prepare_workflow_desktop_apps_poc.sh
```

For the isolated AWS POC sync at `/home/ubuntu/AgentLens_desktop_poc`, reuse
the existing AgentLens virtualenv. The script prepends the current checkout's
`src` directory to `PYTHONPATH`, so the shared executable still imports the
synced POC source:

```bash
AGENTLENS_CLI=/home/ubuntu/AgentLens/.venv/bin/agentlens \
  scripts/prepare_workflow_desktop_poc.sh
```

Run one desktop smoke trajectory:

```bash
.venv/bin/agentlens run configs/experiments/workflow_desktop_poc.yaml \
  --execute \
  --max-runs 1 \
  --log-actions
```

Evaluate one completed trajectory:

```bash
.venv/bin/agentlens evaluate-trajectory path/to/trajectory.json \
  --output-dir agentlens_results/evaluations/example \
  --config configs/experiments/workflow_desktop_poc.yaml
```

## Open Items

- Keep Weka/Blender outcome validation as `manual_pending` until real
  artifact/state evaluators are added.
- Provide or build a Unity/official Workflow-GYM-ready sandbox image.
- Replace `manual_pending` for real desktop app tasks with an artifact/state
  evaluator once the target application is actually installed.
- Broaden the detached GUI launch guard if future desktop tasks add additional
  foreground GUI apps beyond Weka and Blender.
- Decide whether to reconcile or replace the dirty AWS checkout at
  `/home/ubuntu/AgentLens`; current POC work used `/home/ubuntu/AgentLens_desktop_poc`
  to avoid overwriting server-side changes.

## 2026-06-23: Safer Desktop GUI Launch Behavior

What changed:

- Added `desktop.launch_app` as the explicit detached GUI app launch tool.
- Kept `desktop.shell` available for non-GUI inspection and file/programmatic
  work, but added a runtime guard for known foreground GUI launch commands:
  - `blender`
  - `weka`
  - `java -jar /usr/share/java/weka.jar`
- If an agent still emits one of those commands through `desktop.shell`, the
  executor converts it to a detached `nohup bash -lc ... &` launch and returns
  promptly instead of blocking the trajectory loop.
- Added the new action to tool gating, OpenAI tool-call registration, trajectory
  formatting, Wang-style canonical phases, and Actonomy-style labels.
- Updated `workflow_desktop_apps_poc.yaml` to expose `desktop.launch_app`.

Validated:

- `agentlens validate-config configs/experiments/workflow_desktop_apps_poc.yaml`
- `ruff check src/agentlens tests`
- `scripts/prepare_workflow_desktop_apps_poc.sh`
- Direct helper check confirmed `blender` detaches and `ls /tmp` stays a normal
  shell command.

Note:

- `pytest` 9.0.3 is installed in the local venv, but both
  `.venv/bin/python -m pytest tests/test_desktop_actions.py` and
  `.venv/bin/pytest tests/test_desktop_actions.py` exited with code `-1`
  without stdout/stderr in this desktop session. Keep the focused test file; it
  should run in CI or a normal shell environment.
