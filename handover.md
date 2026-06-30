# AgentLens Handover

This file tracks current status, replacement-sensitive decisions, and exact
commands. Keep detailed planning in:

- `docs/trajectory-collection-tasks.md`
- `docs/acting-evaluating-pipeline.md`

## 2026-06-30: Config And Docs Cleanup

What changed:

- Pruned `configs/experiments/` to a single active experiment file:
  - `configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml`
- Reduced the active experiment to the GPT-5.4 DataVoyager smoke only:
  - `dv_most_fuel__gpt54__browser`
  - `dv_most_fuel__gpt54__sandbox`
  - `dv_most_fuel__gpt54__nogui`
- Pruned `docs/` to two project docs:
  - `docs/trajectory-collection-tasks.md`
  - `docs/acting-evaluating-pipeline.md`
- Updated `AGENT.md` and this handover so commands no longer point at deleted
  configs or docs.

Policy:

- Do not enable intervention during standard collection unless the user asks.
- Add retired configs back only when they are needed for a current run, with a
  small explicit YAML and a clear batch folder.
- Do not commit generated trajectory results unless explicitly requested.

## Current Active Smoke

Run from:

```bash
/Users/pan00342/Documents/Projects/AgentLens
```

Active config:

```bash
configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml
```

Current run IDs:

| Run ID | Harness | Model | Task |
| --- | --- | --- | --- |
| `dv_most_fuel__gpt54__browser` | `browser_only` | `gpt-5.4` | `datavoyager_most_fuel_efficient` |
| `dv_most_fuel__gpt54__sandbox` | `full_sandbox` | `gpt-5.4` | `datavoyager_most_fuel_efficient` |
| `dv_most_fuel__gpt54__nogui` | `no_gui_tool_only` | `gpt-5.4` | `datavoyager_most_fuel_efficient` |

Expected answer:

```text
Mazda GLC
```

## Current Practical Commands

Validate the remaining YAML:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
for path in sorted(Path("configs/experiments").glob("*.yaml")):
    yaml.safe_load(path.read_text())
print("yaml ok")
PY
```

Dry-run all active smoke runs:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54__browser --dry-run

.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54__sandbox --dry-run

.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54__nogui --dry-run
```

Run a fresh smoke trajectory:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54__browser \
  --execute \
  --log-actions
```

Regenerate a compact viewer:

```bash
.venv/bin/agentlens trajectory-viewer path/to/trajectory.json
```

Remove dry-run noise after checking:

```bash
rm -f agentlens_results/run_plan.json
```

Check that intervention is off in normal configs:

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

Expected output:

```text
<empty>
```

Run focused validation on recently touched runtime code:

```bash
.venv/bin/python -m py_compile src/agentlens/harnesses/browser_actions.py
.venv/bin/python -m ruff check src/agentlens/harnesses/browser_actions.py
```

## Recent Smoke Results

The full GPT-5.4 DataVoyager smoke has already produced successful local
trajectories for all three harnesses:

| Harness | Path | Status |
| --- | --- | --- |
| `browser_only` | `agentlens_results/domsteer_datavoyager_toolcall_matrix/raw/2026-06-29_08-46-47/trajectories/dv_most_fuel__gpt54__browser_seed0_trial1/trajectory.json` | success, score `1.0` |
| `full_sandbox` | `agentlens_results/domsteer_datavoyager_toolcall_matrix/raw/2026-06-29_08-52-44/trajectories/dv_most_fuel__gpt54__sandbox_seed0_trial1/trajectory.json` | success, score `1.0` |
| `no_gui_tool_only` | `agentlens_results/domsteer_datavoyager_toolcall_matrix/raw/2026-06-29_08-54-08/trajectories/dv_most_fuel__gpt54__nogui_seed0_trial1/trajectory.json` | success, score `1.0` |

## Runtime Notes

- Browser coordinates are browser viewport coordinates.
- Desktop coordinates are virtual desktop screen coordinates.
- Browser `move`/hover waits briefly before screenshot capture so tooltip
  observations can render.
- `browser.keypress` normalizes common uppercase key names such as `END` and
  `HOME` to Playwright key names.

## Open Items

- Re-run the three GPT-5.4 smoke trajectories after this cleanup if a fresh
  batch is needed.
- Add the next DataVoyager task only after the current three-harness smoke path
  is stable.
- Reintroduce TheAgentCompany, Weka, Blender, Unity, or intervention configs as
  small dedicated YAML files when those are the active target again.
- Keep Wang-style aggregation and Act-onomy-style behavioral analysis as
  post-hoc methods over raw trajectories.
