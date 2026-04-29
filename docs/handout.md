# AgentLens Handoff

A unified framework for evaluating browser-agent systems across the same tasks, capturing normalized trajectories, and comparing strategies under different tool / harness / memory / actor configurations.

The project's central thesis (`docs/general-idea.md`): **agents are opportunistic problem-solvers, humans are interface-faithful users**. AgentLens makes that comparison rigorous.

## Where to find what

| Topic | Doc |
|---|---|
| **Project vision, goals (G1–G6), full architecture, paper plan** | `docs/general-idea.md` |
| **All benchmarks** + per-benchmark eval-confirmation conventions + cross-cutting pending work | `docs/benchmarks.md` |
| **Multi-tool + sandboxed sessions plan** — Cuts 1/2/3, agent ↔ human access modes, MemoryScope policy | `docs/multi-tool-and-sessions.md` |
| **Action schema reference** | `docs/screenshot-react-tools.md` |
| **This file** — quickstart, current state snapshot, pending todo | `docs/handout.md` |

## Core comparison axes

```text
Run = Model × ToolHarness × MemoryHarness × UserHarness × Task × Seed × Trial
```

The agent style itself (screenshot-ReAct vs function-calling vs MCP vs DOM-ReAct vs human-as-agent) is also pluggable via the `AgentActor` protocol — a future-extension axis.

## Repo

GitHub: `git@github.com:ppphhhleo/AgentLens.git`

## Setup

```bash
source .venv/bin/activate
cp .env.example .env       # edit: OPENAI_API_KEY, optionally HF_TOKEN, MINIWOB_URL
```

For sandbox / multi-tool runs:

```bash
# Docker Desktop must be running
docker pull ghcr.io/agent-infra/sandbox:latest
```

For Online-Mind2Web (gated HF dataset):

- Visit https://huggingface.co/datasets/osunlp/Online-Mind2Web → click "Agree and access repository"
- Token at https://huggingface.co/settings/tokens → `HF_TOKEN=hf_...` in `.env`

For MiniWoB++:

```bash
mkdir -p ~/.cache/agentlens && cd ~/.cache/agentlens
git clone --depth 1 https://github.com/Farama-Foundation/miniwob-plusplus.git
# .env: MINIWOB_URL=file:///Users/<you>/.cache/agentlens/miniwob-plusplus/miniwob/html/miniwob/
```

For CocoaBench:

```bash
mkdir -p ~/.cache/agentlens && cd ~/.cache/agentlens
git clone https://github.com/cocoabench/cocoa-agent.git
# point task entries at ~/.cache/agentlens/cocoa-agent/cocoabench-example-tasks/<name>/
```

## Main CLI

```bash
agentlens doctor                                  # env check
agentlens list-configs
agentlens validate-config <config.yaml>
agentlens summarize <config.yaml>                 # mock report
agentlens run <config.yaml> --dry-run             # plans only
agentlens run <config.yaml> --execute             # headless real run
agentlens run <config.yaml> --execute --live      # local browser only — headed; visible
agentlens run <config.yaml> --execute --log-actions
agentlens run <config.yaml> --run-id <one_run> --execute --log-actions
agentlens import-online-mind2web --limit 5 --output configs/...   # generate OM2W config from HF
agentlens trajectory-viewer <summary.json>        # static HTML viewer
```

Every CLI `run` invocation auto-snapshots its outputs to `agentlens_results/<experiment>/<UTC_timestamp>/...` so re-running never overwrites prior trajectories or reports.

## Architecture

The framework is layered into **four orthogonal concerns**, each with a small protocol contract so concrete implementations are pluggable:

```
┌────────────────────────────────────────────────────────────────────┐
│  Adapter (per benchmark family)                                    │
│  Owns Playwright + sandbox lifecycle, persists trajectory/reports  │
│      ▼ builds                                                      │
│  ┌─────────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │ AgentActor  │ ←→ │  Orchestrator    │ ←→ │  UserActor       │   │
│  └─────────────┘    │  (turns,         │    └──────────────────┘   │
│        ▲            │   message-       │            ▲              │
│        │            │   passing,       │            │              │
│        │            │   termination)   │            │              │
│        │            └──────────────────┘            │              │
│  ScreenshotReact            │                  NoOpUser            │
│  Mock                       │                  SimulatedFinalJudge │
│  (future)                   │                  SimulatedDialogueUser│
│  - FunctionCalling          │                  (future)            │
│  - MCP                      │                  - HumanCLI          │
│  - DOMReact                 │                  - HumanVNC          │
│  - HumanAgent               │                                      │
└────────────────────────────────────────────────────────────────────┘
                              │
                  ┌───────────▼────────────┐
                  │  Validators            │
                  │  exact / contains /    │
                  │  url_contains /        │
                  │  webjudge / cocoa.test │
                  └────────────────────────┘
```

`src/agentlens/`:

```
actors/
  agent_actor.py          AgentActor protocol (get_init_state + act),
                          AgentState/Observation/Response (Pydantic),
                          OpenAIConfigMixin
  screenshot_react_agent.py
                          ScreenshotReactAgent (wraps the existing loop),
                          MockAgent (replays mock_actions)
  base.py                 UserActor protocol, UserAction, NoOpUser, build_user_actor
  simulated_judge.py      SimulatedFinalJudge (one-shot LLM reviewer)
  dialogue_user.py        SimulatedDialogueUser (multi-turn, persona+goal+private_info)

orchestrator/
  turns.py                TurnBasedOrchestrator
                          - calls agent.act() each turn
                          - calls user.observe() between turns
                          - terminates on accept/reject/no-intervention/max_turns
                          - SESSION_BOUNDARY events between turns
                          - per-turn screenshot subdirs in multi-turn mode
                          - skips user observe entirely when mode='none'

harnesses/
  tool_gating.py          ToolSet + UserToolSet (symmetric agent/user gating)
  eval_protocol.py        Per-task output-format hints + answer reshape
                          (identity / wrap_xml_answer / chat_message)
  screenshot_react_loop.py
                          The inner agent loop (unchanged across these refactors)
  browser_actions.py      Playwright execution + screenshot capture helpers

models/
  base.py                 ChatModel protocol, build_model()
  openai_vision.py        OpenAI Responses-compatible vision model

sandbox/
  aio_sandbox.py          AIO Sandbox container lifecycle
                          + reuse_existing_sandbox + keep_open_seconds flags

tools/
  openai_search.py        Native OpenAI web_search via Responses API

adapters/
  screenshot_react.py     Main adapter; delegates to AgentActor + Orchestrator + UserActor.
                          Local Chromium OR AIO Sandbox via CDP.
  browsergym_bridge.py    Wraps any browsergym/* env (MiniWoB++, AssistantBench, etc.)
  cocoabench.py           CocoaBench-task adapter (each task ships its own AIO Sandbox image)

validators/
  answers.py              exact / contains / url_contains, dispatcher to webjudge
  webjudge.py             LLM-as-judge for live-web outcomes (single-stage MVP)

reports/
  writers.py              summary.json/csv/raw + report.html
  trajectory_viewer.py    Static-HTML per-run viewer
```

The agent's **inner loop** in `screenshot_react_loop.py` has remained stable through every refactor — gating, eval-protocol, orchestrator, AgentActor were all added *around* it without changing it.

## What works today

| Capability | Status |
|---|---|
| Screenshot-ReAct agent loop on local Chromium | ✅ |
| Same loop on **sandboxed** Chromium (AIO Sandbox container, CDP) | ✅ |
| **AgentActor** + **UserActor** protocols (tau2-style symmetric, pluggable on both sides) | ✅ |
| **TurnBasedOrchestrator** — drives multi-turn agent ↔ user dialogue | ✅ |
| Action gating (`tool_harness.tools` constrains action space, dynamically renders prompt) | ✅ |
| Per-step `tool_name` telemetry in trajectory | ✅ |
| Native OpenAI `web_search` (Responses API, same backend as GPT Atlas) | ✅ |
| Multi-tool actions in sandbox: `run_python`, `shell`, `read_file`, `write_file` | ✅ |
| `MemoryScope`-aware sessions: shared container across tasks (`cross_task_same_site`, `cross_benchmark`) | ✅ |
| `SESSION_BOUNDARY` events recording turn / position metadata | ✅ |
| **Single-turn user**: `SimulatedFinalJudge` LLM-as-reviewer with `accept` / `reject` / `annotate_only` policies | ✅ |
| **Multi-turn user**: `SimulatedDialogueUser` — persona + user_goal + private_info + cumulative memory | ✅ |
| **`USER_INTERVENTION`** events recording per-turn decisions | ✅ |
| Eval-confirmation conventions (`output_format_hint`, `answer_format`) declarative per task | ✅ (CocoaBench adapter; others to be wired) |
| Playwright stealth (default ON) for anti-bot mitigation | ✅ |
| Auto-snapshot outputs per CLI invocation | ✅ |
| Per-run `trace.zip` + `video/*.webm` (local browser) | ✅ |
| Per-step screenshots (local + sandbox) | ✅ |
| WebJudge LLM-as-judge validator (single-stage MVP) | ✅ |
| `import-online-mind2web` CLI subcommand for generating OM2W configs | ✅ |
| 6 benchmarks wired: DOMSteer, MiniWoB++, AssistantBench, Online-Mind2Web, DOMSteer-via-sandbox, CocoaBench | ✅ |
| `GATING_VIOLATION` events when agent emits disallowed action | ✅ |
| Static `trajectory_viewer.html` per experiment (limited; full Gradio viewer pending) | ✅ |
| Sandbox **`reuse_existing_sandbox: true`** + **`keep_sandbox_open_seconds: N`** flags for live VNC inspection | ✅ |

## Verified results (real OpenAI calls, gpt-5.4)

| Run | Score | Notes |
|---|---|---|
| MiniWoB++ click-test, click-button, enter-text, choose-list, click-checkboxes (5 tasks) | 5/5 PASS | via BrowserGym bridge |
| AssistantBench imp.0 + 4 test tasks | 0/5 | hard QA; consistent with published baselines |
| Online-Mind2Web 5 tasks (browser only baseline) | mean 0.34 | 3 of 5 failures from anti-bot defenses |
| DOMSteer `tf_discretize_toggle` (browser only) | 1.00 | toggle clicked, URL has `discretize=true` |
| **DOMSteer `tf_discretize_toggle` in sandbox** | 1.00 | same outcome inside Docker container |
| **DOMSteer `datavoyager_most_fuel_efficient` in sandbox + multi-tool** | 1.00 | flipped FAIL→PASS; agent emitted `run_python`, fetched cars dataset, computed `Mazda GLC 46.6 mpg` |
| **DOMSteer `tf_discretize_toggle_judged` (single-turn final-judge user)** | depends on policy | judge verdict recorded; with `combine_with_validator: and` + force-reject persona, the validator's True flips to False and message annotated |
| **DOMSteer `tf_discretize_dialogue` (multi-turn dialogue user)** | 1.00 | turn 1: agent answers without URL hash → user `send_message` requesting it → turn 2: agent updates → user `accept`. 2/3 turns used. |
| CocoaBench `eight_puzzle_game` smoke (multi-tool) | 0.00 (test.py rejected) | infrastructure works end-to-end (container spun, agent used `shell`/`run_python`/`read_file`); agent exhausted 30 steps reverse-engineering the puzzle JS rather than solving the UI. Honest failure, not a harness bug. |

The DataVoyager flip (FAIL → PASS via `run_python`) and the dialogue retry (turn 1 wrong answer → user feedback → turn 2 correct) are the headline cases — concrete evidence the framework can capture trajectory-shape changes that the project's thesis is about.

## Sandbox specifics

When `tool_harness.extra.browser_source: aio_sandbox`:

- Container: `ghcr.io/agent-infra/sandbox:latest` (~3-5 GB image)
- Browser: Chromium inside container, accessed via CDP from host Playwright
- Multi-tool actions (`run_python`, `shell`, `read_file`, `write_file`) routed to bundled MCP servers (Jupyter, shell, file)
- Memory scope `cross_task_same_site` / `cross_benchmark` shares ONE container across tasks
- `tool_harness.extra.stealth: true` (default) injects `playwright_stealth` patches
- **`reuse_existing_sandbox: true`** — attach to whatever's already running on `sandbox_port`; the agent does not spin/stop its own container
- **`keep_sandbox_open_seconds: N`** — linger N seconds after the run completes before tearing the container down (handy for VNC inspection)
- **Limitation:** Playwright `record_video_dir` and `tracing.start()` don't work over `connect_over_cdp`. Sandbox runs have no `trace.zip` or `video/*.webm`. Only `screenshots/step_NNN.png` and `trajectory.json`. Sandbox-side VNC recording is a planned fix (Cut 1.6).

### Live view of a running sandbox

While any sandbox-source run is in progress (or while a probe container is up):

```
http://localhost:8080/vnc/index.html?autoconnect=true&resize=scale
http://localhost:8080/v1/docs                 # Swagger
http://localhost:8080/code-server/            # VS Code in browser
http://localhost:8080/                        # Dashboard
```

Standalone probe (lives until you stop it):

```bash
docker run -d --rm --name agentlens-vnc-probe -p 8080:8080 ghcr.io/agent-infra/sandbox:latest
# ... open the VNC URL above ...
docker stop agentlens-vnc-probe
```

Combine with `reuse_existing_sandbox: true` in your config to have the agent attach to the probe so VNC stays connected throughout the run.

## User actor: who's on the other side

`UserHarnessConfig.mode` selects the user-side actor:

| Mode | What it is | Use case |
|---|---|---|
| `none` (default) | NoOpUser, never intervenes | Standard single-actor run |
| `simulated_final_judge` | One-shot LLM reviewer; observes after agent's `final_answer`; emits `accept` / `reject` | Independent grading signal alongside any validator |
| `simulated_dialogue` | LLM with persona + `user_goal` + `private_info` + multi-turn memory; can `send_message`, `request_clarification`, `accept`, `reject` per turn | Testing agent feedback-handling; eliciting clarification flows |
| (future) `human_cli` | Real human via CLI prompt | Smallest-effort way to put a person in the loop |
| (future) `human_vnc` | Real human via noVNC overlay submit button (G1) | Multi-week; depends on rrweb capture |
| (future) `checkpoint` | Mid-stream user observe every N steps | G3 interface-aware feedback experiments |

`combine_with_validator` policy chooses how the user's verdict folds into the run's success:

- `annotate_only` (default) — record the user's decision; don't change the validator's score
- `and` — both must say PASS for the run to be successful
- `override` — user's decision replaces the validator's

## Eval-confirmation protocols (per benchmark)

Different benchmarks have different "stop-and-deliver" conventions. We encode them declaratively per task via `task.extra`:

| `answer_format` value | Pre-loop | Post-loop |
|---|---|---|
| `identity` (default) | append `output_format_hint` to goal if set | pass `answer` raw to validator |
| `wrap_xml_answer` | append hint | wrap as `<answer>{answer}</answer>` if not already wrapped |
| `chat_message` | append hint | build `[{role:assistant, message:answer}]` for `task.validate(page, msgs)` |

See `docs/benchmarks.md` "Eval confirmation conventions" for the full per-benchmark map.

## Pending todo (consolidated)

### High value, small effort

- **Different judge model than agent** — 1 line per config, removes ~3-7 pt self-preference uplift
- **Cost / $ tracking per task** — token×price rollup in summary report (~30 lines)
- **Resume / checkpoint within an invocation** — skip already-completed trajectories on re-run (~50 lines)
- **`HumanCLIUser`** actor — drop-in via UserActor protocol; reads accept/reject/feedback from stdin (~30 min)
- **Per-step model timeout** — wrap `model.step()` so a hung OpenAI call doesn't stall whole runs (~15 min)
- **Wire `eval_protocol`** into the rest of the adapters (currently only CocoaBench uses it)
- **Sandbox VNC video recording (Cut 1.6)** — record the noVNC stream with ffmpeg so sandbox runs get a video artifact like local runs do (~30-60 min)
- **Refresh `docs/multi-tool-and-sessions.md`** with the orchestrator/actor refactor (~15 min)
- **Refresh `docs/screenshot-react-tools.md`** to mention `web_search`, `run_python`, `shell`, `read_file`, `write_file` (~15 min)

### Medium effort, high strategic value

- **Cut 3 — `--parallel N`** with one container per worker; reject parallel + cross-task scope (~1 day)
- **Trajectory viewer expansion** — current `trajectory_viewer.html` is partial; full version covers `USER_INTERVENTION` + `SESSION_BOUNDARY` and dialogue runs (~1-2 days)
- **`FunctionCallingAgent`** — OpenAI tool-use API instead of free-form JSON (matches CocoaBench-official harness style) (~1 day)
- **Checkpoint user mode** (mid-stream observe via existing `tool_output_since_last_step` channel) (~1 hr)
- **CocoaBench full-tools smoke until pass** — needs richer prompt + per-step timeout
- **rrweb continuous DOM capture (G2)** — required for human runner; captures *between-action* behavior (the canonical interface-faithful signal the project's thesis is about) (~1 day)
- **Anti-bot hardening** — cookie/consent autofill; optional `curl_cffi` for TLS-level stealth on Akamai-class sites
- **Per-task MCP tool discovery** for CocoaBench (extend `tool_harness.tools` from `/v1/mcp/servers` per-task)

### Bigger / paper-grade

- **`HumanVNCUser`** — submit-overlay button on the noVNC page; real human as user actor (G1)
- **`HumanAgent`** — control study: real human as the *agent* on the same task pool
- **Full 3-stage WebJudge** (key-point ID → key-screenshot ID → outcome judgment) — closes ~5-10 pt agreement gap to published Online-Mind2Web baselines
- **More benchmarks not wired**: WorkArena (free ServiceNow dev instance), BrowseComp, WebCanvas (key-node listeners), full WebArena (~130 GB Docker)
- **Custom-image build** for CocoaBench tasks whose Dockerfile isn't trivial
- **Pin dataset + model versions** (HF revision SHA, dated OpenAI snapshot ids) — reproducibility

### Documentation

- `docs/harness-styles.md` capturing alternative agent styles (function-calling, MCP, WebMCP, DOM-ReAct, code-as-action)
- This file (`docs/handout.md`) ← currently up-to-date

## Important: agent ≠ judge ≠ user

Three distinct LLM call sites in the pipeline:

1. **Agent model** — picks the next action each step (`src/agentlens/models/openai_vision.py`). Configured per-run via `model: <id>` in YAML.
2. **Judge model** — runs validators (`src/agentlens/validators/webjudge.py`). Configured per-task via `extra.judge_model`.
3. **User model** — runs the user actor (`src/agentlens/actors/{simulated_judge,dialogue_user}.py`). Configured per `UserHarnessConfig.model`.

These are independent code paths and can use the same model (cheap) or different (less self-preference bias). For paper-grade comparisons, prefer different models for at least 2 of 3.

## Security note

`.env` is gitignored; never paste keys into YAML / chat / committed files. `.env.example` holds only placeholders.

If an OpenAI key was ever pasted in chat in an early session, rotate it at https://platform.openai.com/api-keys.
