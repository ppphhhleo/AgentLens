# GUI-vs-CLI Tasks

This folder holds AgentLens-imported GUI-vs-CLI task catalogs from the public
`rebeccaz4/gui-vs-cli` GitHub benchmark.

Tracked catalogs:

```text
tasks.jsonl            # 440 standard tasks; kept for backward compatibility
tasks_standard.jsonl   # same 440 standard tasks
tasks_grounding.jsonl  # 176 grounded-prompt tasks
```

The standard and grounded-prompt catalogs intentionally stay separate because
many task ids appear in both lists. Use `source_type` plus `id` when comparing
or sampling across both catalogs.

Regenerate from the ignored local checkout with:

```bash
python scripts/import_gui_vs_cli_tasks.py
```

AgentLens should treat these records as follows:

- `task` is the natural-language task text given to the agent.
- `task_grounding`, when present, is the grounded-prompt variant.
- `source_type` is either `standard` or `grounded_prompt`.
- `github_task_path` points to the source directory under
  `task_generator/tasks/` or `task_generator/tasks_grounding/`.
- `app` is the desktop application name.
- `env.files` lists required seed files and target sandbox paths.
- `verification` preserves original verifier command specs.

Runnable execution requires the GitHub task directories, seed assets, verifier
CLIs, and a compatible desktop image. Do not add GUI-vs-CLI tasks to an active
batch until the matching environment image and verifier bridge are available.
