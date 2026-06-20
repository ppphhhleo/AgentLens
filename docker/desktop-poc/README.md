# Desktop POC Image

This image is the minimal desktop automation layer for `desktop_react`.

Build:

```bash
docker build -t agentlens/desktop-poc:latest docker/desktop-poc
```

AWS note: some EC2 Docker installs use the legacy builder without `buildx`;
with the current AIO sandbox base image that builder can hang before the
install layer. If the base image already has `xdotool` plus ImageMagick
`import`/`convert`, this tag is enough for the desktop POC:

```bash
docker tag ghcr.io/agent-infra/sandbox:latest agentlens/desktop-poc:latest
```

For Unity, Blender, or other Workflow-GYM applications, extend this image and
replace `tool_harnesses[].extra.sandbox_image` in
`configs/experiments/workflow_desktop_poc.yaml`.

Required runtime tools:

- `xdotool` for desktop click/type/key actions
- `scrot` or ImageMagick for screenshots
- an X11 desktop already provided by the base sandbox image
