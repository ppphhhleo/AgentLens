"""ARB Judge: 4-dimensional LLM-as-judge validator for agent trajectories.

Evaluates trajectories across the four dimensions defined by the
Agent Reward Bench (ARB) framework:
  1. Success (binary)
  2. Side Effects (binary)
  3. Optimality (1-4 Likert)
  4. Looping (binary)

Reuses ARB's system prompts and XML-tag parsing to maintain evaluation
parity with the original agent-reward-bench implementation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ARBJudgeResult:
    success: bool | None
    score: float | None
    arb_success: str | None
    arb_side_effect: str | None
    arb_optimality: int | None
    arb_looping: str | None
    reasoning: str | None
    raw_response: str
    judge_model: str
    cost_usd: float = 0.0


def compute_composite_score(
    arb_success: str | None,
    arb_side_effect: str | None,
    arb_optimality: int | None,
    arb_looping: str | None,
) -> float | None:
    """Compute a [0, 1] composite score from the four ARB dimensions.

    Weights: success=0.4, optimality=0.3, no_side_effect=0.15, no_looping=0.15
    """
    if arb_success is None:
        return None

    success_val = 1.0 if arb_success == "Successful" else 0.0

    if arb_optimality is not None and isinstance(arb_optimality, int):
        optimality_norm = (arb_optimality - 1) / 3.0
    else:
        optimality_norm = 0.0

    no_side_effect = 1.0 if arb_side_effect == "No" else 0.0
    no_looping = 1.0 if arb_looping == "No" else 0.0

    return (
        success_val * 0.4
        + optimality_norm * 0.3
        + no_side_effect * 0.15
        + no_looping * 0.15
    )


def _parse_optimality(raw: str | None) -> int | None:
    if raw is None:
        return None
    for digit in ("1", "2", "3", "4"):
        if digit in raw:
            return int(digit)
    return None


def judge_trajectory_arb(
    *,
    goal: str,
    steps: list[dict[str, str]],
    last_screenshot_b64: str | None = None,
    last_axtree: str | None = None,
    judge_model: str = "gpt-4o-mini-2024-07-18",
    judge_provider: str = "openai",
    use_screenshot: bool = True,
    use_axtree: bool = True,
    invert_system_prompt: bool = False,
    temperature: float = 0.0,
    max_completion_tokens: int = 1024,
) -> ARBJudgeResult:
    """Run the ARB 4-dimensional LLM judge on a trajectory."""
    from agent_reward_bench.judge import (
        format_chat_messages_for_judge,
        format_content_for_image,
        format_steps,
        parse_judgment,
    )
    from agent_reward_bench.judge.defaults import (
        ACTION_TEMPLATE,
        AXTREE_TEMPLATE,
        FINAL_MSG,
        GOAL_TEMPLATE,
        INVERTED_SYSTEM_PROMPT,
        SYSTEM_PROMPT,
    )

    sys_prompt = INVERTED_SYSTEM_PROMPT if invert_system_prompt else SYSTEM_PROMPT
    goal_msg = GOAL_TEMPLATE.format(goal=goal)
    action_msg = ACTION_TEMPLATE.format(steps=format_steps(steps))

    axtree_msg = None
    if use_axtree and last_axtree:
        axtree_msg = AXTREE_TEMPLATE.format(axtree=last_axtree)

    img_msg_content: list[dict] = []
    if use_screenshot and last_screenshot_b64:
        img_msg_content = format_content_for_image(last_screenshot_b64)

    chat_messages = format_chat_messages_for_judge(
        sys_prompt=sys_prompt,
        goal_msg=goal_msg,
        action_msg=action_msg,
        axtree_msg=axtree_msg,
        img_msg_content=img_msg_content,
        final_msg=FINAL_MSG,
    )

    api_key, base_url = _resolve_provider(judge_provider)
    if not api_key:
        return ARBJudgeResult(
            success=None,
            score=None,
            arb_success=None,
            arb_side_effect=None,
            arb_optimality=None,
            arb_looping=None,
            reasoning="ARB Judge skipped: API key not set",
            raw_response="",
            judge_model=judge_model,
        )

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=judge_model,
            messages=chat_messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            seed=0,
        )
        raw = response.choices[0].message.content or ""
        usage = response.usage
        cost = _estimate_cost(judge_model, usage) if usage else 0.0
    except Exception as exc:
        return ARBJudgeResult(
            success=None,
            score=None,
            arb_success=None,
            arb_side_effect=None,
            arb_optimality=None,
            arb_looping=None,
            reasoning=f"ARB Judge call failed: {type(exc).__name__}: {exc}",
            raw_response="",
            judge_model=judge_model,
        )

    judgment = parse_judgment(raw)

    arb_success = judgment.get("trajectory_success")
    arb_side_effect = judgment.get("trajectory_side_effect")
    arb_optimality_raw = judgment.get("trajectory_optimality")
    arb_looping = judgment.get("trajectory_looping")
    arb_optimality = _parse_optimality(arb_optimality_raw)

    success = arb_success == "Successful" if arb_success else None
    score = compute_composite_score(arb_success, arb_side_effect, arb_optimality, arb_looping)

    return ARBJudgeResult(
        success=success,
        score=score,
        arb_success=arb_success,
        arb_side_effect=arb_side_effect,
        arb_optimality=arb_optimality,
        arb_looping=arb_looping,
        reasoning=judgment.get("reasoning"),
        raw_response=raw,
        judge_model=judge_model,
        cost_usd=cost,
    )


def _resolve_provider(provider: str) -> tuple[str | None, str | None]:
    if provider == "openai":
        return os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_BASE_URL")
    elif provider == "openrouter":
        return os.environ.get("OPENROUTER_API_KEY"), (
            os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
        )
    elif provider == "vllm":
        return os.environ.get("VLLM_API_KEY", "EMPTY"), os.environ.get("VLLM_BASE_URL")
    else:
        return os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_BASE_URL")


def _estimate_cost(model: str, usage) -> float:
    """Rough cost estimate based on model pricing."""
    pricing = {
        "gpt-4o-mini-2024-07-18": (0.15, 0.60),
        "gpt-4o-2024-11-20": (2.50, 10.00),
    }
    input_rate, output_rate = pricing.get(model, (0.15, 0.60))
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
