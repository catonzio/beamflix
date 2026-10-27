"""Unit tests for beamflix.adb. The real adb is never run."""

import subprocess
from unittest.mock import MagicMock, call

import pytest

from beamflix import adb
from beamflix.errors import BeamflixError

FAKE_ADB = "/fake/bin/adb"
IP = "192.168.1.14"

MDNS_OUTPUT = (
    "List of discovered mdns services\n"
    f"adb-2912105GN3WJS2-JlA1fU\t_adb-tls-connect._tcp.\t{IP}:39909\n"
    f"adb-2912105GN3WJS2-JlA1fU\t_adb-tls-pairing._tcp.\t{IP}:39741\n"
)


def completed(stdout="", stderr=""):
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr=stderr)


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    monkeypatch.setattr(adb, "ADB", FAKE_ADB)
    sleep = MagicMock()
    monkeypatch.setattr(adb.time, "sleep", sleep)
    return sleep


@pytest.fixture
def sp_run(monkeypatch):
    mock = MagicMock(return_value=completed())
    monkeypatch.setattr(adb.subprocess, "run", mock)
    return mock


@pytest.fixture
def fake_run(monkeypatch):
    """Replace adb.run (not subprocess) to script outputs."""
    mock = MagicMock(return_value="")
    monkeypatch.setattr(adb, "run", mock)
    return mock


# --- ENV -------------------------------------------------------------------


def test_env_disables_openscreen_mdns_backend():
    assert adb.ENV["ADB_MDNS_OPENSCREEN"] == "0"


def test_env_keeps_the_rest_of_the_process_environment():
    assert adb.ENV["PATH"]


# --- run -------------------------------------------------------------------


def test_run_invokes_adb_with_args_and_forced_env(sp_run):
    adb.run("devices", timeout=3)
    args, kwargs = sp_run.call_args
    assert args[0] == [FAKE_ADB, "devices"]
    assert kwargs["env"] is adb.ENV
    assert kwargs["env"]["ADB_MDNS_OPENSCREEN"] == "0"
    assert kwargs["timeout"] == 3
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False


def test_run_has_default_timeout(sp_run):
    adb.run("devices")
    assert sp_run.call_args.kwargs["timeout"] > 0


def test_run_returns_combined_stdout_and_stderr_stripped(sp_run):
    sp_run.return_value = completed(stdout="  out\n", stderr="err\n\n")
    assert adb.run("x") == "out\nerr"


def test_run_returns_empty_string_on_timeout(sp_run):
    sp_run.side_effect = subprocess.TimeoutExpired(cmd="adb", timeout=1)
    assert adb.run("x") == ""


def test_run_does_not_swallow_nonzero_exit_output(sp_run):
    sp_run.return_value = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="error: closed"
    )
    assert adb.run("x") == "error: closed"


# --- start_server ----------------------------------------------------------


def test_start_server_raises_when_adb_not_in_path(monkeypatch, sp_run):
    monkeypatch.setattr(adb, "ADB", "")
    with pytest.raises(BeamflixError, match="adb not found"):
        adb.start_server()
    sp_run.assert_not_called()


def test_start_server_starts_once_when_bonjour_backend_in_use(sp_run):
    sp_run.side_effect = [
        completed(),
        completed(stdout="mdns daemon version [Bonjour]"),
    ]
    adb.start_server()
    cmds = [c.args[0] for c in sp_run.call_args_list]
    assert cmds == [[FAKE_ADB, "start-server"], [FAKE_ADB, "mdns", "check"]]


def test_start_server_restarts_server_when_openscreen_backend_in_use(sp_run):
    sp_run.side_effect = [
        completed(),  # start-server
        completed(stdout="mdns daemon version [Openscreen discovery 0.0.0]"),
        completed(),  # kill-server
        completed(),  # start-server again
    ]
    adb.start_server()
    cmds = [c.args[0] for c in sp_run.call_args_list]
    assert cmds == [
        [FAKE_ADB, "start-server"],
        [FAKE_ADB, "mdns", "check"],
        [FAKE_ADB, "kill-server"],
        [FAKE_ADB, "start-server"],
    ]


def test_start_server_does_not_capture_output_and_passes_env(sp_run):
    sp_run.side_effect = [
        completed(),
        completed(stdout="Openscreen"),
        completed(),
        completed(),
    ]
    adb.start_server()
    starts = [c for c in sp_run.call_args_list if c.args[0][1:] == ["start-server"]]
    assert len(starts) == 2
    for c in starts:
        kw = c.kwargs
        assert kw["stdout"] == subprocess.DEVNULL
        assert kw["stderr"] == subprocess.DEVNULL
        assert not kw.get("capture_output")
        assert kw["check"] is True
        assert kw["env"]["ADB_MDNS_OPENSCREEN"] == "0"


def test_start_server_propagates_failure_to_start(sp_run):
    sp_run.side_effect = subprocess.CalledProcessError(1, "adb")
    with pytest.raises(subprocess.CalledProcessError):
        adb.start_server()


# --- mdns_port -------------------------------------------------------------


def test_mdns_port_finds_connect_port_in_real_output(fake_run):
    fake_run.return_value = MDNS_OUTPUT
    assert adb.mdns_port(IP, adb.CONNECT_SERVICE) == 39909
    fake_run.assert_called_with("mdns", "services")


def test_mdns_port_finds_pairing_port_in_real_output(fake_run):
    fake_run.return_value = MDNS_OUTPUT
    assert adb.mdns_port(IP, adb.PAIRING_SERVICE) == 39741


def test_mdns_port_ignores_other_ip(fake_run):
    fake_run.return_value = MDNS_OUTPUT
    assert adb.mdns_port("192.168.1.99", adb.CONNECT_SERVICE) is None


@pytest.mark.parametrize("ip", ["192.168.1.1", "192.168.1", "192.168.1.1400"])
def test_mdns_port_does_not_match_ip_that_is_only_a_prefix(fake_run, ip):
    fake_run.return_value = MDNS_OUTPUT
    assert adb.mdns_port(ip, adb.CONNECT_SERVICE) is None


def test_mdns_port_does_not_match_ip_that_is_a_suffix_of_another(fake_run):
    fake_run.return_value = f"adb-x\t_adb-tls-connect._tcp.\t10.{IP}:1234\n"
    assert adb.mdns_port(IP, adb.CONNECT_SERVICE) is None


def test_mdns_port_ignores_unknown_service(fake_run):
    fake_run.return_value = MDNS_OUTPUT
    assert adb.mdns_port(IP, "_other") is None


def test_mdns_port_skips_header_and_malformed_lines(fake_run):
    fake_run.return_value = (
        "List of discovered mdns services\n\n"
        "garbage\n"
        f"adb-x\t_adb-tls-connect._tcp.\t{IP}:4242\n"
    )
    assert adb.mdns_port(IP, adb.CONNECT_SERVICE) == 4242


def test_mdns_port_returns_none_when_no_services(fake_run):
    fake_run.return_value = "List of discovered mdns services\n"
    assert adb.mdns_port(IP, adb.CONNECT_SERVICE) is None


def test_mdns_port_returns_none_on_empty_output(fake_run):
    assert adb.mdns_port(IP, adb.CONNECT_SERVICE) is None


def test_mdns_port_picks_entry_with_matching_ip_among_several(fake_run):
    fake_run.return_value = (
        "adb-a\t_adb-tls-connect._tcp.\t192.168.1.1:1111\n"
        "adb-b\t_adb-tls-connect._tcp.\t192.168.1.14:2222\n"
    )
    assert adb.mdns_port(IP, adb.CONNECT_SERVICE) == 2222


# --- discover_port ---------------------------------------------------------


def test_discover_port_returns_immediately_without_sleeping(monkeypatch, fake_env):
    m = MagicMock(return_value=39909)
    monkeypatch.setattr(adb, "mdns_port", m)
    assert adb.discover_port(IP, adb.CONNECT_SERVICE) == 39909
    m.assert_called_once_with(IP, adb.CONNECT_SERVICE)
    fake_env.assert_not_called()


def test_discover_port_retries_with_sleep_until_found(monkeypatch, fake_env):
    m = MagicMock(side_effect=[None, None, 555])
    monkeypatch.setattr(adb, "mdns_port", m)
    assert adb.discover_port(IP, adb.CONNECT_SERVICE) == 555
    assert m.call_count == 3
    assert fake_env.call_args_list == [call(adb.MDNS_INTERVAL)] * 2


def test_discover_port_gives_up_after_max_attempts_without_final_sleep(
    monkeypatch, fake_env
):
    m = MagicMock(return_value=None)
    monkeypatch.setattr(adb, "mdns_port", m)
    assert adb.discover_port(IP, adb.CONNECT_SERVICE) is None
    assert m.call_count == adb.MDNS_ATTEMPTS
    assert fake_env.call_count == adb.MDNS_ATTEMPTS - 1


def test_discover_port_with_zero_attempts_returns_none(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr(adb, "mdns_port", m)
    monkeypatch.setattr(adb, "MDNS_ATTEMPTS", 0)
    assert adb.discover_port(IP, adb.CONNECT_SERVICE) is None
    m.assert_not_called()


def test_discover_port_finds_port_on_last_attempt(monkeypatch, fake_env):
    m = MagicMock(side_effect=[None] * (adb.MDNS_ATTEMPTS - 1) + [7])
    monkeypatch.setattr(adb, "mdns_port", m)
    assert adb.discover_port(IP, adb.CONNECT_SERVICE) == 7


# --- connect ---------------------------------------------------------------


def test_connect_returns_serial_when_device_is_online(fake_run):
    fake_run.side_effect = ["connected to 192.168.1.14:39909", "device"]
    assert adb.connect(IP, 39909) == f"{IP}:39909"
    assert fake_run.call_args_list[0].args == ("connect", f"{IP}:39909")
    assert fake_run.call_args_list[1].args == ("-s", f"{IP}:39909", "get-state")
    assert len(fake_run.call_args_list) == 2


@pytest.mark.parametrize(
    "state", ["offline", "", "error: device not found", "unauthorized", "no device"]
)
def test_connect_disconnects_stale_transport_and_returns_none(fake_run, state):
    fake_run.side_effect = ["failed to connect", state, "disconnected"]
    assert adb.connect(IP, 39909) is None
    assert fake_run.call_args_list[-1].args == ("disconnect", f"{IP}:39909")


# --- pair ------------------------------------------------------------------


def test_pair_passes_address_and_code_and_returns_output(fake_run):
    out = f"Successfully paired to {IP}:39741 [guid=adb-x]"
    fake_run.return_value = out
    assert adb.pair(IP, 39741, "123456") == out
    assert fake_run.call_args.args == ("pair", f"{IP}:39741", "123456")


def test_pair_raises_with_adb_output_when_not_successful(fake_run):
    fake_run.return_value = "Failed: Wrong password or password format"
    with pytest.raises(BeamflixError) as exc:
        adb.pair(IP, 39741, "000000")
    assert "Wrong password" in str(exc.value)
    assert "Pairing failed" in str(exc.value)


def test_pair_raises_on_empty_output_such_as_timeout(fake_run):
    with pytest.raises(BeamflixError, match="Pairing failed"):
        adb.pair(IP, 39741, "123456")
