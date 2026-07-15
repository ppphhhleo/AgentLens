# Authored GUI-vs-CLI Task Overlays

These AgentLens tasks reuse a seed artifact from an upstream GUI-vs-CLI task
while changing the deliverable to a verifiable answer. They do not modify
`third_party/gui-vs-cli`.

Each `task.json` must declare:

- `agentlens_env_source_task_id`: upstream task whose `env/` files are copied
  into the fresh sandbox;
- `agentlens_env_source_type`: `standard` or `grounded_prompt` upstream source;
- `agentlens_evaluator`: answer evaluator used instead of the source task's
  artifact verifier;
- `metadata.task_taxonomy`: the operational `SP` / `SF` / `SV` / `OP` label.

The full-workflow runner resolves these fields before sandbox setup. This keeps
the seed and app launcher identical to the source task while allowing an
answer-oriented prompt and evaluator.
