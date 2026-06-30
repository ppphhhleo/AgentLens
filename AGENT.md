# AgentLens Agent Instructions

AgentLens is an experimental harness for collecting and analyzing agent, human,
and human-agent trajectories in browser, sandbox, and virtual-desktop tasks.

Read `README.md` first, then `handover.md` for the current run status. Update
`handover.md` whenever you replace a harness, task source, evaluator, Docker
image, analysis pipeline, or batch/result layout.

## Project Priorities

- Capture first: preserve screenshots, actions/tool calls, model messages, tool
  outputs, artifacts, and run metadata.
- Keep tasks, batch configs, local runs, curated examples, evaluators, and
  post-hoc analysis separate.
- Keep model backend separate from harness tier:
  - model backend: OpenAI, Anthropic, Gemini, etc.
  - harness tier: `browser_only`, `full_sandbox`, `desktop_gui_only`,
    `no_gui_tool_only`.
- Standard collection runs must not enable intervention unless the user
  explicitly asks for it.
- Generated runs belong in `runs/` and are gitignored. Publish only small,
  curated examples under `examples/results/`.

## Important Paths

- `src/agentlens/`: runtime, harnesses, tools, evaluators, analysis, reports.
- `tasks/`: benchmark task definitions.
- `configs/batches/`: runnable batch YAMLs.
- `runs/`: local generated outputs; gitignored.
- `examples/results/`: curated result bundles that are intentionally tracked.
- `docs/trajectory-collection-tasks.md`: task catalog and candidates.
- `docs/acting-evaluating-pipeline.md`: evaluator and post-analysis plan.
- `environments/README.md`: Docker/E2B backend notes.

## Current Batch

```bash
configs/batches/gpt54_datavoyager_smoke.yaml
```

Run IDs:

- `dv_most_fuel__gpt54__browser`
- `dv_most_fuel__gpt54__sandbox`
- `dv_most_fuel__gpt54__nogui`

## Validation Commands

```bash
.venv/bin/agentlens validate-config configs/batches/gpt54_datavoyager_smoke.yaml

.venv/bin/agentlens run configs/batches/gpt54_datavoyager_smoke.yaml --dry-run

.venv/bin/python -m ruff check src/agentlens tests
```

Focused tests:

```bash
.venv/bin/python -m pytest tests/test_openai_tool_adapter.py tests/test_anthropic_tool_adapter.py -q
```

## Smoke Run

```bash
.venv/bin/agentlens run configs/batches/gpt54_datavoyager_smoke.yaml \
  --execute \
  --log-actions
```

Regenerate a per-trajectory viewer:

```bash
.venv/bin/agentlens trajectory-viewer path/to/trajectory.json
```

## Result Layout

Local generated runs:

```text
runs/<batch_name>/
  raw/
    <timestamp>/
      trajectories/<run_id>/
        trajectory.json
        trajectory_viewer.html
        screenshots/
  summary/
  analysis/
  dashboard/
```

Curated examples:

```text
examples/results/<example_name>/
  README.md
  batch_config.yaml
  dashboard/
  trajectories/
```

## Coding Notes

- Use `rg` for search.
- Use `apply_patch` for manual file edits.
- Do not commit generated `runs/` output.
- Do not add metadata-only candidate tasks to active batch YAMLs until their
  image/assets/evaluator are available.
- Browser coordinates are browser viewport coordinates.
- Desktop coordinates are virtual desktop screen coordinates.
