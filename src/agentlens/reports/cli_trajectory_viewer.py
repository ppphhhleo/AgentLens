from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from typing import Any


def write_cli_trajectory_viewer(input_path: Path, output_path: Path | None = None) -> Path:
    """Render a static HTML viewer for CLI-only trajectory.json files."""
    input_path = input_path.expanduser().resolve()
    traj = json.loads(input_path.read_text(encoding="utf-8"))
    if not _looks_like_cli_trajectory(traj):
        raise ValueError(f"not a CLI trajectory: {input_path}")

    if output_path is None:
        output_path = input_path.with_name("cli_trajectory_viewer.html")
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _render_page(traj, source_path=input_path, output_path=output_path),
        encoding="utf-8",
    )
    return output_path


def _looks_like_cli_trajectory(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    events = value.get("events")
    if not isinstance(events, list):
        return False
    return any((event or {}).get("event_type") == "cli_execution" for event in events)


def _render_page(traj: dict[str, Any], *, source_path: Path, output_path: Path) -> str:
    task = traj.get("task") or {}
    agent = traj.get("agent") or {}
    metrics = traj.get("metrics") or {}
    validation = _validation_event(traj)
    cli_execution = _cli_execution_event(traj)
    execution_data = (cli_execution or {}).get("data") or {}
    provider_events = execution_data.get("events") or []

    cards = "\n".join(_render_provider_event(event) for event in provider_events)
    if not cards:
        cards = '<section class="card muted-card">No provider stream events recorded.</section>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentLens CLI Trajectory Viewer</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-2: #f9fafc;
      --text: #171a1f;
      --muted: #667085;
      --line: #dfe4ec;
      --accent: #2563eb;
      --ok: #168a4a;
      --bad: #d23f31;
      --code: #f3f5f8;
      --cmd: #7c3aed;
      --thought: #475569;
      --answer: #db2777;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #fff 0, var(--bg) 18rem), var(--bg);
      color: var(--text);
      font: 14px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      padding: .85rem 1rem;
      background: rgba(255,255,255,.94);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 1.15rem; letter-spacing: 0; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: .9rem; }}
    a {{ color: var(--accent); text-decoration: none; }}
    .source {{
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-top: .25rem;
    }}
    .run {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      overflow: hidden;
      box-shadow: 0 14px 34px rgba(28, 38, 57, .08);
    }}
    .run-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: .8rem;
      padding: .75rem .85rem;
      border-bottom: 1px solid var(--line);
    }}
    .run-head h2 {{
      font-size: 1.1rem;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .badges {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: .35rem;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: .18rem .45rem;
      background: var(--panel-2);
      color: var(--text);
      font-size: .78rem;
      white-space: nowrap;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: .32rem .8rem;
      padding: .5rem .85rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }}
    .metric span {{ color: var(--muted); margin-right: .25rem; }}
    .metric strong {{ font-weight: 780; }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    .goal {{
      margin: .75rem .85rem;
      padding: .65rem .75rem;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
    }}
    .goal h3, .section-title {{
      font-size: .8rem;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--muted);
      margin-bottom: .25rem;
    }}
    .timeline {{
      display: grid;
      gap: .55rem;
      padding: 0 .85rem .85rem;
    }}
    .card {{
      border: 1px solid var(--line);
      border-left: 4px solid var(--kind, var(--line));
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
    }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: .75rem;
      padding: .45rem .6rem;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--kind, var(--line)) 7%, white);
    }}
    .card-title {{ font-weight: 780; color: var(--kind, var(--text)); }}
    .card-sub {{ color: var(--muted); font-size: .78rem; }}
    .card-body {{ padding: .55rem .6rem; }}
    .assistant {{ --kind: #2563eb; }}
    .thought {{ --kind: var(--thought); }}
    .command {{ --kind: var(--cmd); }}
    .output {{ --kind: #059669; }}
    .final {{ --kind: var(--answer); }}
    .system {{ --kind: #94a3b8; }}
    .validation {{ --kind: var(--ok); }}
    .muted-card {{ color: var(--muted); padding: .7rem; }}
    pre {{
      max-height: 24rem;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: .6rem;
      border-radius: 7px;
      background: var(--code);
      border: 1px solid var(--line);
      color: #1f2937;
      font-size: .78rem;
    }}
    .text-block {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    details {{ margin: .6rem .85rem .85rem; }}
    summary {{ cursor: pointer; color: var(--accent); }}
    @media (max-width: 800px) {{
      .run-head {{ grid-template-columns: 1fr; }}
      .badges {{ justify-content: flex-start; }}
      main {{ padding: .65rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AgentLens CLI Trajectory Viewer</h1>
    <div class="source">Source: <code>{escape(str(source_path))}</code></div>
  </header>
  <main>
    <section class="run">
      <div class="run-head">
        <div>
          <h2>{escape(str(traj.get("run_id", "")))}</h2>
          <div class="source">{escape(str(traj.get("experiment_id", "")))} · task={escape(str(task.get("id", "")))}</div>
        </div>
        <div class="badges">
          <span class="badge">mode: CLI-only</span>
          <span class="badge">agent: {escape(str(agent.get("id", "")))}</span>
          <span class="badge">model: {escape(str(agent.get("model", "")))}</span>
          <span class="badge">provider: {escape(str(agent.get("provider", "")))}</span>
        </div>
      </div>
      {_render_metrics(metrics, validation)}
      <section class="goal">
        <h3>Goal</h3>
        <div>{escape(str(task.get("goal", "")))}</div>
      </section>
      <section class="goal">
        <h3>CLI Prompt</h3>
        {_render_prompt_summary(traj)}
      </section>
      <div class="timeline">
        <div class="section-title">CLI Execution Timeline</div>
        {cards}
        {_render_validation(validation)}
      </div>
      {_render_raw_details(cli_execution, validation)}
    </section>
  </main>
</body>
</html>
"""


def _render_metrics(metrics: dict[str, Any], validation: dict[str, Any] | None) -> str:
    success = metrics.get("success")
    score = metrics.get("score")
    answer = (validation or {}).get("answer")
    expected = (validation or {}).get("expected_answer")
    items = [
        ("score", score),
        ("success", success),
        ("steps", metrics.get("steps")),
        ("cli actions", metrics.get("tool_calls")),
        ("duration", _format_duration_ms(metrics.get("duration_ms"))),
        ("answer", answer),
        ("expected", expected),
    ]
    cells = "\n".join(
        f'<div class="metric"><span>{escape(label)}</span><strong class="{_status_class(label, value)}">{escape(_short(value))}</strong></div>'
        for label, value in items
        if value is not None
    )
    return f'<div class="meta">{cells}</div>'


def _render_prompt_summary(traj: dict[str, Any]) -> str:
    prompt = next(
        (event for event in traj.get("events") or [] if event.get("event_type") == "cli_prompt"),
        {},
    )
    data = prompt.get("data") or {}
    return (
        f'<div class="text-block">policy={escape(str(data.get("policy", "")))}'
        f'<br>prompt_file={escape(str(data.get("prompt_file", "")))}</div>'
    )


def _render_provider_event(event: dict[str, Any]) -> str:
    event_type = event.get("type")
    if event_type == "assistant":
        return _render_claude_assistant_event(event)
    if event_type == "user":
        return _render_claude_user_event(event)
    if event_type == "result":
        return _card(
            "final",
            "Run result",
            event.get("subtype") or "",
            event.get("result") or _json(event),
        )
    if event_type in {"thread.started", "turn.started", "turn.completed"}:
        body = _json(event.get("usage") or event)
        return _card("system", str(event_type), "", body)
    if event_type in {"item.started", "item.completed"}:
        return _render_codex_item_event(event)
    if event_type == "system":
        subtype = str(event.get("subtype") or "system")
        if subtype == "thinking_tokens":
            return ""
        body = _json({k: v for k, v in event.items() if k not in {"tools", "slash_commands", "skills"}})
        return _card("system", f"System: {subtype}", "", body)
    return _card("system", str(event_type or "event"), "", _json(event))


def _render_claude_assistant_event(event: dict[str, Any]) -> str:
    message = event.get("message") or {}
    cards: list[str] = []
    for item in message.get("content") or []:
        item_type = item.get("type")
        if item_type == "thinking":
            cards.append(_card("thought", "Thinking", "", item.get("thinking") or ""))
        elif item_type == "text":
            text = str(item.get("text") or "")
            kind = "final" if "FINAL_ANSWER:" in text else "assistant"
            title = "Final answer" if kind == "final" else "Assistant"
            cards.append(_card(kind, title, "", text))
        elif item_type == "tool_use":
            name = str(item.get("name") or "tool")
            command = ((item.get("input") or {}).get("command") or _json(item.get("input") or {}))
            cards.append(_card("command", f"Tool call: {name}", "", command, pre=True))
    return "\n".join(cards)


def _render_claude_user_event(event: dict[str, Any]) -> str:
    message = event.get("message") or {}
    cards: list[str] = []
    for item in message.get("content") or []:
        if item.get("type") == "tool_result":
            cards.append(_card("output", "Tool result", "", item.get("content") or "", pre=True))
    if not cards and event.get("tool_use_result"):
        cards.append(_card("output", "Tool result", "", _json(event["tool_use_result"]), pre=True))
    return "\n".join(cards)


def _render_codex_item_event(event: dict[str, Any]) -> str:
    item = event.get("item") or {}
    item_type = item.get("type")
    if item_type == "agent_message":
        text = str(item.get("text") or "")
        kind = "final" if "FINAL_ANSWER:" in text else "assistant"
        title = "Final answer" if kind == "final" else "Assistant"
        return _card(kind, title, str(event.get("type") or ""), text)
    if item_type == "command_execution":
        status = str(item.get("status") or event.get("type") or "")
        command = item.get("command") or ""
        output = item.get("aggregated_output") or ""
        exit_code = item.get("exit_code")
        if event.get("type") == "item.started":
            return _card("command", "Command started", status, command, pre=True)
        body = f"$ {command}"
        if output:
            body += f"\n\n{output}"
        if exit_code is not None:
            body += f"\n[exit_code={exit_code}]"
        return _card("output", "Command completed", status, body, pre=True)
    return _card("system", str(item_type or event.get("type")), "", _json(event))


def _render_validation(validation: dict[str, Any] | None) -> str:
    if not validation:
        return ""
    status = "PASS" if validation.get("success") else "FAIL"
    body = "\n".join(
        f"{key}: {validation.get(key)}"
        for key in ["answer", "expected_answer", "score", "message", "answer_validator"]
        if validation.get(key) is not None
    )
    return _card("validation", f"Validation: {status}", "", body, pre=True)


def _render_raw_details(
    cli_execution: dict[str, Any] | None, validation: dict[str, Any] | None
) -> str:
    raw = {
        "cli_execution": cli_execution,
        "validation": validation,
    }
    return f"<details><summary>Raw CLI records</summary><pre>{escape(_json(raw))}</pre></details>"


def _card(kind: str, title: str, subtitle: str, body: Any, *, pre: bool = False) -> str:
    content = (
        f"<pre>{escape(str(body))}</pre>"
        if pre
        else f'<div class="text-block">{escape(str(body))}</div>'
    )
    return f"""<section class="card {escape(kind)}">
  <div class="card-head">
    <span class="card-title">{escape(title)}</span>
    <span class="card-sub">{escape(subtitle)}</span>
  </div>
  <div class="card-body">{content}</div>
</section>"""


def _cli_execution_event(traj: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            event
            for event in traj.get("events") or []
            if event.get("event_type") == "cli_execution"
        ),
        None,
    )


def _validation_event(traj: dict[str, Any]) -> dict[str, Any] | None:
    event = next(
        (
            event
            for event in traj.get("events") or []
            if event.get("event_type") == "validation_event"
        ),
        None,
    )
    return (event or {}).get("data") if event else None


def _format_duration_ms(value: Any) -> str | None:
    if value is None:
        return None
    try:
        seconds = float(value) / 1000
    except (TypeError, ValueError):
        return str(value)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = int(round(seconds % 60))
    return f"{minutes}m {remainder}s"


def _status_class(label: str, value: Any) -> str:
    if label != "success":
        return ""
    return "ok" if value else "bad"


def _short(value: Any, limit: int = 120) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _relative_artifact_src(path: str, *, output_path: Path) -> str:
    artifact = Path(path)
    if not artifact.is_absolute():
        artifact = Path.cwd() / artifact
    try:
        return Path(os.path.relpath(artifact, output_path.parent)).as_posix()
    except ValueError:
        return artifact.as_uri()
