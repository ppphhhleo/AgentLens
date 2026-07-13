# Local Browser Evaluation Setup

This guide covers local checks for AgentLens browser-oriented tasks. It focuses
on DOMSteer/DataVoyager browser and sandbox runs. Desktop app workflows from
GUI-vs-CLI use the separate Docker runtime described in
`docs/agent-structures-and-tool-tiers.md` and
`docs/archive/trajectory-infra-history.md`.

## Prerequisites

- Python 3.11 or 3.12.
- A shell from the repo root.
- Chromium dependencies installable by Playwright.
- Docker only for `full_sandbox`, `no_gui_tool_only`, desktop, or AIO sandbox
  runs.
- Provider credentials for real model calls:
  - `OPENAI_API_KEY`, or Codex OAuth as described in
    `docs/openai-providers.md`.
  - `ANTHROPIC_API_KEY` for Anthropic configs.
  - `GEMINI_API_KEY` or `GOOGLE_AI_STUDIO_API_KEY` for Gemini configs.

## Install

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

If you use `uv`, the equivalent is:

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'
python -m playwright install chromium
```

Create local secrets:

```bash
cp .env.example .env
```

Edit `.env` and set the provider keys needed by the config you plan to run.
Do not commit `.env`.

## Sanity Checks

Verify the package imports and the CLI entry point works:

```bash
.venv/bin/agentlens doctor
.venv/bin/agentlens list-configs
```

Validate all YAML config files:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml

for path in sorted(Path("configs").glob("**/*.yaml")):
    yaml.safe_load(path.read_text())

print("yaml ok")
PY
```

Validate a current DOMSteer batch:

```bash
.venv/bin/agentlens validate-config \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml
```

## DOMSteer Browser/Sandbox Smoke

Inspect the planned runs without executing model calls:

```bash
.venv/bin/agentlens run \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml \
  --dry-run
```

Run a small local subset once credentials and the browser/sandbox environment
are ready:

```bash
.venv/bin/agentlens run \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml \
  --execute \
  --log-actions \
  --max-runs 1
```

Generated outputs land under:

```text
runs/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison/raw/<timestamp>/
```

Trajectory folders use the readable case naming scheme:

```text
runs/<batch>/raw/<timestamp>/trajectories/{app_or_family}__{task_name}__{prompt_style}__{model_id}__{harness_or_agent}__seed{seed}__trial{trial}/
```

Generate or regenerate a static viewer:

```bash
.venv/bin/agentlens trajectory-viewer path/to/trajectory.json
```

## GUI-vs-CLI Ready Check

The GUI-vs-CLI runner is separate from `agentlens run` because it reuses the
paper's desktop runtime, seed-file upload, application launcher, and verifier
stack.

Check the current GPT-5.5 five-task comparison config:

```bash
PYTHONPATH=src python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml \
  --ready-check-only
```

Run one agent/task pair only after the Docker runtime and provider credentials
are configured:

```bash
PYTHONPATH=src python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml \
  --agent agentlens_gui_toolcall_gpt55 \
  --task gimp_add_alpha_transparent \
  --max-steps 150
```

## Post-Hoc Evaluation And Analysis

Evaluation and analysis are separate from acting. After a trajectory exists,
use the raw `trajectory.json` for:

- outcome validation: final answer, score, finished status
- trajectory summaries: counts, screenshots, errors, tool calls
- Wang-style workflow aggregation
- Act-onomy-style behavior tagging and phase summaries

The high-level design is documented in:

```text
docs/acting-evaluating-pipeline.md
```

Local curated CSVs and figures may live under `runs/curated/`, but `/runs/` is
gitignored. Do not publish EDA plots or run artifacts unless explicitly asked.

## Useful Current Configs

- `configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml`
  - DOMSteer DataVoyager T1-T3 standard/grounded comparison.
- `configs/batches/domsteer_t1_t3_opus48_standard_grounded_gui_comparison.yaml`
  - Existing Opus 4.8 DOMSteer comparison shape.
- `configs/batches/gpt54_datavoyager_smoke.yaml`
  - Older small curated GPT-5.4 DataVoyager smoke.
- `configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml`
  - GUI-vs-CLI five-task standard/grounded comparison.
- `configs/gui_vs_cli/full_workflow_smoke.yaml`
  - One-per-application GUI-vs-CLI full workflow POC.

## Common Failures

- `OPENAI_API_KEY is not set`: copy `.env.example` to `.env` and fill the key,
  or use Codex OAuth as documented in `docs/openai-providers.md`.
- `Executable doesn't exist` from Playwright: run
  `python -m playwright install chromium`.
- Docker connection errors on sandbox configs: start Docker and check the
  required runtime image.
- Live websites fail or block automation: retry with `--live` where supported,
  or use a dry-run/ready-check path first to isolate config issues.
- `run id not found`: run the same config with `--dry-run` and copy the printed
  run ID.
