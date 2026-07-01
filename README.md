# AgentLens

An experimental harness for collecting, evaluating, and analyzing agent trajectories in browser and virtual-desktop tasks. AgentLens supports multiple evaluation paradigms including live browser agent execution, post-hoc trajectory analysis, and LLM-based judge evaluation.

## Features

- **Multi-harness architecture** — browser-only, full sandbox, desktop, screenshot-react, and tool-call adapters
- **YAML-driven experiment configs** — declarative experiment definitions with model, harness, and task specifications
- **Post-hoc evaluation pipeline** — evaluate completed trajectories with trajectory checks, method features, and outcome validators
- **ARB (AgentRewardBench) integration** — 4-dimensional LLM judge scoring (Success, Side Effects, Optimality, Looping) with WHO/WHEN dataset categories
- **Static HTML reports** — trajectory viewers, experiment dashboards, method comparison reports, and ARB evaluation dashboards
- **Dry-run support** — inspect resolved run plans before committing to real execution

## Quick Start

### Prerequisites

- Python 3.11 or 3.12 (required: `>=3.11,<3.13`)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
git clone <your-agentlens-repo-url>
cd AgentLens

# Create virtual environment (using uv)
uv venv .venv --python 3.12
source .venv/bin/activate

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Install Playwright browsers (needed for browser-based tasks)
playwright install chromium
```

### Verify the installation

```bash
agentlens doctor
# Output: AgentLens environment is ready.
```

### List available experiment configs

```bash
agentlens list-configs
```

### Validate a config

```bash
agentlens validate-config configs/experiments/arb_webarena_judge.yaml
```

### Dry-run an experiment

```bash
agentlens run configs/experiments/arb_webarena_judge.yaml --dry-run
```

### Generate a mock summary report

```bash
agentlens summarize configs/experiments/arb_webarena_judge.yaml \
  --output-dir agentlens_results/mock_summary
```

This creates `report.html` and `trajectory_viewer.html` in the output directory.

## CLI Commands

| Command | Description |
|---------|-------------|
| `agentlens doctor` | Verify environment is importable |
| `agentlens validate-config <yaml>` | Validate an experiment config |
| `agentlens list-configs` | List available experiment YAML files |
| `agentlens summarize <yaml>` | Generate mock summary + HTML reports |
| `agentlens run <yaml> --dry-run` | Inspect run plans without executing |
| `agentlens run <yaml> --execute` | Execute an experiment |
| `agentlens trajectory-viewer <json>` | Generate static HTML trajectory viewer |
| `agentlens evaluate-trajectory <json>` | Post-hoc evaluate a single trajectory |
| `agentlens evaluate-batch <paths...>` | Evaluate many trajectories |
| `agentlens matrix-dashboard <yaml>` | Generate model x task x harness dashboard |
| `agentlens arb-evaluate <yaml>` | Run ARB 4D LLM judge evaluation |
| `agentlens import-arb <benchmark> <dir>` | Auto-generate ARB experiment config |
| `agentlens arb-dashboard <results_dir>` | Generate ARB WHO/WHEN dashboard |

---

## AgentRewardBench (ARB) Integration

AgentLens integrates [AgentRewardBench](https://github.com/McGill-NLP/agent-reward-bench) to provide 4-dimensional trajectory evaluation using LLM judges. This enables tool-usage-only benchmarks (WebArena, AssistantBench) that are separate from GUI navigation tasks.

### What is AgentRewardBench?

AgentRewardBench (ARB) is a library for evaluating web agent trajectories across four dimensions:

| Dimension | Type | Description |
|-----------|------|-------------|
| **Success** | Binary | Did the agent complete the task? |
| **Side Effects** | Binary | Did the agent cause unintended changes? |
| **Optimality** | 1-4 Likert | How efficient was the agent's approach? |
| **Looping** | Binary | Did the agent get stuck in repetitive behavior? |

ARB uses LLM-as-judge evaluation — an LLM (default: `gpt-4o-mini`) reads the agent's trajectory and scores it across all four dimensions using structured XML-tag output parsing.

### WHO and WHEN Dimensions

Beyond the 4D scoring, the ARB integration introduces two dataset-level categorization dimensions:

- **WHO** — Which agent model produced the trajectory (e.g., `GenericAgent-gpt-4o-2024-11-20`, `GenericAgent-anthropic_claude-3.7-sonnet`). This enables cross-model comparison.
- **WHEN** — Temporal stability of the task, from AssistantBench's `time_dependency` column:
  - **Static** — Task state doesn't change between interactions
  - **Stable** — State changes gradually and predictably
  - **Unlikely** — State may change but is unlikely to affect the solution

The WHEN dimension is only available for AssistantBench. WebArena tasks do not carry temporal metadata.

### Composite Score Formula

```
composite = success * 0.4 + optimality_norm * 0.3 + no_side_effect * 0.15 + no_looping * 0.15
```

Where `optimality_norm = (optimality - 1) / 3` maps the 1-4 Likert scale to 0-1.

---

## Setting Up agent-reward-bench

### Step 1: Clone the repository

```bash
# From the same parent directory as AgentLens
cd /path/to/your/workspace
git clone https://github.com/McGill-NLP/agent-reward-bench.git
cd agent-reward-bench
```

### Step 2: Install agent-reward-bench

You can install it as a pip package (recommended for AgentLens integration):

```bash
# From the agent-reward-bench directory
pip install -e ".[all]"
```

Or install from PyPI:

```bash
pip install agent-reward-bench
```

If you're using AgentLens's virtual environment, install it there:

```bash
# From the AgentLens directory
source .venv/bin/activate
pip install -e "../agent-reward-bench[all]"

# Or use AgentLens's optional dependency group
uv pip install -e ".[arb]"
```

### Step 3: Install Playwright browsers

ARB requires Playwright for browser interactions during trajectory generation:

```bash
playwright install
```

### Step 4: Download the trajectory dataset

ARB provides pre-generated agent trajectories via Hugging Face:

```python
from huggingface_hub import snapshot_download

# Download all trajectories (~large download)
snapshot_download(
    repo_id="McGill-NLP/agent-reward-bench",
    repo_type="dataset",
    local_dir="./trajectories/"
)
```

The downloaded data is organized as:

```
trajectories/
├── cleaned/                    # Cleaned trajectory JSONs (used by AgentLens)
│   ├── assistantbench/
│   │   └── GenericAgent-<LLM>/
│   │       └── GenericAgent-<LLM>_on_assistantbench/
│   │           ├── assistantbench.validation.0.json
│   │           └── ...
│   ├── webarena/
│   │   └── GenericAgent-<LLM>/
│   │       └── GenericAgent-<LLM>_on_webarena/
│   │           ├── webarena.561.json
│   │           └── ...
│   ├── visualwebarena/
│   └── workarena/
├── judgments/                   # Pre-computed judge outputs
├── screenshots/                # Step-by-step screenshots
```

### Step 5: Set up API keys

The ARB judge requires an OpenAI API key for the LLM judge calls:

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

Or create a `.env` file in the AgentLens root:

```
OPENAI_API_KEY=your-openai-api-key
```

### Step 6: (Optional) Generate your own trajectories

If you want to generate fresh trajectories instead of using the pre-built dataset, you need to set up the web environments first.

#### Set up web environments

- **WebArena / VisualWebArena**: See [gasse/webarena-setup](https://github.com/gasse/webarena-setup/)
- **WorkArena**: See [ServiceNow/WorkArena](https://github.com/ServiceNow/WorkArena/)

#### Set environment variables

```bash
# For WebArena
export WA_HOMEPAGE="https://wa-homepage-${SUFFIX}.${WEBHOST}"
export WA_SHOPPING="https://wa-shopping-${SUFFIX}.${WEBHOST}/"
export WA_SHOPPING_ADMIN="https://wa-shopping-admin-${SUFFIX}.${WEBHOST}/admin"
export WA_REDDIT="https://wa-forum-${SUFFIX}.${WEBHOST}"
export WA_GITLAB="https://wa-gitlab-${SUFFIX}.${WEBHOST}"
export WA_WIKIPEDIA="https://wa-wikipedia-${SUFFIX}.${WEBHOST}/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="https://wa-openstreetmap-${SUFFIX}.${WEBHOST}"
export WA_FULL_RESET="https://wa-reset-${SUFFIX}.${WEBHOST}"

# See agent-reward-bench/vars/set_envs.sh for the full list
```

#### Run the agent

```bash
cd agent-reward-bench

# Run an agent on a benchmark
python scripts/run_agent.py --model "gpt-4o" --benchmark "webarena_100"
python scripts/run_agent.py --model "gpt-4o" --benchmark "assistantbench"

# See all options
python scripts/run_agent.py --help
```

#### Process trajectories

Convert raw AgentLab pickle files to cleaned JSON format:

```bash
# Convert pickle trajectories to JSON
python scripts/convert_trajectories_to_json.py

# Clean processed trajectories (optional but recommended)
python scripts/clean_processed_trajectories.py
```

This produces the `trajectories/cleaned/` directory structure that AgentLens consumes.

---

## Running ARB Benchmarks with AgentLens

### Option A: Auto-generate config from trajectory directory

If you have cleaned trajectory JSONs (from Step 4 or Step 6 above), auto-generate an experiment config:

```bash
# WebArena benchmark
agentlens import-arb webarena_100 /path/to/trajectories/cleaned/webarena \
  --output configs/experiments/arb_webarena_judge.yaml \
  --judge-model gpt-4o-mini-2024-07-18

# AssistantBench benchmark (includes WHEN dimension)
agentlens import-arb assistantbench /path/to/trajectories/cleaned/assistantbench \
  --output configs/experiments/arb_assistantbench_judge.yaml \
  --judge-model gpt-4o-mini-2024-07-18
```

Options:
- `--judge-model` — LLM judge model (default: `gpt-4o-mini-2024-07-18`)
- `--judge-provider` — API provider: `openai`, `openrouter`, `vllm` (default: `openai`)
- `--screenshot/--no-screenshot` — Include last screenshot in judge context (default: on)
- `--axtree/--no-axtree` — Include last accessibility tree (default: off)
- `--limit N` — Max tasks to include

### Option B: Use the example configs

The repo includes example configs with template task entries:

- `configs/experiments/arb_webarena_judge.yaml` — WebArena 100 (5 example tasks, 4 agent models)
- `configs/experiments/arb_assistantbench_judge.yaml` — AssistantBench (4 example tasks with WHEN metadata)

Edit the `trajectory_path` entries to point to your actual trajectory JSON files.

### Validate and dry-run

```bash
# Validate the config
agentlens validate-config configs/experiments/arb_webarena_judge.yaml

# Inspect the run plans
agentlens run configs/experiments/arb_webarena_judge.yaml --dry-run
```

### Run the ARB evaluation

```bash
# Run the LLM judge on all trajectories
agentlens arb-evaluate configs/experiments/arb_webarena_judge.yaml --log-actions

# Or use the general run command
agentlens run configs/experiments/arb_webarena_judge.yaml --execute --log-actions
```

This calls the LLM judge for each trajectory and saves results to `agentlens_results/arb_webarena_judge/`. Each evaluated trajectory gets a `trajectory.json` containing:
- 4D scores in `metrics.extra` (`arb_success`, `arb_side_effect`, `arb_optimality`, `arb_looping`)
- Composite score in `metrics.score`
- WHO metadata in `task.extra.who`
- WHEN metadata in `task.extra.when` (AssistantBench only)

### Generate the dashboard

```bash
agentlens arb-dashboard agentlens_results/arb_webarena_judge/ \
  --output agentlens_results/arb_dashboard.html
```

The dashboard includes:
- Summary cards (total evaluations, overall success rate, agent model count)
- **WHO breakdown table** — per-agent-model success rate, mean optimality, side effect rate, looping rate, composite score
- **WHEN breakdown table** — per-temporal-category stats (AssistantBench only)
- **WHO x WHEN heatmap** — cross-tabulated success rates (AssistantBench only)
- Per-task detail table (expandable)

### Score existing ARB judgments

To evaluate ARB's pre-computed judge outputs against human annotations:

```bash
cd agent-reward-bench
python scripts/score_judgments.py \
  --split test \
  --judgments_base_dir "trajectories/judgments/" \
  --results_save_dir "artifacts/"
```

---

## Project Structure

```
AgentLens/
├── configs/experiments/            # YAML experiment configs
│   ├── arb_webarena_judge.yaml     # ARB WebArena benchmark
│   ├── arb_assistantbench_judge.yaml # ARB AssistantBench benchmark
│   └── ...                         # Other experiment configs
├── src/agentlens/
│   ├── cli.py                      # Typer CLI entry point
│   ├── schemas.py                  # Pydantic data models
│   ├── run_plans.py                # Run plan resolution
│   ├── adapters/
│   │   ├── arb_judge.py            # ARB judge adapter
│   │   ├── arb_trajectory_loader.py # ARB trajectory format bridge
│   │   ├── arb_config_generator.py # Auto-generate ARB configs
│   │   ├── browsergym_direct.py    # BrowserGym adapter
│   │   ├── screenshot_react.py     # Screenshot-React adapter
│   │   └── ...
│   ├── validators/
│   │   ├── arb_judge.py            # ARB LLM judge validator
│   │   ├── answers.py              # Answer validation dispatch
│   │   └── ...
│   ├── evaluators/
│   │   ├── arb_dimensions.py       # ARB 4D score extraction + WHO/WHEN grouping
│   │   ├── bundle.py               # Evaluation bundle pipeline
│   │   └── ...
│   └── reports/
│       ├── arb_dashboard.py        # ARB WHO/WHEN dashboard HTML
│       ├── trajectory_viewer.py    # Trajectory viewer HTML
│       └── ...
├── tests/
├── docs/
├── pyproject.toml
└── AGENT.md                        # Agent instructions
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Lint
ruff check src/agentlens tests

# Run tests
pytest tests/ -q

# Validate all YAML configs
python -c "
from pathlib import Path
import yaml
for path in sorted(Path('configs/experiments').glob('*.yaml')):
    yaml.safe_load(path.read_text())
print('all configs valid')
"
```

## References

- [AgentRewardBench paper](https://arxiv.org/abs/2504.08942) — Lù et al., "AgentRewardBench: Evaluating Automatic Evaluations of Web Agent Trajectories"
- [AgentRewardBench GitHub](https://github.com/McGill-NLP/agent-reward-bench)
- [AgentRewardBench Dataset](https://huggingface.co/datasets/McGill-NLP/agent-reward-bench)
- [AgentRewardBench Leaderboard](https://huggingface.co/spaces/McGill-NLP/agent-reward-bench-leaderboard)
