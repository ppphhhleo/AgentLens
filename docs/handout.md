# AgentLens Handoff

## Project Goal

AgentLens is an MVP for evaluating different browser-agent systems across the same tasks, with normalized trajectories and reports. Current direction: screenshot-only ReAct first (now with real OpenAI vision models), then AgentLab/BrowserGym/AgencyBench adapters, memory harnesses, and richer trajectory replay.

Core comparison axes:

```text
Run = Model x Tool Harness x Memory Harness x Task x Seed x Trial
```

## Current Repo State

Python package scaffold under `src/agentlens`. Pushed to:

```text
git@github.com:ppphhhleo/AgentLens.git
```

Environment:

```bash
source .venv/bin/activate
```

Secrets (gitignored):

```bash
cp .env.example .env
# edit .env, paste OPENAI_API_KEY
```

Main CLI:

```bash
agentlens doctor
agentlens list-configs
agentlens validate-config <config.yaml>
agentlens summarize <config.yaml>
agentlens run <config.yaml> --dry-run
agentlens run <config.yaml> --execute
agentlens run <config.yaml> --execute --live
agentlens run <config.yaml> --execute --live --log-actions
agentlens run <config.yaml> --run-id <one_run> --execute --live --log-actions
```

Useful docs:

```text
docs/general-idea.md
docs/screenshot-react-tools.md
docs/handout.md
```

## Implemented Core

### Schemas

File:

```text
src/agentlens/schemas.py
```

Implemented:

```text
ModelConfig
ToolHarnessConfig
MemoryHarnessConfig
TaskConfig
RunConfig
ExperimentConfig
Trajectory
TrajectoryEvent
RunMetrics
```

`TaskConfig.answer_validator` supports:

```text
exact
contains
url_contains          (UI-state check on final page.url)
semantic_pending
manual_pending
```

### Eval / Report Layer

Files:

```text
src/agentlens/evals/base.py
src/agentlens/evals/aggregate.py
src/agentlens/evals/mock.py
src/agentlens/reports/writers.py
```

Implemented:

```text
SingleRunResult
ExperimentResult
aggregate_results()
summary.json
summary.csv
report.html
summary.raw.json
```

### Run Planning

File:

```text
src/agentlens/run_plans.py
```

Implemented:

```text
build_run_plans()
write_run_plan_json()
with_live_mode()
```

Important: adapter imports are lazy inside `build_run_plans()` to avoid slow CLI startup.

### Models

Files:

```text
src/agentlens/models/base.py          # ChatModel Protocol, ModelStep, build_model()
src/agentlens/models/openai_vision.py # OpenAIVisionModel (vision + JSON mode)
```

Implemented:

```text
ChatModel Protocol            (vision-capable .step() returning ModelStep)
ModelStep dataclass           (thought, action, raw_response, tokens, extra)
ScreenshotObservation         (step_index, screenshot_path, url, viewport)
OpenAIVisionModel
  - chat.completions + image_url base64 data URLs
  - response_format={"type":"json_object"}
  - autodetect gpt-5.x / o1 / o3 / o4 -> max_completion_tokens, default temp
  - tolerant JSON parser (raw_decode, ignores trailing dup objects)
SYSTEM_PROMPT_TEMPLATE        (autonomous-agent framing with {goal} injection)
```

### Harnesses

Files:

```text
src/agentlens/harnesses/browser_actions.py
src/agentlens/harnesses/screenshot_react_loop.py
```

Implemented:

```text
execute_action()              (Playwright-side action exec, shared by mock + real)
capture_screenshot_event()
format_action()
show_marker()                 (CSS-animated pulse at click coords; non-flicker)
OVERLAY_INIT_JS               (registered via context.add_init_script)
DEFAULT_POST_ACTION_SETTLE_MS = 250

run_screenshot_react_loop()
  - screenshot -> model.step -> execute -> screenshot until final_answer / max_steps
  - persists thought, action, raw_response, prompt_tokens, completion_tokens
  - catches model errors into trajectory rather than crashing
```

## Implemented Adapters

### Screenshot ReAct Adapter

File:

```text
src/agentlens/adapters/screenshot_react.py
```

Status:

```text
Main working adapter. Real OpenAI vision model OR mock dispatch.
Playwright headed/headless. Captures trajectory.json + screenshots/.
Optional trace.zip + video/*.webm artifacts (see Defaults below).
```

Dispatch:

```text
provider=local + name=mock_screenshot_react -> mock path (uses task.extra.mock_actions)
provider=openai (vision=true)                -> real loop via OpenAIVisionModel
```

Defaults (overridable via tool_harness.extra):

```text
headless        : true
slow_mo_ms      : 0           (set >0 for explicit pacing)
viewport        : 1600x900
settle_ms       : 2000        (initial page-load settle)
tracing         : on if headless, off if live (DOM-snapshot walk causes flicker)
record_video    : on always   (light cost; useful for sharing/post-hoc review)
```

### AgentLab BrowserGym Dry-Run Adapter

File:

```text
src/agentlens/adapters/agentlab_browsergym.py
```

Status:

```text
Dry-run planning only. Real AgentLab execution NOT implemented.
```

When real exec lands, set `AGENTLAB_EXP_ROOT` to a project-local path so AgentLab does not write to `~/agentlab_results`.

### BrowserGym Direct Adapter

File:

```text
src/agentlens/adapters/browsergym_direct.py
```

Status:

```text
Partially implemented no-model scripted runner. Deprioritized.
click('bid') timed out on a local button; mouse_click(...) rejected by default action mapping.
Do not prioritize until a real need surfaces.
```

## Screenshot ReAct Tools

Action schema:

```text
src/agentlens/actions.py
```

Docs:

```text
docs/screenshot-react-tools.md
```

Supported actions:

```text
screenshot
click           (+ optional keys=[SHIFT|CTRL|ALT|META] held during action)
double_click    (+ optional keys)
scroll          (+ optional keys; accepts scrollX/scrollY camelCase aliases)
type
wait
move            (+ optional keys)
keypress        (keys = list of keys to PRESS, e.g. [Control, a])
drag            (path = [{x,y}, ...] or [[x,y], ...]; + optional keys)
goto            (url required; full Chromium navigation)
back
forward
reload
final_answer
```

Initial task navigation already uses `task.start_url`. `goto` is for mid-trajectory navigation.

OpenAI computer-use compatibility:

```text
- scroll_x/scroll_y also accepted as camelCase scrollX/scrollY.
- drag.path accepts both [x,y] arrays and {x,y} dict forms.
- Mouse-action `keys` are held modifiers (SHIFT/CTRL/ALT/META,
  case-insensitive, with CTRL=CONTROL, CMD=META aliases).
- A JSON action emitted by OpenAI's computer-use Responses API runs
  unchanged in AgentLens, modulo our `final_answer` stop signal.
```

Action visualization in headed mode:

```text
Each click/double_click/scroll/move/drag emits a colored pulse at the action
coordinates via window.__agentlens_show injected once per context. Not part
of the screenshot fed to the model.
```

## Configs

### Demo Config

File:

```text
configs/experiments/demo.yaml
```

Purpose:

```text
Initial memory sweep placeholder. AgentLab/browsergym dry-run planning.
```

### BrowserGym Direct Smoke

File:

```text
configs/experiments/browsergym_direct_smoke.yaml
```

Purpose:

```text
Older direct BrowserGym smoke test. Not the main path.
```

### DOMSteer Screenshot Mock

File:

```text
configs/experiments/domsteer_screenshot_mock.yaml
```

Purpose:

```text
8 DOMSteer-inspired tasks using live URLs and screenshot ReAct mock final answers.
```

Task URLs:

```text
DataVoyager: https://vega.github.io/voyager2/
TF Playground: https://playground.tensorflow.org/
```

Tasks:

```text
DataVoyager:
- datavoyager_most_fuel_efficient
- datavoyager_horsepower_range_by_origin
- datavoyager_europe_100hp_4cyl_count
- datavoyager_8_cylinder_characteristics

TF Playground:
- tf_discretize_toggle
- tf_wrongly_classified_point
- tf_general_regression_network
- tf_general_classification_network
```

### DOMSteer Screenshot Real

File:

```text
configs/experiments/domsteer_screenshot_react.yaml
```

Purpose:

```text
3 DOMSteer tasks running against real OpenAI vision model (currently gpt-5.4).
Requires .env with OPENAI_API_KEY.
```

Run ids:

```text
tf_discretize_toggle_gpt5
datavoyager_most_fuel_efficient_gpt5
datavoyager_europe_100hp_4cyl_count_gpt5
```

Run one task headed with action logs:

```bash
agentlens run configs/experiments/domsteer_screenshot_react.yaml \
  --run-id tf_discretize_toggle_gpt5 \
  --execute --live --log-actions
```

### Screenshot ReAct Tools Smoke

File:

```text
configs/experiments/screenshot_react_tools_smoke.yaml
```

Unified fixture (single file covers both tasks below):

```text
fixtures/screenshot_react_tools.html
```

Two tasks share this fixture:

```text
local_action_tools           : 5-button click smoke (11 steps).
local_action_tools_coverage  : exercises every supported action (25 steps,
                               10 distinct action types).
```

The fixture has two views via query string:

```text
?view=1 (default) -> 5 click targets, modifier-click logger, keypress logger,
                     scroll logger, drag zone, type input, nav link.
?view=2           -> alternate landing for goto/back/forward/reload tests
                     (sessionStorage-backed load counter).
```

Element coordinates in the mock_actions sequences were measured directly
from Playwright `bounding_box()` at the 800x600 viewport, so they match
real on-screen positions.

## Verified Runs

Real model (gpt-5.4):

| Run | Steps | Validator | Result |
|---|---|---|---|
| `tf_discretize_toggle_gpt5` | 2 | url_contains `discretize=true` | PASS |
| `datavoyager_most_fuel_efficient_gpt5` | 11 | exact `Mazda GLC` | FAIL (got `vw rabbit c (diesel)` — 2nd most efficient) |
| `datavoyager_europe_100hp_4cyl_count_gpt5` | 8 | exact `10` | FAIL (got `14`) |

DataVoyager failures are diagnostic, not broken — agent navigated, dragged filters, arrived at confidently wrong numerical answers. Exactly the kind of opportunistic-not-interface-faithful behavior the project is meant to characterize.

Mock smoke (no model, against unified fixture):

| Run | Steps | Coverage | Result |
|---|---|---|---|
| `local_action_tools_mock` | 11 | click, wait, final_answer | PASS |
| `local_action_tools_coverage_mock` | 25 | back, click, drag, forward, goto, keypress, reload, scroll, type, wait, final_answer | PASS |

Coverage smoke proves every supported action executes through Playwright without errors and that the OpenAI-compat extras (camelCase scrollX/Y, array drag path, modifier keys) parse and run.

## Output Locations

Per run:

```text
agentlens_results/<experiment>/trajectories/<run_id>_seed<N>_trial<M>/
  trajectory.json                # events: thought, action, raw_response, tokens
  screenshots/step_NNN.png       # one per step
  trace.zip                      # if tracing on (headless default)
  video/<hash>.webm              # if record_video on (default on)
```

Per experiment:

```text
agentlens_results/<experiment>/screenshot_react_summary/
  summary.json
  summary.csv
  report.html
  summary.raw.json
```

## Viewing a Trace (post-hoc, when tracing was on)

```bash
npx playwright show-trace <path/to/trace.zip>
```

Caveat: Playwright's DOM snapshot replay does NOT capture `<canvas>` pixels (Vega Voyager / TF Playground charts will be blank in DOM replay). The timeline strip and per-action raster screenshots DO show canvas pixels, as do our own `screenshots/` and the `.webm`. rrweb (pending) would solve canvas replay properly.

## Known Design Decisions

1. Action overlay markers ARE on (lightweight CSS pulse, non-flicker, useful in live mode).
2. Tracing default off in live mode (DOM-snapshot walk causes flicker on macOS).
3. Video default on in both modes (light cost, useful artifact).
4. Coordinates are viewport pixels; viewport defaults 1600x900.
5. Screenshot ReAct stays the first real harness before AgentLab/AgencyBench integration.
6. rrweb capture deferred — pairs with viewer work (G2 in general-idea.md).
7. Mock adapter retained alongside real adapter; same code path, dispatch on `model.provider`.

## Pending Next Steps

### Highest Priority

**rrweb continuous DOM capture (G2 in general-idea.md).**

Solves two problems at once:
- Canvas-element replay in trace viewer (Voyager / TF Playground)
- Continuous between-action capture (the central data layer for the human-vs-agent comparison thesis)

Suggested files:

```text
src/agentlens/harnesses/rrweb_capture.py
```

Approach:

```python
context.add_init_script(rrweb_bundle)
context.add_init_script("""
  rrweb.record({
    emit: e => window.__agentlens_emit_rrweb(e),
    recordCanvas: true,
    sampling: { mousemove: 50, scroll: 100 },
  });
""")
context.expose_function("__agentlens_emit_rrweb", lambda e: rrweb_buffer.append(e))
```

Save buffer to `trajectories/<run>/rrweb.jsonl` per run. Replay later with `rrweb-player`.

### Investigate Live-Mode Flicker

User reports residual flicker in headed mode that is NOT captured in the saved `.webm`. Already attempted:

```text
- Disabled trace + video in live mode
- Removed redundant page.mouse.move before click
- Reduced slow_mo from 350 -> 150 -> 0
- Reduced post-action settle from 600 -> 250 ms
- Moved overlay init from per-action page.evaluate to context.add_init_script
```

Remaining hypotheses (since flicker is not in the screencast):

```text
- macOS Chromium window-level repaint when CDP session calls page.screenshot
- Focus/bring-to-front events triggered by Playwright actions
- macOS scrollbar overlay rendering (outside the DOM)
- macOS Retina compositor sync at the OS layer
```

Next diagnostic options:

```text
- Try --no-startup-window flag, --use-gl=desktop, or other launch args
- Try Firefox via playwright.firefox to isolate Chromium-specific cause
- Record at OS level (QuickTime screen recording) instead of CDP screencast,
  to confirm whether flicker is real OS-visible artifact or perceived stutter
```

### Reproduce / Replay From Trajectory

Concept: load a saved `trajectory.json`, re-execute the recorded `BROWSER_ACTION` sequence on a fresh browser, produce a comparable trajectory. Useful for visual regression and prompt-free re-runs.

Suggested files:

```text
src/agentlens/repro/loader.py     # Trajectory.from_dir(path)
src/agentlens/repro/runner.py     # extracted from screenshot_react_loop
```

CLI verb:

```bash
agentlens replay <trajectory_dir> [--live] [--log-actions]
```

All required data already in `trajectory.json`. ~1 hour of work after rrweb lands.

### Semantic LLM-Judge Validator

Currently `semantic_pending` returns `(None, None, ...)`. Real semantic judging needed for tasks like `tf_discretize_toggle` where multiple valid answers exist.

Suggested files:

```text
src/agentlens/validators/semantic.py
```

Approach: another OpenAI call with rubric in `task.extra.rubric`, returns 0-1 score plus rationale. Reuse `OpenAIVisionModel`-style client setup (no image needed).

### Custom Gradio Trajectory Viewer

Currently no in-house viewer. Playwright Trace Viewer covers most of the gap (when tracing is on) but cannot replay canvas. A custom viewer would show: per-step screenshot + thought + action + raw_response + URL + tokens, plus eventually side-by-side human vs. agent.

Suggested files:

```text
src/agentlens/ui/app.py
src/agentlens/ui/replay.py        # rrweb-player embed once rrweb lands
src/agentlens/ui/side_by_side.py
```

Defer until several real trajectories exist worth comparing.

### Memory Harnesses

Stateless real-model baseline now exists (`tf_discretize_toggle_gpt5`, the two DataVoyager runs). Next step: implement memory variants and compare.

Suggested files:

```text
src/agentlens/agents/memory_agent.py        # sliding window of past steps
src/agentlens/agents/cached_agent.py        # DOM-hash -> action cache
src/agentlens/agents/curriculum_agent.py    # task-ordering by failures
```

Update `MemoryHarnessConfig` validators in `screenshot_react.py` to accept new kinds.

### AgentLab Real Execution

`agentlab_browsergym.py` adapter currently dry-run only. Wire into AgentLab's `Study.run` to use `GenericAgent` and produce ExpResult-shaped output that AgentXRay can consume. Set `AGENTLAB_EXP_ROOT` to project-local.

### Future Adapter Work

```text
AgencyBench import adapter
WebCanvas / Mind2Web-Live import adapter (key-node evaluation)
Online-Mind2Web import (300 live tasks, WebJudge validator)
Human runner with noVNC + action segmentation (G1)
Trial runner with feedback injection (G5)
RL export (s,a,r,s') from trajectories (G6)
```

## Dependencies

Pinned in `pyproject.toml`:

```text
agentlab>=0.4.2
browsergym>=0.14.3
openai>=1.50
pandas>=2.2
pydantic>=2.7
python-dotenv>=1.0
pyyaml>=6.0
typer>=0.12
```

Dev:

```text
pytest>=8.0
ruff>=0.6
```

Playwright is a transitive dep via browsergym; if a fresh install is missing browsers, run `python -m playwright install chromium`.

## Quick Smoke

```bash
.venv/bin/ruff check src/agentlens/
.venv/bin/agentlens validate-config configs/experiments/domsteer_screenshot_react.yaml
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
  --run-id tf_discretize_toggle_gpt5 --execute --live --log-actions
```

Expected:

```text
Live mode enabled: launching headed browser windows.
[tf_discretize_toggle_gpt5 seed=0 trial=1] open https://playground.tensorflow.org/
[tf_discretize_toggle_gpt5 step=0] screenshot -> ...
[tf_discretize_toggle_gpt5 step=1] click x=~1300 y=~880 button=left
[tf_discretize_toggle_gpt5 step=2] final_answer answer='...discretize... discrete...gradient...'
[tf_discretize_toggle_gpt5] artifacts: trajectory.json, video_dir=.../video
[tf_discretize_toggle_gpt5] validation success=True score=1.0 message=url contains 'discretize=true'
```

## Important Security Note

An OpenAI API key was pasted into chat in an early session. It was not used or stored by the code, but should be rotated. Current key flow:

```text
.env at repo root (gitignored)  ->  load_dotenv() in cli.py  ->  os.environ["OPENAI_API_KEY"]
```

Never paste keys into YAML, into chat, or into any committed file. `.env.example` holds only a placeholder.
