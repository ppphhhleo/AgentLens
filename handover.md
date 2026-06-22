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

## Current Practical Commands

Prepare desktop POC locally or on AWS:

```bash
scripts/prepare_workflow_desktop_poc.sh
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

- Provide or build a Unity/Blender/Workflow-GYM-ready sandbox image.
- Replace `manual_pending` for real desktop app tasks with an artifact/state
  evaluator once the target application is actually installed.
- Decide whether to reconcile or replace the dirty AWS checkout at
  `/home/ubuntu/AgentLens`; current POC work used `/home/ubuntu/AgentLens_desktop_poc`
  to avoid overwriting server-side changes.
