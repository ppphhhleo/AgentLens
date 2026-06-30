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
  docs/                     # Project planning docs
  third_party/              # Vendored taxonomies or external assets
  tests/                    # Focused regression tests
```

## Current Smoke Batch

Validate the active GPT-5.4 DataVoyager smoke batch:

```bash
.venv/bin/agentlens validate-config configs/batches/gpt54_datavoyager_smoke.yaml
```

Dry-run all three harness tiers:

```bash
.venv/bin/agentlens run configs/batches/gpt54_datavoyager_smoke.yaml --dry-run
```

Run the batch:

```bash
.venv/bin/agentlens run configs/batches/gpt54_datavoyager_smoke.yaml \
  --execute \
  --log-actions
```

Generated outputs go under `runs/`. Curated examples that are useful for
inspection or paper discussion live under `examples/results/`.

## Curated Example

The current published example is:

```text
examples/results/gpt54_datavoyager_smoke/
```

It contains one successful trajectory for each harness tier:

- `browser`
- `sandbox`
- `nogui`

Each trajectory folder contains the canonical `trajectory.json`, a compact
`trajectory_viewer.html`, and screenshots.
