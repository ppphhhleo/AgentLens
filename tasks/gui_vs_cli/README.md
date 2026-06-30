# GUI-vs-CLI Tasks

This folder holds AgentLens task metadata adapted from the public
`rebeccazzzz/gui-vs-cli` Hugging Face dataset and the corresponding
`rebeccaz4/gui-vs-cli` GitHub benchmark.

The Hugging Face dataset is useful for browsing and importing task text,
application names, required seed files, and verifier command specs. It does not
ship the runnable seed assets or verifier implementation. Runnable execution
requires the GitHub task directories, verifier CLIs, and a compatible desktop
image.

AgentLens should treat these tasks as follows:

- `task.goal` is the natural-language task text given to the agent.
- `task.extra.gui_vs_cli.env.files` preserves required seed files.
- `task.extra.gui_vs_cli.verification` preserves verifier commands.
- `answer_validator: manual_pending` means the task is cataloged but not yet
  executable by AgentLens' native evaluator.

Do not add GUI-vs-CLI tasks to an active batch until the matching environment
image and verifier bridge are available.
