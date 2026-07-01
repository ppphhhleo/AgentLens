# Environment Backends

AgentLens separates the agent loop from the computer environment.

Current executable backend:

- Docker/AIO sandbox through `AIOSandboxSession`, used by `screenshot_react`
  and `desktop_react`.

Candidate backend:

- E2B desktop sandboxes, useful for managed remote desktop sessions and easier
  sandbox lifecycle management.

Do not put intervention or simulated-user logic inside an environment backend.
Intervention and simulated actors should stay in AgentLens' harness/actor layer
so the same behavior can run over local Docker, AWS Docker, E2B, or future
desktop providers.

The `rebeccaz4/gui-vs-cli` repository uses a clean backend interface with both
Docker and E2B implementations. The useful design to borrow is the interface:

```text
environment.screenshot() -> PNG bytes
environment.commands.run(command)
environment.files.read/write/remove(path)
environment.stream.get_url()
environment.kill()
```

For AgentLens, E2B should be added as a second implementation of this small
interface only after the Docker desktop path is stable. The trajectory schema
should remain unchanged: screenshots, model messages, actions/tool calls,
shell/file events, intervention events, verifier outputs, and final metrics
should be recorded the same way regardless of backend.

## Local Docker Images

- `environments/docker/desktop-poc`: minimal desktop automation layer.
- `environments/docker/desktop-apps-poc`: extends the minimal image with Weka
  and Blender POC applications.

`desktop-poc` is the base virtual desktop capability. `desktop-apps-poc` is the
application-bearing image for early desktop workflow tasks.
