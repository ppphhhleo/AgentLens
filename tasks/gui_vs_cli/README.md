# GUI-vs-CLI Tasks

This folder holds AgentLens-imported GUI-vs-CLI task catalogs from the public
`rebeccaz4/gui-vs-cli` GitHub benchmark.

Tracked catalogs:

```text
tasks.jsonl            # 440 standard tasks; kept for backward compatibility
tasks_standard.jsonl   # same 440 standard tasks
tasks_grounding.jsonl  # 176 grounded-prompt tasks
task_pairs.jsonl       # 176 standard/grounded matched task pairs
```

The standard and grounded-prompt catalogs intentionally stay separate because
all grounded task ids appear in the standard catalog. Use `source_type` plus
`paired_task_id` when comparing or sampling across both catalogs.

Regenerate from the ignored local checkout with:

```bash
python scripts/import_gui_vs_cli_tasks.py
```

AgentLens should treat these records as follows:

- `task` is the natural-language task text given to the agent.
- `task_grounding`, when present, is the grounded-prompt variant.
- `source_type` is either `standard` or `grounded_prompt`.
- `paired_task_id` is the stable key for matching standard and grounded-prompt
  variants of the same task.
- `github_task_path` points to the source directory under
  `task_generator/tasks/` or `task_generator/tasks_grounding/`.
- `app` is the desktop application name.
- `env.files` lists required seed files and target sandbox paths.
- `verification` preserves original verifier command specs.

Runnable execution requires the GitHub task directories, seed assets, verifier
CLIs, and a compatible desktop image. Do not add GUI-vs-CLI tasks to an active
batch until the matching environment image and verifier bridge are available.

Recommended paired run naming:

```text
{paired_task_id}__standard__{agent_id}
{paired_task_id}__grounded__{agent_id}
```
