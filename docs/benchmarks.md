# Benchmarks

This doc lists every benchmark currently runnable in AgentLens (or planned), with the bare minimum needed to use each: task type, how to run it, and how scores are computed.

All real-model runs require `OPENAI_API_KEY` in `.env`.
Outputs always land under `agentlens_results/<experiment_id>/<UTC_timestamp>/...` (per-invocation snapshot, never overwrites).

---

## Quick comparison

| Benchmark | Task type | Live web? | Validator | Setup needed | Status |
|---|---|---|---|---|---|
| **DOMSteer** | DOMSteer-inspired analytical tasks (DataVoyager, TF Playground) | ✅ live | `exact` / `url_contains` / `semantic_pending` / `manual_pending` | none | shipped (8 tasks) |
| **MiniWoB++** | Tiny synthetic DOM tasks (clicks, inputs, choices) | ❌ static HTML | `task.validate(page, [])` (DOM state) | `git clone` Farama-Foundation/miniwob-plusplus + `MINIWOB_URL` | shipped (5 of 125) |
| **AssistantBench** | Open-ended Q&A from `google.com` | ✅ live | `task.validate(page, chat_messages)` (`question_scorer` fuzzy match) | none — ships in `browsergym.assistantbench` | shipped (5 of 215) |
| **Online-Mind2Web** | 300 web tasks across 136 live sites | ✅ live | WebJudge LLM-as-judge | HF token + accept dataset terms | shipped (5 of 300) |
| **WorkArena** | ServiceNow enterprise UI tasks | ⚠️ ServiceNow dev instance | `task.validate(page, [])` | free ServiceNow developer instance | not wired |
| **WebArena / VisualWebArena** | Self-hosted Magento, Reddit, GitLab, OSM, Wikipedia | ❌ self-hosted | `task.validate(page, [])` (programmatic) | Docker, ~130 GB | not wired |
| **BrowseComp** | OpenAI's hard browsing QA | ✅ live | LLM-judge | `git clone` openai/simple-evals | not wired |
| **Mind2Web-Live / WebCanvas** | Same task pool re-curated for live sites | ✅ live | Key-node JS event listeners (partial credit) | clone WebCanvas repo | not wired |
| **CocoaBench** | Long-horizon multi-tool tasks (browser + shell + files + code) | varies — Docker-per-task | programmatic `test.py` per task | Docker + Docker Compose; uses AIO Sandbox | not wired |

---

## Conventions

- Each task file in `configs/experiments/*.yaml` defines:
  - **`benchmark`**: which suite the task belongs to.
  - **`task_id`**: identifier inside that suite.
  - **`goal`** + **`start_url`**: what the agent does and where it starts.
  - **`answer_validator`**: which validator runs at the end (`exact` | `contains` | `url_contains` | `webjudge` | `semantic_pending` | `manual_pending`).
- Adapter dispatch: `tool_harness.runner` chooses the executor (`screenshot_react` for our default ReAct loop; `browsergym_bridge` for any BrowserGym task).

---

## DOMSteer (custom)

8 tasks across DataVoyager (https://vega.github.io/voyager2/) and TensorFlow Playground (https://playground.tensorflow.org/), inspired by your DOMSteer UIST work.

**Task type:** open-ended analytical questions — *"Which origin's cars show the widest range of horsepower?"*, *"Click the discretize toggle, then describe what changed"*, etc.

**Validators per task:**
- 2 with `exact` (`Mazda GLC`, `10`)
- 1 with `url_contains` (`discretize=true` after toggle click)
- 2 with `semantic_pending` (need an LLM judge — currently abstain, score `None`)
- 3 with `manual_pending` (creative design tasks; need human grading)

**How to run a single task:**
```bash
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
  --run-id tf_discretize_toggle_gpt5 \
  --execute --live --log-actions
```

**How to run all 8:**
```bash
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml --execute
```

**Outputs:** `agentlens_results/domsteer_screenshot_react/<timestamp>/`

---

## MiniWoB++ (BrowserGym)

125 tiny DOM tasks (clicks, choices, text input, simple games). Static HTML — no live web.

**One-time setup:**
```bash
mkdir -p ~/.cache/agentlens && cd ~/.cache/agentlens
git clone --depth 1 https://github.com/Farama-Foundation/miniwob-plusplus.git
```
Then in `.env`:
```
MINIWOB_URL=file:///Users/<you>/.cache/agentlens/miniwob-plusplus/miniwob/html/miniwob/
```

**Validation:** BrowserGym's `task.validate(page, [])` inspects the page DOM for the goal state. Returns `(reward, done, msg, info)` where `reward ∈ {0, 1}`. We pass `chat_messages=[]` for these — they're DOM-state tasks, not Q&A.

**How to run:**
```bash
.venv/bin/agentlens run configs/experiments/miniwob_screenshot_react.yaml --execute
```

**Adding a new task:** look up the env id (e.g., `miniwob.choose-date`), add a task entry with `benchmark: browsergym` and `task_id: miniwob.choose-date` and a matching run.

**Latest result:** 5/5 PASS on `click-test`, `click-button`, `enter-text`, `choose-list`, `click-checkboxes` with gpt-5.4.

---

## AssistantBench (BrowserGym)

214 open-ended QA tasks on real public websites; agent starts at `google.com`. Already installed via `browsergym.assistantbench` — no extra setup.

**Task type:** *"What is the weather in Paris yesterday in Celsius? Answer with the number only."*, *"Which SmartLess episode does not include the names of …"*, etc. Open-ended retrieval + extraction.

**Validation:** `task.validate(page, chat_messages)` reads the agent's answer from `chat_messages[-1]["message"]` (where `role == "assistant"`) and runs it through `question_scorer` against the gold answer (fuzzy normalized match, not exact). Our bridge passes `final_answer.answer` as the synthetic assistant message.

**How to run:**
```bash
.venv/bin/agentlens run configs/experiments/assistantbench_screenshot_react.yaml --execute
```

**Adding a new task:** valid env IDs are `browsergym/assistantbench.test.0` through `assistantbench.test.213`, plus `assistantbench.imp.0`. Add a task with `task_id: assistantbench.test.42` and a matching run.

**Latest result:** 0/5 with gpt-5.4 single-trial — consistent with published baselines (GPT-4 ~25-30% on full set; we have no retry, no scratchpad, 25-step cap).

---

## Online-Mind2Web (custom adapter via webjudge validator)

300 tasks across 136 live websites, validated by an LLM judge.

**One-time setup:**
1. Visit https://huggingface.co/datasets/osunlp/Online-Mind2Web → click **"Agree and access repository"**.
2. Get a token at https://huggingface.co/settings/tokens (Read role).
3. Add to `.env`:
   ```
   HF_TOKEN=hf_...
   ```

**Generating a config:** the dataset is too large to author by hand. The `import-online-mind2web` CLI subcommand pulls tasks from the HF dataset and writes a YAML config:

```bash
.venv/bin/agentlens import-online-mind2web \
  --limit 5 \
  --offset 0 \
  --level medium \
  --model gpt-5.4 \
  --judge gpt-5.4 \
  --output configs/experiments/online_mind2web_screenshot_react.yaml
```

Options:
- `--limit N` — first N tasks of the (filtered) dataset.
- `--offset M` — skip M tasks from the start.
- `--level easy|medium|hard` — restrict by difficulty.
- `--model` — agent model id (OpenAI vision-capable).
- `--judge` — judge model id used by WebJudge (OpenAI vision-capable).
- `--max-steps N` — step cap per agent run.

**How to run:**
```bash
.venv/bin/agentlens run configs/experiments/online_mind2web_screenshot_react.yaml --execute
```

**Validation — WebJudge:**
- LLM-as-judge (`src/agentlens/validators/webjudge.py`).
- Single-stage MVP — feeds the goal, agent's final answer, final URL, and ~6 sampled screenshots (always first + last + evenly-spaced middles) to a vision model.
- Returns `{success: bool, score: float ∈ [0,1], reason: str}`, persisted in the trajectory's validation event.
- Same model can be used as both agent and judge (cheap iteration). For paper-grade numbers, use a different judge to avoid same-model self-preference bias (~3–7 points uplift).
- This is a simplified version of the official WebJudge (which is a 3-stage pipeline: key-point identification → key-screenshot identification → outcome judgment). Our 1-stage version is faster/cheaper but probably 5–10 points lower agreement with human raters than the full pipeline.

**Latest result (5 tasks, gpt-5.4 + gpt-5.4 judge):**

| task | score | failure mode |
|---|---|---|
| FlightAware discussions | 0.70 | partial — found right thread |
| FlightAware AeroAPI plans | 0.98 | clean success |
| Trader Joe's store locator | 0.00 | site returned `Access Denied` |
| Speedo swimsuit shopping | 0.00 | stuck behind cookie banner + signup modal |
| Discogs submission overview | 0.00 | stuck on Cloudflare verification |

Mean 0.34 — within published gpt-class baselines (30-40% with simple harness). 3 of the 5 failures are anti-bot defenses rather than agent reasoning errors — exactly the live-website failure modes the project's thesis is about.

---

## WorkArena (BrowserGym, not wired yet)

Real ServiceNow enterprise UI tasks. Free ServiceNow developer instance required (sign up at developer.servicenow.com, pick a Personal Developer Instance, get URL + admin creds).

**Setup (when wiring):**
- `pip install browsergym[workarena]` (already installed in our venv)
- Set env vars `SNOW_INSTANCE_URL`, `SNOW_INSTANCE_UNAME`, `SNOW_INSTANCE_PWD`
- Then use the existing `browsergym_bridge` runner with `task_id: workarena.servicenow_*`

---

## WebArena / VisualWebArena (BrowserGym, not wired yet)

Heaviest setup. Self-hosted Magento, Reddit (Postmill), GitLab, OpenStreetMap, Kiwix-Wikipedia. ~130 GB Docker, ~half day of setup.

When you actually need it, the bridge works as-is — just `pip install browsergym[webarena]` (installed) and `task_id: webarena.0` etc. Skip until you specifically need to compare against published WebArena numbers.

---

## BrowseComp (not wired yet)

OpenAI's 1,266-task browsing benchmark (released alongside GPT-5).

**Setup (when wiring):** `git clone https://github.com/openai/simple-evals.git`. Tasks are JSON-only, ungated. Validation is OpenAI's published LLM-judge prompt — same shape as our `webjudge.py` but a different prompt template.

**Cost reality:** ~$130-380 for a full 1266-task run. Typical practice is to run a 100-task subset first.

---

## Mind2Web-Live / WebCanvas (not wired yet)

Same Mind2Web task pool re-curated for live websites. **Distinguishing feature: key-node intermediate scoring** — task definitions include JS event listener specs that fire as the agent triggers meaningful intermediate UI states. Score = (# nodes triggered) / (total).

This unlocks **partial-credit + per-step progress signals** (perfect fit for the project's G3 "interface-faithful vs opportunistic" comparison thesis).

When wiring, pattern would be:
- New validator type `key_nodes` in `src/agentlens/validators/key_nodes.py`.
- Listener injection via `context.add_init_script(...)` + `expose_function(...)`.
- Loop unchanged (the agent doesn't see the listeners).

---

## CocoaBench / cocoa-agent (not wired yet)

Long-horizon multi-tool benchmark — each task gets browser + shell + filesystem + code interpreter via [AIO Sandbox](https://github.com/agent-infra/sandbox).

**Distinguishing features:**
- Each task is its own Docker container with `task.yaml` + `test.py`.
- Up to 30 iterations per task (long for agent benchmarks).
- Real long-horizon tasks: `tableau-profit-margin-analysis`, `google-trends-ai-models`, `manhattan-trip-planner`, `us-federal-tax-calculation`, `eight-puzzle-game`.
- **Evaluation: programmatic `test(result)` per task** — no LLM judge needed.

**Setup cost:** Docker + Docker Compose; per-task containers spin up via `docker compose up`. Lighter than WebArena (no central 130 GB image stack) but heavier than Online-Mind2Web (which is just URL+goal).

**Where it fits:** would be the first benchmark exercising our `browser_files` / `full_sandbox` `ToolHarnessTier` (currently only `browser_only` is real). New adapter `src/agentlens/adapters/cocoabench.py`.

---

## Validation method cheatsheet

For quick reference when reading any benchmark's results:

| Validator | Where it lives | Returns | Best for |
|---|---|---|---|
| `exact` | `validators/answers.py` | bool match (case-insensitive, stripped) | known short answers ("Mazda GLC", "10") |
| `contains` | `validators/answers.py` | substring match | answers with extra context |
| `url_contains` | `validators/answers.py` | substring match in final `page.url` | UI state checks (`discretize=true`) |
| `webjudge` | `validators/webjudge.py` | `{success, score, reason}` from LLM | open-ended live-web tasks (Online-Mind2Web) |
| `semantic_pending` | `validators/answers.py` | `(None, None, ...)` placeholder | tasks awaiting LLM-judge upgrade |
| `manual_pending` | `validators/answers.py` | `(None, None, ...)` placeholder | tasks needing human review |
| BrowserGym `task.validate(page, chat)` | inside each gym env | `(reward, done, msg, info)` | any `benchmark: browsergym` task |
| Key-node listeners | (planned) | partial-credit % | benchmarks with intermediate checkpoints |
| `test.py` (CocoaBench-style) | (planned) | pass/fail | benchmarks with programmatic per-task graders |

---

## Eval confirmation conventions (how each benchmark wants the answer delivered)

Different benchmarks have different *stop-and-deliver* protocols — how the agent signals "done", what format the answer must take, and where it lands for the validator. Our agent loop stays the same; only the **prompt addendum** (pre-loop) and the **answer reshape** (post-loop) differ per benchmark.

The four categories we've encountered:

| Category | What the agent does | Where the answer goes | Examples |
|---|---|---|---|
| **A. DOM/state-only** | Leaves the page in the right state. `final_answer` text is ignored. | Validator inspects `page.url` or DOM. | MiniWoB++, WorkArena, WebArena, our `url_contains` |
| **B. Free-text** | Emits `final_answer` with raw text. | Validator fuzzy-matches or LLM-judges. | AssistantBench, our `exact` / `contains` / `webjudge` |
| **C. Wrapped-text** | Emits `final_answer` whose text contains a specific markup pattern. | Validator regex-extracts from the text. | CocoaBench (`<answer>...</answer>`), likely BrowseComp |
| **D. Tool-call** | Emits a specific tool call (e.g. `task_complete(result=...)`). | Validator walks `conversation` for that call. | CocoaBench official harness, any OpenAI function-calling agent |

Categories A–C work with our existing `final_answer` action. Category D would require a separate **function-calling harness style** (parallel to `screenshot_react`); deferred to `docs/harness-styles.md` (planned).

### Per-benchmark cheatsheet

| Benchmark | Category | Output format the agent must produce | How the adapter delivers to the validator |
|---|---|---|---|
| **DOMSteer** | B (`exact`/`contains`) or A (`url_contains`) | Plain text in `final_answer.answer` | Pass raw to `validate_answer` |
| **MiniWoB++** | A | (anything; DOM is what matters) | `task.validate(page, [])` — empty chat list |
| **AssistantBench** | B | Plain text answer | `task.validate(page, [{role:"assistant", message:answer}])` |
| **Online-Mind2Web** | B | Plain text answer | WebJudge sees screenshots + final answer text |
| **CocoaBench** | C | `<answer>...</answer>` wrapped text | `test({"task_result": wrapped_answer, ...})` |
| *(future)* WebArena | A | (DOM state) | `task.validate(page, [])` |
| *(future)* BrowseComp | C | `<answer>...</answer>` wrapped text | OpenAI's published LLM-judge prompt |
| *(future)* WebCanvas | A (key-node listeners) | (DOM events) | JS event listener counts |

### How this is encoded in our schema

`TaskConfig.extra` (free-form dict) carries two declarative fields the adapter consumes:

```yaml
extra:
  output_format_hint: |       # OPTIONAL: appended to the agent's task instruction
    Your final answer MUST be wrapped exactly as <answer>...</answer>.
  answer_format: wrap_xml_answer
    # one of: identity | wrap_xml_answer | chat_message
    # default: identity
```

Adapter behavior:

| `answer_format` value | Pre-loop | Post-loop |
|---|---|---|
| `identity` (default) | append `output_format_hint` to goal if present | pass `answer` raw to validator |
| `wrap_xml_answer` | append hint | wrap as `<answer>{answer}</answer>` if not already wrapped |
| `chat_message` | append hint | build `[{role:"assistant", message:answer}]` and pass to validators that expect chat |

This is implemented in `src/agentlens/harnesses/eval_protocol.py` and consumed by all adapters. The agent loop in `screenshot_react_loop.py` is **unchanged** — it always just emits `final_answer` with text.

### Why this matters for the project's thesis

Different stop conventions can subtly change agent behavior. A wrapped-text protocol forces the model to commit to an exact answer; a DOM-state protocol lets it leave a trail of intermediate clicks without ever articulating the answer; a tool-call protocol pushes toward structured emission. When comparing trajectories across benchmarks, controlling for the eval protocol matters as much as controlling for the model.

---

## Cross-cutting pending work (applies to all benchmarks)

These are NOT benchmark-specific — they're harness improvements that lift quality across DOMSteer, MiniWoB++, AssistantBench, Online-Mind2Web, and any future suite. Track here once, reuse everywhere.

### Correctness / quality

- **Different judge model than agent** for any LLM-judged benchmark — eliminates self-preference bias (~3-7 pt uplift). One CLI flag (`--judge gpt-4o` while agent is `gpt-5.4`).
- **Multi-trial retry with feedback** — extend `RunConfig.trials` so trial N+1 sees prior failure as system-prompt feedback. Captures the recovery patterns G5 in general-idea.md is about.
- **Token / $ tracking per task** — already capture `tokens_input` / `tokens_output`; add a token→$ table and roll-up in summary reports so each run shows real cost.
- **Pin dataset + model versions** — HF datasets and OpenAI model aliases can rev silently. Pin a `revision="<sha>"` on `load_dataset()` calls and use dated snapshot model IDs (`gpt-5.4-20260301`) for reproducibility.

### Operations / scale

- **Resume / checkpoint** — currently re-running an experiment overwrites nothing thanks to per-invocation snapshots, but a single invocation that dies at task N restarts from task 0. Detect existing trajectories with a `validation_event` and skip them.
- **Parallel task execution** — sequential runs are fine for 5–20 tasks but a 300-task Online-Mind2Web run is hours wall-clock. `joblib`/`ray` worker model with isolated browsers per worker.
- **Per-task token budget** — hard cap to prevent a model loop from burning cost.

### Anti-bot / live-web hardening

- **Cookie / consent autofill** — most live-web tasks waste 3–5 steps dismissing GDPR popups. Inject autofill JS via `add_init_script` per common provider (OneTrust, Cookiebot, Quantcast).
- **Stealth Playwright** — `playwright-extra` + stealth plugin reduces Cloudflare/anti-bot loops we hit on Trader Joe's, Discogs, etc.
- **Persistent context with pre-accepted cookies** — `browser.new_context(storage_state=...)` for sites where the cookie/login dance is identical every run.

### Analysis quality

- **Failure-mode taxonomy** — second-pass LLM call over failed trajectories that classifies into `{anti_bot, login_required, page_load, agent_reasoning, infra}`. Currently WebJudge scores conflate these.
- **Per-step success heatmap** — which step did the agent get stuck on? Correlate with task difficulty / website / step type.
- **Cross-config delta reports** — when running same task pool across model/tool/memory variants, generate a delta report (which tasks flipped, by how much).

### Reproducibility

- **Determinism options** — temperature=0 is set; could also pass `seed=` to OpenAI Responses API. Worth verifying determinism end-to-end.
- **Trajectory replay** — load saved `trajectory.json` and re-execute the recorded action sequence on a fresh browser. Designed but not yet built (~1 hour after a real-trajectory baseline exists).

### Project thesis (G1, big lifts — defer)

- **Human runner** (G1) — same task pool, human via noVNC, identical capture, identical WebJudge. Multi-week infra.
- **rrweb continuous DOM capture** (G2) — captures between-action behavior (hover, scan, hesitation) — the canonical interface-faithful signal. ~1 day.

---

## Important: agent ≠ judge

Two distinct LLM call sites in the pipeline:

1. **Agent** — picks the next action each step (in `src/agentlens/models/openai_vision.py`). Configured per-run via `model: <id>` in YAML.
2. **Judge** — runs ONCE at the end, scores the trajectory (in `src/agentlens/validators/webjudge.py`). Configured per-task via `extra.judge_model` (or `--judge` flag in `import-online-mind2web`).

These are independent code paths. The judge model never influences what the agent does. The two can be the same model (cheap) or different (less self-preference bias).
