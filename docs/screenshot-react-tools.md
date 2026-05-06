# Screenshot ReAct Tools

AgentLens supports a screenshot-only ReAct-style browser harness. The harness opens the task `start_url`, captures screenshots, executes browser actions, records trajectory events, and stops on `final_answer`.

The action schema is a near-superset of OpenAI's computer-use tool, with extras for navigation (`goto`, `back`, `forward`, `reload`) and a stop signal (`final_answer`).

## Action Space

Actions use an OpenAI computer-use-like JSON shape.

```json
{
  "type": "click",
  "x": 320,
  "y": 240,
  "button": "left"
}
```

| Action | Status | Purpose |
|---|---:|---|
| `screenshot` | implemented | Request/record a screenshot of current browser state. |
| `click` | implemented | Click at viewport coordinates. Optional `keys` for held modifiers. |
| `double_click` | implemented | Double-click at viewport coordinates. Optional `keys`. |
| `scroll` | implemented | Scroll by `scroll_x` / `scroll_y` from a coordinate. Optional `keys`. |
| `type` | implemented | Type text into the currently focused element. |
| `wait` | implemented | Wait for `ms` milliseconds, defaulting to 1000 ms. |
| `move` | implemented | Move mouse to viewport coordinates. Optional `keys`. |
| `keypress` | implemented | Press one or more keyboard keys. |
| `drag` | implemented | Drag mouse along a coordinate path. Optional `keys`. |
| `goto` | implemented | Navigate directly to a URL. |
| `back` | implemented | Go back one entry in browser history. |
| `forward` | implemented | Go forward one entry in browser history. |
| `reload` | implemented | Reload the current page. |
| `final_answer` | implemented | Stop the loop and submit an answer for validation. |
| `web_search` | implemented | Native OpenAI `web_search` via Responses API. Result text injected into next observation. Tool name: `web.openai_search`. |
| `run_python` | implemented (sandbox tier) | Execute Python in the AIO Sandbox Jupyter kernel. Tool name: `code.run_python`. |
| `shell` | implemented (sandbox tier) | Run a bash command in the AIO Sandbox shell. Tool name: `code.shell`. |
| `read_file` | implemented (sandbox tier) | Read a file from the AIO Sandbox filesystem. Tool name: `files.read`. |
| `write_file` | implemented (sandbox tier) | Write a file into the AIO Sandbox filesystem. Tool name: `files.write`. |

The non-browser actions (`run_python`, `shell`, `read_file`, `write_file`) require `tool_harness.tier: browser_files` or `full_sandbox` AND `tool_harness.extra.browser_source: aio_sandbox`. They mirror `web_search`'s "tool result text → next observation" pattern (see `tool_output_since_last_step` in `models/base.py`).

## Addressing Modes

Click / double-click / scroll / move / type can target an element by **coordinate** (default), **bid** (BrowserGym-style accessibility id from AXTree extraction), **selector** (CSS), or **mark** (Set-of-Marks numeric label). Exactly one of these target fields per action — validated in `actions.py`:

```json
{"type": "click", "x": 320, "y": 240}        // coordinate
{"type": "click", "bid": "a47"}              // bid (DOM-ReAct)
{"type": "click", "selector": "#submit-btn"} // CSS selector
{"type": "click", "mark": "M3"}              // Set-of-Marks
```

Selection per harness via `tool_harness.extra.addressing_modes`:

```yaml
extra:
  addressing_modes: [coordinate]            # vision-only baseline
  addressing_modes: [bid]                   # DOM-ReAct
  addressing_modes: [coordinate, bid]       # hybrid
  addressing_modes: [mark]                  # Set-of-Marks (Anthropic computer-use style)
  addressing_modes: [mark, bid]             # browser-use recipe (most robust)
```

## Perception Modes

Orthogonal to addressing — what the model *sees* in each observation:

```yaml
extra:
  input_modes: [screenshot]                 # default
  input_modes: [axtree]                     # text-only AXTree
  input_modes: [screenshot, axtree]         # max-info hybrid
  input_modes: [set_of_marks]               # screenshot WITH overlaid mark badges
  input_modes: [set_of_marks, axtree]       # browser-use recipe
```

Verified 5/5 modes on the same TF Playground task in `configs/experiments/perception_modes_smoke.yaml`. See the handout's "Supported agentic framework" section for the full matrix.

## Tier

Each tool is gated by `tool_harness.tier`:

| Tier | Action surface |
|---|---|
| `browser_only` | `browser.*`, `web.openai_search`, `task.final_answer` |
| `browser_files` | `browser_only` + `files.read` / `files.write` |
| `full_sandbox` | `browser_files` + `code.run_python` + `code.shell` |

`browser_files` and `full_sandbox` require `tool_harness.extra.browser_source: aio_sandbox`. `tools` further narrows the tier (tier is the upper bound, not the literal action set).

## Coordinate Convention

Coordinates are viewport pixels relative to the top-left of the browser viewport:

```json
{
  "type": "click",
  "x": 80,
  "y": 55,
  "button": "left"
}
```

Each screenshot event stores the current URL, viewport size, goal, and screenshot artifact path.

## Modifier Keys

For all mouse actions (`click`, `double_click`, `scroll`, `move`, `drag`), the optional `keys` field is a list of modifiers held during the action:

```json
{"type": "click", "x": 100, "y": 200, "keys": ["SHIFT"]}
{"type": "click", "x": 100, "y": 200, "keys": ["CTRL"]}
{"type": "click", "x": 100, "y": 200, "keys": ["META"]}
```

Recognized modifier names (case-insensitive):

```text
SHIFT
CTRL / CONTROL
ALT / OPTION
META / CMD / COMMAND / SUPER / WIN
```

For `keypress`, the `keys` field is the list of keys to PRESS (different semantics):

```json
{"type": "keypress", "keys": ["Enter"]}
{"type": "keypress", "keys": ["Control", "a"]}
```

## OpenAI Computer-Use Compatibility

The action schema is intentionally compatible with OpenAI's computer-use tool output, with two ergonomic extras:

- `scroll_x` / `scroll_y` also accepted as `scrollX` / `scrollY` (camelCase).
- `drag.path` accepts either `{"x": .., "y": ..}` objects OR `[x, y]` arrays.

So a JSON action emitted by OpenAI's computer-use Responses API will run through AgentLens unchanged, modulo our `final_answer` stop signal (OpenAI's computer-use signals stop by emitting no further `computer_call`; we use an explicit `final_answer` action because we use chat completions, not Responses API).

## Examples

Click:

```json
{"type": "click", "x": 80, "y": 55, "button": "left"}
```

Shift-click (multi-select):

```json
{"type": "click", "x": 80, "y": 55, "button": "left", "keys": ["SHIFT"]}
```

Type:

```json
{"type": "type", "text": "hello"}
```

Keypress:

```json
{"type": "keypress", "keys": ["Enter"]}
```

Select-all:

```json
{"type": "keypress", "keys": ["Control", "a"]}
```

Scroll:

```json
{"type": "scroll", "x": 400, "y": 300, "scroll_x": 0, "scroll_y": 500}
```

Drag (object form):

```json
{"type": "drag", "path": [{"x": 100, "y": 100}, {"x": 200, "y": 100}]}
```

Drag (array form, OpenAI-compatible):

```json
{"type": "drag", "path": [[100, 100], [200, 100]]}
```

Wait:

```json
{"type": "wait", "ms": 1000}
```

Navigate:

```json
{"type": "goto", "url": "https://example.com"}
{"type": "back"}
{"type": "forward"}
{"type": "reload"}
```

Final answer:

```json
{"type": "final_answer", "answer": "Mazda GLC"}
```

## Mock Testing

Mock action sequences are configured per task under `extra.mock_actions`.

Example:

```yaml
extra:
  mock_actions:
    - type: click
      x: 80
      y: 55
      button: left
    - type: type
      text: hello
    - type: keypress
      keys: [Enter]
    - type: scroll
      x: 400
      y: 300
      scroll_x: 0
      scroll_y: 500
    - type: wait
      ms: 100
    - type: final_answer
      answer: tools ok
```
