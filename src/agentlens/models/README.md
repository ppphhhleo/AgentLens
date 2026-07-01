# Model / Agent Backends

This folder contains the Python wrappers for different agent structures. Batch
YAML selects one of these structures through `model.extra.interaction_backend`;
the tool harness then selects the tool tier.

## Active Backends

| Backend | File | Intended Use |
| --- | --- | --- |
| `tool_call` | `openai_tool_call.py`, `anthropic_tool_call.py` | Main controlled setup. The model receives provider-native function/tool definitions for exactly the tools in the harness. |
| `openai_computer` | `openai_computer_use.py` | OpenAI native computer-use setup with `{"type": "computer"}`. Useful for model-native GUI comparison. |
| `gui_vs_cli_chatgpt` | `gui_vs_cli_chatgpt.py` | Paper-faithful adapter for `rebeccaz4/gui-vs-cli` ChatGPTAgent. Native computer-use actions are converted by the paper agent into pyautogui snippets. |
| `gui_vs_cli_claude` | `gui_vs_cli_chatgpt.py` | Paper-faithful adapter for `rebeccaz4/gui-vs-cli` ClaudeAgent. |
| `gui_vs_cli_gemini` | `gui_vs_cli_chatgpt.py` | Paper-faithful adapter for `rebeccaz4/gui-vs-cli` GeminiAgent. |

## Legacy Backend

`openai_vision.py` is the older screenshot-to-JSON-action wrapper. It is kept
for backward compatibility and reports that still import its prompt template.
New trajectory collection should prefer `tool_call`, `openai_computer`, or
`gui_vs_cli_chatgpt`.

## Tier Control

Do not hard-code benchmark or harness tiers inside these files. A backend
defines how the model speaks; a `ToolHarnessConfig` defines what tools/actions
are allowed for a run.
