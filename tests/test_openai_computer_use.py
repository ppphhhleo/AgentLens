from __future__ import annotations

from types import SimpleNamespace

from agentlens.models.openai_computer_use import _map_computer_action, _parse_response


def test_openai_computer_action_maps_click_to_desktop_click() -> None:
    action = _map_computer_action(
        {"type": "click", "args": {"x": 110, "y": 220, "button": "left"}}
    )

    assert action is not None
    assert action.type == "desktop_click"
    assert action.x == 110
    assert action.y == 220


def test_openai_computer_action_maps_batched_desktop_actions() -> None:
    drag = _map_computer_action(
        {
            "type": "drag",
            "args": {"path": [{"x": 10, "y": 20}, {"x": 80, "y": 120}]},
        }
    )
    scroll = _map_computer_action(
        {"type": "scroll", "args": {"x": 200, "y": 300, "scroll_y": 500}}
    )

    assert drag is not None
    assert drag.type == "desktop_drag"
    assert [(point.x, point.y) for point in drag.path] == [(10, 20), (80, 120)]
    assert scroll is not None
    assert scroll.type == "desktop_scroll"
    assert scroll.scroll_y == 500


def test_openai_computer_response_parser_preserves_raw_call_actions() -> None:
    response = SimpleNamespace(
        id="resp_123",
        output=[
            SimpleNamespace(type="reasoning", summary=[SimpleNamespace(text="Need inspect chart")]),
            SimpleNamespace(
                type="computer_call",
                call_id="call_123",
                pending_safety_checks=[],
                actions=[
                    {"type": "move", "x": 10, "y": 20},
                    {"type": "click", "x": 10, "y": 20},
                ],
            ),
        ],
    )

    parsed = _parse_response(response)

    assert parsed.reasoning_text == "Need inspect chart"
    assert [action["type"] for action in parsed.computer_actions] == ["move", "click"]
    assert parsed.pending_input_items[0]["type"] == "computer_call_output"
    assert parsed.pending_input_items[0]["call_id"] == "call_123"
