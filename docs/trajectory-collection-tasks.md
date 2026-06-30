# Trajectory Collection Task Catalog

This catalog tracks trajectory-collection tasks by benchmark, type, and
application. Runnable task definitions live under `tasks/`; runnable experiment
matrices live under `configs/batches/`.

Current active batch:

```text
configs/batches/gpt54_datavoyager_smoke.yaml
```

Current active task:

```text
tasks/domsteer/datavoyager_most_fuel_efficient/task.yaml
```

## Harness Tiers

| Tier | Meaning | Main Use |
| --- | --- | --- |
| `browser_only` | Browser screenshot plus browser actions only. | Web GUI behavior and visual analytics trajectories. |
| `full_sandbox` | Browser GUI plus code, shell, web search, and file tools in the sandbox. | Mixed GUI/programmatic workflows and workplace-style tasks. |
| `desktop_gui_only` | Virtual desktop screenshot plus mouse/keyboard actions, without shell/code tools. | Human-like desktop application behavior comparisons. |
| `desktop_no_gui_tool_only` | Programmatic app/file tools without screenshots or GUI actions. | Desktop task ablations when a batch/API mode exists. |
| `no_gui_tool_only` | Code, shell, search, and file tools only. | Programmatic baselines for data tasks. |

## Ready Or Smoke-Tested

| Benchmark | Type | Application | Task ID | Current Status | Evaluator |
| --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_most_fuel_efficient` | Active GPT-5.4 smoke task across three harnesses. | `final_answer`, contains `Mazda GLC` |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_europe_100hp_4cyl_count` | Retired from active config until the first GPT-5.4 smoke path is stable. | `final_answer`, exact number `10` |
| TheAgentCompany-style | Workplace analytics / browser + code + files | Browser/files/Python | TAC-shaped local smoke | Not active in current config; next integration target. | Task-specific artifact or answer check |
| GUI-vs-CLI | Desktop spreadsheet analysis | LibreOffice Calc | `gui_vs_cli_calc_budget_multi_sheet` | Metadata imported; not active in current config. | Original verifier commands preserved, bridge pending |
| Workflow-GYM-style | Desktop data analysis | Weka | Weka Iris smoke | Not active in current config. | Mock/manual until artifact evaluator exists |
| Workflow-GYM-style | Desktop visual/spatial authoring | Blender | Blender cube smoke | Not active in current config. | Mock/manual until artifact evaluator exists |

## Candidate Tasks

| Benchmark | Type | Application | Candidate Task | Harness Fit | Missing |
| --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics | DataVoyager | Horsepower range by origin | `browser_only`, `full_sandbox`, `no_gui_tool_only` | Re-add after current smoke matrix is stable. |
| DOMSteer | Visual analytics | DataVoyager | 8-cylinder origin | `browser_only`, `full_sandbox`, `no_gui_tool_only` | Re-add after current smoke matrix is stable. |
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
