from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK_DIR = REPO_ROOT / "tasks" / "gui_vs_cli"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a static browser for matched GUI-vs-CLI standard/grounded tasks."
    )
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TASK_DIR / "grounded_task_browser.html",
    )
    args = parser.parse_args()

    task_dir = args.task_dir
    standard = _load_by_id(task_dir / "tasks_standard.jsonl")
    grounded = _load_by_id(task_dir / "tasks_grounding.jsonl")
    pairs = _load_jsonl(task_dir / "task_pairs.jsonl")

    records = []
    for pair in pairs:
        task_id = pair["id"]
        std = standard[task_id]
        grd = grounded[task_id]
        records.append(
            {
                "id": task_id,
                "app": grd.get("app", ""),
                "standard_task": std.get("task", ""),
                "grounded_task": grd.get("task_grounding", ""),
                "base_task": grd.get("task", ""),
                "metadata": grd.get("metadata", {}),
                "cli_feasibility": grd.get("cli_feasibility", {}),
                "env_files": (grd.get("env") or {}).get("files", []),
                "verification": grd.get("verification", []),
                "standard_path": pair.get("standard_github_task_path", ""),
                "grounded_path": pair.get("grounded_github_task_path", ""),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_render(records), encoding="utf-8")
    print(args.output)
    return 0


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_by_id(path: Path) -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in _load_jsonl(path)}


def _render(records: list[dict[str, Any]]) -> str:
    app_counts = Counter(record["app"] for record in records)
    payload = json.dumps(records, ensure_ascii=False)
    app_options = "\n".join(
        f'<option value="{html.escape(app)}">{html.escape(app)} ({count})</option>'
        for app, count in sorted(app_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    summary_cards = "\n".join(
        f'<div class="card"><b>{html.escape(app)}</b><span>{count}</span></div>'
        for app, count in sorted(app_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>GUI-vs-CLI Grounded Task Browser</title>
  <style>
    :root {{
      --bg: #f7f7f4;
      --ink: #20231f;
      --muted: #6b7068;
      --line: #d9ded4;
      --panel: #ffffff;
      --standard: #276749;
      --grounded: #5b4b8a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 18px 24px 14px;
      background: rgba(247, 247, 244, 0.96);
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 12px; font-size: 22px; }}
    .toolbar {{
      display: grid;
      grid-template-columns: 240px 1fr auto;
      gap: 10px;
      align-items: center;
    }}
    input, select {{
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      font-size: 14px;
    }}
    main {{ padding: 18px 24px 32px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
      gap: 8px;
      margin-bottom: 18px;
    }}
    .card {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--muted);
    }}
    .card b {{ color: var(--ink); }}
    .task {{
      margin: 0 0 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      overflow: hidden;
    }}
    .task-head {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #fbfbf9;
    }}
    .task-title {{ font-weight: 700; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      height: 26px;
      padding: 0 9px;
      border-radius: 999px;
      background: #eef1eb;
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
    }}
    .cols {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0;
    }}
    .col {{
      padding: 14px;
      border-right: 1px solid var(--line);
    }}
    .col:last-child {{ border-right: 0; }}
    .label {{
      margin-bottom: 8px;
      font-weight: 700;
      font-size: 13px;
      color: var(--standard);
    }}
    .col.grounded .label {{ color: var(--grounded); }}
    .text {{
      white-space: pre-wrap;
      line-height: 1.45;
      font-size: 14px;
    }}
    details {{
      border-top: 1px solid var(--line);
      padding: 10px 14px;
    }}
    summary {{ cursor: pointer; color: var(--muted); }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #f3f4f0;
      padding: 10px;
      border-radius: 6px;
      font-size: 12px;
      line-height: 1.4;
    }}
    @media (max-width: 900px) {{
      .toolbar, .cols {{ grid-template-columns: 1fr; }}
      .col {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .col:last-child {{ border-bottom: 0; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>GUI-vs-CLI Grounded Task Browser</h1>
    <div class="toolbar">
      <select id="app">
        <option value="">All interfaces ({len(records)})</option>
        {app_options}
      </select>
      <input id="search" placeholder="Search task id, prompt text, CLI feasibility, verifier..." autocomplete="off">
      <span id="count" class="pill"></span>
    </div>
  </header>
  <main>
    <section class="summary">{summary_cards}</section>
    <section id="tasks"></section>
  </main>
  <script>
    const records = {payload};
    const app = document.getElementById("app");
    const search = document.getElementById("search");
    const count = document.getElementById("count");
    const tasks = document.getElementById("tasks");

    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }}[ch]));
    }}

    function blob(record) {{
      return JSON.stringify(record).toLowerCase();
    }}

    function render() {{
      const appValue = app.value;
      const q = search.value.trim().toLowerCase();
      const filtered = records.filter(record => {{
        if (appValue && record.app !== appValue) return false;
        if (q && !blob(record).includes(q)) return false;
        return true;
      }});
      count.textContent = `${{filtered.length}} shown`;
      tasks.innerHTML = filtered.map(record => `
        <article class="task">
          <div class="task-head">
            <div>
              <div class="task-title">${{esc(record.id)}}</div>
              <div class="meta">${{esc(record.app)}} · standard and grounded pair</div>
            </div>
            <span class="pill">${{esc(record.env_files.length)}} files · ${{esc(record.verification.length)}} checks</span>
          </div>
          <div class="cols">
            <div class="col">
              <div class="label">Standard Prompt</div>
              <div class="text">${{esc(record.standard_task)}}</div>
            </div>
            <div class="col grounded">
              <div class="label">Grounded Prompt</div>
              <div class="text">${{esc(record.grounded_task)}}</div>
            </div>
          </div>
          <details>
            <summary>Metadata, CLI feasibility, paths, files, verifier</summary>
            <pre>${{esc(JSON.stringify({{
              metadata: record.metadata,
              cli_feasibility: record.cli_feasibility,
              standard_path: record.standard_path,
              grounded_path: record.grounded_path,
              env_files: record.env_files,
              verification: record.verification
            }}, null, 2))}}</pre>
          </details>
        </article>
      `).join("");
    }}

    app.addEventListener("change", render);
    search.addEventListener("input", render);
    render();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
