# AgentLens Handover

This file tracks current status, replacement-sensitive decisions, and exact
commands. Longer-term planning lives in:

- `docs/trajectory-collection-tasks.md`
- `docs/agent-structures-and-tool-tiers.md`
- `docs/acting-evaluating-pipeline.md`

## 2026-07-09: High-Delta Grounded Prompt Candidate List

Grounded-vs-standard task selection is now documented in:

```text
tasks/gui_vs_cli/high_delta_prompt_pairs.md
```

Use this file before expanding grounded-vs-standard runs. The key finding is
that the `grounded_prompt` label alone is not enough for behavior-analysis
claims: many GUI-vs-CLI grounded prompts are near-identical to their standard
prompts, especially in Calc/Chrome. For prompt-effect experiments, prefer
Level `2` or `3` pairs where the grounded prompt adds concrete procedure,
menu paths, object locations, or exact interaction sequences.

Already-run GUI-vs-CLI pilot pairs remain:

```text
gimp_add_alpha_transparent
drawio_aws_cloud_arch
godot4_full_enemy_controller
calc_3d_quarterly_consolidation
impress_add_entry_animations_to_bullets
chrome_multi_tab_wikipedia
```

Recommended next high-delta candidates include:

```text
gimp_rotate_180_tiff_export
gimp_fill_bucket_background
drawio_restyle_erd
drawio_fix_and_color_workflow
calc_text_parse_contacts
cloudcompare_gap_csf_ground_filter
cloudcompare_obj_to_mesh_xyz_asc
freecad_export_multi_format
freecad_create_parametric_box
krita_wrap_around_and_mirror
obs_create_scene_collection
zotero_gap_import_ris_file
```

Avoid using draw.io as a primary next result until the draw.io harness failures
are diagnosed. Impress is lower priority because recent runs were slow/noisy.

## 2026-07-09: Readable Trajectory Storage Names

Future trajectory case folders now use metadata-rich names instead of opaque
`{run_id}_seed{seed}_trial{trial}` names where the runner has task/model
metadata. The timestamp remains the batch/snapshot parent folder; the case
folder now follows:

```text
trajectories/{app_or_family}__{task_name}__{prompt_style}__{model_id}__{harness_or_agent}__seed{seed}__trial{trial}/
```

The shared helper is `src/agentlens/trajectory_paths.py`. It is wired into the
main AgentLens adapters and into `scripts/gui_vs_cli_full_workflow_smoke.py`
and `scripts/domsteer_cli_comparison.py`. Existing old run folders are not
renamed in place; curated indexes should keep pointing to those historical
paths.

## 2026-07-09: GPT-5.5 Follow-Up Collection Commands

The next GPT comparison should mirror the Opus 4.8 collection but use a cleaner
task subset. Use GPT-5.5 for:

- GUI-vs-CLI five-task subset: GIMP, draw.io, Godot 4, LibreOffice Calc, and
  Chrome. Do not include Impress by default; it is a known looping/noisy target
  for strict GUI-only.
- DOMSteer DataVoyager T1-T3: standard and grounded prompts.
- Agent styles: AgentLens strict GUI-only tool-call and gui-vs-cli paper-style
  ChatGPT computer-use agent.

Configs:

```text
configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml
configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml
```

The configs currently use model name `gpt-5.5`. If the API exposes a different
alias, update only the `model:` / `name:` fields in those configs before
running.

Local/AWS dry checks:

```bash
cd /home/ubuntu/AgentLens-grounded
set -a; . ./.env; set +a

PYTHONPATH=src python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml \
  --ready-check-only

PYTHONPATH=src python -m agentlens.cli run \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml \
  --dry-run \
  --output runs/gpt55_domsteer_dry_run_plan.json
```

Run GUI-vs-CLI five-task trajectories. Running the two agents separately makes
monitoring and restart easier:

```bash
tmux new -s agentlens_gpt55_five_task_agentlens
cd /home/ubuntu/AgentLens-grounded
set -a; . ./.env; set +a
PYTHONPATH=src python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml \
  --agent agentlens_gui_toolcall_gpt55 \
  --max-steps 150
```

```bash
tmux new -s agentlens_gpt55_five_task_chatgpt
cd /home/ubuntu/AgentLens-grounded
set -a; . ./.env; set +a
PYTHONPATH=src python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_gpt55_five_task_gui_comparison.yaml \
  --agent gui_vs_cli_chatgpt_gpt55 \
  --max-steps 150
```

Run DOMSteer T1-T3:

```bash
tmux new -s agentlens_gpt55_domsteer
cd /home/ubuntu/AgentLens-grounded
set -a; . ./.env; set +a
PYTHONPATH=src python -m agentlens.cli run \
  configs/batches/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison.yaml \
  --execute \
  --log-actions
```

Sync JSON artifacts back first; screenshots can be synced later or served from
AWS because they are large:

```bash
rsync -av --include='*/' --include='*.json' --include='*.yaml' --include='*.html' --exclude='*' \
  ubuntu@ec2-34-218-248-219.us-west-2.compute.amazonaws.com:/home/ubuntu/AgentLens-grounded/runs/gui_vs_cli_grounded_vs_standard_gpt55_five_task_gui_comparison/ \
  /Users/pan00342/Documents/Projects/AgentLens/runs/gui_vs_cli_grounded_vs_standard_gpt55_five_task_gui_comparison/

rsync -av --include='*/' --include='*.json' --include='*.yaml' --include='*.html' --exclude='*' \
  ubuntu@ec2-34-218-248-219.us-west-2.compute.amazonaws.com:/home/ubuntu/AgentLens-grounded/runs/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison/ \
  /Users/pan00342/Documents/Projects/AgentLens/runs/domsteer_t1_t3_gpt55_standard_grounded_gui_comparison/
```

## 2026-07-08: DOMSteer Opus 4.8 Standard/Grounded GUI Comparison

Active batch:

```bash
PYTHONPATH=src python -m agentlens.cli run \
  configs/batches/domsteer_t1_t3_opus48_standard_grounded_gui_comparison.yaml \
  --execute --log-actions
```

AWS:

- Host: `ubuntu@ec2-34-218-248-219.us-west-2.compute.amazonaws.com`
- Repo: `/home/ubuntu/AgentLens-grounded`
- tmux: `agentlens_domsteer_opus48`
- Run root:
  `runs/domsteer_t1_t3_opus48_standard_grounded_gui_comparison/raw/2026-07-08_09-55-22/`

This batch compares T1-T3 DOMSteer standard vs grounded prompts for:

- `agentlens_gui_toolcall`: strict AgentLens GUI-only registered tools.
- `gui_vs_cli_claude`: paper-style Claude computer-use agent converted to
  `desktop_pyautogui` actions.

Important interpretation: the paper-style Claude computer-use path is much
slower and noisier than the strict AgentLens GUI-only path. It often emits
low-level actions such as separate key down/up, mouse down/move/up, waits, and
browser-chrome interactions. Treat its step counts as paper-style computer
agent granularity, not as equivalent to AgentLens full-sandbox or strict
GUI-only step counts.

Compatibility fixes made for future runs:

- `third_party/gui-vs-cli/agents/claude_agent.py` ignores unexpected `text`
  fields on `left_click_drag`.
- `cursor_position` from Claude computer-use is treated as a no-op wait because
  the current AgentLens bridge returns screenshots, not cursor-coordinate tool
  results.

## 2026-07-07: Grounded-vs-Standard Prompt Support

Implemented first-class GUI-vs-CLI task-source selection in
`scripts/gui_vs_cli_full_workflow_smoke.py`.

- Task entries may now set `source_type: standard` or
  `source_type: grounded_prompt`.
- `standard` loads from `task_generator/tasks/<id>/task.json` or
  `tasks/gui_vs_cli/tasks_standard.jsonl`.
- `grounded_prompt` loads from
  `task_generator/tasks_grounding/<id>/task.json` or
  `tasks/gui_vs_cli/tasks_grounding.jsonl`.
- For grounded-prompt runs, the agent receives `task_grounding` as the task
  text. The same environment files and verifier specs are preserved.
- Result directories now use:
  `{paired_task_id}__standard__{agent_id}` or
  `{paired_task_id}__grounded__{agent_id}`.
- Each result directory writes `case_metadata.json` with `task_id`,
  `paired_task_id`, `source_type`, `github_task_path`, app/category, agent,
  model, and family.

New smoke config:

```bash
uv run --no-sync python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_smoke.yaml \
  --agent agentlens_gui_toolcall_gpt54
```

Single paired-task smoke:

```bash
uv run --no-sync python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/grounded_vs_standard_smoke.yaml \
  --agent agentlens_gui_toolcall_gpt54 \
  --task gimp_add_alpha_transparent
```

The initial paired config covers:

- GIMP image editing: `gimp_add_alpha_transparent`
- draw.io diagram editing: `drawio_aws_cloud_arch`
- Godot 4 game/editor workflow: `godot4_full_enemy_controller`
- LibreOffice Calc data/spreadsheet analysis:
  `calc_3d_quarterly_consolidation`
- LibreOffice Impress presentation editing:
  `impress_add_entry_animations_to_bullets`
- Chrome information seeking: `chrome_multi_tab_wikipedia`

Current limitation: this config uses the strict GUI tool-call agent. The
gui-vs-cli desktop bridge can execute desktop GUI actions today, but it should
not yet be treated as a clean `full_sandbox` condition because shell/file/code
tool outputs are not integrated into the desktop observation loop with the same
quality as the main AgentLens batch harness.

LLM-refined phase summaries already exist in
`src/agentlens/analysis/llm_refinement.py` and are enabled by method analysis
with `annotation_mode=llm`. Use them for readable phase names and qualitative
examples, but keep structured metrics as the primary validation evidence.

## 2026-07-04: No-GUI Tier Split

No-GUI/tool-only AgentLens harnesses now use the first-class
`ToolHarnessTier.NO_GUI_TOOL_ONLY` / YAML `tier: no_gui_tool_only` instead of
being labeled `full_sandbox`. This is still the same `screenshot_react` runner
with AIO sandbox code/shell/file/search tools and non-visual model input such
as `extra.input_modes: [axtree]`; `full_sandbox` is reserved for mixed GUI plus
programmatic harnesses.

## 2026-07-02: Current Agent Structures

AgentLens now has five distinct agent structures. Keep these names separate
when reporting results:

| Structure | Current ids/examples | Interface | Use for |
| --- | --- | --- | --- |
| AgentLens strict registered-tool agent | `agentlens_gui_toolcall_*`, `claude_opus46_gui_toolcall` | Provider tool/function calls registered from the harness allow-list. | Controlled browser/desktop GUI-only, no-GUI, and full-sandbox tiers. |
| AgentLens native OpenAI computer agent | `openai_gpt_computer_use` | OpenAI Responses API built-in `{"type": "computer"}`. | Model-native computer-use baseline; not fine-grained provider-side tool tiering. |
| gui-vs-cli paper-style computer agent | `gui_vs_cli_chatgpt`, `gui_vs_cli_claude`, `gui_vs_cli_gemini`, `claude_opus46_gui_vs_cli` | Paper agent structure; provider computer/desktop outputs are executed through pyautogui-style desktop actions and recorded. | Paper-faithful GUI/computer-agent comparison. |
| gui-vs-cli paper-style CLI agent | `gui_vs_cli_cli_claude`, `gui_vs_cli_cli_codex` | `claude` or `codex` CLI inside the gui-vs-cli task image. | Full gui-vs-cli workflow CLI-Anything comparison. |
| DOMSteer standalone CLI-only agent | `claude_opus46_cli`, `codex_gpt55_cli` | `scripts/domsteer_cli_comparison.py` runs provider CLIs with a terminal-only DOMSteer prompt. | Fair terminal/programmatic DOMSteer baseline without converting CLI events into GUI actions. |

Tool-tier reminder:

- Strict GUI-only exposes desktop/browser direct-manipulation tools plus
  `task.final_answer`.
- CLI-Anything/no-visual is reserved for the gui-vs-cli paper-style CLI runner
  (`gui_vs_cli_cli_*`) on gui-vs-cli workflow tasks. Do not use this label for
  DOMSteer by default.
- No-GUI/tool-only exposes `web.openai_search`, `code.run_python`,
  `code.shell`, `files.read`, `files.write`, and `task.final_answer`.
- `code.shell` is the shell/bash capability; use `bash -lc '...'` inside the
  command when bash semantics are needed.
- Full sandbox exposes GUI actions plus search, Python, shell, and file tools.
- CLI-only trajectories still record passive desktop screenshots for audit and
  comparison, but those screenshots are not included in the CLI prompt or model
  input. The DOMSteer CLI runner records `screenshots/initial.png` and
  `screenshots/final.png` as `screenshot_observation` events with
  `fed_to_model: false`.
- For DOMSteer web visual-analytics tasks, do not describe this condition as
  the gui-vs-cli paper's desktop-app "CLI-Anything" setting without a caveat.
  It is better named `domsteer_programmatic_no_visual` or `DOMSteer CLI-only
  data-analysis baseline`.

Four-condition naming for future comparison tables:

| Condition | Meaning | Current implementation |
| --- | --- | --- |
| `gui_only` | Screenshots plus direct manipulation tools only. | AgentLens strict registered-tool GUI agents and paper-style computer agents. |
| `cli_anything_no_visual` | No screenshots/GUI actions; paper CLI-Anything runner inside task image. | `gui_vs_cli_cli_claude`, `gui_vs_cli_cli_codex` for gui-vs-cli tasks. |
| `programmatic_no_visual` | No screenshots/GUI actions; benchmark-specific code/shell/search baseline. | DOMSteer `scripts/domsteer_cli_comparison.py` and future no-GUI tool-call configs. |
| `full_sandbox` | GUI plus programmatic tools. | AgentLens full-sandbox tool-call configs. |

For gui-vs-cli tasks, distinguish task source type by `github_task_path`:

- `task_generator/tasks/` -> `standard`.
- `task_generator/tasks_grounding/` -> `grounded_prompt`.
- Current imported GUI-vs-CLI catalogs:
  - `tasks/gui_vs_cli/tasks.jsonl`: 440 standard tasks.
  - `tasks/gui_vs_cli/tasks_standard.jsonl`: same 440 standard tasks.
  - `tasks/gui_vs_cli/tasks_grounding.jsonl`: 176 grounded-prompt tasks.
  - `tasks/gui_vs_cli/task_pairs.jsonl`: 176 standard/grounded matched pairs.
  - Every grounded-prompt task has a standard counterpart with the same
    `paired_task_id`; the base `task` text is identical and the grounded
    variant adds `task_grounding`.
  - Regenerate from the ignored local GitHub checkout with
    `python scripts/import_gui_vs_cli_tasks.py`.

## 2026-07-02: New CLI And Claude Opus 4.6 Comparison Work

New code/configs:

- `scripts/domsteer_cli_comparison.py`
  - Collects DOMSteer T1-T3 CLI-only trajectories with Claude Code CLI and
    Codex CLI.
  - Preserves raw provider stream files (`claude_stream.jsonl` or
    `codex_stream.jsonl`) and writes `trajectory.json`, `result.json`, and
    batch `summary.json`.
  - Records passive initial/final desktop screenshots for trajectory audit
    without feeding screenshots to the CLI model.
  - Validates only the extracted `FINAL_ANSWER: ...` value against the
    existing DOMSteer answer validators.
- `configs/cli/domsteer_t1_t3_cli_initial_comparison.yaml`
  - Runs `claude_opus46_cli` and `codex_gpt55_cli` over DataVoyager T1-T3.
- `configs/gui_vs_cli/claude_opus46_initial_comparison.yaml`
  - Runs Claude Opus 4.6 across AgentLens strict GUI-toolcall, gui-vs-cli
    Claude computer-agent, and gui-vs-cli Claude CLI structures on selected
    gui-vs-cli desktop workflow tasks.
- `configs/batches/domsteer_t1_t3_claude_opus46_gui_comparison.yaml`
  - Focused DOMSteer T1-T3 comparison for Claude Opus 4.6 strict GUI-toolcall
    versus gui-vs-cli Claude computer-agent.
- `configs/batches/domsteer_t1_gemini_gui_smoke.yaml`
  - Focused DOMSteer T1 smoke for Gemini strict GUI-toolcall and gui-vs-cli
    paper-style Gemini computer-agent.
- `src/agentlens/reports/cli_trajectory_viewer.py`
  - Static viewer for the DOMSteer CLI-only trajectory format.
- `src/agentlens/reports/gui_vs_cli_trajectory_viewer.py`
  - Static viewer for gui-vs-cli list-format trajectories.
- `scripts/gui_vs_cli_full_workflow_smoke.py`
  - Agent config now honors per-agent `extra` values and
    `max_output_tokens`, so Claude Opus 4.6 configs can override defaults.

Completed data collection:

- DOMSteer CLI-only T1-T3 completed on AWS and synced locally:
  - Local root:
    `runs/domsteer_t1_t3_cli_initial_comparison/2026-07-01_13-34-03/`
  - AWS root:
    `/home/ubuntu/AgentLens-smoke/runs/domsteer_t1_t3_cli_initial_comparison/2026-07-01_13-34-03/`
  - Result: 6/6 passed (`claude_opus46_cli` and `codex_gpt55_cli` on T1-T3).
- gui-vs-cli Claude Opus 4.6 workflow smoke completed for Chrome only:
  - AWS root:
    `/home/ubuntu/AgentLens-smoke/runs/gui_vs_cli_claude_opus46_initial_comparison/2026-07-01_13-41-36/`
  - Completed computer-agent trajectory:
    `chrome_dom_inspection_wikipedia__gui_vs_cli_claude_opus46/trajectory.json`.
  - The local sync of this AWS workflow run is incomplete because screenshot
    rsync was stopped; sync selectively if needed.

Partial/incomplete data collection:

- DOMSteer Claude Opus 4.6 GUI-focused batch was started then stopped:
  - AWS root:
    `/home/ubuntu/AgentLens-smoke/runs/domsteer_t1_t3_claude_opus46_gui_comparison/raw/2026-07-01_14-16-17/`
  - `dv_t1__claude_opus46__gui_toolcall` reached the max-step limit and wrote
    a trajectory.
  - `dv_t1__claude_opus46__gui_vs_cli` produced screenshots but did not finish
    before the run was killed.
  - No completed DOMSteer Claude computer-agent trajectory exists yet.

Useful commands:

```bash
.venv/bin/python -m py_compile \
  scripts/domsteer_cli_comparison.py \
  scripts/gui_vs_cli_full_workflow_smoke.py \
  src/agentlens/reports/cli_trajectory_viewer.py \
  src/agentlens/reports/gui_vs_cli_trajectory_viewer.py \
  src/agentlens/reports/trajectory_viewer.py
```

```bash
.venv/bin/agentlens validate-config \
  configs/batches/domsteer_t1_t3_claude_opus46_gui_comparison.yaml
```

```bash
.venv/bin/python scripts/domsteer_cli_comparison.py \
  configs/cli/domsteer_t1_t3_cli_initial_comparison.yaml
```

```bash
.venv/bin/agentlens cli-trajectory-viewer \
  runs/domsteer_t1_t3_cli_initial_comparison/2026-07-01_13-34-03/trajectories/datavoyager_most_fuel_efficient__claude_opus46_cli/trajectory.json
```

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
- Added the public task catalogs:
  - `tasks/gui_vs_cli/tasks.jsonl` / `tasks_standard.jsonl`: 440 standard
    tasks across 18 desktop applications.
  - `tasks/gui_vs_cli/tasks_grounding.jsonl`: 176 grounded-prompt tasks across
    14 desktop applications.
- Removed the earlier hand-written placeholder GUI-vs-CLI task YAML.
- Added environment backend notes:
  - `environments/README.md`

Status:

- The standard catalog has 440 task records across 18 desktop applications.
- The grounded-prompt catalog has 176 task records across 14 desktop
  applications.
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
  - `agentlens_gui_toolcall_gemini`: AgentLens strict GUI-only registered
    tools using the Gemini function-calling adapter.
  - `gui_vs_cli_chatgpt`: the paper's ChatGPT native computer-use agent.
  - `gui_vs_cli_claude`: the paper's Claude computer-use agent.
  - `gui_vs_cli_gemini`: the paper's Gemini generic-desktop agent.
  - `gui_vs_cli_cli_claude`: the paper-style CLI-Anything agent using the
    `claude` CLI inside the Docker task image.
  - `gui_vs_cli_cli_codex`: the paper-style CLI-Anything agent using the
    `codex` CLI inside the Docker task image.
- The gui-vs-cli ChatGPT adapter now wraps tasks in the paper runner's
  `GUI_SCREEN_ONLY_POLICY` by default.

Naming clarification:

| Agent id | Means | Does not mean |
| --- | --- | --- |
| `agentlens_gui_toolcall_gpt54` | AgentLens strict GUI-only registered-tool OpenAI agent. | OpenAI native computer-use. |
| `agentlens_gui_toolcall_haiku` | AgentLens strict GUI-only registered-tool Claude agent. | gui-vs-cli paper Claude agent. |
| `agentlens_gui_toolcall_gemini` | AgentLens strict GUI-only registered-tool Gemini agent. | gui-vs-cli paper Gemini desktop agent. |
| `openai_gpt_computer_use` | AgentLens wrapper around OpenAI Responses native `computer` tool. | Fine-grained registered-tool GUI-only control. |
| `gui_vs_cli_chatgpt` | gui-vs-cli paper-style ChatGPT computer-use agent; outputs are converted through the paper pyautogui path. | AgentLens strict registered-tool agent. |
| `gui_vs_cli_claude` | gui-vs-cli paper-style Claude computer-use agent. | AgentLens strict registered-tool Claude/Haiku agent. |
| `gui_vs_cli_gemini` | gui-vs-cli paper-style Gemini desktop agent. | AgentLens strict Gemini tool-call adapter. |
| `gui_vs_cli_cli_claude` | gui-vs-cli paper-style CLI-Anything Claude Code agent. | Any GUI or screenshot agent. |
| `gui_vs_cli_cli_codex` | gui-vs-cli paper-style CLI-Anything Codex agent. | Any GUI or screenshot agent. |

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
- AgentLens strict Gemini tool-call support is implemented in
  `src/agentlens/models/gemini_tool_call.py` and routed from
  `src/agentlens/models/base.py`. Local parser/constructor smoke passed with a
  dummy key; real model smoke is blocked until a Gemini key is present in
  `.env`.
- Paper-style CLI agents are implemented in
  `scripts/gui_vs_cli_full_workflow_smoke.py` via gui-vs-cli's
  `run_mode="cli"` and `run_cli_agent_interactive` path.
- AWS CLI readiness smoke on 2026-07-01:
  - `runs/smoke_cli_ready_check/2026-07-01_09-52-07/summary.json`
    (`gui_vs_cli_cli_claude`) failed because `claude` is not installed in
    `paraverse-agent-runtime:latest`.
  - `runs/smoke_cli_ready_check/2026-07-01_09-52-51/summary.json`
    (`gui_vs_cli_cli_codex`) failed because `codex` is not installed in
    `paraverse-agent-runtime:latest`.
  - This is an image/authentication blocker, not a runner wiring blocker.
- Follow-up on 2026-07-01:
  - Built AWS image `agentlens-gui-vs-cli-runtime:latest` from
    `paraverse-agent-runtime:latest` with Node 22, Claude Code CLI
    `2.1.197`, and Codex CLI `0.142.5`.
  - Patched `third_party/gui-vs-cli/computer_env/backends/docker/runtime.py`
    so Docker task containers no longer force
    `HTTP_PROXY=http://host.docker.internal:7897`; that proxy broke provider
    CLI network access on AWS.
  - Patched `scripts/gui_vs_cli_full_workflow_smoke.py` to write sandbox-local
    `/home/user/.agentlens_cli_env` from host `.env`. For Codex CLI, it now
    prefers `.secrets/codex/auth.json` ChatGPT login auth when present, and
    only falls back to an `OPENAI_API_KEY` provider config when no saved login
    auth exists.
  - Patched `third_party/gui-vs-cli/evaluation/runtime/cli_agent_runner.py` to
    skip interactive `codex login` recovery when the AgentLens env file
    contains `OPENAI_API_KEY`.
  - CLI binary readiness now passes:
    `runs/smoke_cli_ready_check/2026-07-01_10-18-58/summary.json`.
  - Real `gui_vs_cli_cli_codex` API-key smoke reached OpenAI but was blocked
    by quota: `runs/smoke_cli_codex/2026-07-01_10-34-00/`.
  - After device login, Codex auth was copied to
    `.secrets/codex/auth.json` on AWS and injected into each sandbox. A real
    `gui_vs_cli_cli_codex` smoke passed
    `chrome_dom_inspection_wikipedia` with score `1.0`:
    `runs/smoke_cli_codex/2026-07-01_12-24-38/`.
  - AWS `.env` still lacks `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and
    `GOOGLE_AI_STUDIO_API_KEY` as actual variables. Add them manually on AWS
    before Claude/Gemini smoke.
  - The Anthropic and Gemini keys were later added directly to the AWS `.env`
    with mode `600`.
  - Claude Code API-key auth was verified inside
    `agentlens-gui-vs-cli-runtime:latest`; the CLI reported
    `apiKeySource=ANTHROPIC_API_KEY` and returned `OK`.
  - A one-step AgentLens `gui_vs_cli_claude` model-call smoke succeeded:
    `runs/smoke_gui_vs_cli_claude_model_call/2026-07-01_10-54-40/`.
    It produced a real `desktop_pyautogui` action from
    `third_party/gui-vs-cli/agents/claude_agent.py`; the task verifier failed
    only because `--max-steps 1` is not intended to solve the Chrome workflow.
- DOMSteer should not be called paper-style CLI-Anything by default. DOMSteer
  can be run as GUI/browser/no-GUI AgentLens tiers; a CLI label is only fair
  after defining a separate DOMSteer CLI/browser-skill harness.
- DOMSteer web tasks can still have a useful CLI/no-visual baseline, but label
  it as `domsteer_programmatic_no_visual` or "DOMSteer CLI-only data-analysis
  baseline" rather than the gui-vs-cli paper's desktop-app CLI-Anything setup.
- Gemini DOMSteer GUI smoke config:
  `configs/batches/domsteer_t1_gemini_gui_smoke.yaml`.
  - `dv_t1__gemini__gui_toolcall`: AgentLens strict GUI-only tool-call agent
    using registered direct desktop tools only.
  - `dv_t1__gemini__gui_vs_cli`: gui-vs-cli paper-style Gemini computer-agent
    adapter, preserving raw model output and converting actions to
    `desktop_pyautogui`.
  - The config intentionally uses `gemini-2.5-flash` and `max_steps: 2` for
    smoke because the current Gemini key appears to be on a low request/minute
    quota. Increase steps only after quota/backoff is handled.
- Paper-style `desktop_pyautogui` execution requires the desktop sandbox image
  to include `pyautogui` and `pyperclip`; `agentlens/desktop-poc:latest` is the
  intended local/AWS image for these smoke runs.

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
- `src/agentlens/harnesses/desktop_actions.py`
  - `desktop_pyautogui` now runs with `runuser -u gem` only when the shell is
    root; non-root sandbox shells execute directly against the same display.
- `environments/docker/desktop-poc/Dockerfile`
  - Installs `python3-pip`, `pyautogui`, and `pyperclip` for gui-vs-cli-style
    computer-agent action execution.

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

Run one paper-style CLI readiness check:

```bash
python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/full_workflow_smoke.yaml \
  --ready-check-only \
  --agent gui_vs_cli_cli_claude \
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
