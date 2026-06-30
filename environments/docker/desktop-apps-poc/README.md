# Desktop Apps POC Image

This image extends `agentlens/desktop-poc:latest` with two initial desktop
applications:

- Weka for data-analysis GUI workflows
- Blender for visual-spatial GUI workflows

Build:

```bash
docker build -t agentlens/desktop-apps-poc:latest environments/docker/desktop-apps-poc
```

No active batch currently uses this image. Add a dedicated YAML under
`configs/batches/` when Weka or Blender returns to the active collection plan.
