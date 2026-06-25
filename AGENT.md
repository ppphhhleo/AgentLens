# AgentLens Agent Instructions

This repository is an experimental harness for collecting and analyzing agent,
human, and human-agent trajectories in browser and virtual-desktop tasks.

Read this first, then read `handover.md` for the current milestone status and
exact commands. Update `handover.md` whenever you replace or substantially
change a harness, task source, evaluator, Docker image, analysis pipeline, or
batch/run layout.

## Project Priorities

- Capture first: preserve screenshots, actions/tool calls, model messages,
  tool outputs, artifacts, and run metadata before adding complex evaluation.
- Keep acting, outcome evaluation, trajectory analysis, and dashboards separate.
- Keep model backend separate from harness tier:
  - model backend: OpenAI, Anthropic, Gemini, etc.;
  - harness tier: `browser_only`, `full_sandbox`, `desktop_react`, `no_gui`.
- Standard collection runs must not enable intervention unless the user
  explicitly asks for it. Intervention belongs in dedicated opt-in configs.
- Prefer clean, reproducible batch folders with a frozen config snapshot.

## Working Directory

Main local repo:

```bash
/Users/pan00342/Documents/Projects/AgentLens
```

Run commands from the repo root unless stated otherwise.

Do not edit code directly on AWS. Modify locally, commit/push or sync, then
pull/run on the server.

## Important Files

- `handover.md`: current status, milestones, exact validation/run commands.
- `docs/trajectory-data-layout.md`: expected batch/result layout.
- `docs/trajectory-collection-tasks.md`: task catalog and candidate tasks.
- `docs/task-registry.md`: compact task implementation status.
- `configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml`: current
  DataVoyager tool-call collection config.
- `configs/experiments/domsteer_claude_toolcall_smoke.yaml`: Claude tool-call
  smoke config.
- `configs/experiments/workflow_desktop_apps_poc.yaml`: Weka/Blender desktop
  app smoke config.
- `configs/experiments/intervention_repeated_action_smoke.yaml`: the explicit
  intervention test config. This is the only config that should normally keep
  repeated-action intervention enabled.

## Validation Commands

Use the detailed command list in `handover.md`. The usual minimum checks are:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
for path in sorted(Path("configs/experiments").glob("*.yaml")):
    yaml.safe_load(path.read_text())
print("yaml ok")
PY

.venv/bin/python -m ruff check src/agentlens tests
```

Focused pytest command:

```bash
.venv/bin/python -m pytest tests/test_openai_tool_adapter.py -q
```

In the Codex desktop shell, `pytest` has sometimes exited with code `-1` and no
stdout/stderr. If that happens, use the direct fallback documented in
`handover.md`, and rerun pytest in a normal shell or CI before final landing.

## Common Dry Runs

```bash
.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54mini__browser --dry-run

.venv/bin/agentlens run configs/experiments/domsteer_claude_toolcall_smoke.yaml \
  --dry-run

.venv/bin/agentlens run configs/experiments/workflow_desktop_apps_poc.yaml \
  --dry-run
```

Dry-runs may write `agentlens_results/run_plan.json`; remove it after checking
unless the user wants to keep it:

```bash
rm -f agentlens_results/run_plan.json
```

## Smoke Runs

Before large batch collection, run one fresh smoke trajectory and inspect the
viewer:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54mini__browser \
  --execute \
  --log-actions
```

Generate or regenerate a compact per-trajectory viewer:

```bash
.venv/bin/agentlens trajectory-viewer path/to/trajectory.json
```

## Intervention Rule

Do not turn intervention on during normal collection runs unless the user says
so. To verify this invariant:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
for p in sorted(Path("configs/experiments").glob("*.yaml")):
    data = yaml.safe_load(p.read_text()) or {}
    enabled = []
    for h in data.get("tool_harnesses") or []:
        inter = ((h.get("extra") or {}).get("intervention") or {})
        rep = inter.get("repeated_action") or {}
        if inter.get("enabled") or rep.get("enabled"):
            enabled.append(h.get("id"))
    if enabled:
        print(p, enabled)
PY
```

Expected normal output:

```text
configs/experiments/intervention_repeated_action_smoke.yaml ['browser_capture_with_intervention']
```

## Result Layout

Keep new batches organized as:

```text
agentlens_results/<batch_name>/
  batch_config.yaml
  run_plan.dry_run.json        # optional
  raw/
    <snapshot>/
      trajectories/<run_id>/trajectory.json
  dashboard/
  analysis/
```

Avoid mixing old and new trajectory formats in one dashboard unless the user
explicitly wants provenance comparison.

## Coding Notes

- Use `rg` for search.
- Use `apply_patch` for manual file edits.
- Do not commit generated results unless the user explicitly asks.
- Keep screenshots/videos in result folders; delete large derived artifacts
  such as ad-hoc GIFs unless the user wants them.
- Browser coordinates are browser viewport coordinates.
- Desktop coordinates are virtual desktop screen coordinates.
- Browser `move`/hover waits briefly before screenshot capture so tooltip
  observations can render.
