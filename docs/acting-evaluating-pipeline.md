# Acting and Evaluating Pipeline

AgentLens now separates task execution from post-hoc evaluation.

## Acting

Acting adapters collect trajectories:

- `screenshot_react`: browser and sandbox browser tasks
- `desktop_react`: desktop-app tasks inside the sandbox virtual computer

Each trajectory should preserve:

- screenshots or desktop screenshots
- model messages and provider tool calls
- executed tool calls
- final answer and validation event

## Evaluating

Evaluation happens after trajectory and outcome collection:

```bash
agentlens evaluate-trajectory path/to/trajectory.json \
  --output-dir agentlens_results/evaluations/example \
  --config configs/experiments/domsteer_datavoyager_matrix.yaml
```

The output is `evaluation_bundle.json` with:

- `acting`: model, tool harness, memory harness
- `evaluating.outcome`: recorded outcome and optional current validator result
- `evaluating.trajectory`: process-level counts and flags
- `evaluating.methods.wang`: Wang-style workflow segmentation features
- `evaluating.methods.actonomy`: Act-onomy-style behavior/profile features

Batch mode:

```bash
agentlens evaluate-batch agentlens_results/domsteer_datavoyager_matrix \
  --output-dir agentlens_results/evaluations/domsteer_matrix \
  --config configs/experiments/domsteer_datavoyager_matrix.yaml
```

## Desktop POC

`configs/experiments/workflow_desktop_poc.yaml` defines a Unity smoke task using
`desktop_react`. The sandbox image is replaceable through:

```yaml
tool_harnesses:
  - id: ubuntu_desktop
    extra:
      sandbox_image: agentlens/desktop-poc:latest
```

Build the generic image:

```bash
docker build -t agentlens/desktop-poc:latest docker/desktop-poc
```

For real Workflow-GYM app tasks, extend that image with Unity, Blender, or the
target desktop application.
