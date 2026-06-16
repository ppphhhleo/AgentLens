from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from agentlens.actions import ComputerAction


InterventionMode = Literal["off", "warn"]


@dataclass
class InterventionDecision:
    triggered: bool
    kind: str = "none"
    mode: InterventionMode = "off"
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class RepeatedActionIntervention:
    """Detect consecutive repeated action patterns.

    This starts as a warning-only monitor. It is intentionally simple and
    transparent: no model judge, no hidden task semantics, just action history.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        threshold: int = 5,
        mode: InterventionMode = "warn",
        signature: Literal["type", "target"] = "type",
        message: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.threshold = max(2, int(threshold))
        self.mode = mode
        self.signature = signature
        self.message = (
            message
            or "You seem to be repeating the same kind of action. Re-check the goal and try a different strategy."
        )
        self._signatures: list[tuple[Any, ...]] = []

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> RepeatedActionIntervention:
        config = config or {}
        repeat = config.get("repeated_action") or {}
        if not isinstance(repeat, dict):
            repeat = {}
        return cls(
            enabled=bool(config.get("enabled", False) and repeat.get("enabled", True)),
            threshold=int(repeat.get("threshold", 5)),
            mode=repeat.get("mode", "warn"),
            signature=repeat.get("signature", "type"),
            message=repeat.get("message"),
        )

    def observe(self, action: ComputerAction) -> InterventionDecision:
        if not self.enabled:
            return InterventionDecision(triggered=False)
        sig = self._signature(action)
        self._signatures.append(sig)
        if len(self._signatures) < self.threshold:
            return InterventionDecision(triggered=False)
        window = self._signatures[-self.threshold :]
        if len(set(window)) != 1:
            return InterventionDecision(triggered=False)
        return InterventionDecision(
            triggered=True,
            kind="repeated_action_loop",
            mode=self.mode,
            message=self.message,
            details={
                "threshold": self.threshold,
                "signature": self.signature,
                "action_signature": list(sig),
                "repeat_count": self.threshold,
            },
        )

    def _signature(self, action: ComputerAction) -> tuple[Any, ...]:
        if self.signature == "type":
            return (action.type,)
        if action.type == "drag":
            points = tuple((round(p.x / 25) * 25, round(p.y / 25) * 25) for p in action.path)
            return (action.type, points)
        target = (
            action.bid
            or action.selector
            or action.mark
            or (
                None
                if action.x is None or action.y is None
                else (round(action.x / 25) * 25, round(action.y / 25) * 25)
            )
        )
        payload = {
            "type": action.type,
            "target": target,
            "text": action.text,
            "keys": tuple(action.keys),
            "url": action.url,
            "query": action.query,
            "file_path": action.file_path,
        }
        return tuple(sorted(payload.items()))
