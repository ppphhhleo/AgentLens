# AgentLens Task Registry

This is the planning registry for runnable tasks and candidate tasks. Keep
`handover.md` for milestones and replacement decisions; keep this file for task
scope, readiness, images, and evaluators.

## Status Labels

- `runnable`: config exists and can be executed now.
- `registry-only`: task is defined but not included in the current run matrix.
- `candidate`: useful research target, not yet implemented.
- `blocked`: blocked on data, image, licensing, or evaluator.

## Current Runnable And Registered Tasks

| ID | Source | Domain | Harness | Status | Evaluator | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `datavoyager_most_fuel_efficient` | Domsteer/DataVoyager | Visual analytics, data analysis | `browser_only`, `full_sandbox`, `no_gui_tool_only` | `runnable` | `contains`, expected `Mazda GLC` | Included in current matrix runs. |
| `datavoyager_europe_100hp_4cyl_count` | Domsteer/DataVoyager | Visual analytics, data analysis | `browser_only`, `full_sandbox`, `no_gui_tool_only` | `runnable` | `number_exact`, expected `10` | Included in current matrix runs. |
| `datavoyager_horsepower_range_by_origin` | Domsteer/DataVoyager | Visual analytics, data analysis | Browser/sandbox harnesses | `registry-only` | `exact`, expected `USA` | Add to matrix when expanding from 2 to 4 tasks. |
| `datavoyager_8_cylinder_origin` | Domsteer/DataVoyager | Visual analytics, data analysis | Browser/sandbox harnesses | `registry-only` | `exact`, expected `USA` | Reworded from broad characteristics to exact verifiable answer. |
| `workflowgym_unity_scene_smoke` | Workflow-GYM-style local POC | Visual-spatial GUI workflow | `desktop_react` | `runnable` as harness smoke, `blocked` for real Unity completion | `manual_pending` | Generic desktop image lacks Unity. Use this to test desktop capture/actions/intervention only. |

## Near-Term Candidate Desktop Tasks

| Candidate | Why It Matters | Environment/Image Need | Evaluator Direction | Priority |
| --- | --- | --- | --- | --- |
| Weka Iris preprocessing/classification | Lightweight data-analysis desktop workflow; close to Workflow-GYM representative task. | Java + Weka + Iris `.arff`. | Check saved `.arff`; parse classifier output metrics. | High |
| KNIME mini dashboard | Strong visual data-analysis workflow with node graph behavior and long-horizon planning. | KNIME desktop image with sample data. | Check workflow files/components and exported view metadata/screenshots. | High |
| QGIS shapefile/statistics task | Visual analytics plus spatial reasoning; useful for expert-style comparison. | QGIS image + small shapefile bundle. | Check exported CSV/GeoJSON/TXT and selected feature outputs. | High |
| FreeCAD stepped solid | Visual-spatial CAD workflow; easier than Unity and objectively evaluable. | FreeCAD image. | Use FreeCAD Python/API to verify object dimensions, volume, surface area. | High |
| Blender object/material scene | Visual-spatial creative workflow; easier install than Unity. | Blender image. | Use Blender Python to inspect scene objects, transforms, materials, camera/lights. | Medium |
| Unity cube scene | High-value visual-spatial/game-development workflow. | Unity/Unity Hub image; licensing/login must be solved. | Inspect Unity scene/project artifacts for object names/transforms/materials. | Medium after FreeCAD/Blender |

## Workflow-GYM Public Proxy

The public Workflow-GYM dataset/images are not released yet. Public sources
describe 338 tasks across 58 software environments, but not the full task list.
Until the dataset is released, use this registry as a proxy:

- implement a small number of representative local tasks;
- keep `sandbox_image`, `desktop_start_cmd`, input artifacts, and evaluator
  config outside adapter code;
- update this file and `handover.md` when replacing a proxy task with an
  official Workflow-GYM task or image.

Public representative Workflow-GYM examples worth mirroring:

- QGIS: load shapefile, compute statistics, create path line, export results.
- Weka: preprocess Iris `.arff`, run J48/RandomForest cross-validation, report metrics.
- Money Manager Ex: create account/database, enter transactions, compute expense report.
- CapCut: edit video overlays/effects/transitions/music and export.
- FreeCAD: create stepped solid and report volume/surface area.
- KNIME: build table, create charts, wrap dashboard component.

## Selection Rules

Choose the next task by balancing:

- value for trajectory-analysis research;
- setup cost and licensing risk;
- objective evaluator availability;
- ability to compare human, agent, and collaborative trajectories;
- relevance to visual analytics, data analysis, and expert workflow behavior.

Current recommendation:

1. Add Weka or KNIME as the first real desktop data-analysis workflow.
2. Add FreeCAD or Blender as the first visual-spatial workflow.
3. Keep Unity as a higher-value second-phase stress test after the desktop
   evaluator pattern is stable.
