# AgentLens

AgentLens collects and analyzes trajectories from agents, humans, and
human-agent workflows in browser, sandbox, and desktop environments.

The repository separates task definitions, execution batches, generated runs,
and curated examples:

```text
AgentLens/
  src/agentlens/            # Runtime, harnesses, tools, evaluators, analysis, reports
  tasks/                    # Benchmark task definitions
  configs/batches/          # Runnable batch YAMLs
  environments/             # Docker and remote environment templates
  runs/                     # Local generated runs; gitignored
  examples/results/         # Small curated published result bundles
  docs/                     # Project docs and archived handover history
  third_party/              # Vendored taxonomies or external assets
  tests/                    # Focused regression tests
```

## Current Working State

The active handover is [handover.md](handover.md). It is intentionally short
and points to current collection commands, open items, and replacement-sensitive
decisions. Older smoke-run and setup history lives in
[docs/archive/trajectory-infra-history.md](docs/archive/trajectory-infra-history.md).

The current follow-up collection plan is:

- DOMSteer DataVoyager T1-T3 standard/grounded comparisons.
- GUI-vs-CLI five-task standard/grounded comparisons.
- Agent styles: AgentLens strict GUI-only tool-call and paper-style
  gui-vs-cli computer agents.

Key configs:

```text
configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml
configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml
```

Validate the DOMSteer GPT-5.5 follow-up config:

```bash
.venv/bin/agentlens validate-config \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml
```

Dry-run the DOMSteer plan:

```bash
.venv/bin/agentlens run \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml \
  --dry-run
```

Check the GUI-vs-CLI five-task config without launching environments:

```bash
PYTHONPATH=src python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml \
  --ready-check-only
```

Generated outputs go under `runs/`. Curated examples that are useful for
inspection or paper discussion live under `examples/results/`.

## OpenAI authentication

OpenAI models use `OPENAI_API_KEY` by default. AgentLens can instead reuse an
existing Codex CLI login globally:

```bash
codex login
export AGENTLENS_OPENAI_AUTH_MODE=codex_oauth
export AGENTLENS_CODEX_MODEL=gpt-5.5  # required by helpers without a model
```

Or select it for one model while preserving the configured model ID exactly:

```yaml
models:
  - id: gpt55
    provider: openai
    name: gpt-5.5
    auth_mode: codex_oauth
```

See [OpenAI providers](docs/openai-providers.md) for supported features and
credential-safety details. API keys remain the recommended/default automation
path.

## Task Catalogs

Desktop task metadata that is not yet in an active batch can live under
`tasks/` without polluting runnable configs.

```text
tasks/domsteer/tasks.jsonl
tasks/gui_vs_cli/tasks.jsonl
tasks/gui_vs_cli/tasks_standard.jsonl
tasks/gui_vs_cli/tasks_grounding.jsonl
tasks/gui_vs_cli/task_pairs.jsonl
tasks/gui_vs_cli/high_delta_prompt_pairs.md
```

DOMSteer T1-T3 have runnable standard and grounded DataVoyager task YAMLs with
deterministic final-answer validators. GUI-vs-CLI contains 440 standard desktop
tasks and 176 grounded-prompt matched pairs; use
`tasks/gui_vs_cli/high_delta_prompt_pairs.md` when selecting grounded-vs-standard
tasks for behavioral claims.

## Curated Examples

Published example bundles:

```text
examples/results/gpt54_datavoyager_smoke/
examples/results/domsteer_t1_t3_gui_vs_cli_chatgpt_smoke/
```

The GPT-5.4 DataVoyager example contains one successful trajectory for each
basic harness tier:

- `browser`
- `sandbox`
- `nogui`

Each trajectory folder contains the canonical `trajectory.json`, a compact
`trajectory_viewer.html`, and screenshots.

## Key Docs

- [Agent structures and tool tiers](docs/agent-structures-and-tool-tiers.md)
- [Evaluation and post-analysis plan](docs/acting-evaluating-pipeline.md)
- [Trajectory collection task catalog](docs/trajectory-collection-tasks.md)
- [OpenAI provider authentication](docs/openai-providers.md)
- [Local browser setup](docs/local-browser-evaluation-setup.md)
- [Historical infrastructure archive](docs/archive/trajectory-infra-history.md)
