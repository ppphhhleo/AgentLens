# Multi-Tool Agent + Sandboxed Sessions — Plan

Status: planning. Implementation has not started.

## Goals

1. **Multi-tool agent** — extend the action space beyond browser to include code execution, shell, and file operations. Same gating + telemetry pipeline as today's `web_search`.
2. **Per-task sandboxed execution** — each task runs inside an isolated Docker container so state never leaks between tasks unintentionally.
3. **Optional context preservation across tasks within a session** — when the experiment design calls for it (e.g., learning curves, multi-step research workflows), tasks can share one persistent container with persistent browser state, filesystem, and Python kernel.
4. **Parallelism for isolated runs** — when each task starts fresh anyway, run N tasks concurrently as N containers.

## Constraints

- **Parallel ⇒ isolated.** Sharing a container across concurrent tasks corrupts state and breaks isolation. The design enforces this — when `MemoryScope` requires cross-task sharing, parallelism is rejected with an explicit error.
- **The action gating + prompt synthesis layer we built last session must keep working unchanged.** Tools are added by extending the schema and gating map, not by rewriting either system.
- **The screenshot ReAct loop must not need restructuring.** New tool actions slot into the same dispatch shape as `web_search`.

---

## Execution-mode matrix

| Mode | Container lifetime | Browser state | Filesystem | Python kernel | Use case |
|---|---|---|---|---|---|
| Sequential, isolated | one per task | fresh | fresh | fresh | Standard benchmarks (Online-Mind2Web, AssistantBench) |
| **Sequential, shared** | one per session | persistent | persistent | persistent | **Learning curves (G4 in general-idea.md)**, multi-step research workflows |
| Parallel, isolated | one per task (concurrent) | fresh | fresh | fresh | Scale: 300 tasks in 30 min instead of 5 hours |
| ~~Parallel, shared~~ | n/a — **rejected** | — | — | — | Doesn't make sense (concurrent tasks would race the same browser/kernel) |

The three valid modes are selected via existing schema fields, not new ones.

---

## Honoring `MemoryScope` for container lifecycle

`MemoryHarnessConfig.scope` already enumerates exactly the right axis (it was in the original spec). We just need to honor it:

```text
scope=NONE | IN_TASK
  sequential : one container per task
  parallel   : one container per worker, each runs one task

scope=CROSS_TRIAL
  sequential : one container per (task, all trials)
  parallel   : one container per worker × per task

scope=CROSS_TASK_SAME_SITE
  sequential : one container per (start_url host)
  parallel   : FORBIDDEN — error out, force sequential

scope=CROSS_BENCHMARK
  sequential : one container for the entire run
  parallel   : FORBIDDEN — error out, force sequential
```

A pure function `(scope, parallelism) → grouping_rule` lives in `run_plans.py`. The adapter consumes the grouping and orchestrates container lifecycles.

---

## Architectural shape

```text
CLI
  build plans, decide parallelism (--parallel N)
              ↓
Adapter (extended)
  - Read memory scope from each plan's harness
  - Group plans into "session batches" by scope rules
  - For each batch: spin one container, run all plans inside it
    sequentially, destroy container on exit
  - Across batches: parallel if scope allows
              ↓
Sandbox session (NEW module)
  src/agentlens/sandbox/aio_sandbox.py
  Lifecycle: __enter__ spins container, __exit__ tears down
  Properties: browser CDP url, code kernel, shell, files
  Methods: run_python(code), shell(cmd), files.read/write
              ↓
ScreenshotReactLoop (mostly unchanged)
  - Take page from session.browser instead of launching local Chromium
  - For new tool actions: call session methods (instead of direct
    OpenAI / subprocess)
  - All gating/telemetry already handles the new actions
```

The loop and the model don't change. Adapter and sandbox are new/refactored.

---

## New action types

Added to `ComputerActionType` in `src/agentlens/actions.py`. Each gets a tool-name entry in `tool_gating.TOOL_NAME_BY_ACTION_TYPE` and a schema fragment. They appear in the model's prompt only if the harness's `tools` list includes them.

| Action | Tool name | Fields | Backend (in container) |
|---|---|---|---|
| `run_python` | `code.run_python` | `code: str` | persistent Jupyter kernel |
| `shell` | `code.shell` | `cmd: str` | bash in workspace |
| `read_file` | `files.read` | `path: str` | filesystem read |
| `write_file` | `files.write` | `path: str`, `text: str` | filesystem write |

Result text is injected into the next observation via the existing `tool_output_since_last_step` mechanism (built for `web_search`).

The browser actions and `web_search` action are unchanged.

---

## File-level delta

| Path | Status | Purpose |
|---|---|---|
| `src/agentlens/sandbox/__init__.py` | NEW | package marker |
| `src/agentlens/sandbox/aio_sandbox.py` | NEW | context manager wrapping AIO Sandbox container; exposes browser CDP url, code/shell/files methods |
| `src/agentlens/actions.py` | EDIT | add 4 new action types + their fields |
| `src/agentlens/harnesses/tool_gating.py` | EDIT | add tool names + prompt schema fragments |
| `src/agentlens/harnesses/screenshot_react_loop.py` | EDIT | dispatch new actions to session methods, mirror web_search pattern |
| `src/agentlens/adapters/screenshot_react.py` | REFACTOR | `run_many` becomes scope-aware: groups plans, opens one session per group |
| `src/agentlens/run_plans.py` | EDIT | grouping function + parallelism/scope validation |
| `src/agentlens/cli.py` | EDIT | add `--parallel N` flag |
| `configs/experiments/online_mind2web_multitool.yaml` | NEW | first config with `tools: [..., code.run_python, code.shell, files.read, files.write]` |
| `configs/experiments/online_mind2web_session.yaml` | NEW | first config with `memory_harness.scope: cross_benchmark` and a small task pool |

---

## Phasing

Three cuts, each independently testable.

### Cut 1 — Multi-tool inside isolated containers (~2 days)

- New `sandbox/aio_sandbox.py` context manager.
- Add the 4 new action types + their gating + their loop dispatch.
- Default lifecycle: one container per task (NONE / IN_TASK semantics).
- Adapter changes minimal: replace `playwright.chromium.launch(...)` with `playwright.chromium.connect_over_cdp(session.browser_url)`.
- Smoke test: pick one Online-Mind2Web task that benefits from code execution (e.g., parsing a search results page) and confirm the agent uses `run_python` and the score behavior changes meaningfully.

**Win after Cut 1:** every task runs in a sandboxed container with full multi-tool access. No state leak. Foundation for CocoaBench is in place (same Docker plumbing).

### Cut 2 — Session preservation (sequential shared, ~1 day)

- `run_many` groups plans by `MemoryScope`:
  - `CROSS_TASK_SAME_SITE` → groups by `urlparse(task.start_url).host`
  - `CROSS_BENCHMARK` → one group total
- For each group: open one container, run all member plans sequentially against it.
- New trajectory event type: `SESSION_BOUNDARY` so analysis can see where one task ended and the next began *inside the same container*.
- Test: a small DOMSteer-style task pool with `scope: cross_task_same_site`, confirm browser cookies/state persist across tasks.

**Win after Cut 2:** the original `MemoryScope` design is finally executable. Learning-curve experiments (G4) become possible.

### Cut 3 — Parallelism for isolated scopes (~1 day)

- `--parallel N` flag in CLI.
- `concurrent.futures.ProcessPoolExecutor` (one worker per concurrent task).
- Each worker spawns its own container.
- Validation: refuse to parallelize when scope ≥ `CROSS_TASK_SAME_SITE`. Surface a clear error: *"`--parallel` requires memory scope `none` or `in_task`; this run has `cross_benchmark`."*
- Cap concurrency by available RAM (each Chromium ~500 MB-1 GB).

**Win after Cut 3:** 300-task Online-Mind2Web run drops from hours to minutes.

---

## Costs and pre-requisites

| Cost | Magnitude | Notes |
|---|---|---|
| Docker Desktop on macOS | ~5 GB initial | needs to be running |
| AIO Sandbox image first pull | ~3-5 GB | cached after |
| Per-container startup | 2-10 sec | negligible vs ~30s task durations |
| Per-container RAM | ~500 MB-1 GB | Chrome dominates; 10 parallel ≈ 10 GB |
| Per-container disk | ~100 MB scratch | cleaned on destroy |

Pre-reqs before starting Cut 1:
1. Docker Desktop installed and running (`docker version` succeeds).
2. AIO Sandbox image pullable (`docker pull <agentinfra/aio-sandbox>` or whatever the official tag is).
3. Existing Phase A work (gating + web_search) committed so this is a clean foundation.

---

## Open questions

- **Browser fingerprinting in containerized Chromium.** Headless Chrome in Docker is detected at higher rates by anti-bot systems (Cloudflare, etc.) than the same Chrome on a real macOS. Some Online-Mind2Web tasks fail this way today; in containers they'd fail more. Mitigation is `playwright-extra` + stealth plugin, but it's another configurable. Decide later whether stealth is on by default.
- **Snapshot semantics for shared sessions.** Currently each CLI invocation gets its own timestamp folder. For sequential-shared mode, do all tasks in the session land in one snapshot, or one snapshot per task within a session subfolder? Likely one folder per session with task subfolders.
- **AIO Sandbox image stability.** The project is community-maintained. Pin to a specific image SHA in our config to avoid silent breakage.
- **Cost guard for parallel runs.** With `--parallel 10` on 300 tasks, agent + judge cost is roughly 10× concurrent. Surface estimated cost before launch and confirm.

---

## Access modes — one container, two actors

The same sandbox container can host both an autonomous agent and a human participant. AIO Sandbox exposes Chromium via two surfaces simultaneously:

| Surface | Used by | Mechanism |
|---|---|---|
| **CDP port** (`chromium.connect_over_cdp(...)`) | Autonomous agents | programmatic — what our `screenshot_react` / `browsergym_bridge` adapters use today |
| **noVNC URL** (browser-in-browser) | Human participants | interactive — participant types/clicks in a remote desktop view of the same Chromium |

Both surfaces talk to the **same Chromium process** in the **same container**. So an agent task and a human task running on the same image have:

- same browser binary + version
- same network egress IP / GeoIP
- same fonts, plugins, extensions, locale, timezone
- same anti-bot fingerprint surface

This is what makes a clean human-vs-agent comparison possible (G1 in `general-idea.md`). Without it, "agent fails on Cloudflare; human passes" is confounded between actor strategy and environment.

### How this connects to the rest of the plan

| Plan element | Applies to agents? | Applies to humans? |
|---|---|---|
| Container (image, network, fonts, locale) | **shared** | **shared** |
| Memory scope / session preservation | yes | yes — a "human session" spanning N tasks on one site naturally develops the *interface-faithful* familiarity G3/G4 are about |
| Browser actions (click, scroll, type) | via JSON actions | via VNC mouse/keyboard |
| Multi-tool actions (`run_python`, `shell`, `read_file`, `write_file`, `web_search`) | **agent-only** | **not available** — humans operate the browser directly, with no tool-call API |
| Trajectory format (`trajectory.json`) | same | same — captured via rrweb continuous DOM events + periodic screenshots |
| Validators (`exact`, `url_contains`, `webjudge`, `task.validate`) | same | same — judge is blind to whether the actor was human or agent |

### Comparison axis caveat

Because multi-tool actions are agent-only, fair comparisons need to control for tool set. Two valid framings:

- **"Same tools, different actor"** — human (browser only) vs. browser-only agent (no `web_search`, no `run_python`). Cleanly isolates *strategy*.
- **"What tools change behavior"** — human (browser only) vs. agent with progressively more tools. Measures the *capability surface* contribution.

Both are interesting; the project's central thesis (interface-faithful vs opportunistic) is best supported by the first.

### Schema readiness

The schema already foresaw this dual-actor design:

```python
ToolHarnessConfig.runner ⊇ "human"            # already enumerated, never wired
ToolHarnessTier        ⊇ HUMAN                # already enumerated
```

Wiring the human runner is a separate adapter (`src/agentlens/adapters/human_runner.py`) that follows the same lifecycle as `screenshot_react`:

1. Open a sandbox session (same `aio_sandbox.py` wrapper from Cut 1).
2. Surface noVNC URL to the participant; wait for them to start.
3. Begin capture: rrweb (pending — G2) into the container's filesystem; periodic screenshots; URL/event log.
4. Wait for the participant to submit (overlay button or CLI prompt).
5. Save `trajectory.json` in the unified format; run the same validators as for agent runs.
6. Tear down the container.

### Practical pre-reqs (in addition to the agent path)

| Item | Notes |
|---|---|
| **rrweb capture** (G2) | Required — without continuous DOM capture, human "dwell, hover, scan" patterns are invisible. Already on the project's pending list. |
| **noVNC overlay UI** | Small in-page widget (injected via `add_init_script`) for the participant to mark "task complete" / submit answer. |
| **Consent + demographics flow** | Out of scope for this doc; covered by `general-idea.md` G1 (`consent_flow.py` in the architecture diagram). |
| **Participant routing** | Multi-participant studies need a dispatcher (one container per participant). Out of scope here; same Docker plumbing. |

### Phase note

The human runner is **not in this plan's three Cuts** (which are agent-multi-tool focused). It builds on top of Cut 1's container infrastructure and is a separate workstream once Cut 1 lands. The point of capturing it here is to confirm that the design choices in Cuts 1-3 don't paint us into a corner for G1.

---

## Post-implementation: what this unlocks

Beyond the obvious capability gains, the experimental matrix expands considerably:

```text
Same task pool × Same model × {
  browser_only                                ← today
  browser_only + web_search                   ← today (Phase A)
  browser_files (browser + read/write)
  full_sandbox  (browser + shell + code + files)
} × {
  scope=NONE              (independent runs)
  scope=CROSS_TASK_SAME_SITE  (per-site memory, learning curves)
  scope=CROSS_BENCHMARK   (one persistent agent across all tasks)
} × {
  parallel=1              (deterministic ordering)
  parallel=8              (scale)
}
```

Each cell of that matrix is a different experiment. Comparing trajectories across cells is exactly the project's central thesis (interface-faithful vs opportunistic, learning curves, etc.).
