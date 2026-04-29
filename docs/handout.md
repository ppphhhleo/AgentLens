# AgentLens Handoff

A unified framework for evaluating browser-agent systems across the same tasks, capturing normalized trajectories, and comparing strategies under different tool/harness/memory configurations.

The project's central thesis (`docs/general-idea.md`): **agents are opportunistic problem-solvers, humans are interface-faithful users**. AgentLens makes that comparison rigorous.

## Where to find what

| Topic | Doc |
|---|---|
| **Project vision, goals (G1–G6), full architecture, paper plan** | `docs/general-idea.md` |
| **All benchmarks** (DOMSteer, MiniWoB++, AssistantBench, Online-Mind2Web, planned ones) — task type, run command, validators, cross-cutting pending work | `docs/benchmarks.md` |
| **Multi-tool + sandboxed sessions plan** — Cuts 1/2/3, agent vs human access modes, MemoryScope policy, container architecture | `docs/multi-tool-and-sessions.md` |
| **Action schema reference** (the JSON shapes the agent emits) | `docs/screenshot-react-tools.md` |
| **This file** — quickstart, current state snapshot, pending todo | `docs/handout.md` |

## Core comparison axes

```text
Run = Model × ToolHarness × MemoryHarness × Task × Seed × Trial
```

Vary any axis, observe trajectory differences. Tools and harness are themselves an experimental axis (see `docs/multi-tool-and-sessions.md`).

## Repo

GitHub: `git@github.com:ppphhhleo/AgentLens.git`

## Setup

```bash
source .venv/bin/activate
cp .env.example .env       # edit: OPENAI_API_KEY, optionally HF_TOKEN, MINIWOB_URL
```

For sandbox/multi-tool runs (Cut 1+):
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

## Main CLI

```bash
agentlens doctor                                  # env check
agentlens list-configs
agentlens validate-config <config.yaml>
agentlens summarize <config.yaml>                 # mock report
agentlens run <config.yaml> --dry-run             # plans only
agentlens run <config.yaml> --execute             # headless real run
agentlens run <config.yaml> --execute --live      # headed; visible browser
agentlens run <config.yaml> --execute --log-actions
agentlens run <config.yaml> --run-id <one_run> --execute --live --log-actions
agentlens import-online-mind2web --limit 5 --output configs/...   # generate OM2W config from HF
```

Every CLI `run` invocation auto-snapshots its outputs to `agentlens_results/<experiment>/<UTC_timestamp>/...` so re-running never overwrites prior trajectories or reports.

## Architecture (current)

```
src/agentlens/
├── actions.py                       ComputerAction schema (15 action types)
├── schemas.py                       ExperimentConfig, TaskConfig, MemoryHarnessConfig, etc.
├── cli.py                           Typer CLI; auto-loads .env
├── run_plans.py                     build_run_plans() + group_plans_by_scope() + auto-snapshotting
│
├── models/
│   ├── base.py                      ChatModel protocol, build_model()
│   └── openai_vision.py             OpenAI Responses-compatible vision model
│
├── harnesses/
│   ├── tool_gating.py               ToolSet allow-list + render_action_schema (single source of truth)
│   ├── browser_actions.py           shared Playwright execution + screenshot capture
│   └── screenshot_react_loop.py     screenshot → model → execute → screenshot loop;
│                                    handles browser, web_search, run_python, shell, files
│
├── adapters/
│   ├── screenshot_react.py          main adapter; local browser OR AIO Sandbox via CDP
│   ├── browsergym_bridge.py         wraps any browsergym/* env (MiniWoB++, AssistantBench, etc.)
│   ├── browsergym_direct.py         (deprecated) direct BrowserGym scripted runner
│   └── agentlab_browsergym.py       (dry-run only) AgentLab integration placeholder
│
├── tools/
│   └── openai_search.py             OpenAI Responses API web_search wrapper
│
├── sandbox/
│   └── aio_sandbox.py               AIO Sandbox container lifecycle + jupyter/shell/file methods
│
├── validators/
│   ├── answers.py                   exact / contains / url_contains / dispatcher to webjudge
│   └── webjudge.py                  LLM-as-judge for open-ended live-web tasks
│
├── evals/
│   ├── base.py                      SingleRunResult, ExperimentResult
│   ├── aggregate.py
│   └── mock.py
│
└── reports/
    └── writers.py                   summary.json/csv/raw + report.html
```

## What works today

| Capability | Status |
|---|---|
| Screenshot ReAct loop (vision + JSON actions) on local Chromium | ✅ |
| Screenshot ReAct loop on **sandboxed** Chromium (AIO Sandbox container, CDP) | ✅ |
| Action gating (`tool_harness.tools` constrains the agent's action space, dynamically renders prompt) | ✅ |
| Per-step `tool_name` telemetry in trajectory | ✅ |
| Native OpenAI `web_search` (Responses API, same backend as GPT Atlas) | ✅ |
| Multi-tool actions: `run_python`, `shell`, `read_file`, `write_file` (in sandbox) | ✅ |
| MemoryScope-aware sessions: shared container across tasks (cross_task_same_site, cross_benchmark) | ✅ |
| `SESSION_BOUNDARY` events recording position in shared session | ✅ |
| Playwright stealth (default ON) for anti-bot mitigation | ✅ |
| Auto-snapshot outputs per CLI invocation | ✅ |
| Per-run `trace.zip` (Playwright tracing) and `video/*.webm` (local browser only) | ✅ |
| Per-step screenshots (both local and sandbox) | ✅ |
| WebJudge LLM-as-judge validator (single-stage MVP) | ✅ |
| `import-online-mind2web` CLI subcommand for generating OM2W configs | ✅ |
| 5 benchmarks wired: DOMSteer, MiniWoB++, AssistantBench, Online-Mind2Web, DOMSteer-via-sandbox | ✅ |
| GATING_VIOLATION events when agent emits disallowed action | ✅ |

## Verified results

Real-model (gpt-5.4) results from the latest sessions:

| Run | Score | Notes |
|---|---|---|
| MiniWoB++ click-test, click-button, enter-text, choose-list, click-checkboxes (5 tasks) | 5/5 PASS | via BrowserGym bridge |
| AssistantBench imp.0 + 4 test tasks | 0/5 | hard QA; consistent with published baselines |
| Online-Mind2Web 5 tasks (browser only, baseline) | mean 0.34 | 3 of 5 failures from anti-bot defenses |
| Online-Mind2Web Trader Joe's with `web_search` | 0.00 | search worked; task required interactive site action that was blocked |
| **DOMSteer tf_discretize_toggle in sandbox** | **1.00** | clicked toggle, URL has `discretize=true` |
| **DOMSteer datavoyager_most_fuel_efficient in sandbox + multi-tool** | **1.00** | flipped FAIL→PASS; agent used `run_python` to fetch + compute from raw cars dataset |

The DataVoyager flip is the headline: **same task, same model, same goal — adding `code.run_python` shifted strategy from "navigate the visualization" to "fetch raw data and compute"**. Concrete instance of the project's interface-faithful vs opportunistic thesis.

## Pending todo

Pulled together from `docs/benchmarks.md` (cross-cutting) and `docs/multi-tool-and-sessions.md`:

### Near-term (high value, small effort)
- **Different judge model than agent** — eliminates self-preference bias (~3-7 pt uplift). One CLI flag.
- **Cost / $ tracking per task** — token×price rollup in summary report (~30 lines).
- **Resume / checkpoint within an invocation** — skip already-completed trajectories on re-run (~50 lines).
- **Refresh `screenshot-react-tools.md`** to mention `web_search`, `run_python`, `shell`, `read_file`, `write_file`.

### Multi-tool extensions
- **Sandbox VNC video recording (Cut 1.6)** — videos for sandbox runs via the container's VNC stream (~30-60 min).
- **Cut 3 — parallelism** — `--parallel N` with one container per worker; rejects parallel-shared modes (~1 day).
- **Trajectory viewer** — Gradio app rendering all event types from `trajectory.json` in unified timeline (~1-2 days). Also covers code execution which video can't.
- **rrweb continuous DOM capture** (G2) — required for human runner; also captures between-action behavior (~1 day).

### Benchmarks
- **CocoaBench adapter** — long-horizon multi-tool tasks; same Docker plumbing as Cut 1 (~1-2 days).
- **WorkArena, WebArena, VisualWebArena, BrowseComp, WebCanvas** — unwired suites; effort varies (see `benchmarks.md`).
- **Run all 8 DOMSteer tasks in sandbox + multi-tool** — see how many flip with `run_python` (~1 hour).

### Quality / scale
- **Multi-trial retry with feedback** — supports G5 (recovery patterns); extends `RunConfig.trials` (~80 lines).
- **Cookie / consent autofill** — most live-web tasks waste 3-5 steps on GDPR popups.
- **TLS-level stealth** for aggressive anti-bot sites (Akamai Premium, Cloudflare Turnstile) — `playwright-extra` is JS only; for harder sites need `curl_cffi` or `patchright`.
- **Failure-mode taxonomy** — second-pass LLM call classifies failures as `{anti_bot, login_required, page_load, agent_reasoning, infra}`.
- **Cross-config delta reports** — automate the side-by-side trajectory diffs we currently do by hand.
- **Pin dataset + model versions** — HF revision SHA + dated OpenAI snapshot model IDs.
- **Full 3-stage WebJudge** — closes ~5-10 pt agreement gap to published baselines (~4 hrs). Deferred ("judge is optimization").

### Bigger pieces (G1)
- **Human runner** — same AIO Sandbox container, noVNC access, rrweb capture, same WebJudge. Multi-week.

## Sandbox specifics

When `tool_harness.extra.browser_source: aio_sandbox`:
- Container: `ghcr.io/agent-infra/sandbox:latest` (~3-5 GB image)
- Browser: Chromium inside container, accessed via CDP from host Playwright
- Multi-tool actions (`run_python`, `shell`, `read_file`, `write_file`) routed to the container's bundled MCP servers (Jupyter, shell, file)
- Memory scope `cross_task_same_site` / `cross_benchmark` shares ONE container across tasks; container's browser cookies, filesystem, and Jupyter kernel persist
- `tool_harness.extra.stealth: true` (default) injects `tf_playwright_stealth` patches per page
- **Limitation:** Playwright `record_video_dir` and `tracing.start()` don't work over `connect_over_cdp` — sandbox runs have no `trace.zip` or `video/*.webm`. Only `screenshots/step_NNN.png` and `trajectory.json`. Sandbox VNC recording is a planned fix.

## Important: agent ≠ judge

Two distinct LLM call sites in the pipeline:

1. **Agent** — picks the next action each step (`src/agentlens/models/openai_vision.py`). Configured per-run via `model: <id>` in YAML.
2. **Judge** — runs ONCE at end, scores the trajectory (`src/agentlens/validators/webjudge.py`). Configured per-task via `extra.judge_model` (or `--judge` flag in `import-online-mind2web`).

These are independent code paths. They can be the same model (cheap) or different (less self-preference bias).

## Security note

`.env` is gitignored; never paste keys into YAML/chat/committed files. `.env.example` holds only placeholders.

The OpenAI API key pasted in chat in an early session should be rotated at https://platform.openai.com/api-keys if not already.
