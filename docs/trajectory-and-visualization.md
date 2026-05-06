# Trajectory data, reports, and visualization

How AgentLens captures, persists, reports on, and visualizes a run.

The same data shape is produced by every adapter (`screenshot_react`, `browsergym_bridge`, `cocoabench`) so analysis code never special-cases. This doc is the canonical reference for parsing trajectories, reading summaries, and extending the viewer.

---

## On-disk layout

Every CLI invocation produces a deterministic snapshot under `agentlens_results/<experiment_id>/<UTC_timestamp>/`. Re-running never overwrites — each invocation gets its own timestamp folder.

```
<experiment_id>/<UTC_timestamp>/
├── <runner>_summary/                 e.g. screenshot_react_summary, browsergym_summary, cocoabench_summary
│   ├── summary.json                  per-run scores + metadata, machine-readable (the canonical artifact)
│   ├── summary.csv                   flat tabular form for pandas/Excel
│   ├── summary.raw.json              richer dump (all model_meta, token counts, validator details)
│   ├── report.html                   self-contained per-experiment HTML index (table of runs)
│   └── trajectory_viewer.html        per-experiment static viewer (per-run timelines)
└── trajectories/
    └── <run_id>_seed<N>_trial<M>/
        ├── trajectory.json           ordered list of TrajectoryEvent objects (the source of truth)
        ├── screenshots/
        │   ├── step_000.png          initial
        │   ├── step_NNN.png          one per step
        │   └── step_NNN_marks.png    pre-action capture WITH set-of-marks overlay (SoM mode only)
        ├── trace.zip                 (local browser only) Playwright trace
        └── video/<id>.webm           (local browser only) recorded video
```

Sandbox runs (`browser_source: aio_sandbox`) **do not** produce `trace.zip` or `video/` — Playwright `tracing.start()` and `record_video_dir` don't work over `connect_over_cdp`. Sandbox-side ffmpeg recording is on the todo list (Cut 1.6).

---

## `trajectory.json` schema

Top-level fields (`schemas.py::Trajectory`):

```json
{
  "experiment_id": "...",
  "run_id": "...",
  "trajectory_id": "...",
  "model":          { "id": "...", "name": "...", "provider": "..." },
  "tool_harness":   { "id": "...", "tier": "...", "runner": "..." },
  "memory_harness": { "id": "...", "kind": "...", "scope": "..." },
  "task":           { "id": "...", "benchmark": "...", "goal": "...", "start_url": "..." },
  "seed": 0,
  "trial": 1,
  "metrics": {
    "success": true|false,
    "score": 0.0..1.0|null,
    "duration_ms": 12345,
    "steps": 7,
    "tokens_input":  1234,
    "tokens_output": 567,
    "cost_usd": null,            // pending — see todos
    "tool_calls": 3
  },
  "events": [ /* TrajectoryEvent[] */ ]
}
```

### TrajectoryEvent

Every event has the same shape:

```json
{
  "event_type": "...",        // one of the seven types below
  "step_index": 3,
  "timestamp":  "2026-05-06T12:34:56Z",
  "data":       { /* type-specific payload */ },
  "artifact_paths": ["screenshots/step_003.png"]   // optional
}
```

### The seven event types (`schemas.py::TrajectoryEventType`)

| Event type | Emitted when | Key fields in `data` |
|---|---|---|
| `MODEL_MESSAGE` | every agent step (incl. errors) | `thought`, `action`, `tool_name`, `raw_response`, `prompt_tokens`, `completion_tokens`, `model_meta`, `mock` |
| `BROWSER_ACTION` | after a Playwright action executes | `action`, `error` (None if successful) |
| `TOOL_CALL` | non-browser tool fired (`web_search`, `run_python`, `shell`, `read_file`, `write_file`) | `tool_name`, `action`, `output`, `error`, `extra` |
| `SCREENSHOT` | initial + after every action; pre-action with marks in SoM mode | `url`, `viewport`, `goal`, `kind` (`marks` / `post_action`); `artifact_paths[0]` is the PNG |
| `USER_INTERVENTION` | every UserActor decision in multi-turn runs | `mode`, `decision` (`accept`/`reject`/`send_message`/`request_clarification`/`no_intervention`), `message`, `prior_user_messages` |
| `SESSION_BOUNDARY` | between turns in multi-turn runs; between tasks within a shared session | `turn_index`, `task_index`, `position` (`start_of_turn`/`end_of_turn`) |
| `GATING_VIOLATION` | agent emitted an action not in `tool_harness.tools` | `action`, `tool_name`, `message` |

These seven cover every observable thing — agent reasoning, browser effect, tool side-effect, visual state, user feedback, session boundary, harness rejection.

### Action shape

`data.action` is a serialized `ComputerAction` (`actions.py`):

```json
{
  "type": "click",
  "x": 320, "y": 240,           // exactly one of: (x+y) | bid | selector | mark
  "bid": null, "selector": null, "mark": null,
  "button": "left", "keys": []
}
```

Other action types: `double_click`, `scroll`, `move`, `type`, `keypress`, `wait`, `drag`, `goto`, `back`, `forward`, `reload`, `screenshot`, `web_search`, `run_python`, `shell`, `read_file`, `write_file`, `final_answer`. See `docs/screenshot-react-tools.md` for full schema.

---

## `summary.json` shape

Top-level:

```json
{
  "experiment_id": "...",
  "timestamp": "2026-05-06T12:34:56Z",
  "config_path": "configs/experiments/.../<file>.yaml",
  "runs": [ /* per-run summary objects, see below */ ]
}
```

Per-run summary mirrors the trajectory's metadata + metrics + a relative `trajectory_path` link, so you can stream `summary.json` across runs without loading every trajectory.

### `summary.csv` columns

Flat, one row per (run × seed × trial) — drop into pandas directly:

```
experiment_id, run_id, trajectory_id, model, tool_harness, memory_harness,
task, seed, trial, success, score, duration_ms, steps,
tokens_input, tokens_output, cost_usd, tool_calls
```

`cost_usd` is currently always null — pending the cost-tracking todo. `tool_calls` counts non-browser tool actions (`web_search`, `run_python`, etc.); browser actions are not counted here (use `steps` instead, or filter `events` by `event_type == BROWSER_ACTION`).

### `summary.raw.json`

Same shape as `summary.json` plus per-run `model_meta` (raw model metadata — fingerprint, system fingerprint, OpenAI request id, etc.) and the full `validator_message`. Useful for reproducibility audits.

---

## Visualization paths

### 1. `report.html` — per-experiment table

Generated by `reports/writers.py::make_html_report`. Self-contained HTML; no JS framework, no build step.

**Shows:**
- One row per run with: model · tool_harness · memory_harness · task · seed · trial · score · success · steps · tokens · duration · link to per-run viewer
- Aggregate stats at the top: pass rate, mean score, total tokens
- Color coding: pass = green, fail = red, abstain = grey

**When to use:** first-pass triage of a batch run — "which tasks passed, where to drill in".

**How:** opens directly in any browser. `agentlens_results/<exp>/<ts>/<runner>_summary/report.html`.

### 2. `trajectory_viewer.html` — per-run timeline

Generated by `reports/trajectory_viewer.py`. Single-file HTML (~660 lines of generator → ~1-5 MB output depending on screenshot count).

**Layout (top to bottom for each run):**
- **Header** — run id, experiment id, task id, badges for model/tools/memory
- **Metrics strip** — success, score, steps, tokens, duration as inline pill chips
- **Tool map** — horizontal strip of mini-cells, one per `MODEL_MESSAGE` event, color-coded by tool kind (`browser` / `code` / `web` / `files` / `task`); each cell is an anchor link into the timeline below
- **Goal block** — verbatim task goal text
- **Event timeline** — for each event, in order:
  - Screenshot (with click marker overlay if it was a click action)
  - `event_type` badge + step index + timestamp
  - Event-specific details panel:
    - `MODEL_MESSAGE`: rendered `thought` + pretty-printed `action` JSON + token counts
    - `BROWSER_ACTION`: action + error (if any)
    - `TOOL_CALL`: tool name + truncated output + error
    - `SCREENSHOT`: URL + viewport + kind
    - `USER_INTERVENTION`: mode + decision + message
    - `SESSION_BOUNDARY`: turn / task position
    - `GATING_VIOLATION`: which action, why rejected

**Styling:** dark mode by default; monospace for actions / JSON; "interesting" events (errors, gating violations, user interventions) get an accent border so they're visible on quick scroll.

**When to use:** debugging a single run end-to-end. Read top-to-bottom = chronological replay.

**How:**

```bash
agentlens trajectory-viewer agentlens_results/<exp>/<ts>/<runner>_summary/summary.json
# or regenerate from a hand-edited summary.json
```

The viewer is **static + self-contained** — no server, no relative-asset hell. `scp` the directory off a remote box and double-click locally.

### 3. Live VNC (sandbox runs)

Watch the agent driving Chromium *in real time* during a sandbox run:

```
http://localhost:8080/vnc/index.html?autoconnect=true&resize=scale
```

Combined with `tool_harness.extra.reuse_existing_sandbox: true` + `keep_sandbox_open_seconds: 300`, you can attach to a probe container, run the agent against it, and inspect the page state after the run finishes. Use cases:

- Watching anti-bot loops happen ("why did Cloudflare block me?")
- Manually exploring page state after a failed run
- Showing demos / pair-debugging

The probe pattern (start a sandbox container yourself, point the run at it):

```bash
docker run -d --rm --name agentlens-vnc-probe -p 8080:8080 ghcr.io/agent-infra/sandbox:latest
agentlens run <config>.yaml --execute   # config has reuse_existing_sandbox: true
docker stop agentlens-vnc-probe
```

### 4. `trace.zip` (local browser only)

Playwright DevTools trace — every CDP message, network request, console log, DOM snapshot. Open with `npx playwright show-trace path/to/trace.zip`. Last-resort deep dive when screenshots aren't enough. **Not produced by sandbox runs.**

### 5. `video/*.webm` (local browser only)

Headless browser recording. Useful for demos and replaying anti-bot interaction patterns. **Not produced by sandbox runs** (pending Cut 1.6 — ffmpeg-record the noVNC stream).

---

## Analysis (programmatic)

There is **no dedicated analysis library yet** — analysis is ad-hoc pandas / notebook on top of the persistent JSON. Common patterns:

```python
import json, pandas as pd
from pathlib import Path

# Cross-run table from one experiment
df = pd.read_csv("agentlens_results/<exp>/<ts>/<runner>_summary/summary.csv")
df.groupby(["model", "tool_harness"])["success"].mean()

# Per-step event analysis from a single run
events = json.loads(
    Path("agentlens_results/<exp>/<ts>/trajectories/<run>/trajectory.json").read_text()
)["events"]
tool_calls = [e for e in events if e["event_type"] == "TOOL_CALL"]
gated      = [e for e in events if e["event_type"] == "GATING_VIOLATION"]

# Multi-experiment aggregation — every snapshot is uniform, so just glob
import glob
all_runs = pd.concat([
    pd.read_csv(p) for p in glob.glob("agentlens_results/*/*/<runner>_summary/summary.csv")
])
```

Pending analysis work (in `docs/handout.md` todos):

- **Cross-config delta reports** — same task pool across model/tool/memory variants → "which tasks flipped, by how much"
- **Failure-mode taxonomy** — second-pass LLM call over failed trajectories classifying into `{anti_bot, login_required, page_load, agent_reasoning, infra}`
- **Per-step success heatmap** — which step the agent got stuck on, correlated with task / website / step type
- **Cost / $ tracking** — per-task token×price rollup; backfill `cost_usd` in `summary.csv`

These are all "load the JSON into pandas, write the analysis once" — no architectural blockers, just unprioritized.

---

## Known viewer gaps (drives the "Trajectory viewer expansion" todo)

The current `trajectory_viewer.py` was built for single-actor `screenshot_react` runs. The newer event types are stored in `trajectory.json` but **not yet rendered specially** in the HTML:

- `USER_INTERVENTION` events render as plain event rows — multi-turn dialogue runs look like single-turn runs visually
- `SESSION_BOUNDARY` events render as plain rows — shared-session runs don't visually separate tasks
- `GATING_VIOLATION` doesn't get a distinct accent — gating-rejected actions are easy to miss in long timelines
- No filtering / search across runs in `report.html`
- No cross-config comparison view (diff two YAMLs' results side-by-side)
- Tool-map strip color-codes by tool kind but doesn't surface error / success state

These are all in-place additions to `trajectory_viewer.py` — the data is already in `trajectory.json`, only the rendering needs work. The natural next step is to render `USER_INTERVENTION` and `SESSION_BOUNDARY` distinctly so the dialogue-user runs (the headline "agent fails turn 1, fixed by user feedback turn 2" pattern) become visible without reading raw JSON.

---

## Extending the viewer

Adding a new event type to the renderer:

1. Add the new `TrajectoryEventType` value in `schemas.py`.
2. Emit events from wherever the new state arises (orchestrator, harness, validator).
3. In `trajectory_viewer.py::_render_event_details`, add a `case` for the new event_type that renders the relevant `data` fields.
4. (Optional) Add a CSS class in the viewer's `<style>` block for distinct accent.
5. (Optional) Surface in the tool-map strip via `_event_tool_label` + `_kind_for_tool`.

The viewer's design philosophy is **"every event is a row, plus optional surfaces"**. Don't move logic into JS. Keep it static-HTML so it survives `scp`, `tar`, email attachments.

---

## Cross-references

- Event schema: `src/agentlens/schemas.py` (`TrajectoryEvent`, `TrajectoryEventType`)
- Action schema: `src/agentlens/actions.py` and `docs/screenshot-react-tools.md`
- Report writers: `src/agentlens/reports/writers.py`
- Per-run viewer: `src/agentlens/reports/trajectory_viewer.py`
- Per-benchmark eval-confirmation conventions: `docs/benchmarks.md`
- Project vision / G1-G6: `docs/general-idea.md`
- Cuts 1+2 (shipped) sandbox-session details: `docs/multi-tool-and-sessions.md`
