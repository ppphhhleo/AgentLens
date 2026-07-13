# AgentLens Handover

This file tracks current status, replacement-sensitive decisions, and exact
commands. Longer-term planning and archived history live in:

- `docs/trajectory-collection-tasks.md`
- `docs/agent-structures-and-tool-tiers.md`
- `docs/acting-evaluating-pipeline.md`
- `docs/archive/trajectory-infra-history.md`

Historical June/early-July smoke-run notes and setup details were moved to the
archive file above. Keep this handover focused on current state, next commands,
and replacement-sensitive decisions.


## Current Open Items

- Run the GPT-5.5 follow-up collection if/when the model alias and quota are
  available: GUI-vs-CLI five-task comparison and DOMSteer DataVoyager T1-T3
  standard/grounded comparison.
- Use `tasks/gui_vs_cli/high_delta_prompt_pairs.md` when selecting any new
  grounded-vs-standard tasks; avoid weak prompt-delta pairs for behavioral
  claims.
- Treat draw.io and Impress as noisy until the harness/runtime failures are
  diagnosed.
- Keep `/runs/` local/ignored. Sync JSON artifacts first; screenshots can stay
  on AWS or be synced selectively because they are large.
- Keep Wang-style segmentation, Act-onomy-style tags, and behavior episodes as
  post-hoc trajectory analysis layers over raw trajectories, not as acting-time
  dependencies.

## 2026-07-09: Brief Analysis Hints

Current curated local analysis files are under `runs/curated/`, but `/runs/`
is ignored and should not be pushed. Keep EDA figures/reports local unless the
user explicitly asks to publish selected summary artifacts.

For early results, prioritize simple comparisons before deep annotation:

- Performance by prompt style: standard vs grounded, stratified by task and
  agent type. Do not pool weak prompt-delta pairs with high-delta pairs without
  flagging the difference.
- Performance by agent style: AgentLens strict GUI-only vs gui-vs-cli
  paper-style computer agent, with model held fixed when possible.
- Task sensitivity: report per-task results because prompt grounding appears
  task-dependent and draw.io/Impress have known harness/runtime noise.
- Effort proxies: steps, screenshots, elapsed time, tool calls, and max-step
  termination. Compare these only within the same agent style because
  paper-style computer agents emit lower-level actions.
- Behavior annotation: once `behaviors.csv` is updated, treat behavior episodes
  as explanatory signals, not final ground truth. The preferred metric is
  within-trajectory behavior percentage first, then average those percentages
  by condition/agent/task. Keep absolute episode counts as secondary effort
  context only, because longer trajectories mechanically create more episodes.
- Segment/workflow analysis: use Wang-style segments and Act-onomy tags to
  inspect where challenge/recovery patterns occur; keep LLM-refined summaries
  as qualitative examples rather than the main quantitative claim.

Current defensible early claim shape: grounded prompts and tool/agent condition
can change behavior and effort, but evidence should be stated as pilot-level
until missing cells are filled and noisy tasks are diagnosed.

## 2026-07-09: High-Delta Grounded Prompt Candidate List

Grounded-vs-standard task selection is now documented in:

```text
tasks/gui_vs_cli/high_delta_prompt_pairs.md
```

Use this file before expanding grounded-vs-standard runs. It now covers both
GUI-vs-CLI and the active DOMSteer DataVoyager standard/grounded tasks. The key
finding is that the `grounded_prompt` label alone is not enough for
behavior-analysis claims: many GUI-vs-CLI grounded prompts are near-identical
to their standard prompts, especially in Calc/Chrome. For prompt-effect
experiments, prefer Level `2` or `3` pairs where the grounded prompt adds
concrete procedure, menu paths, object locations, or exact interaction
sequences.

Already-run GUI-vs-CLI pilot pairs remain:

```text
gimp_add_alpha_transparent
drawio_aws_cloud_arch
godot4_full_enemy_controller
calc_3d_quarterly_consolidation
impress_add_entry_animations_to_bullets
chrome_multi_tab_wikipedia
```

Already-run or ready DOMSteer DataVoyager pairs:

```text
datavoyager_most_fuel_efficient
datavoyager_origin_horsepower_range
datavoyager_europe_hp_gt_100_four_cyl
```

These three DOMSteer pairs should remain in the near-term GPT/Opus comparison
set because they are answer-verifiable visual analytics tasks with standard and
grounded YAMLs. T4-T8 are cataloged but verifier-pending.

Recommended next high-delta GUI-vs-CLI candidates include:

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
