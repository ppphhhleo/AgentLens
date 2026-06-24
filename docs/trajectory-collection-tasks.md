# Trajectory Collection Task Catalog

This file is the working catalog for agent trajectory collection. It organizes
tasks by benchmark, task type, and application, and records which harness modes
are appropriate.

Use `docs/task-registry.md` for compact implementation status. Use
`docs/trajectory-data-layout.md` for raw/processed data storage conventions.
Use `handover.md` for milestones and replacement-sensitive decisions.

## Harness Modes

| Mode | Meaning | Best For |
| --- | --- | --- |
| `browser_only` | Browser screenshot/actions only; no code/file tools. | Web visual analytics where the browser UI is the task surface. |
| `full_sandbox` | Browser/desktop plus code, shell, and file tools inside the virtual computer. | Mixed GUI + programmatic workflows; TAC-style tasks; desktop app tasks with artifact checks. |
| `desktop_gui_only` | Desktop screenshot/click/type/keypress/wait/launch app; no shell/code/file tools. | Human-like desktop app interaction comparisons. |
| `desktop_no_gui_tool_only` | Shell/code/files/artifact inspection; no screenshots or GUI actions. | Programmatic ablations and evaluator-style task solving. |
| `no_gui_tool_only` | Browser/desktop not visible; code/file/API tools only. | Web/data tasks that can be solved from data or artifacts without visual interaction. |

Not every task should run in every mode. The goal is to keep the harness matrix
meaningful: GUI modes for interface behavior, no-GUI modes for programmatic
ablations and evaluator baselines.

## Ready After Tested

These tasks are ready for trajectory collection now. Some are still smoke tasks,
but their harnesses have produced trajectories.

| Benchmark | Type | Application | Task ID | Config | Harness Coverage | Evaluator | Status / Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_most_fuel_efficient` | `configs/experiments/domsteer_datavoyager_matrix.yaml`; `configs/experiments/capture_first_domsteer_agentcompany.yaml` | `browser_only`, `full_sandbox`, `no_gui_tool_only` | `contains`, expected `Mazda GLC` | Ready. Previously produced successful sandbox trajectory. |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_europe_100hp_4cyl_count` | `configs/experiments/domsteer_datavoyager_matrix.yaml` | `browser_only`, `full_sandbox`, `no_gui_tool_only` | `number_exact`, expected `10` | Ready in matrix config. |
| TheAgentCompany-style smoke | Workplace data analysis / browser + code + file I/O | Example page + Python + shell + files | `the_agent_company_io_capture_smoke` | `configs/experiments/capture_first_domsteer_agentcompany.yaml` | `full_sandbox`; possible future `no_gui_tool_only` | `exact`, expected `revenue total 60` | Ready as TAC-shaped smoke. This is not full TheAgentCompany integration. |
| Workflow-GYM-style proxy | Desktop data analysis | Weka | `workflowgym_weka_iris_smoke` | `configs/experiments/workflow_desktop_apps_poc.yaml` | `full_sandbox`/desktop; future `desktop_gui_only`, `desktop_no_gui_tool_only` | `manual_pending`, expected `done` | Ready as desktop smoke; local and AWS smoke completed. |
| Workflow-GYM-style proxy | Visual-spatial / complex desktop interface | Blender | `workflowgym_blender_cube_smoke` | `configs/experiments/workflow_desktop_apps_poc.yaml` | `full_sandbox`/desktop; future `desktop_gui_only`, `desktop_no_gui_tool_only` | `manual_pending`, expected `done` | Ready as desktop smoke; local and AWS smoke completed. |

## Configured But Needs Clean Current Run

These are configured or registered, but should not yet be treated as tested
collection tasks in the current matrix.

| Benchmark | Type | Application | Task ID | Target Harness Coverage | Evaluator | What Is Missing |
| --- | --- | --- | --- | --- | --- | --- |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_horsepower_range_by_origin` | `browser_only`, `full_sandbox`, `no_gui_tool_only` | `exact`, expected `USA` | Add to active matrix and confirm clean runs. |
| DOMSteer | Visual analytics / data analysis | DataVoyager | `datavoyager_8_cylinder_origin` | `browser_only`, `full_sandbox`, `no_gui_tool_only` | `exact`, expected `USA` | Add to active matrix and confirm clean runs. |
| Workflow-GYM-style proxy | Visual-spatial desktop GUI smoke | Unity | `workflowgym_unity_scene_smoke` | `desktop_gui_only`, `full_sandbox` | `manual_pending` | Current generic desktop image does not install Unity; use only for harness smoke until an image exists. |

## Candidate Tasks Not Ready Yet

These are the next useful trajectory-collection targets, but they need task
design, images/data, and/or evaluators before collection.

| Benchmark | Type | Application | Candidate Task | Target Harness Coverage | Missing |
| --- | --- | --- | --- | --- | --- |
| TheAgentCompany | Workplace analytics / enterprise workflow | Browser + code + docs/files | Real TAC task from the benchmark environment | `full_sandbox`; selected `no_gui_tool_only` ablations if artifacts/data are accessible | Real TAC environment/container and task adapter. |
| Workflow-GYM-style proxy | Desktop data analysis | Weka | Run J48/RandomForest on Iris and report accuracy or confusion matrix | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only` | Concrete objective and artifact/state evaluator. |
| Workflow-GYM-style proxy | Visual-spatial / artifact creation | Blender | Create named cube/material/camera scene and save `.blend` | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only` | Blender Python evaluator. |
| Workflow-GYM-style proxy | Spatial visual analytics | QGIS | Load shapefile, compute/export statistic, create path/selection | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only` | QGIS image, sample data, evaluator. |
| Workflow-GYM-style proxy | Visual data workflow / dashboard | KNIME | Build node workflow and generate chart/dashboard component | `desktop_gui_only`, `full_sandbox`; limited no-GUI if batch mode works | KNIME image, sample data, evaluator. |
| Workflow-GYM-style proxy | CAD / visual-spatial analysis | FreeCAD | Create object with dimensions and compute volume/surface area | `desktop_gui_only`, `full_sandbox`, `desktop_no_gui_tool_only` | FreeCAD image and geometry evaluator. |
| Workflow-GYM | Visual-spatial GUI workflow | Unity | Create or modify a scene/project | `desktop_gui_only`, `full_sandbox`; limited batch-mode no-GUI if available | Reliable Unity image, licensing/login, evaluator. |

## Workflow-GYM Harness Compatibility

Workflow-GYM-style desktop tasks should support multiple harness modes when
the application makes it meaningful:

| Application | `desktop_gui_only` | `full_sandbox` | `desktop_no_gui_tool_only` | Notes |
| --- | --- | --- | --- | --- |
| Weka | Yes | Yes | Yes | No-GUI can use Weka CLI or Python/sklearn over the dataset. |
| Blender | Yes | Yes | Yes | No-GUI can use `blender --background --python ...`. |
| QGIS | Yes | Yes | Partial | No-GUI possible with `ogrinfo`, `geopandas`, or `qgis_process` if installed. |
| KNIME | Yes | Yes | Partial | No-GUI depends on KNIME batch execution and workflow artifacts. |
| FreeCAD | Yes | Yes | Yes | No-GUI can use FreeCAD Python APIs for geometry creation/checking. |
| Unity | Partial | Partial | Partial | Depends on Unity image, licensing, and batch-mode support. |

## Immediate Collection Plan

1. Collect DOMSteer/DataVoyager trajectories for the two ready tasks across
   `browser_only`, `full_sandbox`, and `no_gui_tool_only` using
   `configs/experiments/domsteer_datavoyager_matrix_v2_toolcall.yaml`.
2. Keep `the_agent_company_io_capture_smoke` in the collection set as the
   workplace code/file I/O smoke task.
3. Rerun Weka and Blender smoke after the `desktop.launch_app` update, locally
   and on AWS, to confirm no foreground shell blocking.
4. Add the two remaining DataVoyager tasks after clean matrix confirmation.
5. Promote Weka and Blender from smoke tasks to real evaluable tasks by adding
   concrete objectives and artifact/state evaluators.
