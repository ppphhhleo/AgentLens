# Trajectory Processing v0

## Goal

Convert raw AgentLens `trajectory.json` files into a compact workflow-step
representation and behavior labels for initial scalable analysis.

This is a deterministic first pass inspired by two ideas:

- aggregate low-level GUI/computer-use actions into higher-level workflow steps
- annotate each step and sequence with a reusable behavior/challenge codebook

The current implementation is intentionally rule-based. It should create a
stable dataset for inspection before adding LLM-based annotators.

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

## Outputs

| File | Purpose |
|---|---|
| `workflow_steps.jsonl` | One induced workflow step per line, with span, phase, labels, summary, and evidence. |
| `trajectory_summaries.jsonl` | One trajectory-level summary per line. |
| `trajectory_summaries.csv` | Spreadsheet-friendly summary table. |
| `behavior_codebook.json` | Current deterministic labels and definitions. |

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

- Add an LLM annotator over induced workflow steps, not raw actions.
- Add pairwise comparison reports: success vs failure, intervention vs no
  intervention, human vs agent.
- Add screenshot-difference and DOM/rrweb evidence once continuous capture is
  available.
- Separate `human_challenge` vs `agent_challenge` once human runner data exists.
