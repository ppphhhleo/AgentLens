# Trajectory Collection Task Catalog

This is the working catalog for trajectory collection tasks. It is organized by
benchmark, task type, and application. Keep runnable smoke tasks separate from
candidate tasks so the current collection path stays clear.

Current active config:

```text
configs/experiments/domsteer_datavoyager_toolcall_matrix.yaml
```

Current active smoke matrix:

| Model | Task | Harnesses |
| --- | --- | --- |
| `gpt-5.4` | `datavoyager_most_fuel_efficient` | `browser_only`, `full_sandbox`, `no_gui_tool_only` |

## Harness Tiers

| Tier | Meaning | Main Use |
| --- | --- | --- |
| `browser_only` | Browser screenshot plus browser actions only. | Web GUI behavior and visual analytics trajectories. |
| `full_sandbox` | Browser GUI plus code, shell, web search, and file tools in the sandbox. | Mixed GUI/programmatic workflows and agent-company-style tasks. |
| `desktop_gui_only` | Virtual desktop screenshot plus mouse/keyboard actions, without shell/code tools. | Human-like desktop application behavior comparisons. |
| `desktop_no_gui_tool_only` | Programmatic app/file tools without screenshots or GUI actions. | Desktop task ablations when a batch/API mode exists. |
| `no_gui_tool_only` | Code, shell, search, and file tools only. | Programmatic baselines for data tasks. |

## Ready Or Smoke-Tested

| Benchmark | Type | Application | Task ID | Current Status | Evaluator |
| --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_most_fuel_efficient` | Active GPT-5.4 smoke task across three harnesses. | `final_answer`, contains `Mazda GLC` |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_europe_100hp_4cyl_count` | Previously configured; retired from active smoke config until the first GPT-5.4 matrix is clean. | `final_answer`, exact number `10` |
| TheAgentCompany-style | Workplace analytics / browser + code + files | Browser/files/Python | TAC-shaped local smoke | Not active in current config; keep as next integration target once the smoke matrix is stable. | Task-specific artifact or answer check |
| Workflow-GYM-style | Desktop data analysis | Weka | Weka Iris smoke | Previously prototyped; not active in current config. | Mock/manual until artifact evaluator exists |
| Workflow-GYM-style | Desktop visual/spatial authoring | Blender | Blender cube smoke | Previously prototyped; not active in current config. | Mock/manual until artifact evaluator exists |

## Candidate Tasks

| Benchmark | Type | Application | Candidate Task | Harness Fit | Missing |
| --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics | DataVoyager | Horsepower range by origin | `browser_only`, `full_sandbox`, `no_gui_tool_only` | Re-add after current smoke matrix is stable. |
| DOMSteer | Visual analytics | DataVoyager | 8-cylinder origin | `browser_only`, `full_sandbox`, `no_gui_tool_only` | Re-add after current smoke matrix is stable. |
| TheAgentCompany | Occupational workplace analytics | Browser + docs + shell/code | Real benchmark task | Mostly `full_sandbox`, with no-GUI ablations where artifacts are accessible. | Real task adapter, data mount, evaluator. |
| Workflow-GYM | Visual/spatial desktop GUI workflow | Unity | Scene/project creation or modification | `desktop_gui_only`, `full_sandbox`; possible batch-mode no-GUI. | Reliable image, licensing/login, launch command, evaluator. |
| Workflow-GYM | Visual/spatial desktop GUI workflow | Blender | Create scene and save `.blend` artifact | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only`. | Concrete objective and Blender Python evaluator. |
| Workflow-GYM | Data analysis desktop GUI | Weka | Run model and report accuracy/confusion matrix | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only`. | Dataset, concrete answer, artifact/state evaluator. |
| Workflow-GYM-style | Spatial analytics | QGIS | Load GIS data and compute/export statistic | `desktop_gui_only`, `full_sandbox`; partial no-GUI. | Image, data, evaluator. |
| Workflow-GYM-style | Visual workflow / dashboard | KNIME | Build node workflow and chart/dashboard | `desktop_gui_only`, `full_sandbox`; partial no-GUI. | Image, sample data, evaluator. |

## Current Collection Rule

Keep the active collection config small until the GPT-5.4 three-harness smoke is
stable. Add tasks back one at a time, with exact expected answer/evaluator,
harness compatibility, and a run ID naming convention before collecting a larger
batch.
