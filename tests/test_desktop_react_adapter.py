from types import SimpleNamespace

from agentlens.adapters import desktop_react


class _FakeSandbox:
    def __init__(self, results: list[SimpleNamespace]) -> None:
        self.results = iter(results)
        self.commands: list[tuple[str, int]] = []

    def shell(self, command: str, *, timeout_sec: int) -> SimpleNamespace:
        self.commands.append((command, timeout_sec))
        return next(self.results)


def test_browser_target_check_uses_cdp_and_expected_host() -> None:
    command = desktop_react._browser_target_check_command(
        "https://vega.github.io/voyager2/"
    )

    assert "127.0.0.1:9222/json/list" in command
    assert "vega.github.io" in command
    assert "chrome-error://" in command


def test_desktop_setup_commands_run_as_desktop_user() -> None:
    maximize = desktop_react._maximize_active_window_command()
    navigate = desktop_react._force_start_url_command(
        "https://vega.github.io/voyager2/"
    )

    assert "runuser -u gem" in maximize
    assert "xdotool search --onlyvisible" in maximize
    assert "wmctrl" in maximize
    assert "runuser -u gem" in navigate
    assert "127.0.0.1:9222" in navigate
    assert "/json/new?" in navigate
    assert "/json/activate/" in navigate
    assert "windowactivate --sync" in navigate
    assert "https://vega.github.io/voyager2/" in navigate


def test_wait_for_browser_ready_requires_two_stable_matches(monkeypatch) -> None:
    sandbox = _FakeSandbox(
        [
            SimpleNamespace(ok=True, output="https://vega.github.io/voyager2/"),
            SimpleNamespace(ok=True, output="https://vega.github.io/voyager2/"),
        ]
    )
    monkeypatch.setattr(desktop_react.time, "sleep", lambda _seconds: None)

    ready, observed_url = desktop_react._wait_for_browser_ready(
        sandbox,
        "https://vega.github.io/voyager2/",
        timeout_s=5,
    )

    assert ready is True
    assert observed_url == "https://vega.github.io/voyager2/"
    assert len(sandbox.commands) == 2


def test_wait_for_browser_ready_rejects_wrong_host(monkeypatch) -> None:
    sandbox = _FakeSandbox(
        [SimpleNamespace(ok=False, output="https://example.com/")] * 3
    )
    times = iter([0.0, 0.0, 0.5, 1.0, 1.5, 2.0])
    monkeypatch.setattr(desktop_react.time, "monotonic", lambda: next(times, 2.0))
    monkeypatch.setattr(desktop_react.time, "sleep", lambda _seconds: None)

    ready, observed_url = desktop_react._wait_for_browser_ready(
        sandbox,
        "https://vega.github.io/voyager2/",
        timeout_s=1,
    )

    assert ready is False
    assert observed_url == "https://example.com/"
