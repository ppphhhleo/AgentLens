# AgentLens Handover

This file tracks current status, replacement-sensitive decisions, and exact
commands. Longer-term planning lives in:

- `docs/trajectory-collection-tasks.md`
- `docs/agent-structures-and-tool-tiers.md`
- `docs/acting-evaluating-pipeline.md`

## 2026-06-30: Repo Structure Cleanup

What changed:

- Active batch config now lives at:
  - `configs/batches/gpt54_datavoyager_smoke.yaml`
- Added task definitions under:
  - `tasks/domsteer/datavoyager_most_fuel_efficient/task.yaml`
- Added `task_files` support so batch YAMLs can reference task files.
- Default generated outputs now go to `runs/`.
- Moved the curated GPT-5.4 smoke result bundle to:
  - `examples/results/gpt54_datavoyager_smoke/`
- Removed duplicated published summary viewers and stale summary folders.
- Moved Docker templates to `environments/docker/`.
- Removed stale scripts that referenced deleted configs.

Policy:

- `runs/` is local and gitignored.
- `examples/results/` is for small, intentionally published examples.
- Do not enable intervention during standard collection unless explicitly asked.

## 2026-06-30: GUI-vs-CLI Task Catalog

What changed:

- Added `gui_vs_cli` as a recognized `TaskConfig.benchmark`.
- Added the full public task catalog:
  - `tasks/gui_vs_cli/tasks.jsonl`
- Removed the earlier hand-written placeholder GUI-vs-CLI task YAML.
- Added environment backend notes:
  - `environments/README.md`

Status:

- The catalog has 440 task records across 18 desktop applications.
- It preserves task text, required seed files, and verifier commands from the
  public GUI-vs-CLI dataset.
- These tasks are not in an active batch yet.
- They need a compatible desktop image, seed assets, and a verifier bridge
  before they can produce executable trajectories in AgentLens.

Decision:

- Do not vendor or couple to the whole E2B stack yet.
- Borrow the backend abstraction idea instead: screenshot, command execution,
  file read/write, stream URL, and kill.
- Keep intervention and simulated-user actors above the environment backend so
  they work the same over Docker, AWS Docker, E2B, or future providers.

Local reference clone:

- `third_party/gui-vs-cli/` contains a local ignored copy of
  `rebeccaz4/gui-vs-cli` at commit `8fee696`.
- It is for code reference only and is intentionally ignored by git.
- If it needs to be refreshed:

```bash
rm -rf third_party/gui-vs-cli
git clone --depth 1 --filter=blob:none https://github.com/rebeccaz4/gui-vs-cli.git third_party/gui-vs-cli
```

## 2026-06-30: DOMSteer Task Catalog

What changed:

- Added DOMSteer catalog docs:
  - `tasks/domsteer/README.md`
  - `tasks/domsteer/tasks.jsonl`
- The catalog has exactly 8 records: the four DataVoyager and four TensorFlow
  Playground experiment tasks from Section 8.1.
- DataVoyager study tasks T1-T3 include deterministic expected answers:
  - T1 most fuel-efficient car: `Mazda GLC`.
  - T2 widest horsepower range by origin: `USA`.
  - T3 European cars with horsepower > 100 and four cylinders: `10`.
- Tasks T4-T8 keep `answer_validator: manual_pending` and
  `verification.type: pending` because no exact answer is given in the paper.

Status:

- T1-T3 are runnable task YAMLs and included in the current 30-run smoke batch.
- T4 and TensorFlow Playground tasks need rubrics or state/screenshot
  evaluators before batch collection.

## 2026-07-01: DOMSteer T1-T3 GPT-5.4 / Claude Smoke

What changed:

- Added runnable task YAMLs for the remaining answer-verifiable DOMSteer
  DataVoyager tasks:
  - `tasks/domsteer/datavoyager_origin_horsepower_range/task.yaml`
  - `tasks/domsteer/datavoyager_europe_hp_gt_100_four_cyl/task.yaml`
- Added the current 30-run smoke batch:
  - `configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml`
- The batch covers:
  - 3 tasks: T1, T2, T3.
  - 2 model families: GPT-5.4 and Claude Sonnet 4.6.
  - GPT-5.4 tool-call variants: browser, full sandbox, no-GUI, desktop GUI.
  - GPT-5.4 native OpenAI computer-use variant: desktop GUI.
  - GPT-5.4 gui-vs-cli ChatGPTAgent variant: desktop GUI through pyautogui.
  - Claude tool-call variants: browser, full sandbox, no-GUI, desktop GUI.

Expected answers:

| Task | Expected Answer | Validator |
| --- | --- | --- |
| `datavoyager_most_fuel_efficient` | `Mazda GLC` | `contains` |
| `datavoyager_origin_horsepower_range` | `USA` | `contains` |
| `datavoyager_europe_hp_gt_100_four_cyl` | `10` | `number_exact` |

Commands:

```bash
uv run --no-sync python -m agentlens.cli validate-config \
  configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml

uv run --no-sync python -m agentlens.cli run \
  configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml \
  --dry-run \
  --max-runs 30 \
  --output /tmp/agentlens_domsteer_t1_t3_smoke_plan.json
```

Execute when API keys and Docker/AIO sandbox are ready:

```bash
uv run --no-sync python -m agentlens.cli run \
  configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml \
  --execute \
  --log-actions
```

Required API keys:

- `OPENAI_API_KEY` for GPT-5.4 and OpenAI computer-use runs.
- `ANTHROPIC_API_KEY` for Claude Sonnet 4.6 runs.

## Current Active Smoke

Active config:

```bash
configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml
```

Task files:

```bash
tasks/domsteer/datavoyager_most_fuel_efficient/task.yaml
tasks/domsteer/datavoyager_origin_horsepower_range/task.yaml
tasks/domsteer/datavoyager_europe_hp_gt_100_four_cyl/task.yaml
```

Run shape:

| Model/Backend | Harnesses | Tasks | Runs |
| --- | --- | --- | ---: |
| GPT-5.4 tool-call | browser, full sandbox, no-GUI, desktop GUI | T1-T3 | 12 |
| GPT-5.4 OpenAI computer-use | desktop GUI | T1-T3 | 3 |
| GPT-5.4 gui-vs-cli ChatGPTAgent | desktop GUI via pyautogui | T1-T3 | 3 |
| Claude Sonnet 4.6 tool-call | browser, full sandbox, no-GUI, desktop GUI | T1-T3 | 12 |

Desktop GUI comparison:

- `desktop_gui_toolcall` is the strict AgentLens GUI-only setup: the prompt and
  registered tools expose only desktop GUI actions plus `final_answer`.
- `desktop_gui_openai_computer` is the paper-faithful setup: clean GUI-only
  operator prompt plus OpenAI Responses API `{"type": "computer"}`. Raw native
  computer calls are preserved in trajectory metadata and mapped into
  AgentLens desktop actions for execution, intervention compatibility, and
  post-hoc analysis.
- `desktop_gui_gui_vs_cli_chatgpt` imports the local ignored
  `third_party/gui-vs-cli/agents/chatgpt_agent.py` reference agent. It uses
  that agent's `previous_response_id` chain and native computer tool, then
  executes the returned pyautogui snippets as `desktop.pyautogui` actions so
  we can compare against the paper's agent structure directly.
- All desktop GUI runs open the task `start_url` inside the virtual desktop
  browser via `desktop_start_cmd_template`.

Expected answers:

```text
T1: Mazda GLC
T2: USA
T3: 10
```

## Commands

Validate:

```bash
.venv/bin/agentlens validate-config configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml
```

Dry-run:

```bash
.venv/bin/agentlens run configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml --dry-run --max-runs 30
```

If `.venv/bin/agentlens` is unavailable, use:

```bash
uv run --no-sync python -m agentlens.cli run configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml --dry-run --max-runs 30
```

Execute:

```bash
.venv/bin/agentlens run configs/batches/domsteer_t1_t3_gpt54_claude_smoke.yaml \
  --execute \
  --log-actions
```

Regenerate a compact viewer:

```bash
.venv/bin/agentlens trajectory-viewer path/to/trajectory.json
```

Check intervention is off:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
for p in sorted(Path("configs/batches").glob("*.yaml")):
    data = yaml.safe_load(p.read_text()) or {}
    enabled = []
    for h in data.get("tool_harnesses") or []:
        inter = ((h.get("extra") or {}).get("intervention") or {})
        rep = inter.get("repeated_action") or {}
        if inter.get("enabled") or rep.get("enabled"):
            enabled.append(h.get("id"))
    if enabled:
        print(p, enabled)
PY
```

Expected output:

```text
<empty>
```

## Published Example

Curated result bundle:

```text
examples/results/gpt54_datavoyager_smoke/
```

Dashboard:

```text
examples/results/gpt54_datavoyager_smoke/dashboard/dashboard.html
```

Trajectories:

| Harness | Path | Status |
| --- | --- | --- |
| `browser_only` | `examples/results/gpt54_datavoyager_smoke/trajectories/browser/trajectory.json` | success, score `1.0` |
| `full_sandbox` | `examples/results/gpt54_datavoyager_smoke/trajectories/sandbox/trajectory.json` | success, score `1.0` |
| `no_gui_tool_only` | `examples/results/gpt54_datavoyager_smoke/trajectories/nogui/trajectory.json` | success, score `1.0` |

## Open Items

- Add the next DataVoyager task only after the current five-run smoke matrix
  remains stable under the new layout.
- GUI-vs-CLI tasks still need a runnable Docker image/asset mount and verifier
  bridge before batch collection.
- Reintroduce TheAgentCompany, Weka, Blender, Unity, or intervention configs as
  small dedicated batch YAMLs when those are active again.
- Keep Wang-style aggregation and Act-onomy-style behavioral analysis as
  post-hoc methods over raw trajectories.

## 2026-07-01: gui-vs-cli ChatGPTAgent DOMSteer T1-T3 Smoke

What changed:

- Added `interaction_backend: gui_vs_cli_chatgpt`, which imports the ignored
  local reference agent at `third_party/gui-vs-cli/agents/chatgpt_agent.py`.
- Added a `desktop.pyautogui` action type and executor so the reference agent's
  native computer-use outputs can remain as pyautogui snippets in the recorded
  trajectory.
- Fixed desktop startup for URL-based desktop tasks:
  - `desktop_react` now honors `settle_ms` after launch.
  - URL tasks force the browser address bar to `task.start_url` before the
    first screenshot.
- Fixed pyautogui execution in the AIO sandbox:
  - sandbox display is `:99.0`, not `:0`.
  - pyautogui must run as the desktop user `gem`, not root.

Smoke results:

| Task | Run ID | Score | Notes |
| --- | --- | ---: | --- |
| T1 | `dv_t1__gpt54__gui_vs_cli_chatgpt` | 1.0 | Answered `Mazda GLC`; used visual field dragging first, then DevTools/fetch. |
| T2 | `dv_t2__gpt54__gui_vs_cli_chatgpt` | 1.0 | Answered `USA`; used DevTools/fetch. |
| T3 | `dv_t3__gpt54__gui_vs_cli_chatgpt` | 1.0 | Answered `10`; used address-bar JavaScript/fetch. |

Result paths:

```text
runs/domsteer_t1_t3_gpt54_claude_smoke/raw/2026-06-30_18-09-48/trajectories/dv_t1__gpt54__gui_vs_cli_chatgpt_seed0_trial1/trajectory.json
runs/domsteer_t1_t3_gpt54_claude_smoke/raw/2026-06-30_18-13-28/trajectories/dv_t2__gpt54__gui_vs_cli_chatgpt_seed0_trial1/trajectory.json
runs/domsteer_t1_t3_gpt54_claude_smoke/raw/2026-06-30_18-15-57/trajectories/dv_t3__gpt54__gui_vs_cli_chatgpt_seed0_trial1/trajectory.json
```

Published example:

```text
examples/results/domsteer_t1_t3_gui_vs_cli_chatgpt_smoke/
```

Interpretation:

- The paper-style ChatGPTAgent path is now enabled and runnable on DOMSteer
  T1-T3.
- It does not behave like a strict visual-analytics GUI-only agent: because the
  paper structure only constrains behavior through prompt and native computer
  actions, the model can still open DevTools or run JavaScript through the GUI.
- This is useful for comparison against `desktop_gui_toolcall`, where AgentLens
  controls the tool tier explicitly.

OpenAI computer-use note:

- The OpenAI Responses API `{"type": "computer"}` exposes native computer-use
  actions such as click, double-click, scroll, type, wait, keypress, drag, move,
  and screenshot. It does not expose a fine-grained provider-side tier like
  "allow clicks but disallow DevTools".
- AgentLens currently maps native computer-use or gui-vs-cli pyautogui outputs
  into internal desktop actions so execution, logging, intervention, and
  trajectory analysis share one interface.
- A cleaner future variant is to execute provider-native computer actions
  directly, preserve the raw provider actions in the trajectory, and generate
  normalized action views only for post-hoc analysis.

## 2026-07-01: Agent Structure And Tool-Tier Cleanup

What changed:

- Added the agent/tier map:
  - `docs/agent-structures-and-tool-tiers.md`
  - `src/agentlens/models/README.md`
  - `src/agentlens/actors/README.md`
- Marked `src/agentlens/models/openai_vision.py` as the legacy
  screenshot-to-JSON-action backend.
- Removed generated `__pycache__` directories from local source, tests, and the
  ignored `third_party/gui-vs-cli` clone.

Current interpretation:

- Strict pure GUI should use the AgentLens tool-call backend with only GUI
  tools registered and runtime-gated.
- OpenAI native `{"type": "computer"}` and the gui-vs-cli ChatGPTAgent path
  are useful comparison baselines, but they are not strict visual-only
  controls because the model can still navigate visible GUI routes into
  DevTools or address-bar JavaScript.
- GUI-vs-CLI full workflow tasks are cataloged in
  `tasks/gui_vs_cli/tasks.jsonl`, but full execution still needs the compatible
  desktop image, seed-file bridge, app launcher bridge, and verifier bridge.

## 2026-07-01: GUI-vs-CLI Full Workflow Enablement POC

What changed:

- Added a GUI-vs-CLI full-workflow smoke plan:
  - `configs/gui_vs_cli/full_workflow_smoke.yaml`
- Added an executable bridge script:
  - `scripts/gui_vs_cli_full_workflow_smoke.py`
- The bridge reuses gui-vs-CLI's environment setup, app launcher, seed-file
  upload, and verifier code, then runs either:
  - `openai_gpt_computer_use`: OpenAI native computer-use.
  - `agentlens_gui_toolcall_gpt54`: AgentLens strict GUI-only registered tools.
  - `agentlens_gui_toolcall_haiku`: AgentLens strict GUI-only registered tools.
  - `agentlens_gui_toolcall_gemini`: listed but disabled until a Gemini
    registered-tool provider adapter exists.
  - `gui_vs_cli_chatgpt`: the paper's ChatGPT native computer-use agent.
  - `gui_vs_cli_claude`: the paper's Claude computer-use agent.
  - `gui_vs_cli_gemini`: the paper's Gemini generic-desktop agent.
- The gui-vs-cli ChatGPT adapter now wraps tasks in the paper runner's
  `GUI_SCREEN_ONLY_POLICY` by default.

Naming clarification:

| Agent id | Means | Does not mean |
| --- | --- | --- |
| `agentlens_gui_toolcall_gpt54` | AgentLens strict GUI-only registered-tool OpenAI agent. | OpenAI native computer-use. |
| `agentlens_gui_toolcall_haiku` | AgentLens strict GUI-only registered-tool Claude agent. | gui-vs-cli paper Claude agent. |
| `openai_gpt_computer_use` | AgentLens wrapper around OpenAI Responses native `computer` tool. | Fine-grained registered-tool GUI-only control. |
| `gui_vs_cli_chatgpt` | gui-vs-cli paper-style ChatGPT computer-use agent; outputs are converted through the paper pyautogui path. | AgentLens strict registered-tool agent. |
| `gui_vs_cli_claude` | gui-vs-cli paper-style Claude computer-use agent. | AgentLens strict registered-tool Claude/Haiku agent. |
| `gui_vs_cli_gemini` | gui-vs-cli paper-style Gemini desktop agent. | The disabled AgentLens strict Gemini tool-call adapter. |

Rule of thumb: `gui_vs_cli_*` refers to the paper-style agent structure from
`third_party/gui-vs-cli`; `agentlens_gui_toolcall_*` refers to AgentLens'
strict registered tool list.

Selected smoke categories:

| App | Task | Category |
| --- | --- | --- |
| Audacity | `audacity_add_chapter_labels` | audio editing |
| Chrome | `chrome_dom_inspection_wikipedia` | browser research |
| CloudCompare | `cloudcompare_colorize_add_rgb` | point-cloud visualization |
| draw.io | `drawio_aws_cloud_arch` | diagram editing |
| FreeCAD | `freecad_add_sphere_to_doc` | spatial CAD |
| GIMP | `gimp_add_alpha_transparent` | image editing |
| Godot 4 | `godot4_add_autoload_singleton` | game editor |
| Krita | `krita_add_document_metadata` | digital art |
| LibreOffice Calc | `calc_3d_quarterly_consolidation` | spreadsheet analysis |
| LibreOffice Impress | `impress_add_entry_animations_to_bullets` | presentation editing |
| LibreOffice Writer | `libreoffice_writer_agenda_document` | document editing |
| MuseScore 3 | `musescore3_add_composer_and_export_all` | music notation |
| OBS | `obs_add_sources_to_existing` | streaming scene setup |
| Obsidian | `obsidian_add_links_to_existing` | knowledge-base editing |
| RenderDoc | `renderdoc_add_recent_captures` | graphics debugging |
| Shotcut | `shotcut_720p_project_single_clip` | video editing |
| Zoom | `zoom_accessibility_bundle` | application preferences |
| Zotero | `zotero_add_author_to_survey` | reference management |

Current status:

- AWS workspace: `/home/ubuntu/AgentLens-smoke` on
  `ubuntu@ec2-34-218-248-219.us-west-2.compute.amazonaws.com`.
- AWS image `paraverse-agent-runtime:latest` is built from the gui-vs-cli
  Docker stack and patched with `websocket-client` for Chrome verifier checks.
- Ready-check smoke passed for all 18 selected GUI-vs-CLI app categories:
  `runs/gui_vs_cli_full_workflow_smoke_ready/2026-06-30_21-17-22/summary.json`.
- OpenAI native computer-use smoke now runs end-to-end without the previous
  Responses API continuation error. The Chrome task still failed behaviorally:
  `runs/gui_vs_cli_full_workflow_smoke/2026-06-30_21-27-31/`.
- Strict AgentLens GUI-only OpenAI smoke initially exposed a key-chord execution
  bug (`ctrl+shift+b` treated as one key); this is fixed in
  `scripts/gui_vs_cli_full_workflow_smoke.py`.
- Further OpenAI smoke is currently blocked by API quota:
  `insufficient_quota`.
- Claude/Gemini smoke is pending actual `.env` variables:
  `ANTHROPIC_API_KEY=...` and `GEMINI_API_KEY=...` or
  `GOOGLE_AI_STUDIO_API_KEY=...`.

Recent implementation fixes:

- `src/agentlens/models/openai_computer_use.py`
  - Sends the first built-in `computer` request as task text only.
  - Sends screenshots only as `computer_call_output` on follow-up turns.
  - Treats absence of a returned `computer_call` as terminal instead of sending
    an invalid `previous_response_id` + fresh image request.
- `scripts/gui_vs_cli_full_workflow_smoke.py`
  - Splits key chords such as `ctrl+shift+b`, `ctrl-l`, and aliases
    `return -> enter` before converting to pyautogui.
- `pyproject.toml`
  - Adds `websocket-client>=1.8` for reused GUI-vs-CLI verifier code.

Build runtime image:

```bash
cd third_party/gui-vs-cli
DOCKER_ENV_PLATFORM=linux/amd64 \
  bash computer_env/provision/docker/build_image.sh paraverse-agent-runtime:latest
```

Run readiness smoke:

```bash
python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/full_workflow_smoke.yaml \
  --ready-check-only
```

Run one full smoke:

```bash
python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/full_workflow_smoke.yaml \
  --agent agentlens_gui_toolcall_gpt54 \
  --task chrome_dom_inspection_wikipedia
```

AWS command pattern:

```bash
ssh -i /Users/pan00342/.ssh/agent-lens.pem \
  ubuntu@ec2-34-218-248-219.us-west-2.compute.amazonaws.com

cd /home/ubuntu/AgentLens-smoke
set -a && . ./.env && set +a
.venv/bin/python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/full_workflow_smoke.yaml \
  --agent agentlens_gui_toolcall_gpt54 \
  --task chrome_dom_inspection_wikipedia
```
