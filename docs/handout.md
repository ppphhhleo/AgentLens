# AgentLens Handoff

> **For the next agent session.** This file is the single entry point — reading top-to-bottom should be enough to pick up the project. The thesis, architecture, what works, and what's left to do (with rationale) are all here. Cross-references to deeper docs are inline.

A unified framework for evaluating browser-agent systems across the same tasks, capturing normalized trajectories, and comparing strategies under different tool / harness / memory / actor configurations.

The project's central thesis (`docs/general-idea.md`): **agents are opportunistic problem-solvers, humans are interface-faithful users**. AgentLens makes that comparison rigorous.

## Start here (orientation, ~5 min)

1. **Mental model** — `Run = Model × ToolHarness × MemoryHarness × UserHarness × Task × Seed × Trial`. Every YAML config is one experiment matrix; a CLI invocation enumerates all cells.
2. **Key files** — read in this order:
   - `src/agentlens/schemas.py` — Pydantic config types; the source of truth for what's configurable
   - `src/agentlens/actions.py` — the agent's action space (one Pydantic union)
   - `src/agentlens/harnesses/screenshot_react_loop.py` — the inner agent loop (small, ~300 lines, stable through every refactor)
   - `src/agentlens/orchestrator/turns.py` — the pure message-passing layer between AgentActor and UserActor
   - `src/agentlens/adapters/screenshot_react.py` — wires Playwright + sandbox lifecycle around the loop
3. **Run something** — `agentlens run configs/experiments/domsteer_screenshot_react.yaml --execute --live --log-actions` (needs `OPENAI_API_KEY`). Smoke configs in `configs/experiments/*_smoke.yaml`.
4. **What changed recently** — capture-first virtual-computer support is now wired for AWS smoke runs: screenshots + browser actions + Python/shell/file I/O + artifact diffs. The current pilot config is `configs/experiments/capture_first_domsteer_agentcompany.yaml`; the deterministic intervention smoke is `configs/experiments/intervention_repeated_action_smoke.yaml`.
5. **Where to extend** — the four pluggable axes are AgentActor, UserActor, perception modes, and addressing modes. The orchestrator is **not** pluggable — it's the contract.

## Where to find what

| Topic | Doc |
|---|---|
| **Project vision, goals (G1–G6), full architecture, paper plan** | `docs/general-idea.md` |
| **All benchmarks** + per-benchmark eval-confirmation conventions + cross-cutting pending work | `docs/benchmarks.md` |
| **Multi-tool + sandboxed sessions plan** — Cuts 1/2/3, agent ↔ human access modes, MemoryScope policy | `docs/multi-tool-and-sessions.md` |
| **Action schema reference** | `docs/screenshot-react-tools.md` |
| **Trajectory data + reports + viewer** — on-disk layout, `trajectory.json` event schema, viewer/report walkthrough | `docs/trajectory-and-visualization.md` |
| **Capture-first virtual computer + intervention plan** — AWS setup notes, I/O capture, repeated-action intervention | `docs/capture-first-computer-use-and-intervention.md` |
| **Trajectory processing v0** — raw actions → workflow steps → behavior labels | `docs/trajectory-processing-v0.md` |
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
agentlens process-trajectories agentlens_results --output-dir agentlens_results/trajectory_processing/local_v0
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
                          The inner agent loop; now includes sandbox I/O
                          telemetry and optional step-level interventions
  browser_actions.py      Playwright execution + screenshot/hint overlay helpers
  interventions.py        Rule monitors; currently repeated-action warning

models/
  base.py                 ChatModel protocol, build_model()
  openai_vision.py        OpenAI Responses-compatible vision model

sandbox/
  aio_sandbox.py          AIO Sandbox container lifecycle
                          + AWS Docker runtime flags, reuse_existing_sandbox,
                          keep_open_seconds, code/shell/file fallbacks

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

analysis/
  trajectory_processing.py
                          Deterministic offline processor:
                          trajectory.json -> workflow_steps.jsonl,
                          trajectory_summaries.csv/jsonl, behavior codebook
```

The agent's **inner loop** in `screenshot_react_loop.py` has remained stable through every refactor — gating, eval-protocol, orchestrator, AgentActor were all added *around* it without changing it.

## (1) Supported benchmarks

| Benchmark | Adapter / runner | Eval method | Status | Smoke config |
|---|---|---|---|---|
| **DOMSteer** (own, 8 tasks) | `screenshot_react` (local Chromium or AIO Sandbox) | `url_contains` / `final_answer` / `webjudge` | ✅ wired | `domsteer_screenshot_react.yaml`, `domsteer_sandbox.yaml` |
| **MiniWoB++** | `browsergym_bridge` | env-native success | ✅ wired (5/5 PASS smoke) | `miniwob_screenshot_react.yaml` |
| **AssistantBench** | `browsergym_bridge` | env-native (free-form QA) | ✅ wired (hard; 0/5 baseline) | `assistantbench_screenshot_react.yaml` |
| **Online-Mind2Web** | `screenshot_react` + `import-online-mind2web` CLI | WebJudge LLM-as-judge (single-stage MVP) | ✅ wired (mean 0.34 on 5-task slice) | `online_mind2web_screenshot_react.yaml`, `online_mind2web_session.yaml` |
| **CocoaBench** | `cocoabench` (per-task AIO Sandbox image) | `cocoa.test.py` (XML-wrapped answer) | ✅ wired; long-horizon failure cases known | `cocoabench_smoke.yaml` |
| **DOMSteer-via-sandbox** (DOMSteer tasks executed inside AIO Sandbox) | `screenshot_react` + `browser_source: aio_sandbox` | same as DOMSteer | ✅ wired | `domsteer_sandbox.yaml`, `online_mind2web_multitool.yaml` |
| **Capture-first pilot** (DOMSteer + AgentCompany-style I/O smoke) | `screenshot_react` local/AIO Sandbox | final answer + artifact diffs | ✅ wired; AWS smoke verified | `capture_first_domsteer_agentcompany.yaml` |
| WorkArena, BrowseComp, WebCanvas, full WebArena, VisualWebArena | — | — | ⏳ planned | — |

Per-benchmark eval-confirmation conventions (identity / wrap_xml_answer / chat_message) live in `docs/benchmarks.md`.

## (2) Supported agentic framework

Pluggable on three axes — agent style, user style, perception/addressing — bound together by a thin orchestrator.

**AgentActor protocol** (`actors/agent_actor.py`): `get_init_state()` + `act(state, observation) → response`.

| AgentActor | What it does | Status |
|---|---|---|
| `ScreenshotReactAgent` | Free-form JSON ReAct over OpenAI vision; supports all perception/addressing modes below | ✅ |
| `MockAgent` | Replays a canned `mock_actions` list; for harness/orchestrator unit tests | ✅ |
| `FunctionCallingAgent` | OpenAI tool-use API instead of JSON (matches CocoaBench-official harness style) | ⏳ |
| `MCPAgent` | Speaks MCP tools surfaced by AIO Sandbox or per-task MCP servers | ⏳ |
| `DOMReactAgent` (subsumed) | Just `ScreenshotReactAgent` with `input_modes: [axtree]` + `addressing_modes: [bid]` | ✅ via mode flags |
| `WebMCPAgent` | Targets sites publishing Chrome's WebMCP; needs synthetic test sites | ⏳ |
| `HumanAgent` | Real human as the agent (control study) | ⏳ |

**UserActor protocol** (`actors/base.py`): symmetric to AgentActor — same shape, different intent.

| UserActor | Mode | Status |
|---|---|---|
| `NoOpUser` | `none` (default) — never intervenes | ✅ |
| `SimulatedFinalJudge` | `simulated_final_judge` — one-shot LLM reviewer at end-of-trajectory | ✅ |
| `SimulatedDialogueUser` | `simulated_dialogue` — multi-turn LLM with persona + user_goal + private_info + cumulative memory | ✅ |
| `HumanCLIUser` | `human_cli` — accept/reject/feedback over stdin | ⏳ |
| `HumanVNCUser` | `human_vnc` — submit overlay on noVNC stream (G1) | ⏳ |
| Checkpoint user | mid-stream observe every N steps | ⏳ |

**Step-level intervention monitor** (`harnesses/interventions.py`): separate from `UserActor`.
It runs inside the agent action loop, before execution, and can record warnings
or future blocks. Current implementation is warning-only repeated-action
detection. This is deliberately distinct from `SimulatedDialogueUser`: the
simulated user is a turn-level collaborator/judge; the intervention monitor is
a step-level detector/coach.

**Orchestrator** (`orchestrator/turns.py`): `TurnBasedOrchestrator` is the protocol layer — pure message-passing between AgentActor and UserActor, emits `SESSION_BOUNDARY` events, terminates on accept / reject / no-intervention / max_turns. **Not pluggable** — it's the contract, not a strategy.

**Perception modes** (`input_modes`) and **addressing modes** (`addressing_modes`) are orthogonal flags on `tool_harness.extra`:

| `input_modes` | `addressing_modes` | Style |
|---|---|---|
| `[screenshot]` | `[coordinate]` | Vision-only baseline (computer-use) |
| `[axtree]` | `[bid]` | DOM-ReAct (BrowserGym style) |
| `[screenshot, axtree]` | `[coordinate, bid]` | Hybrid (max-info) |
| `[set_of_marks]` | `[mark]` | SoM-only (Anthropic computer-use style) |
| `[set_of_marks, axtree]` | `[mark, bid]` | **`browser-use` recipe** (most robust) |

5/5 modes verified on `tf_discretize_toggle`; 4/5 PASS. Pure-SoM-alone fails on adjacent small-target visual confusion (model picks neighbor mark) — documented limitation, not a framework bug. See `configs/experiments/perception_modes_smoke.yaml`.

**Eval-confirmation protocols** (`harnesses/eval_protocol.py`): `identity`, `wrap_xml_answer`, `chat_message` — declarative per-task via `task.extra`, lets one ScreenshotReactAgent satisfy benchmarks with different stop-and-deliver conventions.

**Memory scopes** (`MemoryScope`): `none` / `in_task` / `cross_trial` / `cross_task_same_site` / `cross_benchmark` — controls AIO Sandbox session reuse across tasks.

## (3) Tools and harness

**Action space** — the union of `ComputerAction` types in `actions.py`. Each action is gated per-harness via `tool_harness.tools` (allowlist) and dynamically rendered into the prompt schema:

| Tool name | Action type(s) | Tier required |
|---|---|---|
| `browser.screenshot` | `screenshot` | browser_only |
| `browser.click` / `browser.double_click` | `click` / `double_click` (coord OR bid OR selector OR mark) | browser_only |
| `browser.scroll` / `browser.move` | `scroll` / `move` | browser_only |
| `browser.type` / `browser.keypress` / `browser.wait` | `type` / `keypress` / `wait` | browser_only |
| `browser.drag` | `drag` (path of points) | browser_only |
| `browser.goto` / `browser.back` / `browser.forward` / `browser.reload` | navigation | browser_only |
| `web.openai_search` | `web_search` (Responses API; same backend as GPT Atlas) | browser_only |
| `code.run_python` | `run_python` (Jupyter MCP) | full_sandbox |
| `code.shell` | `shell` (shell MCP) | full_sandbox |
| `files.read` / `files.write` | `read_file` / `write_file` (file MCP) | browser_files / full_sandbox |
| `task.final_answer` | `final_answer` | always |
| `user.accept` / `user.reject` / `user.send_message` / `user.request_clarification` / `user.no_intervention` | UserAction (gated by `UserToolSet`) | user side |

**Tiers** (`ToolHarnessTier` enum in `schemas.py`) — coarse capability budget; each adapter enforces an accept-list at run time:

| Tier | Action surface | Browser source | Adapters that accept it |
|---|---|---|---|
| `browser_only` | `browser.*`, `web.openai_search`, `task.final_answer` | local Chromium **or** AIO Sandbox | `screenshot_react`, `browsergym_bridge`, `browsergym_direct`, `agentlab` |
| `browser_files` | `browser_only` + `files.read` / `files.write` | requires AIO Sandbox | `screenshot_react`, `cocoabench` |
| `full_sandbox` | `browser_files` + `code.run_python` + `code.shell` | requires AIO Sandbox | `screenshot_react`, `cocoabench` |

The `tools` allowlist further narrows the tier (e.g. tier `full_sandbox` with `tools: [browser.click, task.final_answer]` is valid — tier is the upper bound, not the literal action set). Mismatches (e.g. `browsergym_bridge` + `full_sandbox`) are rejected at adapter dispatch.

**ToolHarnessConfig** (`schemas.py`):

- `runner`: `screenshot_react` | `browsergym_bridge` | `cocoabench` | `browsergym_direct` | `agentlab`
- `tier`: `browser_only` | `browser_files` | `full_sandbox`
- `tools`: explicit allowlist (drives prompt schema + runtime gating)
- `prompt_version`: e.g. `screenshot_react_json_v1`
- `extra`: free-form per-runner flags
  - **Perception**: `input_modes`, `addressing_modes`
  - **Browser source**: `browser_source: local | aio_sandbox`, `headless`, `slow_mo_ms`, `settle_ms`, `viewport`, `stealth`
  - **Sandbox**: `sandbox_image`, `sandbox_port`, `reuse_existing_sandbox`, `keep_sandbox_open_seconds`
  - **AWS sandbox runtime**: `sandbox_shm_size`, `sandbox_cap_add`, `sandbox_security_opt`, `sandbox_watch_paths`
  - **Recording**: `tracing`, `record_video`
  - **Intervention**: `intervention.enabled`, `intervention.repeated_action.threshold`, `mode`, `signature`, `message`

**UserHarnessConfig**: `mode`, `model`, `tools` (allowlisted UserActions), `persona`, `intervention_policy`, `combine_with_validator` (`annotate_only` | `and` | `override`), `max_turns`, `extra`.

**Trajectory event types** (`schemas.py`): `MODEL_MESSAGE`, `BROWSER_ACTION`, `TOOL_CALL`, `SCREENSHOT`, `USER_INTERVENTION`, `SESSION_BOUNDARY`, `GATING_VIOLATION` — same shape across every runner so the report writer / viewer don't need to special-case.

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
| Artifact diffs around sandbox tool calls (`created`, `modified`, `deleted`) | ✅ |
| AWS EC2 AIO Sandbox launch with Chrome CDP (`--shm-size=2g`, `SYS_ADMIN`, unconfined seccomp) | ✅ |
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
| Warning-only repeated-action intervention with page text hint + `USER_INTERVENTION` event | ✅ |
| Offline trajectory processing: raw events → workflow steps → behavior labels/summaries | ✅ |

## Verified results

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
| AWS `tac_io_capture_mock` | 1.00 | AIO Sandbox started on EC2, captured screenshot + `write_file`/`run_python`/`shell`/`read_file`, and recorded artifact diffs for `/tmp/agentlens_capture_smoke.csv` and `/tmp/agentlens_capture_report.txt`. |
| AWS DOMSteer DataVoyager with `gpt-4o-mini-2024-07-18` before intervention | 0.00 | Capture worked; model repeated drag actions for 11 steps, then hit a short TPM rate limit. Useful initial repeated-action challenge case. Config now uses `gpt-5.4-nano`. |
| Local `intervention_repeated_action_smoke` | 1.00 | Three repeated mock drags triggered exactly one warning-only `USER_INTERVENTION` event. |
| Local `process-trajectories agentlens_results` | 41 trajectories processed | Produced `workflow_steps.jsonl`, `trajectory_summaries.jsonl`, `trajectory_summaries.csv`, and `behavior_codebook.json` under `agentlens_results/trajectory_processing/local_v0`. |

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

## Trajectory data + visualization

Full reference: **`docs/trajectory-and-visualization.md`** (on-disk layout, `trajectory.json` event schema, summary CSV columns, the viewer/report walkthrough, analysis patterns, viewer-extension guide).

In brief:

- Every CLI invocation snapshots to `agentlens_results/<experiment>/<UTC_ts>/` — never overwrites
- `trajectory.json` is an ordered list of `TrajectoryEvent`s with seven event types: `MODEL_MESSAGE`, `BROWSER_ACTION`, `TOOL_CALL`, `SCREENSHOT`, `USER_INTERVENTION`, `SESSION_BOUNDARY`, `GATING_VIOLATION` — same shape across every adapter
- Two static HTML surfaces, both self-contained (`scp`-able): `report.html` (per-experiment table) and `trajectory_viewer.html` (per-run timeline)
- Live VNC at `http://localhost:8080/vnc/...` for sandbox runs; `trace.zip` + `video/*.webm` for local-browser runs
- No dedicated analysis library — analysis is pandas-on-`summary.csv` today
- Viewer doesn't yet render `USER_INTERVENTION` / `SESSION_BOUNDARY` / `GATING_VIOLATION` distinctly — see the "Trajectory viewer expansion" todo

## Known limitations (won't-fix-quickly; don't chase)

- **Pure Set-of-Marks visual confusion on small adjacent targets.** Mode `[set_of_marks]` + `[mark]` consistently picks the wrong neighbor on TF Playground's discretize toggle (M20 vs M21). Increasing badge font to 14px did not fix it. SoM+AXTree (the actual `browser-use` recipe) passes. This is a **model-perception limitation**, not a framework bug — confirmed by the 5-mode smoke matrix.
- **Sandbox runs have no `trace.zip` / `video/*.webm`.** Playwright `record_video_dir` and `tracing.start()` don't work over `connect_over_cdp`. Sandbox runs only emit `screenshots/step_NNN.png` + `trajectory.json`. Fix path is sandbox-side ffmpeg recording (Cut 1.6 in pending todos).
- **WebMCP has no real-world publishers.** The Chrome WebMCP proposal is interesting but no live sites publish it yet. A `WebMCPAgent` needs synthetic test sites to demonstrate.
- **CocoaBench `eight_puzzle_game` smoke fails at the agent level, not the harness.** The agent reverse-engineers the puzzle JS instead of solving the UI. Don't keep re-running it expecting different results without changing the prompt or step budget.
- **AssistantBench scores are low (0/5 on our 5-task slice) and that's expected.** Hard QA, no retry, no scratchpad, 25-step cap — consistent with published GPT-class baselines around 25-30%.

## Pending todo (consolidated, with rationale)

Each item names *what*, *why it matters* (so a fresh agent can prioritize), and a rough size.

### High value, small effort

- **Wire perception modes through `browsergym_bridge` + `cocoabench` adapters** — *only `screenshot_react` honors `input_modes` / `addressing_modes` today.* **Why:** the perception-mode comparison is the project's central experimental knob; until every adapter respects it, MiniWoB++/AssistantBench/CocoaBench can't be in the same comparison plot. (~2 hrs)
- **Wire `eval_protocol` into non-CocoaBench adapters** — *only `cocoabench.py` calls `goal_with_format_hint` / `prepare_answer_for_validator`.* **Why:** without this, benchmarks with different stop-and-deliver conventions (BrowseComp wrapped-XML, WebCanvas key-node) need bespoke adapters instead of one declarative `task.extra.answer_format`. (~1 hr)
- **Different judge model than agent** — 1 line per config. **Why:** same-model self-preference adds ~3-7 pt uplift; for any paper claim, the judge must be independent. (~10 min)
- **Per-step model timeout** — wrap `model.step()` with a deadline. **Why:** today a hung OpenAI call stalls the whole batch run; one slow task ruins overnight results. (~15 min)
- **Cost / $ tracking per task** — token × price rollup in `summary.json` / `report.html`. **Why:** without this, "is this run worth re-running" is a guess. ~30 lines.
- **Resume / checkpoint within an invocation** — detect existing `validation_event` and skip. **Why:** a 300-task run that dies at task 100 currently restarts from 0 — costly and slow. ~50 lines.
- **`HumanCLIUser`** actor — UserActor reading accept/reject/feedback from stdin. **Why:** smallest-possible "real human in the loop" — unblocks early G1 experiments without the noVNC build. (~30 min)
- **Sandbox VNC video recording (Cut 1.6)** — ffmpeg-record the noVNC stream. **Why:** sandbox runs currently produce no `video/*.webm` (Playwright tracing doesn't work over CDP); without video, debugging anti-bot failures and showing demos is painful. (~30-60 min)

### Medium effort, high strategic value

- **Cut 3 — `--parallel N`** with one container per worker; reject parallel + cross-task-scope memory. **Why:** the only thing standing between us and full Online-Mind2Web (300 tasks); sequentially that's hours wall-clock, parallel it's minutes. The schema already enforces the scope/parallelism constraint. (~1 day)
- **Trajectory viewer expansion** — render `USER_INTERVENTION`, `SESSION_BOUNDARY`, `GATING_VIOLATION` events; show dialogue runs end-to-end. **Why:** without this, multi-turn user dialogue is invisible in the report — the headline "agent failed turn 1, fixed by user feedback turn 2" pattern can only be seen by reading raw JSON. (~1-2 days)
- **`FunctionCallingAgent`** — OpenAI tool-use API instead of free-form JSON. **Why:** (a) matches CocoaBench-official harness so we can reproduce their numbers; (b) eliminates JSON-parsing failures we sometimes see on small models. (~1 day)
- **Checkpoint user mode** — mid-stream observe every N steps via `tool_output_since_last_step`. **Why:** G3 (interface-aware feedback) requires the user to intervene *during* a task, not just at the end. The wiring already exists; just needs an orchestrator branch. (~1 hr)
- **CocoaBench full-tools smoke until pass** — agent currently exhausts steps reverse-engineering puzzle JS. **Why:** until at least one CocoaBench task PASSES end-to-end, we can't claim long-horizon multi-tool support in the paper. Needs richer prompt + per-step timeout above. (~half day)
- **rrweb continuous DOM capture (G2)** — capture between-action behavior (hover, scan, dwell). **Why:** this IS the project's thesis signal — interface-faithful behavior shows up in micro-interactions, not in the final-action sequence. Required for any G1 human-vs-agent comparison. (~1 day)
- **Anti-bot hardening** — cookie/consent autofill; optional `curl_cffi` for TLS-level stealth. **Why:** 3/5 Online-Mind2Web failures in our smoke were anti-bot, not agent reasoning. Without hardening, scores blame the agent for environment failures. (~1 day)
- **Per-task MCP tool discovery for CocoaBench** — read each task's `/v1/mcp/servers` to expand `tool_harness.tools` dynamically. **Why:** CocoaBench tasks ship task-specific MCP servers; without discovery, we either over-provision (security risk) or miss task-essential tools. (~half day)

### Bigger / paper-grade

- **`HumanVNCUser`** (G1) — submit-overlay button on the noVNC page; real human as user actor. **Why:** the canonical G1 study (real human reviewing real agent on real interface). Multi-week; depends on rrweb capture above.
- **`HumanAgent`** — real human as the *agent* on the same task pool. **Why:** the control study for the project's central thesis — without this, "humans are interface-faithful" is asserted, not measured.
- **Full 3-stage WebJudge** (key-point ID → key-screenshot ID → outcome). **Why:** closes ~5-10 pt agreement gap to published Online-Mind2Web baselines; required if we want our scores to be comparable to theirs.
- **More benchmarks**: WorkArena (free ServiceNow dev instance — ~half day), BrowseComp (~half day), WebCanvas (key-node listeners — novel partial-credit signal), full WebArena (~130 GB Docker, ~half day setup). **Why:** broader benchmark coverage = stronger generality claims; WebCanvas's key-node listeners specifically would unblock per-step progress signals.
- **WebMCP synthetic test site + `WebMCPAgent`** — Chrome's experimental Model Context Protocol for web pages. **Why:** WebMCP is the only "real" structured-action interface modern web sites might converge on; no real publishers exist yet, so we'd need synthetic sites to demonstrate the agent style. Speculative but cheap to scaffold (~half day for synthetic site + agent).
- **Custom-image build** for CocoaBench tasks whose Dockerfile isn't `FROM ghcr.io/agent-infra/sandbox`. **Why:** unblocks the long-tail of CocoaBench tasks beyond the example set.
- **Pin dataset + model versions** (HF revision SHA, dated OpenAI snapshot ids). **Why:** without this, "reproduce our table 3" is best-effort — model aliases and HF datasets silently rev.

### Documentation

- **`docs/harness-styles.md`** — capture alternative agent styles (function-calling, MCP, WebMCP, DOM-ReAct, code-as-action) as one reference. **Why:** the perception/addressing-mode matrix is one taxonomy axis; "harness style" (free-form JSON vs tool-use vs MCP) is a second axis we're already building toward. (~1 hr)
- **This file (`docs/handout.md`)** — kept current; refreshed `2026-05-06`.

### Recently shipped (do NOT redo)

- ✅ AgentActor + UserActor protocols, TurnBasedOrchestrator (commit history)
- ✅ Multi-tool sandbox actions (`run_python` / `shell` / `read_file` / `write_file`)
- ✅ MemoryScope-aware sessions; `reuse_existing_sandbox` + `keep_sandbox_open_seconds`
- ✅ AXTree perception + bid/selector/mark addressing + Set-of-Marks (commit `0634795`)
- ✅ `eval_protocol` (identity / wrap_xml_answer / chat_message) — wired in CocoaBench adapter
- ✅ Doc refresh of `multi-tool-and-sessions.md`, `screenshot-react-tools.md`, `benchmarks.md` (`2026-05-06`)

## Important: agent ≠ judge ≠ user

Three distinct LLM call sites in the pipeline:

1. **Agent model** — picks the next action each step (`src/agentlens/models/openai_vision.py`). Configured per-run via `model: <id>` in YAML.
2. **Judge model** — runs validators (`src/agentlens/validators/webjudge.py`). Configured per-task via `extra.judge_model`.
3. **User model** — runs the user actor (`src/agentlens/actors/{simulated_judge,dialogue_user}.py`). Configured per `UserHarnessConfig.model`.

These are independent code paths and can use the same model (cheap) or different (less self-preference bias). For paper-grade comparisons, prefer different models for at least 2 of 3.

## Security note

`.env` is gitignored; never paste keys into YAML / chat / committed files. `.env.example` holds only placeholders.

If an OpenAI key was ever pasted in chat in an early session, rotate it at https://platform.openai.com/api-keys.
