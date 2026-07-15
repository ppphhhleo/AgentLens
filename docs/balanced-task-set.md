# Balanced Task Set

This is the controlled, standard-versus-grounded collection set. It balances
the four cognitive task types at three canonical tasks each. The two analysis
axes remain explicit per task: `outcome_form` and `evidence_mode`.

Each canonical task has two prompt variants and is intended for two GPT agent
conditions: registered-tool GUI-only and native computer use. One trial is 48
trajectories: `12 tasks x 2 prompts x 2 agents`.

| Type | Task | App | Outcome form | Evidence mode | Outcome evaluator | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| SP | `gimp_add_alpha_transparent` | GIMP | specified | visual/spatial | upstream artifact verifier | ready |
| SP | `calc_text_parse_contacts` | LibreOffice Calc | specified | text/data | upstream artifact verifier | ready after Calc check |
| SP | `libreoffice_writer_grant_proposal_v2` | LibreOffice Writer | specified | text/data | upstream artifact verifier | grounded overlay added; smoke Writer |
| SF | `calc_highest_average_salary` | LibreOffice Calc | specified | text/data | exact final answer | smoke ready |
| SF | `zotero_doi_year_lookup` | Zotero | specified | text/data | exact final answer | smoke ready |
| SF | `wikipedia_birth_order` | Chrome/Wikipedia | specified | text/data | final answer | smoke ready |
| SV | `datavoyager_most_fuel_efficient` | DataVoyager | specified | visual/spatial | final answer | ready |
| SV | `datavoyager_origin_horsepower_range` | DataVoyager | specified | visual/spatial | final answer | ready |
| SV | `datavoyager_europe_hp_gt_100_four_cyl` | DataVoyager | specified | visual/spatial | final answer | ready |
| OP | `godot4_full_enemy_controller` | Godot 4 | open-ended | text/data | upstream artifact verifier | ready |
| OP | `tfplayground_regression_two_datasets` | TensorFlow Playground | open-ended | visual/spatial | final-state screenshot LLM judge | reset smoke required |
| OP | `tfplayground_classification_four_datasets` | TensorFlow Playground | open-ended | visual/spatial | final-state screenshot LLM judge | reset smoke required |

## Prompt Pair Invariants

For every pair, preserve the same initial environment, target deliverable, and
evaluator. The grounded prompt may add navigation or procedural guidance; it
must not reveal an answer, add a requirement, or change the required artifact.

The Writer pair is locally authored because GUI-vs-CLI provides only the
standard task. Its grounded overlay preserves the original environment and all
13 verifier checks.

## TensorFlow Playground

Before every TF trial, navigate a fresh browser profile to the exact bare URL:

```text
https://playground.tensorflow.org/
```

Capture the default initial state before the agent receives control. This setup
is not an agent action. The outcome judge receives only the final screenshot
and scores the visible result: trained state, readable test loss below `0.01`,
and, for classification, a clearly separated boundary. It does **not** score
or require a particular feature selection, layer count, or architecture.

This is a reproducible LLM-judged criterion, not a deterministic TF state
evaluator. Keep the judge model, rubric, and screenshot path in the outcome
record, and label results accordingly.

## Run Components

```text
configs/gui_vs_cli/initial_patch_gpt55_workflow_pairs.yaml
configs/gui_vs_cli/initial_patch_gpt55_writer_pair.yaml
configs/gui_vs_cli/initial_patch_gpt55_sensemaking_pairs.yaml
configs/batches/initial_patch_gpt55_web_sensemaking_visual.yaml
configs/batches/initial_patch_gpt55_tfplayground_design_pairs.yaml
configs/patches/balanced_gpt55_standard_grounded_task_set.yaml
```

Run the Writer and TF no-model launch/reset checks before paid collection. Do
not use the final standard-versus-grounded comparison until both conditions of
a task have passed the same readiness gate.
