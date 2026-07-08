# DOMSteer Tasks

This folder holds DOMSteer task and workflow catalogs derived from:

- Pan Hao, Rishi Selvakumaran, Jacob Sun, Qianwen Wang. "Beyond Chat and
  Clicks: GUI Agents for In-Situ Assistance via Live Interface Transformation."
  arXiv:2604.14668.

Tracked files:

```text
datavoyager_most_fuel_efficient/task.yaml
datavoyager_most_fuel_efficient_grounded/task.yaml
datavoyager_origin_horsepower_range/task.yaml
datavoyager_origin_horsepower_range_grounded/task.yaml
datavoyager_europe_hp_gt_100_four_cyl/task.yaml
datavoyager_europe_hp_gt_100_four_cyl_grounded/task.yaml
tasks.jsonl
```

`tasks.jsonl` is a lightweight catalog in the same spirit as the
GUI-vs-CLI JSONL catalogs under `tasks/gui_vs_cli/`: one JSON object per
task/workflow. It currently contains only the eight DOMSteer experiment tasks
from the user-study setup: four DataVoyager tasks and four TensorFlow
Playground tasks.

Important distinctions:

- `experiment_task` entries are the eight DOMSteer user-study tasks.
- T1-T3 have deterministic final-answer validators.
- T4-T8 keep `answer_validator: manual_pending` because the paper does not
  provide exact final answers and the tasks require rubrics or state evaluators.
- T1-T3 now have two runnable prompt variants:
  - the original task YAMLs keep the standard, goal-only prompt;
  - the sibling `_grounded` task YAMLs use procedure-grounded prompts that
    identify relevant fields and workflow checks without revealing the answer.

Do not assume every DOMSteer task is automatically executable. For active agent
runs, create a task YAML with a concrete `start_url`, expected answer or rubric,
and harness assumptions.
