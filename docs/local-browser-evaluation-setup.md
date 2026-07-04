# Local Browser Evaluation Setup

This guide sets up AgentLens for local testing of the web/browser evaluation path.
It focuses on browser-only and sandboxed-browser tasks, not desktop app harnesses.

## What Already Exists

There is partial setup guidance in `docs/handout.md`, evaluation details in
`docs/acting-evaluating-pipeline.md`, and tool details in
`docs/screenshot-react-tools.md`. This document is the dedicated local setup
path for browser evaluation.

## Prerequisites

- Python 3.11 or 3.12
- A shell from the repo root
- Chromium dependencies installable by Playwright
- Docker only if you want `full_sandbox` / AIO sandbox browser runs
- `OPENAI_API_KEY` for real OpenAI model runs
- `ANTHROPIC_API_KEY` only for Anthropic configs

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

Edit `.env` and set at least:

```bash
OPENAI_API_KEY=sk-...
```

Optional values used by specific configs:

```bash
ANTHROPIC_API_KEY=...
OPENAI_BASE_URL=...
ANTHROPIC_BASE_URL=...
HF_TOKEN=...
MINIWOB_URL=file:///path/to/miniwob/html/miniwob/
```

## Sanity Checks

Verify the package imports and the CLI entry point works:

```bash
.venv/bin/agentlens doctor
.venv/bin/agentlens list-configs
```

Validate all experiment YAML files:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml

for path in sorted(Path("configs/experiments").glob("*.yaml")):
    yaml.safe_load(path.read_text())

print("yaml ok")
PY
```

Validate one browser config through the AgentLens schema:

```bash
.venv/bin/agentlens validate-config configs/experiments/browsergym_direct_smoke.yaml
```

## First Browser Smoke Test

Start with the no-model BrowserGym direct smoke. It uses a local `data:` URL, so
it does not require an API key or live website access:

```bash
.venv/bin/agentlens run configs/experiments/browsergym_direct_smoke.yaml \
  --dry-run

.venv/bin/agentlens run configs/experiments/browsergym_direct_smoke.yaml \
  --execute --log-actions
```

Expected output lands under:

```text
agentlens_results/browsergym_direct_smoke/<UTC_TIMESTAMP>/
```

The trajectory file is typically:

```text
agentlens_results/browsergym_direct_smoke/<UTC_TIMESTAMP>/trajectories/smoke_click_seed0_trial1/trajectory.json
```

Generate a static viewer:

```bash
.venv/bin/agentlens trajectory-viewer \
  agentlens_results/browsergym_direct_smoke/<UTC_TIMESTAMP>/trajectories/smoke_click_seed0_trial1/trajectory.json
```

## Real Browser Agent Run

For a model-backed browser task, use a small run from the DOMSteer configs. First
inspect the run IDs:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
  --dry-run
```

Then execute one run:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
  --run-id tf_discretize_toggle_gpt5 \
  --execute --log-actions
```

To watch the browser locally:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
  --run-id tf_discretize_toggle_gpt5 \
  --execute --live --log-actions
```

If the run ID differs, use the exact ID printed by `--dry-run`.

## Post-Hoc Evaluation

Evaluation is separate from acting. After a trajectory exists:

```bash
.venv/bin/agentlens evaluate-trajectory \
  path/to/trajectory.json \
  --output-dir agentlens_results/evaluations/local_single \
  --config configs/experiments/domsteer_screenshot_react.yaml
```

Batch evaluation scans directories for `trajectory.json` files:

```bash
.venv/bin/agentlens evaluate-batch \
  agentlens_results/domsteer_screenshot_react \
  --output-dir agentlens_results/evaluations/domsteer_local \
  --config configs/experiments/domsteer_screenshot_react.yaml
```

Evaluation writes `evaluation_bundle.json` for single trajectories and
`evaluation_bundles.jsonl` plus summaries for batch runs.

## Sandboxed Browser Runs

Use this only when the harness has `tier: full_sandbox` or
`extra.browser_source: aio_sandbox`.

Prerequisites:

```bash
docker version
docker pull ghcr.io/agent-infra/sandbox:latest
```

Dry-run a sandboxed browser config:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_sandbox.yaml \
  --dry-run
```

Execute one sandboxed run:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_sandbox.yaml \
  --max-runs 1 \
  --execute --log-actions
```

Sandboxed browser runs use Docker for the browser, shell, Python, file I/O, and
optional search tools. Browser-only runs do not need Docker.

## Useful Browser Configs

- `configs/experiments/browsergym_direct_smoke.yaml`: no-model local browser smoke
- `configs/experiments/domsteer_screenshot_react.yaml`: browser-only model-backed web tasks
- `configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml`: browser-only, sandbox, and no-GUI tool-call matrix
- `configs/experiments/domsteer_sandbox.yaml`: full sandbox browser tasks
- `configs/experiments/online_mind2web_screenshot_react.yaml`: live Online-Mind2Web-style tasks

Note: `configs/experiments/screenshot_react_tools_smoke.yaml` currently contains
absolute fixture URLs from another machine. Prefer `browsergym_direct_smoke.yaml`
for a portable first smoke test.

## Common Failures

- `OPENAI_API_KEY is not set`: copy `.env.example` to `.env` and fill the key.
- `Executable doesn't exist` from Playwright: run `python -m playwright install chromium`.
- Docker connection errors on sandbox configs: start Docker and pull
  `ghcr.io/agent-infra/sandbox:latest`.
- Live websites fail or block automation: retry with `--live` for inspection, or
  use browser-only local smoke tests to isolate environment issues.
- `run id not found`: run the same config with `--dry-run` and copy the printed
  run ID.
