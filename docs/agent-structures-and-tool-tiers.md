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
| `gemini_tool_call.py` | Controlled Gemini tool-call agent. | Explicit API-registered function list plus AgentLens runtime gate. |
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
| `strict_gui_toolcall` | `openai_tool_call.py`, `anthropic_tool_call.py`, or `gemini_tool_call.py` | GUI actions only; no shell/code/file/MCP tools. |
| `native_computer_gui` | `openai_computer_use.py` | OpenAI native computer-use GUI. Good for model-native comparison, not strict visual-only control. |
| `paper_faithful_gui_vs_cli` | `gui_vs_cli_chatgpt.py` | Reproduces the gui-vs-cli ChatGPTAgent action structure through pyautogui snippets. |
| `paper_cli_anything` | `scripts/gui_vs_cli_full_workflow_smoke.py` with `gui_vs_cli_cli_*` agents | Paper-style CLI-Anything: no visual input, no GUI actions, CLI agent runs inside the gui-vs-cli task image. Use for gui-vs-cli workflow tasks unless a benchmark-specific CLI-Anything harness is explicitly built. |
| `programmatic_no_visual` | Tool-call agent with code/shell/files/search tools only | Programmatic baseline: no screenshots and no GUI actions, but not necessarily the paper's CLI-Anything setup. This is the current fair DOMSteer no-visual condition. |
| `full_sandbox` | `openai_tool_call.py`, `anthropic_tool_call.py`, or `gemini_tool_call.py` | GUI plus shell/code/file/search tools. |

For reporting, keep these four experimental conditions separate:

| Condition | Visual Input | GUI Actions | Programmatic/CLI Access | Current Scope |
| --- | --- | --- | --- | --- |
| `gui_only` | Yes | Yes, direct manipulation only | No | DOMSteer, gui-vs-cli, desktop POCs |
| `cli_anything_no_visual` | No | No | Yes, paper CLI agent inside task image | gui-vs-cli workflow tasks |
| `programmatic_no_visual` | No | No | Yes, AgentLens code/shell/files/search or benchmark-specific scripts | DOMSteer and data-analysis baselines |
| `full_sandbox` | Usually yes | Yes | Yes | Mixed-capability upper-bound / agent-company-style condition |

The important rule: do not call DOMSteer `programmatic_no_visual`
"CLI-Anything" unless we implement a DOMSteer-specific CLI-Anything harness
with the same constraints as the paper condition.

## Agent Name Mapping

The GUI-vs-CLI smoke config uses explicit agent ids. These names encode the
agent structure, not just the provider model.

| Agent id | Provider/model family | Agent structure | Tool/control meaning |
| --- | --- | --- | --- |
| `openai_gpt_computer_use` | OpenAI GPT | AgentLens wrapper for OpenAI Responses native `computer` tool. | Native computer-use GUI loop. Broad provider-side computer tool; not strict subtool control. |
| `agentlens_gui_toolcall_gpt54` | OpenAI GPT-5.4 | AgentLens registered-tool agent using `openai_tool_call.py`. | Strict GUI-only direct-manipulation tool list registered by AgentLens. |
| `agentlens_gui_toolcall_haiku` | Anthropic Claude Haiku | AgentLens registered-tool agent using `anthropic_tool_call.py`. | Strict GUI-only direct-manipulation tool list registered by AgentLens. |
| `agentlens_gui_toolcall_gemini` | Gemini | AgentLens registered-tool agent using `gemini_tool_call.py`. | Strict GUI-only direct-manipulation tool list registered by AgentLens. Requires `GEMINI_API_KEY` or `GOOGLE_AI_STUDIO_API_KEY`. |
| `gui_vs_cli_chatgpt` | OpenAI GPT | gui-vs-cli paper-style `ChatGPTAgent`. | Computer-use agent from the gui-vs-cli repo; model emits native computer actions that the paper code converts to pyautogui snippets. |
| `gui_vs_cli_claude` | Anthropic Claude | gui-vs-cli paper-style `ClaudeAgent`. | Claude computer-use agent from the gui-vs-cli repo; not the AgentLens strict registered-tool Claude agent. |
| `gui_vs_cli_gemini` | Gemini | gui-vs-cli paper-style `GeminiAgent`. | Gemini desktop agent from the gui-vs-cli repo; not the disabled AgentLens strict registered-tool Gemini agent. |
| `gui_vs_cli_cli_claude` | Claude Code CLI | gui-vs-cli paper-style CLI agent. | Runs `claude -p ...` inside the Docker task image with the paper's CLI-Anything-only prompt. Requires `claude` installed and authenticated inside the image. |
| `gui_vs_cli_cli_codex` | Codex CLI | gui-vs-cli paper-style CLI agent. | Runs `codex exec ...` inside the Docker task image with the paper's CLI-Anything-only prompt. Requires `codex` installed and authenticated inside the image. |

In short: `gui_vs_cli_*` means "paper-style gui-vs-cli agent structure"; it
does not mean AgentLens strict GUI-only tool registration. The strict
AgentLens variants are the `agentlens_gui_toolcall_*` ids.

## Full Sandbox vs Paper-Style Computer Agent

Do not treat `full_sandbox`, strict GUI-only, and paper-style computer agents
as interchangeable conditions.

| Condition | Agent path | What the model can use | Action granularity |
| --- | --- | --- | --- |
| AgentLens strict GUI-only | `agentlens_gui_toolcall_*` | Only the registered direct-manipulation tools and `task.final_answer`. | Usually one model round can emit one or more structured AgentLens actions. |
| AgentLens full sandbox | `agentlens_*_toolcall` with the full-sandbox tool harness | GUI tools plus programmatic tools such as shell, Python, files, and search. | Structured AgentLens actions from an explicit tool allow-list. |
| Paper-style computer agent | `gui_vs_cli_chatgpt`, `gui_vs_cli_claude`, `gui_vs_cli_gemini` | Provider-native computer/desktop interface from the gui-vs-cli paper agents. | Often low-level pyautogui snippets, for example separate key down/up, mouse down/move/up, and waits. |

The paper-style agents are useful for faithful comparison with the gui-vs-cli
paper, but they are not the same as AgentLens full sandbox. They convert
provider-native computer actions into `desktop_pyautogui` code and run that
code in the desktop. This makes the trajectory useful, but it also means step
counts are not directly comparable with AgentLens strict GUI-only runs.

Known adapter compatibility notes:

- `left_click_drag` may include an unexpected `text` field from newer Claude
  computer-use responses; the adapter ignores it.
- `cursor_position` is treated as a no-op wait in AgentLens because the current
  bridge returns the next screenshot, not a cursor-coordinate tool result.

## GUI-vs-CLI Full Workflow Tasks

AgentLens has imported the GUI-vs-CLI task catalogs:

```text
tasks/gui_vs_cli/tasks.jsonl            # 440 standard tasks
tasks/gui_vs_cli/tasks_standard.jsonl   # same 440 standard tasks
tasks/gui_vs_cli/tasks_grounding.jsonl  # 176 grounded-prompt tasks
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
- Paper-style CLI structures such as `gui_vs_cli_cli_claude` and
  `gui_vs_cli_cli_codex`.

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

Paper-style CLI readiness smoke:

```bash
python scripts/gui_vs_cli_full_workflow_smoke.py \
  configs/gui_vs_cli/full_workflow_smoke.yaml \
  --ready-check-only \
  --agent gui_vs_cli_cli_claude \
  --task chrome_dom_inspection_wikipedia
```

As of 2026-07-01, AWS has a derived CLI-enabled image:

```text
agentlens-gui-vs-cli-runtime:latest
```

It is based on `paraverse-agent-runtime:latest` and includes:

- Claude Code CLI: `claude`
- Codex CLI: `codex`
- Runtime wrappers that source `/home/user/.agentlens_cli_env`, set
  `HOME=/home/user`, and drop root execution to the sandbox `user` account.

The runner writes `/home/user/.agentlens_cli_env` and, when `OPENAI_API_KEY` is
available, writes `/home/user/.codex/config.toml` with a custom
`openai_env` provider using `env_key = "OPENAI_API_KEY"`.

AWS smoke status:

- CLI binary readiness passes for `gui_vs_cli_cli_claude` and
  `gui_vs_cli_cli_codex`.
- `gui_vs_cli_cli_codex` reaches the OpenAI API, but the current key is blocked
  by quota (`Quota exceeded. Check your plan and billing details.`).
- `gui_vs_cli_claude` and `gui_vs_cli_cli_claude` require
  `ANTHROPIC_API_KEY` in the AWS `.env`; do not commit that file.

## DOMSteer And CLI Agents

DOMSteer DataVoyager/TensorFlow Playground tasks are web visual-analytics
tasks. They can be run as GUI/browser/no-GUI tool tiers in AgentLens, but they
are not directly paper-style GUI-vs-CLI CLI tasks unless we build a separate
DOMSteer CLI/browser-skill harness.

For a fair label, use:

- `domsteer_gui`: visual direct manipulation.
- `domsteer_browser_tool`: browser/DOM or MCP-style browser tools.
- `domsteer_no_gui`: programmatic analysis tools.
- `domsteer_cli_browser_skill`: only if we intentionally design a CLI skill
  that solves DOMSteer through command-line/browser automation.

Provider target matrix:

| Provider family | `gui_only` | `cli_anything_no_visual` | `programmatic_no_visual` | `full_sandbox` |
| --- | --- | --- | --- | --- |
| GPT/OpenAI | AgentLens tool-call or native computer-use | Codex CLI for gui-vs-cli tasks | AgentLens no-GUI or Codex CLI baseline | AgentLens full-sandbox tool-call |
| Claude/Anthropic | AgentLens tool-call or gui-vs-cli Claude computer agent | Claude Code CLI for gui-vs-cli tasks | AgentLens no-GUI or Claude Code baseline | AgentLens full-sandbox tool-call |
| Gemini | AgentLens tool-call or gui-vs-cli Gemini computer agent | Not implemented yet unless a Gemini CLI/task runner is selected | AgentLens no-GUI tool-call if tool/function support is sufficient | AgentLens full-sandbox tool-call |
| GLM/DeepSeek | Planned OpenAI-compatible or provider-specific wrapper | Not implemented | Planned if the model supports tool/function calls or CLI access | Planned |

For cross-provider comparisons, keep the VM setup constant within a task
family: same Docker image, screen size, start state, seeded files, app launcher,
and evaluator. Change only the agent/model condition.
