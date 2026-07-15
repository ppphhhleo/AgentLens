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
tfplayground_discretize_effect/task.yaml
tfplayground_misclassified_point/task.yaml
tfplayground_regression_two_datasets/task.yaml
tfplayground_regression_two_datasets_grounded/task.yaml
tfplayground_classification_four_datasets/task.yaml
tfplayground_classification_four_datasets_grounded/task.yaml
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
- T5-T8 now have TensorFlow Playground task YAMLs. T7 and T8 each have a
  distinct standard and procedure-grounded YAML. They remain `manual_pending`
  because they need rubrics or state/screenshot judges before they should be
  used for automatic performance claims.

Do not assume every DOMSteer task is automatically executable. For active agent
runs, create a task YAML with a concrete `start_url`, expected answer or rubric,
and harness assumptions.
