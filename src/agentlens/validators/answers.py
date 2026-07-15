from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from agentlens.schemas import TaskConfig


def validate_answer(
    answer: str | None,
    task: TaskConfig,
    final_url: str | None = None,
    screenshot_paths: list[Path] | None = None,
) -> tuple[bool | None, float | None, str]:
    """Validate a final answer (and optional final UI state) against task metadata."""
    if task.answer_validator == "url_contains":
        if task.expected_answer is None:
            return None, None, "url_contains needs expected_answer"
        if final_url is None:
            return False, 0.0, "no final url captured"
        success = task.expected_answer.casefold() in final_url.casefold()
        return (
            success,
            1.0 if success else 0.0,
            f"url contains {task.expected_answer!r}" if success else f"final url {final_url!r} missing {task.expected_answer!r}",
        )

    if task.answer_validator == "webjudge":
        # LLM-as-judge: needs screenshots + goal. Final answer optional.
        from agentlens.validators.webjudge import judge_trajectory

        result = judge_trajectory(
            goal=task.goal or "",
            final_answer=answer,
            final_url=final_url,
            screenshot_paths=list(screenshot_paths or []),
            judge_model=task.extra.get("judge_model") if task.extra else None,
            rubric=task.extra.get("judge_rubric") if task.extra else None,
            max_screenshots=int(task.extra.get("judge_max_screenshots", 6))
            if task.extra
            else 6,
        )
        msg = (
            f"WebJudge({result.judge_model}) success={result.success} "
            f"score={result.score:.2f}: {result.reason}"
        )
        return result.success, result.score, msg

    if task.answer_validator == "semantic_pending":
        return None, None, "semantic validation pending"

    if task.answer_validator == "manual_pending":
        return None, None, "manual validation pending"

    if answer is None:
        return False, 0.0, "missing final answer"

    if task.expected_answer is None or task.answer_validator is None:
        return None, None, "no answer validator configured"

    normalized_answer = answer.strip().casefold()
    expected = task.expected_answer.strip().casefold()

    if task.answer_validator == "exact":
        success = normalized_answer == expected
        return success, 1.0 if success else 0.0, "exact match" if success else "exact mismatch"

    if task.answer_validator == "contains":
        success = expected in normalized_answer
        return success, 1.0 if success else 0.0, "contains match" if success else "contains mismatch"

    if task.answer_validator == "number_exact":
        expected_number = _to_decimal(expected)
        answer_numbers = [_to_decimal(match) for match in _NUMBER_RE.findall(normalized_answer)]
        answer_numbers = [number for number in answer_numbers if number is not None]
        success = expected_number is not None and expected_number in answer_numbers
        return (
            success,
            1.0 if success else 0.0,
            "number exact match" if success else "number exact mismatch",
        )

    return None, None, f"unsupported validator: {task.answer_validator}"


_NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")


def _to_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None
