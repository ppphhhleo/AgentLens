# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AgentLens is a research platform for comparing human and agent trajectories on live web interfaces. Central thesis: **agents are opportunistic problem-solvers, humans are interface-faithful users**. Built as an extension of ServiceNow's BrowserGym/AgentLab ecosystem.

## Setup and commands

```bash
source .venv/bin/activate
cp .env.example .env       # edit: OPENAI_API_KEY
```

Run the check, lint, test:
```bash
ruff check src/                    # lint
ruff format --check src/           # format check
pytest                             # no tests exist yet
```

Run experiments:
```bash
agentlens list-configs
agentlens validate-config configs/experiments/<file>.yaml
agentlens run configs/experiments/<file>.yaml --dry-run
agentlens run configs/experiments/<file>.yaml --execute --live --log-actions
agentlens run configs/experiments/<file>.yaml --execute --run-id <one_run> --log-actions
agentlens trajectory-viewer agentlens_results/<exp>/<ts>/<runner>_summary/summary.json
agentlens import-online-mind2web --limit 5 --output configs/experiments/om2w.yaml
```

For sandbox runs (multi-tool actions: `run_python`, `shell`, `read_file`, `write_file`):
```bash
docker pull ghcr.io/agent-infra/sandbox:latest    # one-time, ~3-5 GB
```
Then set `browser_source: aio_sandbox` in the harness config. Live VNC at `http://localhost:8080/vnc/index.html?autoconnect=true&resize=scale`.

## Architecture

The framework layers four orthogonal concerns, each with a protocol contract:

**Adapters** own Playwright + sandbox lifecycle for a benchmark family. `ScreenshotReactAdapter` is the main one; `BrowserGymBridgeAdapter`, `BrowserGymDirectAdapter`, and `CocoaBenchAdapter` handle specific benchmarks.

**AgentActor** (`actors/agent_actor.py`) — protocol with `get_init_state(observation)` + `act(observation, state) → response`. Current implementations: `ScreenshotReactAgent` (free-form JSON ReAct over OpenAI vision), `MockAgent` (replays canned actions).

**TurnBasedOrchestrator** (`orchestrator/turns.py`) — drives turn-taking between AgentActor and UserActor. Calls `agent.act()` each turn, `user.observe()` between turns. Terminates on accept/reject/no-intervention/max_turns. **Not pluggable.**

**UserActor** (`actors/base.py`) — symmetric protocol to AgentActor. `NoOpUser`, `SimulatedFinalJudge` (one-shot LLM reviewer), `SimulatedDialogueUser` (multi-turn persona-driven).

The inner agent loop (`harnesses/screenshot_react_loop.py`, ~300 lines) is stable — gating, eval-protocol, orchestrator, and AgentActor were all added *around* it without changing it.

### Key data flow

```
ExperimentConfig (YAML) → build_run_plans() → adapter.build_run_plans() → adapter.run_many()
```

Each CLI invocation snapshots to `agentlens_results/<experiment>/<UTC_timestamp>/` — never overwrites prior runs.

### Dimension matrix

`Run = Model × ToolHarness × MemoryHarness × UserHarness × Task × Seed × Trial`

- **Perception modes** (`input_modes` on `tool_harness.extra`): `screenshot`, `axtree`, `set_of_marks` (and combinations)
- **Addressing modes** (`addressing_modes` on `tool_harness.extra`): `coordinate`, `bid`, `selector`, `mark` (and combinations)
- **Tool tiers** (`ToolHarnessTier`): `browser_only` → `browser_files` → `full_sandbox`
- **Memory scopes** (`MemoryScope`): `none` → `in_task` → `cross_trial` → `cross_task_same_site` → `cross_benchmark`

### Source of truth

`src/agentlens/schemas.py` is the canonical source of truth for all configuration types (`ExperimentConfig`, `RunConfig`, `TaskConfig`, `ToolHarnessConfig`, `MemoryHarnessConfig`, `UserHarnessConfig`) and trajectory types (`Trajectory`, `TrajectoryEvent`, `RunMetrics`). Always start there when adding config surface.

`src/agentlens/actions.py` defines the `ComputerAction` Pydantic model — the full action space. Open it when adding a new tool.

`src/agentlens/harnesses/tool_gating.py` is the single source of truth for tool allow-lists. Both prompt rendering and runtime gating read from the same `ToolSet`. Adding a new action requires entries in both `actions.py` and `tool_gating.py`.

### Key modules

| Module | Role |
|---|---|
| `schemas.py` | All Pydantic config + trajectory types |
| `actions.py` | `ComputerAction` union type |
| `harnesses/tool_gating.py` | Tool allow-lists, prompt schema rendering, `ToolSet` |
| `harnesses/screenshot_react_loop.py` | Inner agent ReAct loop — model.call → action → execute |
| `harnesses/browser_actions.py` | Playwright execution + screenshot capture |
| `harnesses/eval_protocol.py` | Per-benchmark output-format conventions (`identity` / `wrap_xml_answer` / `chat_message`) |
| `models/base.py` | `ChatModel` protocol + `build_model()` factory |
| `models/openai_vision.py` | OpenAI vision model wrapper |
| `orchestrator/turns.py` | `TurnBasedOrchestrator` |
| `actors/agent_actor.py` | `AgentActor` protocol, `AgentState`, `AgentObservation` |
| `actors/base.py` | `UserActor` protocol, `build_user_actor()` factory |
| `adapters/screenshot_react.py` | Main adapter — wires Playwright + sandbox + AgentActor + Orchestrator |
| `adapters/browsergym_bridge.py` | Wraps any `browsergym/*` env |
| `adapters/cocoabench.py` | CocoaBench adapter (per-task Docker images) |
| `run_plans.py` | YAML → executable plans, memory-scope grouping, snapshot directories |
| `sandbox/aio_sandbox.py` | `AIOSandboxSession` context manager for Docker containers |
| `perception/axtree.py` | AXTree extraction |
| `perception/set_of_marks.py` | Set-of-Marks overlay injection |
| `validators/answers.py` | `exact` / `contains` / `url_contains` validators |
| `validators/webjudge.py` | LLM-as-judge (single-stage MVP) |
| `reports/writers.py` | `summary.json`/`csv`/`html` report generation |
| `reports/trajectory_viewer.py` | Static HTML per-run viewer |

### Trajectory format

Every adapter produces the same `trajectory.json` shape: a `Trajectory` with `events: list[TrajectoryEvent]`. Seven event types: `MODEL_MESSAGE`, `BROWSER_ACTION`, `TOOL_CALL`, `SCREENSHOT`, `USER_INTERVENTION`, `SESSION_BOUNDARY`, `GATING_VIOLATION`. Analysis code never needs to special-case per adapter.

### Three independent LLM call sites

1. **Agent model** — picks each action (`models/openai_vision.py`, configured via `model: <id>`)
2. **Judge model** — scores the trajectory (`validators/webjudge.py`, configured via `task.extra.judge_model`)
3. **User model** — runs the user actor (`actors/simulated_judge.py`, configured via `UserHarnessConfig.model`)

For paper-grade results, use different models for at least 2 of 3 to avoid self-preference bias (~3-7 pt uplift).

### Eval-confirmation conventions

Different benchmarks need different "stop and deliver" protocols. Declared per-task via `task.extra.answer_format`:
- `identity` (default) — pass answer raw to validator
- `wrap_xml_answer` — wrap as `<answer>...</answer>` (CocoaBench, BrowseComp)
- `chat_message` — build `[{role:assistant, message:answer}]` (AssistantBench)

Implemented in `harnesses/eval_protocol.py`; currently only wired in CocoaBench adapter.

### Sandbox / multi-tool

When `browser_source: aio_sandbox`, the agent connects to Chromium inside a Docker container via CDP. Multi-tool actions (`run_python`, `shell`, `read_file`, `write_file`) route to the container's bundled MCP servers. Playwright tracing/video don't work over CDP — sandbox runs only produce `screenshot/*.png` + `trajectory.json`.

### Configs

Experiment configs live in `configs/experiments/`. Smoke configs (suffixed `_smoke.yaml`) are good starting points for testing. The `import-online-mind2web` CLI generates configs from the HF dataset rather than hand-authoring them.

## Important conventions

- Per-invocation snapshot directories under `agentlens_results/` — re-running never overwrites
- `tool_harness.tier` is an upper bound; `tool_harness.tools` is the exact allowlist
- `tool_harness.extra` carries free-form per-runner flags (perception, addressing, sandbox, recording)
- When adding a new action type, add it to BOTH `actions.py` (`ComputerActionType`) and `tool_gating.py` (`TOOL_NAME_BY_ACTION_TYPE` + `_ACTION_SCHEMA_FRAGMENTS`)
- `.env` is gitignored; never paste keys into YAML, chat, or committed files
