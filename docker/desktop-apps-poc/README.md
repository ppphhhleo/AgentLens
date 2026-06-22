# Desktop Apps POC Image

This image extends `agentlens/desktop-poc:latest` with two initial desktop
applications:

- Weka for data-analysis GUI workflows
- Blender for visual-spatial GUI workflows

Build:

```bash
docker build -t agentlens/desktop-apps-poc:latest docker/desktop-apps-poc
```

Smoke config:

```bash
configs/experiments/workflow_desktop_apps_poc.yaml
```

These tasks currently use `manual_pending` outcome validation. They are for
trajectory capture, desktop action coverage, and analysis-pipeline smoke tests;
artifact/state evaluators should be added after the task designs stabilize.
