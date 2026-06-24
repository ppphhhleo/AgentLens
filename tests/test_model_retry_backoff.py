from __future__ import annotations

from agentlens.harnesses.screenshot_react_loop import (
    _model_retry_delay_seconds,
    _provider_retry_hint_seconds,
)


def test_provider_retry_hint_seconds_parses_ms_and_seconds() -> None:
    assert _provider_retry_hint_seconds("Please try again in 341ms.") == 0.341
    assert _provider_retry_hint_seconds("Please try again in 2.5 seconds.") == 2.5
    assert _provider_retry_hint_seconds("no hint") is None


def test_model_retry_delay_uses_exponential_without_hint() -> None:
    delay = _model_retry_delay_seconds(
        RuntimeError("temporary failure"),
        attempt=3,
        base_sleep_s=2.0,
        max_sleep_s=60.0,
    )

    assert delay == 8.0


def test_model_retry_delay_respects_provider_hint_and_cap() -> None:
    delay = _model_retry_delay_seconds(
        RuntimeError("Rate limit reached. Please try again in 50 seconds."),
        attempt=2,
        base_sleep_s=2.0,
        max_sleep_s=60.0,
    )

    assert delay == 60.0
