# Trajectory Data Layout

This file defines the storage convention for new AgentLens trajectory
collection batches. Keep raw acting outputs separate from post-hoc analysis
outputs so dashboards never silently mix old and new data.

## Batch Root

Use one explicit batch root per collection pass:

```text
agentlens_results/<batch_id>/
```

For the current DataVoyager recollection:

```text
agentlens_results/domsteer_datavoyager_toolcall_matrix/
```

## Directory Contract

```text
agentlens_results/<batch_id>/
  batch_config.yaml              # frozen config snapshot used for this batch
  run_plan.dry_run.json          # optional resolved dry-run expansion
  raw/
    trajectories/
      <run_id>_seed<seed>_trial<trial>/
        trajectory.json
        screenshots/
          step_000.png
          step_001.png
          ...
        trace.zip                  # optional, local browser only
        video/                     # optional, local browser only
    screenshot_react_summary/
      summary.json
      summary.csv
      summary.raw.json
      report.html
      viewer.html

  dashboard/
    dashboard.html
    dashboard.manifest.json

  analysis/
    method_comparison/
      <run_id>/
        original/trajectory.json
        wang/
        actonomy/
        method_comparison.html
    evaluations/
      ...

  smoke/
    batch_config.yaml            # same frozen config unless smoke has a variant
    raw/                         # smoke trajectories kept out of production raw/
    dashboard.html
```

## Current Collection Config

The clean DataVoyager tool-call config is:

```text
configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml
```

It includes:

- 3 models: `gpt54_mini`, `gpt4o_mini`, `gpt5_mini`
- 2 active DataVoyager tasks:
  - `datavoyager_most_fuel_efficient`
  - `datavoyager_europe_100hp_4cyl_count`
- 3 harnesses:
  - `browser_only`
  - `full_sandbox`
  - `no_gui_tool_only`
- 18 run specs total

The config writes raw trajectories to:

```text
agentlens_results/domsteer_datavoyager_toolcall_matrix/raw
```

## Recommended Collection Flow

Freeze the config into the batch folder:

```bash
cp configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  agentlens_results/domsteer_datavoyager_toolcall_matrix/batch_config.yaml
```

Optionally dry-run the matrix. This is a debugging/audit artifact, not the
source of truth:

```bash
.venv/bin/agentlens run \
  agentlens_results/domsteer_datavoyager_toolcall_matrix/batch_config.yaml \
  --dry-run \
  --output agentlens_results/domsteer_datavoyager_toolcall_matrix/run_plan.dry_run.json
```

`run_plan.dry_run.json` is the runner's resolved view of the batch after
references, defaults, seeds, trials, and filters are expanded. It can be
deleted and regenerated from `batch_config.yaml`.

Smoke-run one trajectory first:

```bash
.venv/bin/agentlens run \
  agentlens_results/domsteer_datavoyager_toolcall_matrix/batch_config.yaml \
  --execute \
  --max-runs 1 \
  --log-actions
```

Render the dashboard against only the tool-call raw root:

```bash
.venv/bin/agentlens matrix-dashboard \
  agentlens_results/domsteer_datavoyager_toolcall_matrix/batch_config.yaml \
  --trajectory-root agentlens_results/domsteer_datavoyager_toolcall_matrix/raw \
  --output agentlens_results/domsteer_datavoyager_toolcall_matrix/dashboard/dashboard.html \
  --report-root agentlens_results/domsteer_datavoyager_toolcall_matrix/analysis/method_comparison
```

Run the full matrix after the smoke looks sane:

```bash
.venv/bin/agentlens run \
  agentlens_results/domsteer_datavoyager_toolcall_matrix/batch_config.yaml \
  --execute \
  --log-actions
```

Then rerender the dashboard with `--generate-reports` only when you are ready
to spend analysis-model calls:

```bash
.venv/bin/agentlens matrix-dashboard \
  agentlens_results/domsteer_datavoyager_toolcall_matrix/batch_config.yaml \
  --trajectory-root agentlens_results/domsteer_datavoyager_toolcall_matrix/raw \
  --output agentlens_results/domsteer_datavoyager_toolcall_matrix/dashboard/dashboard.html \
  --report-root agentlens_results/domsteer_datavoyager_toolcall_matrix/analysis/method_comparison \
  --generate-reports \
  --annotation-mode llm \
  --llm-provider openai \
  --llm-model gpt-5.4-mini
```

## Rule

Do not point a dashboard for a new batch at a parent folder that also contains
older runs. The dashboard intentionally picks the latest trajectory by `run_id`;
using a mixed root can hide which collection pass a cell came from.

Treat `configs/experiments/*.yaml` as editable templates. Treat
`agentlens_results/<batch_id>/batch_config.yaml` as the frozen provenance record
for that batch.

Treat `run_plan.dry_run.json` as optional. It is useful when debugging exactly
what the runner intended to execute, but it is secondary to `batch_config.yaml`.
