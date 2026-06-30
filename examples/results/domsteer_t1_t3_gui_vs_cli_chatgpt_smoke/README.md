# DOMSteer T1-T3 gui-vs-cli ChatGPTAgent Smoke

This curated bundle preserves the first successful DOMSteer DataVoyager
T1-T3 smoke trajectories collected with the paper-style
`gui_vs_cli_chatgpt` backend.

## Setup

- Batch config:
  - `batch_config.yaml`
- Model:
  - GPT-5.4 through OpenAI Responses API native `{"type": "computer"}`
- Agent structure:
  - `third_party/gui-vs-cli/agents/chatgpt_agent.py`
  - Responses are converted by the gui-vs-cli agent into pyautogui snippets.
  - AgentLens records those snippets as `desktop.pyautogui` actions.
- Environment:
  - AgentLens AIO desktop sandbox.
  - Desktop screenshots/actions use the virtual desktop coordinate frame.

## Results

| Task | Trajectory | Expected | Score | Behavioral Note |
| --- | --- | --- | ---: | --- |
| T1 most fuel-efficient car | `trajectories/t1_gui_vs_cli_chatgpt/trajectory.json` | `Mazda GLC` | 1.0 | Started with GUI field dragging, then used DevTools/fetch. |
| T2 widest horsepower range by origin | `trajectories/t2_gui_vs_cli_chatgpt/trajectory.json` | `USA` | 1.0 | Used DevTools/fetch through the GUI. |
| T3 European cars, horsepower > 100, four cylinders | `trajectories/t3_gui_vs_cli_chatgpt/trajectory.json` | `10` | 1.0 | Used address-bar JavaScript/fetch through the GUI. |

## Interpretation

These runs are useful as a paper-faithful GUI baseline, but they are not strict
visual-only GUI behavior. The native computer-use tool constrains the model to
desktop actions, yet the model can still use GUI routes to programmatic
workflows, such as DevTools or `javascript:` URLs.

For strict visual-only comparison, use an AgentLens tool tier or policy layer
that explicitly restricts browser chrome, DevTools, address-bar JavaScript, and
other programmatic GUI escape routes.
