from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ComputerActionType = Literal[
    "screenshot",
    "click",
    "double_click",
    "scroll",
    "type",
    "wait",
    "move",
    "keypress",
    "drag",
    "final_answer",
]


class DragPoint(BaseModel):
    x: float
    y: float


class ComputerAction(BaseModel):
    """OpenAI computer-use-style action plus AgentLens final_answer."""

    type: ComputerActionType
    x: float | None = None
    y: float | None = None
    button: Literal["left", "right", "middle", "wheel", "back", "forward"] = "left"
    scroll_x: float = 0
    scroll_y: float = 0
    text: str | None = None
    keys: list[str] = Field(default_factory=list)
    path: list[DragPoint] = Field(default_factory=list)
    answer: str | None = None
    ms: int | None = None

    @model_validator(mode="after")
    def validate_required_fields(self) -> ComputerAction:
        if self.type in {"click", "double_click", "move", "scroll"}:
            if self.x is None or self.y is None:
                raise ValueError(f"action '{self.type}' requires x and y")
        if self.type == "type" and self.text is None:
            raise ValueError("action 'type' requires text")
        if self.type == "keypress" and not self.keys:
            raise ValueError("action 'keypress' requires keys")
        if self.type == "drag" and len(self.path) < 2:
            raise ValueError("action 'drag' requires at least two path points")
        if self.type == "final_answer" and self.answer is None:
            raise ValueError("action 'final_answer' requires answer")
        return self

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | str) -> ComputerAction:
        if isinstance(raw, str):
            return cls(type="final_answer", answer=raw)
        return cls.model_validate(raw)

