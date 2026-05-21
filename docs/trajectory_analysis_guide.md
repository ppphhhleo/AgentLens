# AgentLens — Agent & Human Trajectory Analysis Guide

> A concise, end-to-end guide to capturing, visualizing, and comparing
> agent and human trajectories on live web interfaces.

---

## Prerequisites

### 1. Python Environment

```bash
# Activate the virtual environment
source .venv/bin/activate

# Set your OpenAI API key (required for real agent & simulated-human runs)
cp .env.example .env          # then edit .env with your key
```

### 2. Platform Override (required on Ubuntu 26.04)

Playwright does not officially support Ubuntu 26.04. Every command must
include the platform override environment variable:

```bash
export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64
```

> **Tip**: Add this to your `~/.bashrc` so it persists across sessions:
> ```bash
> echo 'export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64' >> ~/.bashrc
> ```

All commands in this guide include the override inline for clarity.

### 3. System Dependencies for Headless Chromium

Playwright's automatic dependency installer may fail on Ubuntu 26.04 due
to renamed packages. Install the required libraries manually:

```bash
sudo apt-get install -y \
  libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
  libxrandr2 libgbm1 libpangocairo-1.0-0 libasound2t64 \
  libnspr4 libnss3 libxfixes3 libxcursor1
```

### 4. Task Websites

The experiment tasks use **public external websites** (not localhost):
- DataVoyager: `https://vega.github.io/voyager2/`
- TensorFlow Playground: `https://playground.tensorflow.org/`

The headless Chromium on your server navigates to these URLs directly
over the internet. No local web server is needed for the tasks themselves.

---

## 1 — Agent Trajectories

### 1a. Mock Agent (no API key needed — great for smoke-testing)

The mock runner replays pre-configured answers without calling any LLM.

```bash
# Validate the config first
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens validate-config configs/experiments/domsteer_screenshot_mock.yaml

# Run ALL 8 mock tasks
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens run configs/experiments/domsteer_screenshot_mock.yaml \
    --execute --log-actions

# Run a SINGLE task by run-id
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens run configs/experiments/domsteer_screenshot_mock.yaml \
    --execute --run-id datavoyager_most_fuel_efficient_mock --log-actions
```

**Config file**: `configs/experiments/domsteer_screenshot_mock.yaml`
**What it produces**: screenshots, `trajectory.json`, Playwright trace, video, and summary reports.

---

### 1b. Real Vision Agent (LLM-driven, requires OPENAI_API_KEY)

The `screenshot_react` runner sends live screenshots to a vision model
(e.g. GPT-5.4) which reasons and selects browser actions step-by-step.

```bash
# Run all 8 DOMSteer tasks with GPT-5.4 vision
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
    --execute --log-actions

# Run just one task
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
    --execute --run-id tf_discretize_toggle_gpt5 --log-actions
```

**Config file**: `configs/experiments/domsteer_screenshot_react.yaml`
**Key difference from mock**: each `model_message` event now contains the
LLM's real chain-of-thought in the `"thought"` field and its chosen action.

---

## 2 — Human / Simulated-Human Trajectories

AgentLens captures human behavior via its **UserActor** system. The
`TurnBasedOrchestrator` drives turn-taking between the agent and a
user actor, recording every human decision as a `user_intervention` event
in the same `trajectory.json`.

### 2a. Simulated Final Judge (single-turn human review)

A second LLM plays the role of a human reviewer. After the agent finishes,
the judge inspects the screenshots + answer and emits `accept` / `reject`.

```bash
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens run configs/experiments/domsteer_with_judge.yaml \
    --execute --log-actions
```

**Config file**: `configs/experiments/domsteer_with_judge.yaml`
**Key sections in the YAML**:
```yaml
user_harnesses:
  - id: judge_v1
    mode: simulated_final_judge     # LLM acts as human reviewer
    model: gpt5_judge               # separate model to avoid self-bias
    intervention_policy: final_only # reviews once, after agent finishes
    combine_with_validator: annotate_only  # logs verdict without overriding score
    persona: |
      You are a strict reviewer ...
```

**What appears in trajectory.json**: a `user_intervention` event:
```json
{
  "event_type": "user_intervention",
  "data": {
    "type": "accept",
    "text": "The URL confirms discretize=true and the description matches."
  }
}
```

---

### 2b. Simulated Dialogue (multi-turn human interaction)

A second LLM acts as a conversational user who can reject, request
clarification, or send messages — forcing the agent to retry across
multiple turns.

```bash
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens run configs/experiments/dialogue_smoke.yaml \
    --execute --log-actions
```

**Config file**: `configs/experiments/dialogue_smoke.yaml`
**Key sections in the YAML**:
```yaml
user_harnesses:
  - id: dialogue_v1
    mode: simulated_dialogue        # multi-turn back-and-forth
    model: gpt5_user
    intervention_policy: every_turn # user reviews after EVERY agent turn
    max_turns: 3                    # up to 3 agent attempts
    tools:
      - user.accept
      - user.reject
      - user.send_message
      - user.request_clarification
    persona: |
      TURN 1: Always send_message asking the agent to ALSO state the
      EXACT URL hash parameter ...
```

**What appears in trajectory.json**: multiple `session_boundary` and
`user_intervention` events interleaved with agent `model_message` events,
showing the full multi-turn negotiation.

---

## 3 — Running on EC2 / Remote Servers

### 3a. Headless Mode (default — recommended for EC2)

All the commands in §1 and §2 run in **headless mode** by default. The
agent controls a headless Chromium instance — no display required. This
is the recommended approach for EC2 because:

- Screenshots are captured at every step automatically
- Video recordings are saved to `trajectories/*/video/`
- Playwright traces are saved to `trajectories/*/trace.zip`
- The full trajectory JSON with reasoning + actions is always generated

**You get identical data whether you run headless or live.**

### 3b. Live Mode with VNC (watch the agent in real-time from your laptop)

If you want to visually watch the agent navigate the browser in real-time
from your local machine, you need a virtual display + VNC server.

**Step 1 — Install display packages (one-time)**:
```bash
sudo apt-get install -y xvfb x11vnc
```

**Step 2 — Start virtual display + VNC on EC2**:
```bash
# Start a virtual framebuffer on display :99
Xvfb :99 -screen 0 1920x1080x24 &

# Start VNC server exposing that display (no password, port 5900)
x11vnc -display :99 -nopw -forever -rfbport 5900 &
```

**Step 3 — Create an SSH tunnel from your laptop**:
```bash
# Run this on YOUR LOCAL MACHINE (not EC2)
ssh -L 5900:localhost:5900 ubuntu@<your-ec2-public-ip>
```

**Step 4 — Connect a VNC viewer on your laptop** to `localhost:5900`.
Use any VNC client (RealVNC Viewer, TigerVNC, macOS Screen Sharing, etc.).

**Step 5 — Run AgentLens with `--live`**:
```bash
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
DISPLAY=:99 \
  .venv/bin/agentlens run configs/experiments/domsteer_screenshot_react.yaml \
    --execute --live --log-actions
```

The Chromium browser will appear in your VNC viewer, and you can watch
the agent scroll, click, and type in real-time.

> **Important**: The `--live` flag will fail without a display server.
> If you see `Missing X server or $DISPLAY`, ensure Xvfb is running and
> the `DISPLAY=:99` env var is set.

### 3c. Headless vs. Live — Comparison

| | Headless (no `--live`) | Live (`--live` + VNC) |
|---|---|---|
| **Setup** | Nothing extra | Xvfb + x11vnc + SSH tunnel |
| **Screenshots** | ✅ Captured at every step | ✅ Same |
| **Video recording** | ✅ Automatic | ✅ Same |
| **Trajectory JSON** | ✅ Full reasoning + actions | ✅ Identical |
| **Watch in real-time** | ❌ | ✅ See browser in VNC |
| **Best for** | Analysis, batch runs | Demos, debugging |

---

## 4 — Viewing & Comparing Trajectories

### 4a. Generated Reports (automatic)

Every `--execute` run automatically produces these under
`agentlens_results/<experiment>/<timestamp>/`:

| File | Purpose |
|------|---------|
| `trajectories/*/trajectory.json` | Full structured trajectory per run |
| `trajectories/*/screenshots/` | PNG screenshots at each step |
| `trajectories/*/trace.zip` | Playwright trace (open with `playwright show-trace`) |
| `trajectories/*/video/` | Screen recording of the session |
| `screenshot_react_summary/summary.json` | Aggregated results for all runs |
| `screenshot_react_summary/summary.csv` | Tabular summary |
| `screenshot_react_summary/report.html` | Summary HTML report |
| `screenshot_react_summary/trajectory_viewer.html` | Interactive visual timeline |

### 4b. Accessing the Trajectory Viewer from Your Local Machine

The `trajectory_viewer.html` is a static HTML file on the EC2 server.
To view it in your local browser:

**Option A — HTTP server + SSH tunnel** (recommended):
```bash
# On EC2: start a static file server
cd /home/ubuntu/AgentLens
python3 -m http.server 8888

# On YOUR LAPTOP: create SSH tunnel
ssh -L 8888:localhost:8888 ubuntu@<your-ec2-public-ip>

# Open in your local browser:
# http://localhost:8888/agentlens_results/<experiment>/<timestamp>/screenshot_react_summary/trajectory_viewer.html
```

**Option B — Copy files to your laptop**:
```bash
# On YOUR LAPTOP:
scp -r ubuntu@<your-ec2-ip>:/home/ubuntu/AgentLens/agentlens_results/<experiment>/<timestamp>/screenshot_react_summary/ ./
# Then open trajectory_viewer.html in your browser
```

**Option C — VS Code Remote SSH**:
If you're using VS Code with Remote SSH, right-click `trajectory_viewer.html`
in the file explorer and select **"Open with Live Server"** or **"Download"**.

### 4c. Regenerate the Trajectory Viewer

```bash
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens trajectory-viewer \
    agentlens_results/<experiment>/<timestamp>/screenshot_react_summary/summary.json
```

The viewer shows:
- **Tool/Action Timeline**: color-coded strip of every event
- **Thought + Action pairs**: agent's reasoning alongside the chosen action
- **Screenshots with click markers**: red circles at exact (x, y) coordinates
- **User Intervention cards**: human feedback, accept/reject decisions
- **Validation results**: score, success, expected vs actual answer

### 4d. Playwright Trace Viewer

For the deepest browser-level inspection (DOM snapshots, network, console):

```bash
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/playwright show-trace \
    agentlens_results/<experiment>/<timestamp>/trajectories/<run>/trace.zip
```

---

## 5 — Programmatic Trajectory Analysis

### 5a. Load and Parse a Trajectory

```python
import json
from pathlib import Path

traj_path = Path("agentlens_results/<experiment>/<timestamp>/trajectories/<run>/trajectory.json")
traj = json.loads(traj_path.read_text())

print(f"Run: {traj['run_id']}")
print(f"Model: {traj['model']['name']}")
print(f"Score: {traj['metrics']['score']}")
print(f"Steps: {traj['metrics']['steps']}")
print(f"Duration: {traj['metrics']['duration_ms']}ms")
```

### 5b. Extract Agent Reasoning vs. Human Interventions

```python
for event in traj["events"]:
    et = event["event_type"]
    data = event.get("data", {})

    if et == "model_message":
        # Agent's internal reasoning + chosen action
        print(f"  [Agent Thought] {data.get('thought', '')}")
        print(f"  [Agent Action]  {data.get('action', {}).get('type', '?')}")

    elif et == "user_intervention":
        # Human (or simulated human) feedback
        print(f"  [Human] {data.get('type', '?')}: {data.get('text', '')}")

    elif et == "browser_action":
        # Executed browser action
        action = data.get("action", {})
        print(f"  [Executed] {action.get('type', '?')} at ({action.get('x')}, {action.get('y')})")

    elif et == "screenshot":
        print(f"  [Screenshot] {event.get('artifact_paths', [])}")

    elif et == "validation_event":
        print(f"  [Validation] success={data.get('success')} score={data.get('score')}")
```

### 5c. Compare Two Trajectories (Agent vs. Human-Judged)

```python
import json

def load_traj(path):
    return json.loads(Path(path).read_text())

agent_traj = load_traj("agentlens_results/domsteer_screenshot_react/<ts>/trajectories/<run>/trajectory.json")
judged_traj = load_traj("agentlens_results/domsteer_with_judge/<ts>/trajectories/<run>/trajectory.json")

# Compare step counts
agent_steps = agent_traj["metrics"]["steps"]
judged_steps = judged_traj["metrics"]["steps"]
print(f"Agent-only steps: {agent_steps}")
print(f"Agent+Judge steps: {judged_steps}")

# Extract human interventions from judged run
interventions = [
    e for e in judged_traj["events"]
    if e["event_type"] == "user_intervention"
]
for i in interventions:
    print(f"  Judge said: {i['data']['type']} — {i['data'].get('text', '')}")
```

---

## 6 — Trajectory Event Types Reference

Every `trajectory.json` uses the same unified schema regardless of whether
the run is agent-only, mock, or human-involved.

| Event Type | Source | Contains |
|---|---|---|
| `session_boundary` | Orchestrator | Turn start/end markers |
| `screenshot` | Adapter | URL, viewport, `artifact_paths` to PNG |
| `model_message` | Agent LLM | `thought` (reasoning), `action` (chosen tool), `tool_name` |
| `browser_action` | Playwright | Executed action details, error if any |
| `tool_call` | Sandbox | Code/file/shell tool executions |
| `user_intervention` | Human/Judge | `type` (accept/reject/send_message), `text` |
| `validation_event` | Validator | `success`, `score`, `message`, `expected_answer` |
| `gating_violation` | ToolSet | Blocked action + reason |

---

## 7 — Quick Reference: Available Experiment Configs

| Config | Runner | Human Actor | API Key? |
|---|---|---|---|
| `domsteer_screenshot_mock.yaml` | Mock (canned answers) | None | No |
| `domsteer_screenshot_react.yaml` | GPT-5.4 vision | None | Yes |
| `domsteer_with_judge.yaml` | GPT-5.4 vision | Simulated judge (1 turn) | Yes |
| `dialogue_smoke.yaml` | GPT-5.4 vision | Simulated dialogue (3 turns) | Yes |
| `demo.yaml` | Varies | None | Yes |
| `perception_modes_smoke.yaml` | Multi-mode | None | Yes |

List all available configs:
```bash
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 \
  .venv/bin/agentlens list-configs
```
