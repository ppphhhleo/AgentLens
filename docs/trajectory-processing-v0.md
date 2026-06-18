# Trajectory Processing v0

## Goal

Convert raw AgentLens `trajectory.json` files into a compact workflow-step
representation and behavior labels for initial scalable analysis.

This is a deterministic first pass inspired by two ideas:

- aggregate low-level GUI/computer-use actions into higher-level workflow steps
- annotate each step and sequence with a reusable behavior/challenge codebook

The current implementation is intentionally rule-based. It should create a
stable dataset for inspection before adding LLM-based annotators.

The processor now exposes two separable method views over the same
`trajectory.json` files:

- **Wang-style workflow induction**: structure-first analysis,
  `action nodes -> state segments -> workflow steps`.
- **Act-onomy-style codebook aggregation**: codebook-first analysis,
  `turns -> taxonomy assignments -> sessions/profile`.

These are intentionally not collapsed into one output. The point is to compare
whether a trajectory difference is primarily temporal/workflow-level,
action-semantics-level, or visible only through the project-specific behavior
labels below.

## Command

```bash
agentlens process-trajectories agentlens_results \
  --output-dir agentlens_results/trajectory_processing/local_v0 \
  --repeat-threshold 5
```

Multiple inputs are allowed:

```bash
agentlens process-trajectories path/to/run_a path/to/run_b/trajectory.json \
  --output-dir agentlens_results/trajectory_processing/study_v0
```

For a side-by-side HTML report on one trajectory:

```bash
agentlens compare-trajectory-methods path/to/trajectory.json \
  --output-dir agentlens_results/method_comparison/example_run
```

## Outputs

| File | Purpose |
|---|---|
| `workflow_steps.jsonl` | One induced workflow step per line, with span, phase, labels, summary, and evidence. |
| `trajectory_summaries.jsonl` | One trajectory-level summary per line. |
| `trajectory_summaries.csv` | Spreadsheet-friendly summary table. |
| `behavior_codebook.json` | Current deterministic labels and definitions. |
| `methods/canonical_events.jsonl` | AgentLens `trajectory.json` converted into action-bearing canonical turns. |
| `methods/wang_action_nodes.jsonl` | Wang-style low-level action nodes with before/after screenshots and state-diff scores. |
| `methods/wang_state_segments.jsonl` | Deterministic state/phase segments before semantic workflow merging. |
| `methods/wang_workflow_steps.jsonl` | Wang-style final workflow steps. |
| `methods/actonomy_annotations.jsonl` | Act-onomy taxonomy assignments for each turn/action. |
| `methods/actonomy_sessions.jsonl` | Aggregated Act-onomy-coded sessions. |
| `methods/actonomy_profiles.jsonl` | Per-trajectory behavior profiles from Act-onomy counts. |
| `method_comparison.html` | Single-run side-by-side HTML when using `compare-trajectory-methods`. |

## Workflow Step Induction

Raw events are first grouped by `step_index`. Each model/action step becomes a
micro-step. Consecutive micro-steps are aggregated when they share the same
phase:

- `observe`
- `inspect_or_orient`
- `navigate`
- `gui_manipulate`
- `external_search`
- `programmatic_work`
- `finalize`
- `meta`

Hard breaks occur at final answers, errors, interventions, and repeated-action
loop detections.

## Wang-Style Method

Implementation: `src/agentlens/analysis/wang_workflow.py`.

The adapter mirrors the public `workflow-induction-toolkit` shape without
shelling out to it:

1. Convert AgentLens steps to action nodes with `action`, `goal`, `state.before`,
   `state.after`, and `state.diff_score`.
2. Segment by phase and screenshot state transitions.
3. Merge state segments into deterministic workflow steps.

The current semantic merge is rule-based. This is a conservative replacement
for the toolkit's LLM semantic merge so we can inspect and validate the
intermediate files before adding model calls.

## Act-onomy-Style Method

Implementation: `src/agentlens/analysis/actonomy.py`.

The adapter uses a pinned Act-onomy taxonomy snapshot in
`third_party/actonomy/`, licensed CC BY 4.0. It does **not** execute the
upstream Claude Code skill. Instead, it deterministically maps AgentLens action
types to Act-onomy codes and then aggregates coded turns into sessions.

This is intentionally weaker than the upstream quote-level LLM annotation, but
it is reproducible and suitable for scalable first-pass comparison. Later we
can add an LLM quote/span annotator as a separate optional layer.

## Behavior Labels

Current labels:

- `programmatic_approach`
- `ui_centric_exploration`
- `direct_gui_manipulation`
- `verification_attempt`
- `artifact_creation`
- `repeated_action_loop`
- `tool_or_action_error`
- `intervention_triggered`
- `final_answer`
- `final_answer_without_verification`
- `recovery_attempt`
- `no_final_answer`

Each label is evidence-based and derived from action types, tool-call results,
artifact diffs, action errors, intervention events, and simple intent terms in
model thoughts.

## Next Improvements

- Add an LLM annotator over induced workflow steps and Act-onomy turn surfaces,
  not raw trajectories.
- Add pairwise comparison reports: success vs failure, intervention vs no
  intervention, human vs agent.
- Add screenshot-difference and DOM/rrweb evidence once continuous capture is
  available.
- Separate `human_challenge` vs `agent_challenge` once human runner data exists.
