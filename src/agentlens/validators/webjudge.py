"""WebJudge: LLM-as-judge validator for live-website agent trajectories.

Implements an OpenAI-style outcome judgment for tasks where the success
criterion is "did the agent visibly accomplish the goal" rather than a
DOM-state or string-match check. Inspired by the WebJudge work in
Online-Mind2Web (Xue et al., 2025).

Single-stage MVP: feeds the goal, the agent's final answer, the final
URL, and a sampled set of step screenshots to a vision-capable judge
model and asks for a strict-JSON {success, score, reason}.

Multi-stage WebJudge (key-point identification -> key-screenshot
identification -> outcome judgment) can layer on top later.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from agentlens.openai_provider import (
    build_openai_client,
    resolve_auth_mode,
    resolve_helper_model,
)

DEFAULT_JUDGE_MODEL = "gpt-4o"
DEFAULT_MAX_SCREENSHOTS = 6  # cap images to control token cost

JUDGE_SYSTEM_PROMPT = """You are WebJudge, an evaluator for autonomous web agents.

You will receive:
- The TASK the agent was asked to perform on a live website.
- The agent's FINAL ANSWER (may be empty).
- The FINAL URL the agent ended on.
- A sequence of SCREENSHOTS captured during the agent's execution.

Decide whether the agent SUCCESSFULLY completed the task.

Be strict but fair:
- "Success" means the task is meaningfully accomplished, not just attempted.
- Partial progress (e.g., navigated to right page but did not finish the
  required action) is NOT success.
- A confident-sounding answer that contradicts the screenshots is NOT success.
- If the agent stopped on the right page with the right state visible, count
  it as success even if the textual answer is short.

Respond with a single JSON object, NO markdown fences:
{
  "success": true | false,
  "score": <float in [0, 1]>,
  "reason": "<one or two sentence justification grounded in the screenshots>"
}
"""


@dataclass
class WebJudgeResult:
    success: bool
    score: float
    reason: str
    raw_response: str
    judge_model: str


def judge_trajectory(
    *,
    goal: str,
    final_answer: str | None,
    final_url: str | None,
    screenshot_paths: list[Path],
    judge_model: str | None = None,
    max_screenshots: int = DEFAULT_MAX_SCREENSHOTS,
) -> WebJudgeResult:
    """Score a finished trajectory using an LLM-as-judge.

    Returns a WebJudgeResult; never raises (errors are encoded in the result).
    """
    try:
        mode = resolve_auth_mode()
        if mode == "codex_oauth":
            judge_model = resolve_helper_model(judge_model, fallback_env="WEBJUDGE_MODEL")
        else:
            judge_model = judge_model or os.environ.get("WEBJUDGE_MODEL") or DEFAULT_JUDGE_MODEL
    except (ValueError, RuntimeError) as exc:
        return WebJudgeResult(
            success=False,
            score=0.0,
            reason=f"WebJudge configuration failed: {exc}",
            raw_response="",
            judge_model=judge_model or "(not configured)",
        )
    if mode == "api_key" and not os.environ.get("OPENAI_API_KEY"):
        return WebJudgeResult(
            success=False,
            score=0.0,
            reason="WebJudge skipped: OPENAI_API_KEY not set",
            raw_response="",
            judge_model=judge_model,
        )

    sampled = _sample_screenshots(screenshot_paths, max_screenshots)
    user_text = (
        f"TASK: {goal}\n"
        f"FINAL URL: {final_url or '(not captured)'}\n"
        f"FINAL ANSWER: {final_answer if final_answer is not None else '(no answer emitted)'}\n\n"
        f"SCREENSHOTS: {len(sampled)} key frames from the agent's run, in order."
    )
    content: list[dict] = [{"type": "text", "text": user_text}]
    for path in sampled:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _to_data_url(path)},
            }
        )

    client = build_openai_client(auth_mode=mode, model=judge_model)
    try:
        kwargs: dict = {
            "model": judge_model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
        }
        if judge_model.startswith(("gpt-5", "o1", "o3", "o4")):
            kwargs["max_completion_tokens"] = 400
        else:
            kwargs["max_tokens"] = 400
            kwargs["temperature"] = 0.0
        resp = client.chat.completions.create(**kwargs)
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - judge errors should not crash the run
        return WebJudgeResult(
            success=False,
            score=0.0,
            reason=f"WebJudge call failed: {type(exc).__name__}: {exc}",
            raw_response="",
            judge_model=judge_model,
        )

    try:
        decoder = json.JSONDecoder()
        data, _end = decoder.raw_decode(raw if not raw.startswith("```") else raw.strip("`").lstrip("json").strip())
    except json.JSONDecodeError as exc:
        return WebJudgeResult(
            success=False,
            score=0.0,
            reason=f"WebJudge returned non-JSON ({exc}): {raw[:160]!r}",
            raw_response=raw,
            judge_model=judge_model,
        )

    success = bool(data.get("success", False))
    score = float(data.get("score", 1.0 if success else 0.0))
    reason = str(data.get("reason", ""))
    return WebJudgeResult(
        success=success,
        score=score,
        reason=reason,
        raw_response=raw,
        judge_model=judge_model,
    )


def _sample_screenshots(paths: list[Path], cap: int) -> list[Path]:
    """Take up to `cap` screenshots: always include first and last, fill middle evenly."""
    if not paths:
        return []
    if len(paths) <= cap:
        return list(paths)
    if cap == 1:
        return [paths[-1]]
    # Always include first and last; sample evenly between.
    indices = [0]
    if cap > 2:
        step = (len(paths) - 1) / (cap - 1)
        indices.extend(round(i * step) for i in range(1, cap - 1))
    indices.append(len(paths) - 1)
    # Dedup while preserving order.
    seen: set[int] = set()
    chosen: list[Path] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            chosen.append(paths[idx])
    return chosen


def _to_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
