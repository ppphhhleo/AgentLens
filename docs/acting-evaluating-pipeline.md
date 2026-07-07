# Evaluation And Post-Analysis Plan

AgentLens keeps four layers separate:

1. `acting`: model loop, harness tier, tool calls, screenshots, artifacts.
2. `outcome`: finish status, final answer, score, validator result.
3. `trajectory`: process-level counts, errors, loops, actions, observations.
4. `analysis`: Wang-style workflow aggregation and Act-onomy-style behavioral
   tagging/summarization.

## Current Smoke Path

```bash
.venv/bin/agentlens run configs/batches/gpt54_datavoyager_smoke.yaml --dry-run
```

Fresh trajectories are written under:

```text
runs/gpt54_datavoyager_smoke/raw/<timestamp>/trajectories/<run_id>/
```

Published examples are curated separately:

```text
examples/results/gpt54_datavoyager_smoke/
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

LLM-refined summaries are available through method analysis with
`annotation_mode=llm`. In that mode, the deterministic Wang and Act-onomy
outputs are first generated, then an LLM pass replaces the merge layer with
semantic phase names, phase summaries, and LLM-assigned per-turn Act-onomy
labels. The raw response is stored under the method output `llm/` directory.

Use these summaries for inspection, dashboard readability, and qualitative
examples. Do not make them the only primary result: the main validation tables
should still use structured trajectory variables such as success, score,
rounds, tool/action counts, repeated actions, verification/recovery labels,
segment counts, and codebook-label proportions.

These methods should remain post-hoc. They should not mutate the raw trajectory.

## Near-Term Checks

- Verify each trajectory records raw provider tool calls and executed tool
  results.
- Keep screenshots in trajectory folders and use one compact
  `trajectory_viewer.html` per trajectory.
- Do not generate or publish summary-level duplicate trajectory viewers.
- Do not enable intervention during collection unless explicitly requested.
- Add new benchmark tasks only after the task catalog records harness fit,
  expected answer or artifact, and evaluator design.
