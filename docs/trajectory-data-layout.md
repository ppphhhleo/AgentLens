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
agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/
```

## Directory Contract

```text
agentlens_results/<batch_id>/
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
```

## Current V2 Collection Config

The clean DataVoyager v2 config is:

```text
configs/experiments/domsteer_datavoyager_matrix_v2_toolcall.yaml
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
agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/raw
```

## Recommended Collection Flow

Dry-run the matrix:

```bash
.venv/bin/agentlens run \
  configs/experiments/domsteer_datavoyager_matrix_v2_toolcall.yaml \
  --dry-run \
  --output agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/run_plan.json
```

Smoke-run one trajectory first:

```bash
.venv/bin/agentlens run \
  configs/experiments/domsteer_datavoyager_matrix_v2_toolcall.yaml \
  --execute \
  --max-runs 1 \
  --log-actions
```

Render the dashboard against only the v2 raw root:

```bash
.venv/bin/agentlens matrix-dashboard \
  configs/experiments/domsteer_datavoyager_matrix_v2_toolcall.yaml \
  --trajectory-root agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/raw \
  --output agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/dashboard/dashboard.html \
  --report-root agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/analysis/method_comparison
```

Run the full matrix after the smoke looks sane:

```bash
.venv/bin/agentlens run \
  configs/experiments/domsteer_datavoyager_matrix_v2_toolcall.yaml \
  --execute \
  --log-actions
```

Then rerender the dashboard with `--generate-reports` only when you are ready
to spend analysis-model calls:

```bash
.venv/bin/agentlens matrix-dashboard \
  configs/experiments/domsteer_datavoyager_matrix_v2_toolcall.yaml \
  --trajectory-root agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/raw \
  --output agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/dashboard/dashboard.html \
  --report-root agentlens_results/domsteer_datavoyager_matrix_v2_toolcall/analysis/method_comparison \
  --generate-reports \
  --annotation-mode llm \
  --llm-provider openai \
  --llm-model gpt-5.4-mini
```

## Rule

Do not point a dashboard for a new batch at a parent folder that also contains
older runs. The dashboard intentionally picks the latest trajectory by `run_id`;
using a mixed root can hide which collection pass a cell came from.
