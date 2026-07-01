# Agent Structures And Tool Tiers

AgentLens separates the model/agent structure from the tool harness tier.

## Practical Pure-GUI Setup

For controlled pure-GUI collection, use the AgentLens tool-call structure with
a GUI-only tool harness.

The model is only registered with GUI tools such as:

- `desktop.screenshot`
- `desktop.click`
- `desktop.double_click`
- `desktop.drag`
- `desktop.scroll`
- `desktop.move`
- `desktop.type`
- `desktop.keypress`
- `desktop.wait`
- `task.final_answer`

Do not expose:

- `code.run_python`
- `code.shell`
- `desktop.shell`
- `browser.goto`
- `files.read`
- `files.write`
- MCP/browser-devtools tools

This is the cleanest provider-side control AgentLens currently has because the
available tool list is enforced by the API tool registration and again by the
runtime gate.

One caveat: native computer-use agents can still use visible GUI routes to
programmatic behavior, such as opening DevTools or typing `javascript:` into the
address bar. Preventing that requires an additional environment/policy layer,
for example blocking DevTools shortcuts, address-bar JavaScript, or browser
chrome regions after setup.

## Agent Files

Current agent/model wrappers live under `src/agentlens/models/`.

| File | Use | Tool Control |
| --- | --- | --- |
| `openai_tool_call.py` | Main controlled OpenAI agent. Used for browser-only, full-sandbox, no-GUI, and strict desktop GUI tiers. | Explicit API-registered tool list plus AgentLens runtime gate. |
| `anthropic_tool_call.py` | Controlled Claude tool-call agent. | Explicit API-registered tool list plus AgentLens runtime gate. |
| `openai_computer_use.py` | OpenAI native computer-use agent using `{"type": "computer"}`. | Broad native computer tool; no fine-grained provider-side subtool tier. |
| `gui_vs_cli_chatgpt.py` | Adapter for the gui-vs-cli paper's ChatGPTAgent. | Paper-faithful native computer-use output converted to pyautogui snippets. |
| `openai_vision.py` | Legacy JSON-action screenshot agent. | Prompt-rendered action schema plus runtime gate; avoid for new collection unless needed for backward compatibility. |

The repo does not need one Python file per benchmark task. The useful split is
one Python file per agent structure, with the harness tier selected by batch
YAML.

## Recommended Comparison Matrix

Use distinct run labels for these setups:

| Label | Agent Structure | Harness Meaning |
| --- | --- | --- |
| `strict_gui_toolcall` | `openai_tool_call.py` or `anthropic_tool_call.py` | GUI actions only; no shell/code/file/MCP tools. |
| `native_computer_gui` | `openai_computer_use.py` | OpenAI native computer-use GUI. Good for model-native comparison, not strict visual-only control. |
| `paper_faithful_gui_vs_cli` | `gui_vs_cli_chatgpt.py` | Reproduces the gui-vs-cli ChatGPTAgent action structure through pyautogui snippets. |
| `full_sandbox` | `openai_tool_call.py` or `anthropic_tool_call.py` | GUI plus shell/code/file/search tools. |
| `no_gui` | `openai_tool_call.py` or `anthropic_tool_call.py` | Programmatic tools only, no screenshots or GUI actions. |

## Agent Name Mapping

The GUI-vs-CLI smoke config uses explicit agent ids. These names encode the
agent structure, not just the provider model.

| Agent id | Provider/model family | Agent structure | Tool/control meaning |
| --- | --- | --- | --- |
| `openai_gpt_computer_use` | OpenAI GPT | AgentLens wrapper for OpenAI Responses native `computer` tool. | Native computer-use GUI loop. Broad provider-side computer tool; not strict subtool control. |
| `agentlens_gui_toolcall_gpt54` | OpenAI GPT-5.4 | AgentLens registered-tool agent using `openai_tool_call.py`. | Strict GUI-only direct-manipulation tool list registered by AgentLens. |
| `agentlens_gui_toolcall_haiku` | Anthropic Claude Haiku | AgentLens registered-tool agent using `anthropic_tool_call.py`. | Strict GUI-only direct-manipulation tool list registered by AgentLens. |
| `agentlens_gui_toolcall_gemini` | Gemini | Planned AgentLens registered-tool agent. | Disabled until a Gemini provider tool-call adapter exists. |
| `gui_vs_cli_chatgpt` | OpenAI GPT | gui-vs-cli paper-style `ChatGPTAgent`. | Computer-use agent from the gui-vs-cli repo; model emits native computer actions that the paper code converts to pyautogui snippets. |
| `gui_vs_cli_claude` | Anthropic Claude | gui-vs-cli paper-style `ClaudeAgent`. | Claude computer-use agent from the gui-vs-cli repo; not the AgentLens strict registered-tool Claude agent. |
| `gui_vs_cli_gemini` | Gemini | gui-vs-cli paper-style `GeminiAgent`. | Gemini desktop agent from the gui-vs-cli repo; not the disabled AgentLens strict registered-tool Gemini agent. |

In short: `gui_vs_cli_*` means "paper-style gui-vs-cli agent structure"; it
does not mean AgentLens strict GUI-only tool registration. The strict
AgentLens variants are the `agentlens_gui_toolcall_*` ids.

## GUI-vs-CLI Full Workflow Tasks

AgentLens has imported the GUI-vs-CLI task catalog:

```text
tasks/gui_vs_cli/tasks.jsonl
```

The catalog is not enough to run the full paper workflow by itself. Full
execution still needs:

1. A compatible desktop image with the paper's application stack.
2. Seed files mounted to the paths listed in each task's `env.files`.
3. A verifier bridge that can execute the task's original verification
   commands inside the desktop environment.
4. A launcher bridge that opens the correct application and task state before
   the first screenshot.

Until those pieces exist, GUI-vs-CLI tasks should stay in the catalog and not
be added to active collection batches except as explicitly marked POCs.

Current POC bridge:

```text
configs/gui_vs_cli/full_workflow_smoke.yaml
scripts/gui_vs_cli_full_workflow_smoke.py
```

This bridge reuses gui-vs-cli's desktop environment setup, app launcher,
seed-file upload, and verifier stack, then runs either:

- AgentLens-native structures such as `agentlens_gui_toolcall_gpt54`.
- Provider-native computer-use structures such as `openai_gpt_computer_use`.
- Paper-style gui-vs-cli structures such as `gui_vs_cli_claude`.

The smoke config selects one representative task from each GUI-vs-CLI
application category, currently 18 applications.

Build the paper-style local Docker runtime before full execution:

```bash
cd third_party/gui-vs-cli
DOCKER_ENV_PLATFORM=linux/amd64 \
  bash computer_env/provision/docker/build_image.sh paraverse-agent-runtime:latest
```

Readiness smoke:

```bash
uv run --no-sync python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/full_workflow_smoke.yaml \
  --ready-check-only
```

Full smoke for one task and one agent:

```bash
uv run --no-sync python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/full_workflow_smoke.yaml \
  --agent agentlens_gui_toolcall_gpt54 \
  --task chrome_dom_inspection_wikipedia
```
