from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    "goto",
    "back",
    "forward",
    "reload",
    "web_search",
    "run_python",
    "shell",
    "read_file",
    "write_file",
    "mcp_tool",
    "desktop_screenshot",
    "desktop_click",
    "desktop_double_click",
    "desktop_triple_click",
    "desktop_scroll",
    "desktop_move",
    "desktop_drag",
    "desktop_type",
    "desktop_keypress",
    "desktop_launch_app",
    "desktop_pyautogui",
    "desktop_shell",
    "desktop_wait",
    "final_answer",
]


class DragPoint(BaseModel):
    x: float
    y: float

    @classmethod
    def from_raw(cls, raw: Any) -> DragPoint:
        if isinstance(raw, DragPoint):
            return raw
        if isinstance(raw, dict):
            return cls(x=float(raw["x"]), y=float(raw["y"]))
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return cls(x=float(raw[0]), y=float(raw[1]))
        raise ValueError(f"unsupported drag point shape: {raw!r}")


class ComputerAction(BaseModel):
    """OpenAI computer-use-style action plus AgentLens additions.

    Compatibility notes:
    - scroll_x/scroll_y also accepted as camelCase scrollX/scrollY.
    - drag.path accepts either {"x": .., "y": ..} dicts or [x, y] arrays.
    - keys is dual-use: required for `keypress` (the keys to press), and
      optional held-modifier list on click/double_click/scroll/move/drag.
    - goto is AgentLens-only (not in OpenAI's computer-use spec).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    type: ComputerActionType
    x: float | None = None
    y: float | None = None
    button: Literal["left", "right", "middle", "wheel", "back", "forward"] = "left"
    scroll_x: float = Field(default=0, alias="scrollX")
    scroll_y: float = Field(default=0, alias="scrollY")
    text: str | None = None
    keys: list[str] = Field(default_factory=list)
    path: list[DragPoint] = Field(default_factory=list)
    answer: str | None = None
    ms: int | None = None
    url: str | None = None
    query: str | None = None
    code: str | None = None
    cmd: str | None = None
    app: str | None = None
    # NOTE: `path` (above) is the drag-coordinate path; do NOT reuse it for
    # filesystem paths. read_file / write_file use `file_path`.
    file_path: str | None = None
    content: str | None = None
    mcp_tool: str | None = None
    mcp_args: dict[str, Any] = Field(default_factory=dict)
    # Addressing modes (alternative to x,y for click/double_click/move/scroll
    # /drag). At validate time exactly one of (x+y) | bid | selector | mark
    # must be set for those action types.
    bid: str | None = None             # accessibility-tree element id
    selector: str | None = None        # raw CSS selector
    mark: str | None = None            # set-of-marks label (e.g. "A3")

    @field_validator("path", mode="before")
    @classmethod
    def _coerce_path(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [DragPoint.from_raw(point) for point in value]
        return value

    @model_validator(mode="after")
    def validate_required_fields(self) -> ComputerAction:
        # Addressing-mode targets: exactly one of (x+y) | bid | selector | mark
        if self.type in {"click", "double_click", "move", "scroll", "type"}:
            modes_set = sum(
                [
                    self.x is not None and self.y is not None,
                    self.bid is not None,
                    self.selector is not None,
                    self.mark is not None,
                ]
            )
            if modes_set == 0:
                if self.type != "type":
                    raise ValueError(
                        f"action '{self.type}' requires a target — set (x+y) OR bid OR selector OR mark"
                    )
            if modes_set > 1:
                raise ValueError(
                    f"action '{self.type}' has multiple targets set; choose ONE of (x+y) / bid / selector / mark"
                )
        if self.type == "type" and self.text is None:
            raise ValueError("action 'type' requires text")
        if self.type == "desktop_click" and (self.x is None or self.y is None):
            raise ValueError("action 'desktop_click' requires x and y")
        if self.type == "desktop_double_click" and (self.x is None or self.y is None):
            raise ValueError("action 'desktop_double_click' requires x and y")
        if self.type == "desktop_triple_click" and (self.x is None or self.y is None):
            raise ValueError("action 'desktop_triple_click' requires x and y")
        if self.type == "desktop_move" and (self.x is None or self.y is None):
            raise ValueError("action 'desktop_move' requires x and y")
        if self.type == "desktop_drag" and len(self.path) < 2:
            raise ValueError("action 'desktop_drag' requires at least two path points")
        if self.type == "desktop_type" and self.text is None:
            raise ValueError("action 'desktop_type' requires text")
        if self.type == "desktop_keypress" and not self.keys:
            raise ValueError("action 'desktop_keypress' requires keys")
        if self.type == "desktop_launch_app" and not self.app:
            raise ValueError("action 'desktop_launch_app' requires app")
        if self.type == "desktop_pyautogui" and not self.code:
            raise ValueError("action 'desktop_pyautogui' requires code")
        if self.type == "keypress" and not self.keys:
            raise ValueError("action 'keypress' requires keys")
        if self.type == "drag" and len(self.path) < 2:
            raise ValueError("action 'drag' requires at least two path points")
        if self.type == "final_answer" and self.answer is None:
            raise ValueError("action 'final_answer' requires answer")
        if self.type == "goto" and not self.url:
            raise ValueError("action 'goto' requires url")
        if self.type == "web_search" and not self.query:
            raise ValueError("action 'web_search' requires query")
        if self.type == "run_python" and not self.code:
            raise ValueError("action 'run_python' requires code")
        if self.type == "shell" and not self.cmd:
            raise ValueError("action 'shell' requires cmd")
        if self.type == "desktop_shell" and not self.cmd:
            raise ValueError("action 'desktop_shell' requires cmd")
        if self.type == "read_file" and not self.file_path:
            raise ValueError("action 'read_file' requires file_path")
        if self.type == "write_file":
            if not self.file_path:
                raise ValueError("action 'write_file' requires file_path")
            if self.content is None:
                raise ValueError("action 'write_file' requires content")
        if self.type == "mcp_tool" and not self.mcp_tool:
            raise ValueError("action 'mcp_tool' requires mcp_tool")
        return self

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | str) -> ComputerAction:
        if isinstance(raw, str):
            return cls(type="final_answer", answer=raw)
        return cls.model_validate(raw)
