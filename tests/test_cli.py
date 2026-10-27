import runpy
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import beamflix
from beamflix import cli
from beamflix.chromecast import REMOTE_KEYS, WIRELESS_DEBUGGING_PATH
from beamflix.errors import BeamflixError, ConnectionFailed


class FakeDevice:
    def __init__(self, serial="192.168.1.14:39667", calls=None):
        self.serial = serial
        self.calls = calls if calls is not None else []
        self.press = MagicMock(side_effect=lambda k: self.calls.append(("press", k)))
        self.clean = MagicMock(side_effect=lambda: self.calls.append(("clean",)))
        self.reboot = MagicMock(side_effect=lambda: self.calls.append(("reboot",)))
        self.launch = MagicMock(return_value="Starting: Intent { ... }")


@pytest.fixture
def device():
    return FakeDevice()


@pytest.fixture
def mocks(monkeypatch, device):
    """Patch every external boundary so nothing real (adb, network) is touched."""
    m = SimpleNamespace(
        connect=MagicMock(return_value=device),
        pair=MagicMock(),
        search=MagicMock(),
        choose=MagicMock(),
        select=MagicMock(return_value=False),
    )
    monkeypatch.setattr("beamflix.chromecast.connect", m.connect)
    monkeypatch.setattr("beamflix.pairing.pair", m.pair)
    monkeypatch.setattr("beamflix.justwatch.search", m.search)
    monkeypatch.setattr("beamflix.providers.choose", m.choose)
    monkeypatch.setattr("beamflix.profiles.select", m.select)
    monkeypatch.setattr(cli, "PROFILES", {"Disney Plus": "dandi"})
    return m


def set_title(mocks, provider="Netflix"):
    mocks.search.return_value = SimpleNamespace(name="The Bear", year=2022, offers=[])
    mocks.choose.return_value = SimpleNamespace(
        provider=provider, package="com.pkg", deeplink="intent://x"
    )


# ---- argument parsing: command vs title ----


@pytest.mark.parametrize(
    "word", ["play", "pause", "toggle", "startup", "shutdown", "clean", "restart"]
)
def test_single_command_word_runs_remote(mocks, monkeypatch, word):
    remote = MagicMock()
    monkeypatch.setattr(cli, "remote", remote)
    cli.main([word])
    remote.assert_called_once_with(word)
    mocks.search.assert_not_called()


def test_command_word_is_case_insensitive(mocks, monkeypatch):
    remote = MagicMock()
    monkeypatch.setattr(cli, "remote", remote)
    cli.main(["TOGGLE"])
    remote.assert_called_once_with("toggle")


def test_connect_command_runs_pair_and_connect(mocks, monkeypatch):
    pc = MagicMock()
    monkeypatch.setattr(cli, "pair_and_connect", pc)
    cli.main(["Connect"])
    pc.assert_called_once_with()


@pytest.mark.parametrize(
    "words, query",
    [
        (["play", "something"], "play something"),
        (["the", "bear"], "the bear"),
        (["Inception"], "Inception"),
        (["connect", "four"], "connect four"),
    ],
)
def test_other_word_combinations_are_title_searches(monkeypatch, words, query):
    play, remote = MagicMock(), MagicMock()
    monkeypatch.setattr(cli, "play", play)
    monkeypatch.setattr(cli, "remote", remote)
    cli.main(words)
    play.assert_called_once_with(query)
    remote.assert_not_called()


def test_no_words_exits_with_argparse_error_code_2(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_main_without_argv_reads_sys_argv(monkeypatch):
    play = MagicMock()
    monkeypatch.setattr(cli, "play", play)
    monkeypatch.setattr(sys, "argv", ["beamflix", "the", "bear"])
    cli.main()
    play.assert_called_once_with("the bear")


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in [
        "connect",
        "play",
        "pause",
        "toggle",
        "startup",
        "shutdown",
        "clean",
        "restart",
    ]:
        assert command in out


def test_commands_list_matches_readme():
    assert set(cli.COMMANDS) == {
        "connect",
        "play",
        "pause",
        "toggle",
        "startup",
        "shutdown",
        "clean",
        "restart",
    }


# ---- error handling in main ----


def test_beamflix_error_exits_with_message(monkeypatch):
    monkeypatch.setattr(cli, "play", MagicMock(side_effect=BeamflixError("boom")))
    with pytest.raises(SystemExit) as exc:
        cli.main(["x"])
    assert exc.value.code == "boom"


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, EOFError])
def test_interrupt_prints_message_and_exits_130(monkeypatch, capsys, exc_type):
    monkeypatch.setattr(cli, "play", MagicMock(side_effect=exc_type()))
    with pytest.raises(SystemExit) as exc:
        cli.main(["x"])
    assert exc.value.code == 130
    captured = capsys.readouterr()
    assert "Interrupted" in captured.err
    assert "Interrupted" not in captured.out


# ---- play ----


def test_play_without_results_raises_no_results(mocks):
    mocks.search.return_value = None
    with pytest.raises(BeamflixError, match="No results for 'the bear'"):
        cli.play("the bear")
    mocks.choose.assert_not_called()
    mocks.connect.assert_not_called()


def test_play_through_main_reports_no_results(mocks):
    mocks.search.return_value = None
    with pytest.raises(SystemExit) as exc:
        cli.main(["nothing", "here"])
    assert exc.value.code == "No results for 'nothing here'"


def test_play_launches_package_and_deeplink_and_prints_progress(mocks, device, capsys):
    set_title(mocks, "Netflix")
    cli.play("the bear")
    mocks.search.assert_called_once_with("the bear")
    mocks.choose.assert_called_once_with(mocks.search.return_value)
    device.launch.assert_called_once_with("com.pkg", "intent://x")
    out = capsys.readouterr().out
    assert "Found: The Bear (2022)" in out
    assert "Opening on Netflix: intent://x" in out
    assert "Connected to 192.168.1.14:39667" in out
    assert "Starting: Intent { ... }" in out


def test_play_without_configured_profile_does_not_select(mocks, capsys):
    set_title(mocks, "Netflix")
    cli.play("the bear")
    mocks.select.assert_not_called()
    assert "Selected profile" not in capsys.readouterr().out


def test_play_selects_configured_profile_and_reports_it(mocks, device, capsys):
    set_title(mocks, "Disney Plus")
    mocks.select.return_value = True
    cli.play("x")
    mocks.select.assert_called_once_with(device, "com.pkg", "dandi")
    assert "Selected profile: dandi" in capsys.readouterr().out


def test_play_does_not_report_profile_when_selection_fails(mocks, capsys):
    set_title(mocks, "Disney Plus")
    mocks.select.return_value = False
    cli.play("x")
    mocks.select.assert_called_once()
    assert "Selected profile" not in capsys.readouterr().out


def test_play_selects_profile_only_after_launch(mocks, device):
    set_title(mocks, "Disney Plus")
    order = []
    device.launch.side_effect = lambda *a: order.append("launch") or ""
    mocks.select.side_effect = lambda *a: order.append("select") or True
    cli.play("x")
    assert order == ["launch", "select"]


# ---- remote ----


@pytest.mark.parametrize("command", list(REMOTE_KEYS))
def test_remote_key_commands_press_mapped_keycode(mocks, device, capsys, command):
    cli.remote(command)
    device.press.assert_called_once_with(REMOTE_KEYS[command])
    device.clean.assert_not_called()
    device.reboot.assert_not_called()
    out = capsys.readouterr().out
    assert f"Sent {command} to {device.serial}" in out
    assert WIRELESS_DEBUGGING_PATH not in out


def test_remote_clean_calls_clean_only(mocks, device, capsys):
    cli.remote("clean")
    device.clean.assert_called_once_with()
    device.press.assert_not_called()
    device.reboot.assert_not_called()
    out = capsys.readouterr().out
    assert f"Sent clean to {device.serial}" in out
    assert "rebooting" not in out


def test_remote_restart_cleans_then_reboots_and_prints_reminder(mocks, device, capsys):
    cli.remote("restart")
    assert device.calls == [("clean",), ("reboot",)]
    device.press.assert_not_called()
    out = capsys.readouterr().out
    assert f"Sent restart to {device.serial}" in out
    assert "enable wireless debugging again" in out
    assert WIRELESS_DEBUGGING_PATH in out


# ---- connect() helper ----


def test_connect_returns_device_without_pairing(mocks, device, capsys):
    assert cli.connect() is device
    mocks.pair.assert_not_called()
    assert "Connecting to the Chromecast..." in capsys.readouterr().out


def test_connect_pairs_and_retries_on_connection_failed(mocks, device):
    mocks.connect.side_effect = [ConnectionFailed("refused"), device]
    assert cli.connect() is device
    mocks.pair.assert_called_once_with()
    assert mocks.connect.call_count == 2


def test_connect_propagates_plain_beamflix_error_without_pairing(mocks):
    mocks.connect.side_effect = BeamflixError("wireless debugging looks disabled")
    with pytest.raises(BeamflixError, match="looks disabled"):
        cli.connect()
    mocks.pair.assert_not_called()


def test_connect_propagates_failure_after_pairing(mocks):
    mocks.connect.side_effect = ConnectionFailed("still refused")
    with pytest.raises(ConnectionFailed):
        cli.connect()
    mocks.pair.assert_called_once()
    assert mocks.connect.call_count == 2


def test_remote_command_does_not_pair_on_plain_error(mocks):
    mocks.connect.side_effect = BeamflixError("nope")
    with pytest.raises(SystemExit) as exc:
        cli.main(["toggle"])
    assert exc.value.code == "nope"
    mocks.pair.assert_not_called()


# ---- connect command (pair_and_connect) ----


def test_connect_command_connects_and_prints_serial(mocks, device, capsys):
    cli.main(["connect"])
    mocks.pair.assert_not_called()
    out = capsys.readouterr().out
    assert "Connecting to the Chromecast..." in out
    assert "Connected to 192.168.1.14:39667" in out


@pytest.mark.parametrize(
    "error",
    [
        ConnectionFailed("refused"),
        BeamflixError("Wireless debugging looks disabled"),
    ],
)
def test_connect_command_pairs_then_reconnects_on_any_beamflix_error(
    mocks, device, capsys, error
):
    mocks.connect.side_effect = [error, device]
    cli.main(["connect"])
    mocks.pair.assert_called_once_with()
    assert mocks.connect.call_count == 2
    assert "Connected to 192.168.1.14:39667" in capsys.readouterr().out


def test_connect_command_fails_if_second_connect_fails(mocks):
    mocks.connect.side_effect = [BeamflixError("a"), BeamflixError("b")]
    with pytest.raises(SystemExit) as exc:
        cli.main(["connect"])
    assert exc.value.code == "b"


# ---- package wiring ----


def test_package_exports_main():
    assert beamflix.main is cli.main
    assert beamflix.__all__ == ["main"]


def test_python_dash_m_runs_main(monkeypatch):
    main = MagicMock()
    monkeypatch.setattr("beamflix.cli.main", main)
    runpy.run_module("beamflix.__main__", run_name="__main__")
    main.assert_called_once_with()


def test_module_execution_never_invokes_real_adb(monkeypatch):
    # Safety net: the runpy test above must not spawn any subprocess.
    spawn = MagicMock(side_effect=AssertionError("subprocess used"))
    monkeypatch.setattr(subprocess, "run", spawn)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr("beamflix.cli.main", MagicMock())
    runpy.run_module("beamflix.__main__", run_name="__main__")
    spawn.assert_not_called()
