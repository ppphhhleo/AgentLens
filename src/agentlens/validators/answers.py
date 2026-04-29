from __future__ import annotations

from agentlens.schemas import TaskConfig


def validate_answer(
    answer: str | None,
    task: TaskConfig,
    final_url: str | None = None,
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

    if task.answer_validator == "semantic_pending":
        return None, None, "semantic validation pending"

    if task.answer_validator == "manual_pending":
        return None, None, "manual validation pending"

    return None, None, f"unsupported validator: {task.answer_validator}"

