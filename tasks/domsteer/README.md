# DOMSteer Tasks

This folder holds DOMSteer task and workflow catalogs derived from:

- Pan Hao, Rishi Selvakumaran, Jacob Sun, Qianwen Wang. "Beyond Chat and
  Clicks: GUI Agents for In-Situ Assistance via Live Interface Transformation."
  arXiv:2604.14668.

Tracked files:

```text
datavoyager_most_fuel_efficient/task.yaml
tasks.jsonl
```

`tasks.jsonl` is a lightweight catalog in the same spirit as
`tasks/gui_vs_cli/tasks.jsonl`: one JSON object per task/workflow. It currently
contains only the eight DOMSteer experiment tasks from the user-study setup:
four DataVoyager tasks and four TensorFlow Playground tasks.

Important distinctions:

- `experiment_task` entries are the eight DOMSteer user-study tasks.
- T1-T3 have deterministic final-answer validators.
- T4-T8 keep `answer_validator: manual_pending` because the paper does not
  provide exact final answers and the tasks require rubrics or state evaluators.

Do not assume every DOMSteer task is automatically executable. For active agent
runs, create a task YAML with a concrete `start_url`, expected answer or rubric,
and harness assumptions.
