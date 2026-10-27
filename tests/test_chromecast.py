"""Tests for beamflix.chromecast."""

import xml.etree.ElementTree as ET

import pytest

from beamflix import chromecast
from beamflix.chromecast import REMOTE_KEYS, Chromecast
from beamflix.errors import BeamflixError, ConnectionFailed

SERIAL = "192.168.1.50:5555"


@pytest.fixture
def calls(monkeypatch):
    """Record every adb.run call; returns the list of (args, timeout)."""
    recorded = []

    def fake_run(*args, timeout=15):
        recorded.append((args, timeout))
        return "out"

    monkeypatch.setattr(chromecast.adb, "run", fake_run)
    return recorded


@pytest.fixture
def cast():
    return Chromecast(SERIAL)


def shell_commands(calls):
    return [a[3] for a, _ in calls]


def test_remote_keys_map_commands_to_documented_keycodes():
    assert REMOTE_KEYS == {
        "play": "KEYCODE_MEDIA_PLAY",
        "pause": "KEYCODE_MEDIA_PAUSE",
        "toggle": "KEYCODE_MEDIA_PLAY_PAUSE",
        "startup": "KEYCODE_WAKEUP",
        "shutdown": "KEYCODE_SLEEP",
    }


def test_shell_targets_the_serial_and_returns_output(cast, calls):
    assert cast.shell("ls", timeout=3) == "out"
    assert calls == [(("-s", SERIAL, "shell", "ls"), 3)]


def test_shell_default_timeout(cast, calls):
    cast.shell("ls")
    assert calls[0][1] == 15


def test_press_sends_keyevent(cast, calls):
    cast.press("KEYCODE_HOME")
    assert calls[0][0] == ("-s", SERIAL, "shell", "input keyevent KEYCODE_HOME")


def test_wake_presses_wakeup(cast, calls):
    cast.wake()
    assert shell_commands(calls) == ["input keyevent KEYCODE_WAKEUP"]


def test_stop_app_force_stops_package(cast, calls):
    cast.stop_app("com.netflix.ninja")
    assert shell_commands(calls) == ["am force-stop com.netflix.ninja"]


def test_open_deeplink_starts_quoted_uri_and_returns_output(cast, calls):
    assert cast.open_deeplink("intent://x#Intent;end") == "out"
    assert shell_commands(calls) == ["am start 'intent://x#Intent;end'"]


def test_launch_wakes_then_force_stops_then_opens_link(cast, calls):
    result = cast.launch("com.pkg", "intent://link")
    assert result == "out"
    assert shell_commands(calls) == [
        "input keyevent KEYCODE_WAKEUP",
        "am force-stop com.pkg",
        "am start 'intent://link'",
    ]
    assert all(a[:2] == ("-s", SERIAL) for a, _ in calls)


def test_clean_stops_third_party_apps_trims_caches_and_goes_home(cast, calls):
    cast.clean()
    cmds = shell_commands(calls)
    assert len(cmds) == 3
    assert "pm list packages -3" in cmds[0]
    assert "am force-stop" in cmds[0]
    assert cmds[1] == "pm trim-caches 999G"
    assert cmds[2] == "input keyevent KEYCODE_HOME"
    assert calls[0][1] == 60 and calls[1][1] == 60


def test_reboot_runs_adb_reboot_for_serial(cast, calls):
    cast.reboot()
    assert calls == [(("-s", SERIAL, "reboot"), 15)]


def test_dump_ui_returns_element_for_valid_xml(cast, monkeypatch, calls):
    monkeypatch.setattr(
        chromecast.adb, "run", lambda *a, timeout=15: "<hierarchy><node/></hierarchy>"
    )
    root = cast.dump_ui()
    assert isinstance(root, ET.Element)
    assert root.tag == "hierarchy"


def test_dump_ui_dumps_to_path_then_reads_it(cast, calls):
    cast.dump_ui()
    cmd = shell_commands(calls)[0]
    assert "uiautomator dump" in cmd and chromecast.UI_DUMP_PATH in cmd
    assert "cat " + chromecast.UI_DUMP_PATH in cmd


@pytest.mark.parametrize("garbage", ["", "ERROR: could not get idle state", "<a><b>"])
def test_dump_ui_returns_none_when_output_is_not_xml(cast, monkeypatch, garbage):
    monkeypatch.setattr(chromecast.adb, "run", lambda *a, timeout=15: garbage)
    assert cast.dump_ui() is None


@pytest.fixture
def adb_mocks(monkeypatch):
    state = {"started": 0, "discovered": 40000, "connect_result": SERIAL, "connect_args": None}

    def start_server():
        state["started"] += 1

    def discover_port(ip, service):
        state["discover_args"] = (ip, service)
        return state["discovered"]

    def connect(ip, port):
        state["connect_args"] = (ip, port)
        return state["connect_result"]

    monkeypatch.setattr(chromecast.adb, "start_server", start_server)
    monkeypatch.setattr(chromecast.adb, "discover_port", discover_port)
    monkeypatch.setattr(chromecast.adb, "connect", connect)
    return state


def test_connect_starts_server_and_uses_discovered_port(adb_mocks):
    cc = chromecast.connect("10.0.0.2", 5555)
    assert adb_mocks["started"] == 1
    assert adb_mocks["discover_args"] == ("10.0.0.2", chromecast.adb.CONNECT_SERVICE)
    assert adb_mocks["connect_args"] == ("10.0.0.2", 40000)
    assert isinstance(cc, Chromecast) and cc.serial == SERIAL


def test_connect_falls_back_to_configured_port_when_nothing_discovered(adb_mocks):
    adb_mocks["discovered"] = None
    cc = chromecast.connect("10.0.0.2", 5555)
    assert adb_mocks["connect_args"] == ("10.0.0.2", 5555)
    assert cc.serial == SERIAL


def test_connect_uses_configured_defaults(adb_mocks):
    adb_mocks["discovered"] = None
    chromecast.connect()
    assert adb_mocks["connect_args"] == (chromecast.CHROMECAST_IP, chromecast.CHROMECAST_PORT)


def test_connect_nothing_discovered_and_failure_suggests_wireless_debugging_and_connect(
    adb_mocks,
):
    adb_mocks["discovered"] = None
    adb_mocks["connect_result"] = None
    with pytest.raises(BeamflixError) as exc:
        chromecast.connect("10.0.0.2", 5555)
    # The CLI treats ConnectionFailed as "needs pairing"; this must not be one
    assert not isinstance(exc.value, ConnectionFailed)
    msg = str(exc.value)
    assert "10.0.0.2" in msg
    assert "ireless debugging" in msg
    assert "beamflix connect" in msg


def test_connect_discovered_port_but_failure_raises_connection_failed(adb_mocks):
    adb_mocks["connect_result"] = None
    with pytest.raises(ConnectionFailed) as exc:
        chromecast.connect("10.0.0.2", 5555)
    assert "10.0.0.2:40000" in str(exc.value)
