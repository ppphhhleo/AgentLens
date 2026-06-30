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

## 2026-06-30: GUI-vs-CLI Task Catalog

What changed:

- Added `gui_vs_cli` as a recognized `TaskConfig.benchmark`.
- Added the full public task catalog:
  - `tasks/gui_vs_cli/tasks.jsonl`
- Removed the earlier hand-written placeholder GUI-vs-CLI task YAML.
- Added environment backend notes:
  - `environments/README.md`

Status:

- The catalog has 440 task records across 18 desktop applications.
- It preserves task text, required seed files, and verifier commands from the
  public GUI-vs-CLI dataset.
- These tasks are not in an active batch yet.
- They need a compatible desktop image, seed assets, and a verifier bridge
  before they can produce executable trajectories in AgentLens.

Decision:

- Do not vendor or couple to the whole E2B stack yet.
- Borrow the backend abstraction idea instead: screenshot, command execution,
  file read/write, stream URL, and kill.
- Keep intervention and simulated-user actors above the environment backend so
  they work the same over Docker, AWS Docker, E2B, or future providers.

Local reference clone:

- `third_party/gui-vs-cli/` contains a local ignored copy of
  `rebeccaz4/gui-vs-cli` at commit `8fee696`.
- It is for code reference only and is intentionally ignored by git.
- If it needs to be refreshed:

```bash
rm -rf third_party/gui-vs-cli
git clone --depth 1 --filter=blob:none https://github.com/rebeccaz4/gui-vs-cli.git third_party/gui-vs-cli
```

## 2026-06-30: DOMSteer Task Catalog

What changed:

- Added DOMSteer catalog docs:
  - `tasks/domsteer/README.md`
  - `tasks/domsteer/tasks.jsonl`
- The catalog has exactly 8 records: the four DataVoyager and four TensorFlow
  Playground experiment tasks from Section 8.1.
- DataVoyager study tasks T1-T3 include deterministic expected answers:
  - T1 most fuel-efficient car: `Mazda GLC`.
  - T2 widest horsepower range by origin: `USA`.
  - T3 European cars with horsepower > 100 and four cylinders: `10`.
- Tasks T4-T8 keep `answer_validator: manual_pending` and
  `verification.type: pending` because no exact answer is given in the paper.

Status:

- Only `datavoyager_most_fuel_efficient` is currently an active runnable YAML.
- T2 and T3 are ready to convert into task YAMLs.
- T4 and TensorFlow Playground tasks need rubrics or state/screenshot
  evaluators before batch collection.

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
| `dv_most_fuel__gpt54__desktop_toolcall_gui` | `desktop_gui_toolcall` | `gpt-5.4` | `datavoyager_most_fuel_efficient` |
| `dv_most_fuel__gpt54__desktop_openai_computer` | `desktop_gui_openai_computer` | `gpt-5.4` via OpenAI native computer tool | `datavoyager_most_fuel_efficient` |

Desktop GUI comparison:

- `desktop_gui_toolcall` is the strict AgentLens GUI-only setup: the prompt and
  registered tools expose only desktop GUI actions plus `final_answer`.
- `desktop_gui_openai_computer` is the paper-faithful setup: clean GUI-only
  operator prompt plus OpenAI Responses API `{"type": "computer"}`. Raw native
  computer calls are preserved in trajectory metadata and mapped into
  AgentLens desktop actions for execution, intervention compatibility, and
  post-hoc analysis.
- Both desktop runs open the task `start_url` inside the virtual desktop browser
  via `desktop_start_cmd_template`.

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

If `.venv/bin/agentlens` is unavailable, use:

```bash
uv run --no-sync python -m agentlens.cli run configs/batches/gpt54_datavoyager_smoke.yaml --dry-run
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

- Add the next DataVoyager task only after the current five-run smoke matrix
  remains stable under the new layout.
- GUI-vs-CLI tasks still need a runnable Docker image/asset mount and verifier
  bridge before batch collection.
- Reintroduce TheAgentCompany, Weka, Blender, Unity, or intervention configs as
  small dedicated batch YAMLs when those are active again.
- Keep Wang-style aggregation and Act-onomy-style behavioral analysis as
  post-hoc methods over raw trajectories.
