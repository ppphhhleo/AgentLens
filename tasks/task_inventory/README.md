# Task Inventory

`collection_task_registry.jsonl` is the canonical inventory of candidate and
collection-ready tasks. Each record identifies one canonical task, its task
type and axes, prompt-pair availability, prompt source files, harness fit,
evaluation method, and readiness status.

Collection manifests select task IDs from this inventory; they do not define
task prompts or verifiers. Prompt text and verification remain in the
referenced task YAML/JSON source files. This prevents a launch config from
silently changing a task's scientific contract.

For the current balanced GPT patch, use:

```bash
uv run --no-sync python scripts/validate_task_registry.py
```

The preflight validates all 12 selected tasks before any model call. It checks
that standard and grounded source files exist and agree on environment, target
verification, answer contract, start URL, and canonical task identity.

`configs/patches/balanced_gpt55_standard_grounded_task_set.yaml` is the
selection manifest. It deliberately has a different role from the full
inventory: it names the 12-task launch set and component configs, while the
registry retains both selected and future candidates.
