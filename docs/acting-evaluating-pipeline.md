# Evaluation And Post-Analysis Plan

AgentLens should keep four layers separate:

1. `acting`: model loop, harness tier, tool calls, screenshots, and artifacts.
2. `outcome`: task finish status, final answer, score, and validator result.
3. `trajectory`: process-level counts, errors, loops, actions, observations.
4. `analysis`: Wang-style workflow aggregation and Act-onomy-style behavioral
   tagging/summarization.

## Current Smoke Path

Active config:

```bash
.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54__browser --dry-run

.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54__sandbox --dry-run

.venv/bin/agentlens run configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml \
  --run-id dv_most_fuel__gpt54__nogui --dry-run
```

Fresh trajectories should go under:

```text
agentlens_results/domsteer_datavoyager_toolcall_matrix/raw/<timestamp>/trajectories/<run_id>/
```

Each batch should keep a copy of the YAML used for that batch when possible:

```text
agentlens_results/<batch_name>/
  batch_config.yaml
  raw/
  dashboard/
  analysis/
```

## Outcome Evaluation

For the current DataVoyager smoke task:

| Field | Value |
| --- | --- |
| Validator | `final_answer` |
| Expected answer | `Mazda GLC` |
| Match rule | `contains` |

Outcome evaluation is necessary but not enough. It tells whether a trajectory
finished the task, but it does not explain why the run succeeded, failed, or
used a different strategy.

## Trajectory Analysis

Use the same raw trajectory as input to multiple post-hoc methods:

| Method | Input | Output | Purpose |
| --- | --- | --- | --- |
| Wang-style workflow aggregation | screenshots, tool calls, actions, observations | workflow segments / phases | Coarse process structure and stage comparison. |
| Act-onomy-style behavior coding | per-turn observation/thought/action/tool data | cognitive/action labels plus phase summaries | Behavioral profile and codebook-driven comparison. |

These methods should remain post-hoc. They should not mutate the raw trajectory.

## Near-Term Checks

- Verify each trajectory records raw provider tool calls and executed tool
  results.
- Keep screenshots in trajectory folders and use compact HTML viewers for
  inspection.
- Do not enable intervention during collection unless explicitly requested.
- Treat manual/mock desktop evaluators as placeholders until artifact/state
  validators are implemented.
- Add new benchmark tasks only after the task catalog records harness fit,
  expected answer or artifact, and evaluator design.
