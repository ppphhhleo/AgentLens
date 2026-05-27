#!/usr/bin/env python3
"""AgentLens Human Study Server

A lightweight web server that provides a shareable link for user study
participants. Proxies target websites (TF Playground, DataVoyager) with
an injected JavaScript event recorder so every click, scroll, and
keystroke is captured as a trajectory event.

Usage:
    # Development / testing (localhost only)
    python human_study/server.py

    # Deployed study (accessible from outside)
    python human_study/server.py --host 0.0.0.0 --port 8080

Architecture:
    Participant Browser  →  This Server (proxy + recorder injection)
                         →  Target Website (TF Playground, DataVoyager)
                         ←  Proxied HTML + injected recorder.js
                         →  POST /api/events (recorded user interactions)
                         →  POST /api/submit (final answer)
                         →  trajectory.json saved in results/

Security notes:
    - TODO(security): For production deployment, add authentication/tokens
      for study sessions to prevent unauthorized access.
    - TODO(security): Add rate limiting on API endpoints.
    - Server listens on 127.0.0.1 by default (safe for testing).
      Use --host 0.0.0.0 only for study deployment behind a firewall/VPN.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs, unquote

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
RESULTS_DIR = ROOT_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Task registry ────────────────────────────────────────────────────
# Loaded from the experiment config at startup, or use these defaults.
DEFAULT_TASKS = [
    {
        "id": "tf_discretize_toggle",
        "goal": 'Find the "Discretize output" toggle in the TensorFlow Playground UI and click it. Then describe what visually changed in the output panel.',
        "start_url": "https://playground.tensorflow.org/",
        "expected_answer": None,
        "answer_validator": "url_contains:discretize=true",
    },
    {
        "id": "datavoyager_most_fuel_efficient",
        "goal": "What is the most fuel-efficient car in the dataset? Explore the data using the interface to find the answer.",
        "start_url": "https://vega.github.io/voyager2/",
        "expected_answer": "mazda glc",
        "answer_validator": "exact_match",
    },
    {
        "id": "datavoyager_europe_100hp_4cyl_count",
        "goal": "How many Europe cars have horsepower under 100 and 4 cylinders?",
        "start_url": "https://vega.github.io/voyager2/",
        "expected_answer": "34",
        "answer_validator": "exact_match",
    },
    {
        "id": "datavoyager_horsepower_range_by_origin",
        "goal": "Which origin's cars show the widest range of horsepower?",
        "start_url": "https://vega.github.io/voyager2/",
        "expected_answer": None,
        "answer_validator": "semantic",
    },
    {
        "id": "datavoyager_8_cylinder_characteristics",
        "goal": "What characteristics do cars with 8 cylinders have? Explore and describe.",
        "start_url": "https://vega.github.io/voyager2/",
        "expected_answer": None,
        "answer_validator": "semantic",
    },
    {
        "id": "tf_wrongly_classified_point",
        "goal": "Locate one example data point that is wrongly classified in the output plot.",
        "start_url": "https://playground.tensorflow.org/",
        "expected_answer": None,
        "answer_validator": "manual",
    },
]

TASKS: dict[str, dict] = {t["id"]: t for t in DEFAULT_TASKS}

# ── Active sessions ──────────────────────────────────────────────────
# Maps session_id -> session data (in-memory; persisted on submit)
SESSIONS: dict[str, dict] = {}

# ── HTTP client for proxying ─────────────────────────────────────────
HTTP_CLIENT = httpx.Client(
    follow_redirects=True,
    timeout=30.0,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    },
)


def _read_static(filename: str) -> str:
    """Read a static file from the static/ directory."""
    return (STATIC_DIR / filename).read_text(encoding="utf-8")


def _get_task(task_id: str) -> dict | None:
    return TASKS.get(task_id)


def _create_session(participant_id: str, task_id: str) -> str:
    """Create a new study session and return its ID."""
    session_id = str(uuid.uuid4())[:8]
    task = _get_task(task_id)
    if task is None:
        raise ValueError(f"Unknown task: {task_id}")
    SESSIONS[session_id] = {
        "session_id": session_id,
        "participant_id": participant_id,
        "task_id": task_id,
        "task": task,
        "events": [],
        "answer": None,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "submitted": False,
    }
    logger.info(
        "Session %s created: participant=%s task=%s",
        session_id, participant_id, task_id,
    )
    return session_id


def _proxy_and_inject(
    target_url: str, session_id: str, task_goal: str, server_origin: str,
) -> bytes:
    """Fetch target URL, inject recorder JS, return modified HTML.

    Instead of using <base href> (which causes cross-origin issues in
    Safari), we proxy ALL sub-resources through our server.  Every
    relative URL in the HTML is left as-is — they resolve relative to
    /study/<session_id>/, and our proxy handler serves them.
    """
    resp = HTTP_CLIENT.get(target_url)
    html = resp.text
    content_type = resp.headers.get("content-type", "")

    # Only inject into HTML pages
    if "text/html" not in content_type:
        return resp.content

    # Read the recorder JS
    recorder_js = _read_static("recorder.js")

    # Build the injection snippet
    # Security: task_goal is escaped for JS string inclusion
    escaped_goal = (
        task_goal
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "")
    )

    injection = f"""
<!-- AgentLens Study Recorder -->
<script>
window.__agentlens_session_id = '{session_id}';
window.__agentlens_task_goal = '{escaped_goal}';
window.__agentlens_api_base = '{server_origin}';
</script>
<script>{recorder_js}</script>
"""

    # Inject after <head> tag (or at the beginning if no <head>)
    if re.search(r"<head[^>]*>", html, re.IGNORECASE):
        html = re.sub(
            r"(<head[^>]*>)",
            r"\1" + injection,
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        html = injection + html

    return html.encode("utf-8")


def _get_target_base(session_id: str) -> str | None:
    """Get the target site base URL for a session (e.g. 'https://vega.github.io/voyager2/')."""
    session = SESSIONS.get(session_id)
    if not session:
        return None
    start_url = session["task"]["start_url"]
    parsed = urlparse(start_url)
    base_path = parsed.path
    if not base_path.endswith("/"):
        base_path = base_path.rsplit("/", 1)[0] + "/"
    return f"{parsed.scheme}://{parsed.netloc}{base_path}"


# Content-type mapping for common extensions
_EXT_CONTENT_TYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".ico": "image/x-icon",
    ".map": "application/json",
}


def _proxy_subresource(target_base: str, subpath: str) -> tuple[bytes, str]:
    """Fetch a sub-resource from the target site.

    Returns (content_bytes, content_type).
    """
    url = target_base + subpath
    try:
        resp = HTTP_CLIENT.get(url)
    except Exception as e:
        logger.warning("Proxy fetch failed: %s → %s", url, e)
        return b"", "text/plain"

    ct = resp.headers.get("content-type", "")
    if not ct:
        # Guess from extension
        ext = "." + subpath.rsplit(".", 1)[-1] if "." in subpath else ""
        ct = _EXT_CONTENT_TYPES.get(ext, "application/octet-stream")

    return resp.content, ct


class StudyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the study server."""

    def log_message(self, format, *args):
        logger.info("%s - %s", self.client_address[0], format % args)

    def _send_response(self, code: int, body: bytes, content_type: str = "text/html"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Allow cross-origin requests from the proxied page
        self.send_header("Access-Control-Allow-Origin", "*")
        # Security headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self._send_response(code, body, "application/json")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    # ── GET routes ────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Landing page
        if path == "/" or path == "":
            self._serve_landing()
            return

        # Start a study session
        if path == "/start":
            qs = parse_qs(parsed.query)
            participant_id = qs.get("pid", ["anonymous"])[0]
            task_id = qs.get("task", [None])[0]
            if not task_id or task_id not in TASKS:
                self._send_json(400, {"error": f"Invalid task_id: {task_id}"})
                return
            session_id = _create_session(participant_id, task_id)
            # Redirect to the study page
            redirect_url = f"/study/{session_id}/"
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.end_headers()
            return

        # Study page: /study/<session_id>/ or /study/<session_id>/<subpath>
        if path.startswith("/study/"):
            parts = path.split("/", 3)  # ['', 'study', session_id, subpath?]
            session_id = parts[2] if len(parts) > 2 else None

            if not session_id or session_id not in SESSIONS:
                self._send_json(404, {"error": "Session not found"})
                return

            # Subpath after /study/<session_id>/
            subpath = parts[3] if len(parts) > 3 else ""

            if subpath == "" or subpath == "/":
                # Main study page — proxy and inject recorder
                session = SESSIONS[session_id]
                task = session["task"]
                host = self.headers.get("Host", "127.0.0.1:8080")
                server_origin = f"http://{host}"
                html = _proxy_and_inject(
                    task["start_url"], session_id, task["goal"],
                    server_origin=server_origin,
                )
                self._send_response(200, html, "text/html; charset=utf-8")
            else:
                # Sub-resource (JS, CSS, template, image, etc.)
                # Proxy from the target site
                target_base = _get_target_base(session_id)
                if not target_base:
                    self._send_json(404, {"error": "Session not found"})
                    return
                content, ct = _proxy_subresource(target_base, subpath)
                self._send_response(200, content, ct)
            return

        # Static files
        if path.startswith("/static/"):
            filename = path.split("/static/")[-1]
            filepath = STATIC_DIR / filename
            if filepath.exists() and filepath.is_file():
                content = filepath.read_bytes()
                ct = "text/javascript" if filename.endswith(".js") else "text/css"
                self._send_response(200, content, ct)
            else:
                self._send_json(404, {"error": "File not found"})
            return

        # Admin results viewer
        if path == "/admin/results":
            self._serve_results()
            return

        # API: session info
        if path.startswith("/api/session/"):
            session_id = path.split("/")[-1]
            if session_id in SESSIONS:
                session = SESSIONS[session_id]
                self._send_json(200, {
                    "session_id": session_id,
                    "task_id": session["task_id"],
                    "goal": session["task"]["goal"],
                    "events_count": len(session["events"]),
                    "submitted": session["submitted"],
                })
            else:
                self._send_json(404, {"error": "Session not found"})
            return

        self._send_json(404, {"error": "Not found"})

    # ── POST routes ───────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Receive events batch
        if path == "/api/events":
            body = self._read_body()
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON"})
                return
            session_id = data.get("session_id")
            if not session_id or session_id not in SESSIONS:
                self._send_json(404, {"error": "Session not found"})
                return
            events = data.get("events", [])
            SESSIONS[session_id]["events"].extend(events)
            self._send_json(200, {
                "ok": True,
                "total_events": len(SESSIONS[session_id]["events"]),
            })
            return

        # Submit answer
        if path == "/api/submit":
            body = self._read_body()
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON"})
                return
            session_id = data.get("session_id")
            if not session_id or session_id not in SESSIONS:
                self._send_json(404, {"error": "Session not found"})
                return
            answer = data.get("answer", "")
            session = SESSIONS[session_id]
            session["answer"] = answer
            session["completed_at"] = datetime.now(UTC).isoformat()
            session["submitted"] = True

            # Save trajectory
            traj_path = _save_trajectory(session)
            logger.info(
                "Session %s submitted: participant=%s answer='%s' → %s",
                session_id,
                session["participant_id"],
                answer[:80],
                traj_path,
            )
            self._send_json(200, {
                "ok": True,
                "trajectory_path": str(traj_path),
            })
            return

        self._send_json(404, {"error": "Not found"})

    # ── Page renderers ────────────────────────────────────────────

    def _serve_landing(self):
        """Render the landing page with task list."""
        # Build task cards using safe DOM construction in JS
        tasks_json = json.dumps(list(TASKS.values()))

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgentLens — Human Study</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, sans-serif;
    background: #0a0a0f;
    color: #e0e0e8;
    min-height: 100vh;
}}
.hero {{
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    padding: 60px 40px 40px;
    text-align: center;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}}
.hero h1 {{
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #4af, #30d158);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 12px;
}}
.hero p {{ color: #888; font-size: 1rem; max-width: 600px; margin: 0 auto; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 40px 20px; }}
.participant-form {{
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 32px;
    display: flex;
    align-items: center;
    gap: 16px;
}}
.participant-form label {{
    font-weight: 600;
    font-size: 0.9rem;
    white-space: nowrap;
}}
.participant-form input {{
    flex: 1;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 10px 14px;
    color: #fff;
    font-size: 0.95rem;
    outline: none;
}}
.participant-form input:focus {{ border-color: #4af; }}
.task-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 16px; }}
.task-card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 24px;
    transition: all 0.2s;
    cursor: pointer;
}}
.task-card:hover {{
    border-color: #4af;
    background: rgba(74, 170, 255, 0.05);
    transform: translateY(-2px);
}}
.task-card h3 {{
    font-size: 0.95rem;
    color: #4af;
    margin-bottom: 8px;
    font-family: 'SF Mono', monospace;
}}
.task-card p {{
    font-size: 0.88rem;
    color: #aaa;
    line-height: 1.5;
    margin-bottom: 12px;
}}
.task-card .site-tag {{
    display: inline-block;
    background: rgba(48, 209, 88, 0.15);
    color: #30d158;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}}
.btn {{
    display: inline-block;
    padding: 10px 24px;
    background: linear-gradient(135deg, #0a84ff, #30d158);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    transition: opacity 0.2s;
    float: right;
}}
.btn:hover {{ opacity: 0.85; }}
</style>
</head>
<body>
<div class="hero">
    <h1>🔍 AgentLens Human Study</h1>
    <p>Complete browser tasks while your interactions are recorded. Your data helps us compare human and AI browsing strategies.</p>
</div>
<div class="container">
    <div class="participant-form">
        <label for="pid">UMN ID:</label>
        <input type="text" id="pid" placeholder="Enter your UMN ID" value="">
    </div>
    <h2 style="font-size:1.1rem; margin-bottom:20px; color:#ccc;">Tasks</h2>
    <div class="task-grid" id="task-grid"></div>
</div>
<script>
// Build task cards safely using DOM APIs (no innerHTML with user data)
const tasks = {tasks_json};
const grid = document.getElementById('task-grid');
tasks.forEach(task => {{
    const card = document.createElement('div');
    card.className = 'task-card';

    const h3 = document.createElement('h3');
    h3.textContent = task.id;
    card.appendChild(h3);

    const p = document.createElement('p');
    p.textContent = task.goal;
    card.appendChild(p);

    const tag = document.createElement('span');
    tag.className = 'site-tag';
    tag.textContent = task.start_url.includes('tensorflow') ? '🧠 TF Playground' : '📊 DataVoyager';
    card.appendChild(tag);

    const btn = document.createElement('a');
    btn.className = 'btn';
    btn.textContent = 'Start Task →';
    btn.addEventListener('click', (e) => {{
        e.preventDefault();
        const pid = document.getElementById('pid').value.trim() || 'anonymous';
        window.location.href = '/start?pid=' + encodeURIComponent(pid) + '&task=' + encodeURIComponent(task.id);
    }});
    card.appendChild(btn);

    card.addEventListener('click', (e) => {{
        if (e.target !== btn) btn.click();
    }});
    grid.appendChild(card);
}});
</script>
</body>
</html>"""
        self._send_response(200, html.encode("utf-8"))

    def _serve_results(self):
        """Render admin results page."""
        # Results are now in per-participant subdirectories:
        # results/<participant_id>/<task>_<session>.json
        result_files = sorted(RESULTS_DIR.glob("**/*.json"), reverse=True)
        rows_html = ""
        for f in result_files[:50]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                rows_html += (
                    f"<tr><td>{f.name}</td>"
                    f"<td>{data.get('participant_id', '?')}</td>"
                    f"<td>{data.get('task_id', '?')}</td>"
                    f"<td>{data.get('answer', '')[:60]}</td>"
                    f"<td>{len(data.get('events', []))}</td>"
                    f"<td>{data.get('started_at', '')[:19]}</td></tr>\n"
                )
            except Exception:
                continue

        # NOTE: rows_html is built from server-side JSON files we control,
        # not from user input, so this is safe from XSS.
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Study Results</title>
<style>
body {{ font-family: Inter, sans-serif; background: #0a0a0f; color: #e0e0e8; padding: 40px; }}
h1 {{ color: #4af; margin-bottom: 20px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.08); text-align: left; font-size: 0.85rem; }}
th {{ color: #888; font-weight: 600; }}
</style></head><body>
<h1>📊 Study Results ({len(result_files)} sessions)</h1>
<table>
<tr><th>File</th><th>Participant</th><th>Task</th><th>Answer</th><th>Events</th><th>Started</th></tr>
{rows_html}
</table></body></html>"""
        self._send_response(200, html.encode("utf-8"))


def _save_trajectory(session: dict) -> Path:
    """Convert session data to AgentLens-compatible trajectory and save."""
    trajectory = {
        "trajectory_id": session["session_id"],
        "experiment_id": "human_study",
        "run_id": f"human_{session['task_id']}_{session['participant_id']}",
        "seed": 0,
        "trial": 1,
        "model": {
            "id": "human",
            "provider": "local",
            "name": "human_study_web",
            "temperature": 0.0,
            "vision": True,
        },
        "task_id": session["task_id"],
        "task": session["task"],
        "participant_id": session["participant_id"],
        "started_at": session["started_at"],
        "completed_at": session["completed_at"],
        "answer": session["answer"],
        "events": session["events"],
        "metrics": {
            "success": None,
            "score": None,
            "duration_ms": _calc_duration(session),
            "steps": len(session["events"]),
            "source": "human_study_web",
        },
    }

    # Save under per-participant subdirectory (UMN x500 ID).
    # Structure: results/<participant_id>/<task_id>_<session_id>.json
    # This groups all results by participant for easier data gathering.
    participant_dir_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", session["participant_id"])
    participant_dir = RESULTS_DIR / participant_dir_name
    participant_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{session['task_id']}_{session['session_id']}.json"
    # Sanitize filename — only allow alphanumeric, underscore, hyphen, dot
    filename = re.sub(r"[^a-zA-Z0-9_\-.]", "_", filename)
    traj_path = participant_dir / filename
    traj_path.write_text(json.dumps(trajectory, indent=2), encoding="utf-8")
    return traj_path


def _calc_duration(session: dict) -> int | None:
    """Calculate duration in ms from session timestamps."""
    try:
        started = datetime.fromisoformat(session["started_at"])
        completed = datetime.fromisoformat(session["completed_at"])
        return int((completed - started).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description="AgentLens Human Study Server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to listen on. Use 0.0.0.0 for external access. Default: 127.0.0.1",
    )
    parser.add_argument("--port", type=int, default=8080, help="Port. Default: 8080")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to AgentLens experiment YAML to load tasks from.",
    )
    args = parser.parse_args()

    # Optionally load tasks from experiment config
    if args.config:
        try:
            import yaml
            with open(args.config, "r") as f:
                config = yaml.safe_load(f)
            for task in config.get("tasks", []):
                TASKS[task["id"]] = {
                    "id": task["id"],
                    "goal": task.get("goal", ""),
                    "start_url": task.get("start_url", ""),
                    "expected_answer": task.get("expected_answer"),
                    "answer_validator": task.get("answer_validator", "manual"),
                }
            logger.info("Loaded %d tasks from %s", len(TASKS), args.config)
        except Exception as e:
            logger.warning("Failed to load config %s: %s", args.config, e)

    server = HTTPServer((args.host, args.port), StudyHandler)
    logger.info(
        "AgentLens Human Study Server running at http://%s:%d/",
        args.host, args.port,
    )
    logger.info("Admin results: http://%s:%d/admin/results", args.host, args.port)
    logger.info("Results directory: %s", RESULTS_DIR)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
