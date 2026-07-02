# Trajectory Collection Task Catalog

This catalog tracks trajectory-collection tasks by benchmark, type, and
application. Runnable task definitions live under `tasks/`; runnable experiment
matrices live under `configs/batches/`.

Current active batch:

```text
configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml
```

Agent structures and tool-tier definitions:

```text
docs/agent-structures-and-tool-tiers.md
```

Current active tasks:

```text
tasks/domsteer/datavoyager_most_fuel_efficient/task.yaml
tasks/domsteer/datavoyager_origin_horsepower_range/task.yaml
tasks/domsteer/datavoyager_europe_hp_gt_100_four_cyl/task.yaml
```

Task catalogs:

```text
tasks/domsteer/tasks.jsonl
tasks/gui_vs_cli/tasks.jsonl
```

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
| TheAgentCompany-style | Workplace analytics / browser + code + files | Browser/files/Python | TAC-shaped local smoke | Not active in current config; next integration target. | Task-specific artifact or answer check |
| GUI-vs-CLI | Desktop applications | 18 apps | `tasks/gui_vs_cli/tasks.jsonl` | Full 440-task metadata list imported; not active in current config. | Original verifier commands preserved, bridge pending |
| Workflow-GYM-style | Desktop data analysis | Weka | Weka Iris smoke | Not active in current config. | Mock/manual until artifact evaluator exists |
| Workflow-GYM-style | Desktop visual/spatial authoring | Blender | Blender cube smoke | Not active in current config. | Mock/manual until artifact evaluator exists |

## GUI-vs-CLI Imported Catalog

Tracked source:

```text
tasks/gui_vs_cli/tasks.jsonl
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
| `grounded_prompt` | 0 |

App counts:

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

## DOMSteer Catalog

Tracked source:

```text
tasks/domsteer/tasks.jsonl
```

The catalog currently has the eight DOMSteer experiment tasks from the
user-study setup:

| Record Type | Count | Use |
| --- | ---: | --- |
| `experiment_task` | 8 | T1-T3 are answer-verifiable; T4-T8 keep verifier pending because no exact answer is provided. |

Applications covered:

| Application | Records |
| --- | ---: |
| DataVoyager 2 | 4 |
| TensorFlow Playground | 4 |

## Candidate Tasks

| Benchmark | Type | Application | Candidate Task | Harness Fit | Missing |
| --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics | DataVoyager | 8-cylinder car characteristics | `browser_only`, `full_sandbox`, `no_gui_tool_only` | Needs interpretation rubric. |
| DOMSteer | Interactive ML | TensorFlow Playground | Discretize, misclassification, regression/classification design tasks | `browser_only`, `full_sandbox`; no-GUI is weak unless DOM/state tools are added. | Reproducible initial state and rubric/state evaluator. |
| TheAgentCompany | Occupational workplace analytics | Browser + docs + shell/code | Real benchmark task | Mostly `full_sandbox`; no-GUI ablations where artifacts are accessible. | Real task adapter, data mount, evaluator. |
| GUI-vs-CLI | Desktop data/spreadsheet analysis | LibreOffice Calc | Budget multi-sheet workbook setup | `desktop_gui_only`, `full_sandbox`, possible CLI/no-GUI with skills. | Runnable image, seed `budget.xlsx`, verifier bridge. |
| GUI-vs-CLI | Desktop visual/spatial workflows | FreeCAD / CloudCompare / GIMP | Geometry, point-cloud, and image-editing tasks | `desktop_gui_only`, `full_sandbox`, possible CLI/no-GUI with app-specific skills. | Select subset, import assets, verifier bridge. |
| Workflow-GYM | Visual/spatial desktop GUI workflow | Unity | Scene/project creation or modification | `desktop_gui_only`, `full_sandbox`; possible batch-mode no-GUI. | Reliable image, licensing/login, launch command, evaluator. |
| Workflow-GYM | Visual/spatial desktop GUI workflow | Blender | Create scene and save `.blend` artifact | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only`. | Concrete objective and Blender Python evaluator. |
| Workflow-GYM | Data analysis desktop GUI | Weka | Run model and report accuracy/confusion matrix | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only`. | Dataset, concrete answer, artifact/state evaluator. |

## Collection Rule

Add tasks back one at a time. Each task should have a task file, clear harness
fit, expected answer or artifact, evaluator design, and run ID naming convention
before larger batch collection.
