# Trajectory Collection Task Catalog

This catalog tracks trajectory-collection tasks by benchmark, type, and
application. Runnable task definitions live under `tasks/`; runnable experiment
matrices live under `configs/batches/`.

Next runnable expansion batch:

```text
configs/gui_vs_cli/zoom_zotero_obsidian_standard_grounded_smoke.yaml
configs/gui_vs_cli/authored_sensemaking_standard_grounded_smoke.yaml
```

Agent structures and tool-tier definitions:

```text
docs/agent-structures-and-tool-tiers.md
```

Prepared task configurations:

```text
configs/gui_vs_cli/grounded_vs_standard_smoke.yaml
configs/gui_vs_cli/zoom_zotero_obsidian_standard_grounded_smoke.yaml
configs/batches/custom_web_sf_gpt55_smoke.yaml
configs/browsergym/webarena_reddit_shopping_gpt55_smoke.yaml
tasks/domsteer/datavoyager_most_fuel_efficient/task.yaml
tasks/domsteer/datavoyager_origin_horsepower_range/task.yaml
tasks/domsteer/datavoyager_europe_hp_gt_100_four_cyl/task.yaml
tasks/domsteer/tfplayground_discretize_effect/task.yaml
tasks/domsteer/tfplayground_misclassified_point/task.yaml
tasks/domsteer/tfplayground_regression_two_datasets/task.yaml
tasks/domsteer/tfplayground_regression_two_datasets_grounded/task.yaml
tasks/domsteer/tfplayground_classification_four_datasets/task.yaml
tasks/domsteer/tfplayground_classification_four_datasets_grounded/task.yaml
```

Near-term rollout priority:

1. GUI-vs-CLI desktop/workflow tasks.
2. DOMSteer TensorFlow Playground tasks for interactive visual ML behavior.
3. Hosted WebArena and TheAgentCompany after URLs/adapters and success criteria
   are settled.

Task catalogs:

```text
tasks/domsteer/tasks.jsonl
tasks/gui_vs_cli/tasks.jsonl
tasks/gui_vs_cli/high_delta_prompt_pairs.md
tasks/webarena/hosted_shopping_forum_tasks.jsonl
```

Detailed task option sampling matrix:

```text
docs/task-candidate-matrix.md
```

Canonical machine-readable registry:

```text
tasks/task_inventory/collection_task_registry.jsonl
```

The registry has one record per canonical task, not per prompt variant. It
records the cognitive task type (`SP`, `SF`, `SV`, `OP`),
the app, prompt-pair
availability and delta strength, visual-decoding requirement, available
harnesses, evaluator state, and rollout wave. The app does not determine the
task type: a specified draw.io edit is `SP`, while a chart-reading answer task
is `SV`.

The registry also records three independent design axes: `outcome_form`
(`specified` or `open_ended`), `evidence_mode` (`text_data` or
`visual_spatial`), and `procedure_variant` (the prompt-pair design available
for that canonical task). Run metadata remains authoritative for the specific
prompt used in one trajectory (`standard` or `grounded`).

## Initial GPT Collection Patch

The first controlled GPT-5.5 patch is coordinated through:

```text
configs/patches/initial_gpt55_gui_collection.yaml
```

| Component | Config | Canonical Tasks | Trajectories Per Trial |
| --- | --- | --- | ---: |
| Desktop workflows | `configs/gui_vs_cli/initial_patch_gpt55_workflow_pairs.yaml` | GIMP alpha edit, Calc contact parsing, Godot controller | 12 |
| Desktop sensemaking | `configs/gui_vs_cli/initial_patch_gpt55_sensemaking_pairs.yaml` | Calc salary, Zotero DOI/year | 8 |
| Web sensemaking/analytics | `configs/batches/initial_patch_gpt55_web_sensemaking_visual.yaml` | Wikipedia birth order, DataVoyager T1-T3 | 16 |

Each component compares standard versus grounded prompts and GPT GUI-only
registered tools versus GPT native computer use, for 36 trajectories in one
trial. The current desktop app-launch check passed for GIMP, draw.io, Godot,
Calc, and Zotero on the AWS GUI-vs-CLI image. This is environment readiness,
not agent-success evidence. Draw.io remains a gated addition until a real
trajectory passes.

For the GUI-only-first pass, use the `gui_only_subset` in the manifest. It
contains 18 GPT-5.5 Codex-OAuth trajectories and uses
`configs/batches/initial_patch_gpt55_gui_only_web_sensemaking_visual.yaml` for
the web/DataVoyager component; it never schedules native computer-use calls.

## Collection Waves

| Wave | Purpose | Tasks | Run only when |
| --- | --- | --- | --- |
| 1 | Establish a controlled four-type pilot. | DataVoyager T1-T3 (`SV`), Wikipedia birth-order plus Calc/Zotero lookup (`SF`), GIMP/draw.io (`SP`), Godot (`OP`). | The selected agent/harness passes one no-model readiness check. |
| 2 | Broaden the application mix while retaining paired prompts. | Zoom, Zotero, Obsidian. | Each app starts from the intended seed state and its original verifier passes a manual control run. |
| 3 | Add genuinely visual controls and creative tasks. | TensorFlow Playground T5-T8. | A reproducible initial state and task-specific rubric/state evaluator exist. |
| 4 | Add web information-seeking and visual-web tasks. | WebArena/VisualWebArena shopping and Reddit tasks. | Hosted URLs, credentials, and BrowserGym reward checks are configured. |

For a standard-vs-grounded comparison, include only task pairs with
`prompt_delta_strength >= 2`. Retain delta-0 tasks as `SP` anchors, but
do not interpret them as evidence about prompt grounding.

## Harness Tiers

| Tier | Meaning | Main Use |
| --- | --- | --- |
| `browser_only` | Browser screenshot plus browser actions only. | Web GUI behavior and visual analytics trajectories. |
| `full_sandbox` | Browser GUI plus code, shell, web search, and file tools in the sandbox. | Mixed GUI/programmatic workflows and workplace-style tasks. |
| `desktop_gui_only` | Virtual desktop screenshot plus mouse/keyboard actions, without shell/code tools. | Human-like desktop application behavior comparisons. |
| `desktop_no_gui_tool_only` | Programmatic app/file tools without screenshots or GUI actions. | Desktop task ablations when a batch/API mode exists. |
| `no_gui_tool_only` | Code, shell, search, and file tools only. | Programmatic baselines for data tasks. |

For analysis and reporting, distinguish four broader experimental conditions:

| Condition | Meaning | Use |
| --- | --- | --- |
| `gui_only` | The agent sees screenshots and can use only direct manipulation tools. | Main visual/GUI behavior comparison. |
| `cli_anything_no_visual` | The agent has no screenshots and no GUI actions; it uses the gui-vs-cli paper's CLI-Anything style runner inside the task image. | Use for gui-vs-cli workflow tasks. Do not apply this label to DOMSteer unless a DOMSteer-specific CLI-Anything harness is built. |
| `programmatic_no_visual` | The agent has no screenshots and no GUI actions, but uses AgentLens no-GUI tools or benchmark-specific scripts. | DOMSteer and data-analysis baselines. |
| `full_sandbox` | The agent can use both GUI and programmatic tools. | Upper-bound / occupational-style mixed capability setting. |

Within a task family, keep the environment fixed across conditions:

- same Docker image or VM base image
- same screen size and coordinate frame
- same start URL/app launcher
- same seed files and mounted paths
- same evaluator and expected-answer/artifact rule

## Ready Or Smoke-Tested

| Benchmark | Type | Application | Task ID | Current Status | Evaluator |
| --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_most_fuel_efficient` | In 30-run GPT-5.4/Claude smoke batch. | `final_answer`, contains `Mazda GLC` |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_origin_horsepower_range` | In 30-run GPT-5.4/Claude smoke batch. | `final_answer`, contains `USA` |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_europe_hp_gt_100_four_cyl` | In 30-run GPT-5.4/Claude smoke batch. | `final_answer`, exact number `10` |
| Custom web | Text/data sensemaking | Chrome / Wikipedia | `wikipedia_birth_order` | Standard + grounded task YAMLs and GPT-5.5 batch config prepared; not yet run. | `final_answer`, contains `Ada Lovelace` |
| AgentLens-authored on GUI-vs-CLI seeds | Text/data sensemaking | Calc / Zotero | `calc_highest_average_salary`, `zotero_doi_year_lookup` | Standard + grounded answer tasks prepared; upstream seed artifacts remain unchanged. | Exact final answer (`Engineering`, `2018`) |
| GUI-vs-CLI | Occupational/text workflows | Zoom / Zotero / Obsidian | `zoom_mute_mic_on_join`, `zotero_add_note_to_item`, `obsidian_add_links_to_existing` | Config added; ready-check requires `agentlens-gui-vs-cli-runtime:latest` image. | Original gui-vs-cli verifiers |
| DOMSteer | Interactive visual ML | TensorFlow Playground | `tfplayground_discretize_effect`, `tfplayground_misclassified_point`, `tfplayground_regression_two_datasets`, `tfplayground_classification_four_datasets` | Task YAMLs added for trajectory collection. | T5/T6 remain manual; T7/T8 use a final-state screenshot LLM judge after reset smoke. |
| TheAgentCompany-style | Workplace analytics / browser + code + files | Browser/files/Python | TAC-shaped local smoke | Not active in current config; next integration target. | Task-specific artifact or answer check |
| GUI-vs-CLI | Desktop applications | 18 apps | `tasks/gui_vs_cli/tasks.jsonl` | Full 440-task metadata list imported; not active in current config. | Original verifier commands preserved, bridge requires verification |
| Hosted WebArena | Web shopping / forum | Amazon-like / Reddit-like hosted sites | `webarena_shopping_basic_requires_hosted_url`, `webarena_forum_basic_requires_hosted_url` | Records added; require hosted URLs and success criteria. | Requires final-answer/state evaluator |
| Workflow-GYM-style | Desktop data analysis | Weka | Weka Iris smoke | Not active in current config. | Mock/manual until artifact evaluator exists |
| Workflow-GYM-style | Desktop visual/spatial authoring | Blender | Blender cube smoke | Not active in current config. | Mock/manual until artifact evaluator exists |

## GUI-vs-CLI Imported Catalog

Tracked source:

```text
tasks/gui_vs_cli/tasks.jsonl            # standard tasks, backward-compatible path
tasks/gui_vs_cli/tasks_standard.jsonl   # standard tasks
tasks/gui_vs_cli/tasks_grounding.jsonl  # grounded-prompt tasks
tasks/gui_vs_cli/task_pairs.jsonl       # matched standard/grounded pairs
```

Task source type is inferred from `github_task_path`:

| Prefix | Source Type | Meaning |
| --- | --- | --- |
| `task_generator/tasks/` | `standard` | Standard gui-vs-cli task prompt. |
| `task_generator/tasks_grounding/` | `grounded_prompt` | Grounded-prompt variant; keep separate from standard tasks when sampling or reporting. |

Current imported catalog status:

| Source Type | Count |
| --- | ---: |
| `standard` | 440 |
| `grounded_prompt` | 178 |

The original imported set contains 176 grounded-prompt tasks, each with a
corresponding standard task with the same
`paired_task_id`/`id`; their base `task` text is identical and the grounded
variant adds `task_grounding`. Use `task_pairs.jsonl` for matched standard vs
grounded experiments.

AgentLens additionally includes two curated grounded prompts for standard-only
apps: `zoom_mute_mic_on_join` and `obsidian_add_links_to_existing`. They are
marked with `metadata.curated_by: agentlens`.

For grounded-vs-standard behavior analysis, do not sample uniformly from all
176 grounded tasks. Many grounded prompts are near-identical to their standard
task text. Use `tasks/gui_vs_cli/high_delta_prompt_pairs.md` for pairs where the
grounded prompt adds meaningful procedural guidance.

Standard task app counts:

| Application | Tasks |
| --- | ---: |
| RenderDoc | 41 |
| LibreOffice Writer | 39 |
| LibreOffice Calc | 36 |
| LibreOffice Impress | 32 |
| FreeCAD | 26 |
| Zotero | 26 |
| MuseScore 3 | 25 |
| Audacity | 24 |
| CloudCompare | 23 |
| Obsidian | 23 |
| Shotcut | 20 |
| Zoom | 20 |
| GIMP | 19 |
| Godot 4 | 19 |
| OBS Studio | 18 |
| Chrome | 17 |
| Krita | 17 |
| draw.io | 15 |

Grounded-prompt task app counts:

| Application | Tasks |
| --- | ---: |
| LibreOffice Calc | 26 |
| FreeCAD | 25 |
| Audacity | 24 |
| CloudCompare | 20 |
| Zotero | 19 |
| draw.io | 15 |
| GIMP | 12 |
| OBS Studio | 9 |
| Krita | 8 |
| LibreOffice Impress | 7 |
| RenderDoc | 5 |
| Chrome | 4 |
| Godot 4 | 1 |
| LibreOffice Writer | 1 |
| Zoom | 1 AgentLens-curated |
| Obsidian | 1 AgentLens-curated |

## Hosted WebArena Catalog

Tracked placeholder source:

```text
tasks/webarena/hosted_shopping_forum_tasks.jsonl
```

This is a lightweight hosted-site path, not full BrowserGym/WebArena
environment control. Treat hosted WebArena tasks like DOMSteer-style web tasks:
fixed URL, task prompt, screenshot/action trajectory capture, and a lightweight
final-answer or final-state evaluator. BrowserGym reward integration can be
added later after hosted-task capture is stable.

Pending records:

| Domain | App Label | Status | Needed Before Running |
| --- | --- | --- | --- |
| Shopping | `shopping_amazon_like` | Requires hosted URL | hosted URL, task prompt, success criteria |
| Forum | `reddit_like_forum` | Requires hosted URL | hosted URL, task prompt, success criteria |

## DOMSteer Catalog

Tracked source:

```text
tasks/domsteer/tasks.jsonl
```

The catalog currently has the eight DOMSteer experiment tasks from the
user-study setup:

| Record Type | Count | Use |
| --- | ---: | --- |
| `experiment_task` | 8 | T1-T3 are answer-verifiable; T4-T8 keep verifier required because no exact answer is provided. |

Applications covered:

| Application | Records |
| --- | ---: |
| DataVoyager 2 | 4 |
| TensorFlow Playground | 4 |

Collection-ready TensorFlow Playground task YAMLs:

| Task ID | Simple Type | Evaluation Status |
| --- | --- | --- |
| `tfplayground_discretize_effect` | `SV` interactive ML | Manual/rubric required |
| `tfplayground_misclassified_point` | `SV` interactive ML | Manual/rubric required |
| `tfplayground_regression_two_datasets` | `OP` objective network design | Final-state screenshot LLM judge; fresh-profile reset smoke required |
| `tfplayground_classification_four_datasets` | `OP` objective network design | Final-state screenshot LLM judge; fresh-profile reset smoke required |

## Candidate Tasks

| Benchmark | Type | Application | Candidate Task | Harness Fit | Missing |
| --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics | DataVoyager | 8-cylinder car characteristics | `browser_only`, `full_sandbox`, `no_gui_tool_only` | Needs interpretation rubric. |
| DOMSteer | Interactive ML | TensorFlow Playground | Discretize, misclassification, regression/classification design tasks | `browser_only`, `full_sandbox`; no-GUI is weak unless DOM/state tools are added. | Reproducible initial state and rubric/state evaluator. |
| TheAgentCompany | Occupational workplace analytics | Browser + docs + shell/code | Real benchmark task | Mostly `full_sandbox`; no-GUI ablations where artifacts are accessible. | Later expansion after GUI-vs-CLI and DOMSteer TensorFlow; real task adapter, data mount, evaluator. |
| GUI-vs-CLI | Desktop data/spreadsheet analysis | LibreOffice Calc | Budget multi-sheet workbook setup | `desktop_gui_only`, `full_sandbox`, possible CLI/no-GUI with skills. | Runnable image, seed `budget.xlsx`, verifier bridge. |
| GUI-vs-CLI | Desktop visual/spreadsheet analysis | LibreOffice Calc | Conditional-formatting sales heatmap | `desktop_gui_only`, `full_sandbox`, possible CLI/no-GUI with skills. | Preferred Calc task when visible plot/visual encoding involvement is required. |
| GUI-vs-CLI | Desktop visual/spatial workflows | FreeCAD / CloudCompare / GIMP | Geometry, point-cloud, and image-editing tasks | `desktop_gui_only`, `full_sandbox`, possible CLI/no-GUI with app-specific skills. | Select subset, import assets, verifier bridge. |
| Workflow-GYM | Visual/spatial desktop GUI workflow | Unity | Scene/project creation or modification | `desktop_gui_only`, `full_sandbox`; possible batch-mode no-GUI. | Reliable image, licensing/login, launch command, evaluator. |
| Workflow-GYM | Visual/spatial desktop GUI workflow | Blender | Create scene and save `.blend` artifact | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only`. | Concrete objective and Blender Python evaluator. |
| Workflow-GYM | Data analysis desktop GUI | Weka | Run model and report accuracy/confusion matrix | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only`. | Dataset, concrete answer, artifact/state evaluator. |

## Collection Rule

Add tasks back one at a time. Each task should have a task file, clear harness
fit, expected answer or artifact, evaluator design, and run ID naming convention
before larger batch collection.
