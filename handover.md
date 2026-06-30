# AgentLens Handover

This file tracks current status, replacement-sensitive decisions, and exact
commands. Longer-term planning lives in:

- `docs/trajectory-collection-tasks.md`
- `docs/acting-evaluating-pipeline.md`

## 2026-06-30: Repo Structure Cleanup

What changed:

- Active batch config now lives at:
  - `configs/batches/gpt54_datavoyager_smoke.yaml`
- Added task definitions under:
  - `tasks/domsteer/datavoyager_most_fuel_efficient/task.yaml`
- Added `task_files` support so batch YAMLs can reference task files.
- Default generated outputs now go to `runs/`.
- Moved the curated GPT-5.4 smoke result bundle to:
  - `examples/results/gpt54_datavoyager_smoke/`
- Removed duplicated published summary viewers and stale summary folders.
- Moved Docker templates to `environments/docker/`.
- Removed stale scripts that referenced deleted configs.

Policy:

- `runs/` is local and gitignored.
- `examples/results/` is for small, intentionally published examples.
- Do not enable intervention during standard collection unless explicitly asked.

## Current Active Smoke

Active config:

```bash
configs/batches/gpt54_datavoyager_smoke.yaml
```

Task file:

```bash
tasks/domsteer/datavoyager_most_fuel_efficient/task.yaml
```

Run IDs:

| Run ID | Harness | Model | Task |
| --- | --- | --- | --- |
| `dv_most_fuel__gpt54__browser` | `browser_only` | `gpt-5.4` | `datavoyager_most_fuel_efficient` |
| `dv_most_fuel__gpt54__sandbox` | `full_sandbox` | `gpt-5.4` | `datavoyager_most_fuel_efficient` |
| `dv_most_fuel__gpt54__nogui` | `no_gui_tool_only` | `gpt-5.4` | `datavoyager_most_fuel_efficient` |

Expected answer:

```text
Mazda GLC
```

## Commands

Validate:

```bash
.venv/bin/agentlens validate-config configs/batches/gpt54_datavoyager_smoke.yaml
```

Dry-run:

```bash
.venv/bin/agentlens run configs/batches/gpt54_datavoyager_smoke.yaml --dry-run
```

Execute:

```bash
.venv/bin/agentlens run configs/batches/gpt54_datavoyager_smoke.yaml \
  --execute \
  --log-actions
```

Regenerate a compact viewer:

```bash
.venv/bin/agentlens trajectory-viewer path/to/trajectory.json
```

Check intervention is off:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
for p in sorted(Path("configs/batches").glob("*.yaml")):
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

Expected output:

```text
<empty>
```

## Published Example

Curated result bundle:

```text
examples/results/gpt54_datavoyager_smoke/
```

Dashboard:

```text
examples/results/gpt54_datavoyager_smoke/dashboard/dashboard.html
```

Trajectories:

| Harness | Path | Status |
| --- | --- | --- |
| `browser_only` | `examples/results/gpt54_datavoyager_smoke/trajectories/browser/trajectory.json` | success, score `1.0` |
| `full_sandbox` | `examples/results/gpt54_datavoyager_smoke/trajectories/sandbox/trajectory.json` | success, score `1.0` |
| `no_gui_tool_only` | `examples/results/gpt54_datavoyager_smoke/trajectories/nogui/trajectory.json` | success, score `1.0` |

## Open Items

- Add the next DataVoyager task only after the current three-harness smoke path
  remains stable under the new layout.
- Reintroduce TheAgentCompany, Weka, Blender, Unity, or intervention configs as
  small dedicated batch YAMLs when those are active again.
- Keep Wang-style aggregation and Act-onomy-style behavioral analysis as
  post-hoc methods over raw trajectories.
