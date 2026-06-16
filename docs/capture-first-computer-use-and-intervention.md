# Capture-First Computer-Use Plan

## Objective

AgentLens should capture browser and virtual-computer trajectories before it tries
to intervene. The first milestone is reconstructable trajectories for complex
visual analytics, data-analysis, and workplace-style tasks.

The target trajectory is a single timeline containing:

- GUI observations: screenshots, URL or active app/window, viewport/screen size
- GUI actions: click, double click, scroll, drag, type, keypress, wait, navigation
- I/O actions: web search, Python, shell, file reads, file writes
- I/O outputs: stdout, stderr, exit status, file contents, tool errors
- Artifact changes: created, modified, deleted files around tool calls
- Outcome: final answer, final URL/state, score, validation message

## Task Backends

| Backend | Current route | Capture focus |
|---|---|---|
| DOMSteer / web visual analytics | `screenshot_react` with Playwright | screenshots, browser actions, final answer |
| Virtual computer / sandbox | `screenshot_react` with `browser_source: aio_sandbox` | browser + code/shell/file I/O |
| TheAgentCompany | future mounted TAC task container or service endpoints | workplace browser/code/file workflows |
| Desktop professional apps | future computer-use executor | screenshots, mouse/keyboard, active window, artifacts |

The first TheAgentCompany integration should not require rewriting AgentLens.
It should adapt TAC's task container contract:

- read `/instruction/task.md`
- initialize with `/utils/init.sh`
- run the agent in the task workspace
- grade with `/utils/eval.py`
- record AgentLens trajectory alongside TAC's evaluator output

## Capture Acceptance Criteria

For every completed trajectory, a reviewer should be able to answer:

1. What did the agent see at each step?
2. What did it decide and why?
3. What GUI action or I/O action happened?
4. What changed on screen or in files after the action?
5. What artifacts were created or modified?
6. Why did the validator pass or fail?

If any answer is missing, fix capture before adding intervention logic.

## Current Verified State

The capture-first pilot is implemented in:

- `configs/experiments/capture_first_domsteer_agentcompany.yaml`
- `configs/experiments/intervention_repeated_action_smoke.yaml`

Verified locally:

- config validation
- deterministic sandbox I/O smoke
- deterministic repeated-action intervention smoke

Verified on AWS EC2:

- AIO Sandbox launches with Chrome CDP using Docker runtime flags:
  - `--shm-size=2g`
  - `--cap-add=SYS_ADMIN`
  - `--security-opt seccomp=unconfined`
- `tac_io_capture_mock` captures:
  - screenshot
  - `files.write`
  - `code.run_python`
  - `code.shell`
  - `files.read`
  - artifact diffs around `/tmp` files
- DOMSteer DataVoyager capture ran with a cheap vision model and surfaced a
  repeated-drag challenge pattern.

The current cheap model in the pilot config is `gpt-5.4-nano`.

## Real-Time Intervention Design

Once capture is stable, add an intervention middleware between proposed action
and execution:

```text
observe state
-> model proposes action
-> intervention monitor evaluates trajectory prefix + proposed action
-> allow / warn / block / inject_message / request_human / terminate
-> execute or skip action
-> record USER_INTERVENTION event
```

### Implemented Decision Schema

```python
InterventionDecision:
    triggered: bool
    kind: str
    mode: off | warn
    message: str
    details: dict
```

### Implemented Monitor

Implemented first:

- repeated-action warning
  - default policy: warn only, do not block
  - can match by action `type` or coarser `target`
  - writes a `USER_INTERVENTION` event
  - displays a transient textual hint on the page
  - injects the warning text into the agent's next observation

This monitor is intentionally simple because repeated action looping is one of
the clearest scalable GUI-agent failure modes: it can be detected from action
logs without human interpretation.

### Future Monitors

Add only after repeated-action intervention is evaluated:

- repeated failed click or no state change
- repeated URL/page loop
- no file/artifact progress after code/shell steps
- premature `final_answer`
- task-boundary violation

Then add LLM/VLM monitors:

- objective drift
- workflow stage omission
- visual grounding failure
- false progress
- ignoring visible/tool error messages

### Evaluation Conditions

Run each task under:

- no intervention
- rule monitor
- LLM/VLM monitor
- human-in-the-loop monitor, later

Measure:

- success rate
- recovery after detected challenge
- step/time cost
- intervention precision
- false positives and false negatives
- artifact quality

This makes intervention a validation layer for the trajectory analysis: if a
detected pattern matters, intervening at that point should improve recovery or
success against a matched no-intervention baseline.
