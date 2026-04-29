# Screenshot ReAct Tools

AgentLens currently supports a screenshot-only ReAct-style browser harness. The harness opens the task `start_url`, captures screenshots, executes browser actions, records trajectory events, and stops on `final_answer`.

## Current Action Space

Actions use an OpenAI computer-use-like JSON shape plus AgentLens-specific `final_answer`.

```json
{
  "type": "click",
  "x": 320,
  "y": 240,
  "button": "left"
}
```

Supported actions:

| Action | Status | Purpose |
|---|---:|---|
| `screenshot` | implemented | Request/record a screenshot of current browser state. |
| `click` | implemented | Click at viewport coordinates. |
| `double_click` | implemented | Double-click at viewport coordinates. |
| `scroll` | implemented | Scroll by `scroll_x` / `scroll_y` from a coordinate. |
| `type` | implemented | Type text into the currently focused element. |
| `wait` | implemented | Wait for `ms` milliseconds, defaulting to 1000 ms. |
| `move` | implemented | Move mouse to viewport coordinates. |
| `keypress` | implemented | Press one or more keyboard keys. |
| `drag` | implemented | Drag mouse along a coordinate path. |
| `final_answer` | implemented | Stop the loop and submit an answer for validation. |
| `goto` | planned | Navigate directly to a URL. Initial task navigation already uses `start_url`. |

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

## Examples

Click:

```json
{"type": "click", "x": 80, "y": 55, "button": "left"}
```

Type:

```json
{"type": "type", "text": "hello"}
```

Keypress:

```json
{"type": "keypress", "keys": ["Enter"]}
```

Scroll:

```json
{"type": "scroll", "x": 400, "y": 300, "scroll_x": 0, "scroll_y": 500}
```

Wait:

```json
{"type": "wait", "ms": 1000}
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

