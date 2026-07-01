# GUI-vs-CLI Tasks

This folder holds the GUI-vs-CLI task catalog from the public
`rebeccazzzz/gui-vs-cli` Hugging Face dataset and references the corresponding
`rebeccaz4/gui-vs-cli` GitHub benchmark.

Tracked catalog:

```text
tasks.jsonl
```

It contains 440 task records across 18 desktop applications.

The Hugging Face dataset is useful for browsing and importing task text,
application names, required seed files, and verifier command specs. It does not
ship the runnable seed assets or verifier implementation. Runnable execution
requires the GitHub task directories, verifier CLIs, and a compatible desktop
image.

AgentLens should treat these records as follows:

- `task` is the natural-language task text given to the agent.
- `app` is the desktop application name.
- `env.files` lists required seed files and target sandbox paths.
- `verification` preserves original verifier command specs.

Do not add GUI-vs-CLI tasks to an active batch until the matching environment
image and verifier bridge are available.
