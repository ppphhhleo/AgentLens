# AgentLens Handoff

## Project Goal

AgentLens is an MVP for evaluating different browser-agent systems across the same tasks, with normalized trajectories and reports. The current direction is screenshot-only ReAct first, then AgentLab/BrowserGym/AgencyBench adapters, memory harnesses, and richer trajectory replay.

Core comparison axes:

```text
Run = Model x Tool Harness x Memory Harness x Task x Seed x Trial
```

## Current Repo State

Python package scaffold exists under `src/agentlens`.

Environment:

```bash
source .venv/bin/activate
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

`TaskConfig` supports:

```text
expected_answer
answer_validator: exact | contains | semantic_pending | manual_pending
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

## Implemented Adapters

### AgentLab BrowserGym Dry-Run Adapter

File:

```text
src/agentlens/adapters/agentlab_browsergym.py
```

Status:

```text
Dry-run planning only.
Real AgentLab execution is not implemented yet.
```

Notes:

```text
AgentLab may try to write to ~/agentlab_results unless AGENTLAB_EXP_ROOT is set.
When implementing real execution, set AGENTLAB_EXP_ROOT to a project-local path.
```

### BrowserGym Direct Adapter

File:

```text
src/agentlens/adapters/browsergym_direct.py
```

Status:

```text
Partially implemented no-model scripted runner.
It can open BrowserGym/openended and write trajectories.
The earlier button-click smoke exposed action-space mismatch/flakiness, so this is not the main path right now.
```

Known issue:

```text
click('bid') timed out on a local button.
mouse_click(...) was rejected by default action mapping.
Do not prioritize this adapter until screenshot_react is stable.
```

### Screenshot ReAct Adapter

File:

```text
src/agentlens/adapters/screenshot_react.py
```

Status:

```text
Main working adapter.
No external model yet.
Uses mock actions configured in YAML.
Opens real pages with Playwright.
Captures screenshots.
Executes computer-use-style browser actions.
Writes trajectory.json and reports.
Supports --live and --log-actions.
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
click
double_click
scroll
type
wait
move
keypress
drag
final_answer
```

Not implemented yet:

```text
goto
```

Initial task navigation already uses `task.start_url`.

Action logs:

```bash
agentlens run <config> --execute --log-actions
```

Live browser:

```bash
agentlens run <config> --execute --live
```

Live browser plus action logs:

```bash
agentlens run <config> --execute --live --log-actions
```

No visual overlay is implemented. This was intentionally deferred. Current action visibility is terminal logs plus screenshots.

## Configs

### Demo Config

File:

```text
configs/experiments/demo.yaml
```

Purpose:

```text
Initial memory sweep placeholder.
Uses AgentLab/browsergym dry-run planning.
```

### BrowserGym Direct Smoke

File:

```text
configs/experiments/browsergym_direct_smoke.yaml
```

Purpose:

```text
Older direct BrowserGym smoke test.
Not the main path.
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

Validation:

```text
Exact:
- Mazda GLC
- 10

Pending:
- semantic_pending
- manual_pending
```

Run one TF Playground task:

```bash
agentlens run configs/experiments/domsteer_screenshot_mock.yaml \
  --run-id tf_discretize_toggle_mock \
  --execute \
  --live \
  --log-actions
```

### Screenshot ReAct Tools Smoke

File:

```text
configs/experiments/screenshot_react_tools_smoke.yaml
```

Fixture:

```text
fixtures/screenshot_react_tools_smoke.html
```

Purpose:

```text
Visible local page that performs five mocked clicks with waits.
Useful for testing --live and --log-actions.
```

Run:

```bash
agentlens run configs/experiments/screenshot_react_tools_smoke.yaml \
  --execute \
  --live \
  --log-actions
```

Expected behavior:

```text
Visible local HTML page opens.
Five buttons are clicked.
Terminal logs each action.
Trajectory captures screenshots step_000.png through step_010.png.
Summary shows success=True, score=1.0.
```

## Verified Commands

These have been run successfully:

```bash
.venv/bin/agentlens validate-config configs/experiments/domsteer_screenshot_mock.yaml
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_mock.yaml --run-id tf_discretize_toggle_mock --dry-run
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_mock.yaml --run-id tf_discretize_toggle_mock --execute
.venv/bin/agentlens run configs/experiments/domsteer_screenshot_mock.yaml --run-id tf_discretize_toggle_mock --execute --live
.venv/bin/agentlens run configs/experiments/screenshot_react_tools_smoke.yaml --execute --live --log-actions
.venv/bin/ruff check .
```

Important: headed browser execution may require elevated permissions when run through Codex tools.

## Output Locations

DOMSteer screenshot mock:

```text
agentlens_results/domsteer_screenshot_mock/screenshot_react_summary/report.html
agentlens_results/domsteer_screenshot_mock/screenshot_react_summary/summary.csv
agentlens_results/domsteer_screenshot_mock/screenshot_react_summary/summary.json
agentlens_results/domsteer_screenshot_mock/trajectories/*/trajectory.json
agentlens_results/domsteer_screenshot_mock/trajectories/*/screenshots/*.png
```

Tools smoke:

```text
agentlens_results/screenshot_react_tools_smoke/screenshot_react_summary/report.html
agentlens_results/screenshot_react_tools_smoke/screenshot_react_summary/summary.csv
agentlens_results/screenshot_react_tools_smoke/trajectories/local_action_tools_mock_seed0_trial1/trajectory.json
agentlens_results/screenshot_react_tools_smoke/trajectories/local_action_tools_mock_seed0_trial1/screenshots/*.png
```

## Known Design Decisions

1. Do not overlay action markers on the target website yet.
2. Use terminal `--log-actions` for live status.
3. Keep website untouched.
4. Consider Playwright trace later.
5. Consider rrweb capture later for continuous DOM trajectory replay.
6. Keep screenshot ReAct as the first real harness before AgentLab/AgencyBench integration.

## Pending Next Steps

### Highest Priority

Implement a real model-backed screenshot ReAct loop.

Expected behavior:

```text
screenshot -> model JSON action -> execute action -> screenshot -> ... -> final_answer
```

Suggested files:

```text
src/agentlens/models/base.py
src/agentlens/models/openai_vision.py
src/agentlens/harnesses/screenshot_react_loop.py
```

Use strict JSON action format. Do not parse loose ReAct text.

Action output example:

```json
{
  "thought": "I need to inspect the visualization controls.",
  "action": {
    "type": "click",
    "x": 420,
    "y": 312,
    "button": "left"
  }
}
```

Stop output:

```json
{
  "thought": "I can answer now.",
  "action": {
    "type": "final_answer",
    "answer": "..."
  }
}
```

### Next Validation Work

Add real validators:

```text
exact answer: already implemented
contains answer: already implemented
semantic answer: pending
manual rubric: pending
UI state validation: pending
```

For semantic validation, use an LLM judge later, but keep deterministic exact validators for known answers.

### Next Tool Work

Add:

```text
goto action
optional Playwright trace recording
optional video recording
optional rrweb capture
```

### Next Benchmark Work

Run screenshot ReAct with a real model on:

```text
tf_discretize_toggle_mock
datavoyager_most_fuel_efficient_mock
datavoyager_europe_100hp_4cyl_count_mock
```

Then remove `_mock` naming once real model execution is active.

### Future Adapter Work

Implement:

```text
AgentLab real execution adapter
AgencyBench import adapter
memory harnesses
AgentXRay integration
trajectory viewer
```

## Important Security Note

An OpenAI API key was pasted into chat earlier. It was not used or stored by the code, but it should be revoked/rotated before any real OpenAI testing.

