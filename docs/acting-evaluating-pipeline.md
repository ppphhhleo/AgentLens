# Evaluation And Post-Analysis Plan

AgentLens keeps four layers separate:

1. `acting`: model loop, harness tier, tool calls, screenshots, artifacts.
2. `outcome`: finish status, final answer, score, validator result.
3. `trajectory`: process-level counts, errors, loops, actions, observations.
4. `analysis`: Wang-style workflow aggregation and Act-onomy-style behavioral
   tagging/summarization.

## Current Collection Paths

```bash
.venv/bin/agentlens run \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml \
  --dry-run
```

Fresh trajectories are written under:

```text
runs/<batch_id>/raw/<timestamp>/trajectories/<case_id>/
```

Published examples are curated separately:

```text
examples/results/gpt54_datavoyager_smoke/
examples/results/domsteer_t1_t3_gui_vs_cli_chatgpt_smoke/
```

## Outcome Evaluation

For the answer-verifiable DOMSteer DataVoyager tasks:

| Task | Validator | Expected |
| --- | --- | --- |
| `datavoyager_most_fuel_efficient` | `final_answer` / contains | `Mazda GLC` |
| `datavoyager_origin_horsepower_range` | `final_answer` / contains | `USA` |
| `datavoyager_europe_hp_gt_100_four_cyl` | `final_answer` / exact number | `10` |

Outcome evaluation is necessary but not enough. It tells whether a trajectory
finished the task, but it does not explain why the run succeeded, failed, or
used a different strategy.

## Trajectory Analysis

Use the same raw trajectory as input to multiple post-hoc methods:

| Method | Input | Output | Purpose |
| --- | --- | --- | --- |
| Wang-style workflow aggregation | screenshots, tool calls, actions, observations | workflow segments / phases | Coarse process structure and stage comparison. |
| Act-onomy-style behavior coding | per-turn observation/thought/action/tool data | cognitive/action labels plus phase summaries | Behavioral profile and codebook-driven comparison. |

For behavior-code analysis, normalize before aggregating across conditions:

1. For each trajectory, compute each behavior's percentage of that trajectory's
   behavior episodes.
2. Average those within-trajectory percentages by condition, agent type, prompt
   style, task, or success group.
3. Report absolute behavior episode counts separately as an effort/trajectory
   length signal, not as the primary comparison.

This avoids making longer or more failure-prone trajectories look behaviorally
dominant only because they contain more annotated episodes.

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
- Stratify grounded-vs-standard analysis by prompt-delta strength; do not pool
  weak prompt-delta pairs with high-delta pairs without flagging it.
