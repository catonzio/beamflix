"""Tests for beamflix.pairing."""

import pytest

from beamflix import pairing
from beamflix.errors import BeamflixError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(pairing.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


@pytest.fixture
def sleeps(no_sleep):
    return no_sleep


def feed_inputs(monkeypatch, *answers):
    prompts = []
    it = iter(answers)

    def fake_input(prompt=""):
        prompts.append(prompt)
        return next(it)

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


# ---- _discover_pairing_port


def test_discover_returns_port_found_on_first_attempt(monkeypatch, capsys, sleeps):
    monkeypatch.setattr(pairing.adb, "mdns_port", lambda ip, svc: 37000)
    assert pairing._discover_pairing_port("1.2.3.4") == 37000
    assert sleeps == []
    assert capsys.readouterr().out.endswith("\n")


def test_discover_queries_pairing_service_for_ip(monkeypatch):
    seen = []
    monkeypatch.setattr(
        pairing.adb, "mdns_port", lambda ip, svc: seen.append((ip, svc)) or 1
    )
    pairing._discover_pairing_port("1.2.3.4")
    assert seen == [("1.2.3.4", pairing.adb.PAIRING_SERVICE)]


def test_discover_polls_with_sleep_until_found(monkeypatch, capsys, sleeps):
    results = iter([None, None, 41000])
    monkeypatch.setattr(pairing.adb, "mdns_port", lambda ip, svc: next(results))
    assert pairing._discover_pairing_port("ip") == 41000
    assert sleeps == [pairing.DISCOVERY_INTERVAL] * 2
    out = capsys.readouterr().out
    assert ".." in out and out.endswith("\n")


def test_discover_gives_up_after_max_attempts_returning_none(
    monkeypatch, capsys, sleeps
):
    count = []
    monkeypatch.setattr(pairing.adb, "mdns_port", lambda ip, svc: count.append(1))
    assert pairing._discover_pairing_port("ip") is None
    assert len(count) == pairing.DISCOVERY_ATTEMPTS
    assert len(sleeps) == pairing.DISCOVERY_ATTEMPTS
    assert capsys.readouterr().out.endswith("\n")


@pytest.mark.parametrize("exc", [RuntimeError("boom"), KeyboardInterrupt()])
def test_discover_ends_progress_line_even_on_exception(monkeypatch, capsys, exc):
    def raiser(ip, svc):
        raise exc

    monkeypatch.setattr(pairing.adb, "mdns_port", raiser)
    with pytest.raises(type(exc)):
        pairing._discover_pairing_port("ip")
    assert capsys.readouterr().out.endswith("\n")


# ---- _ask_port


def test_ask_port_enter_accepts_discovered_default_shown_in_brackets(monkeypatch):
    prompts = feed_inputs(monkeypatch, "")
    assert pairing._ask_port(37000) == 37000
    assert "[37000]" in prompts[0]


def test_ask_port_typed_value_overrides_discovered(monkeypatch):
    feed_inputs(monkeypatch, " 42000 ")
    assert pairing._ask_port(37000) == 42000


def test_ask_port_typed_value_works_without_discovery_and_has_no_brackets(monkeypatch):
    prompts = feed_inputs(monkeypatch, "42000")
    assert pairing._ask_port(None) == 42000
    assert "[" not in prompts[0]


@pytest.mark.parametrize("discovered", [None, 37000])
@pytest.mark.parametrize("answer", ["abc", "12a", "-5", "1.5"])
def test_ask_port_non_numeric_raises(monkeypatch, discovered, answer):
    feed_inputs(monkeypatch, answer)
    with pytest.raises(BeamflixError, match="Invalid port"):
        pairing._ask_port(discovered)


def test_ask_port_empty_without_discovery_raises_missing_port(monkeypatch):
    feed_inputs(monkeypatch, "  ")
    with pytest.raises(BeamflixError, match="Missing pairing port"):
        pairing._ask_port(None)


# ---- pair


def test_pair_prints_instructions_asks_code_and_pairs(monkeypatch, capsys):
    monkeypatch.setattr(pairing.adb, "mdns_port", lambda ip, svc: 37000)
    feed_inputs(monkeypatch, "", "  123456 ")
    paired = []
    monkeypatch.setattr(
        pairing.adb,
        "pair",
        lambda ip, port, code: paired.append((ip, port, code)) or "Paired OK",
    )
    pairing.pair("1.2.3.4")
    out = capsys.readouterr().out
    assert "not paired" in out
    assert "Wireless debugging" in out
    assert "Pair device with pairing code" in out
    assert "Paired OK" in out
    assert paired == [("1.2.3.4", 37000, "123456")]


def test_pair_typed_port_overrides_discovered(monkeypatch):
    monkeypatch.setattr(pairing.adb, "mdns_port", lambda ip, svc: 37000)
    feed_inputs(monkeypatch, "40000", "654321")
    paired = []
    monkeypatch.setattr(
        pairing.adb,
        "pair",
        lambda ip, port, code: paired.append((ip, port, code)) or "",
    )
    pairing.pair("ip")
    assert paired == [("ip", 40000, "654321")]


def test_pair_without_port_does_not_ask_code_or_pair(monkeypatch):
    monkeypatch.setattr(pairing.adb, "mdns_port", lambda ip, svc: None)
    prompts = feed_inputs(monkeypatch, "")
    called = []
    monkeypatch.setattr(pairing.adb, "pair", lambda *a: called.append(a))
    with pytest.raises(BeamflixError, match="Missing pairing port"):
        pairing.pair("ip")
    assert len(prompts) == 1 and called == []


def test_pair_uses_configured_ip_by_default(monkeypatch):
    seen = []
    monkeypatch.setattr(pairing.adb, "mdns_port", lambda ip, svc: seen.append(ip) or 1)
    feed_inputs(monkeypatch, "", "000000")
    monkeypatch.setattr(pairing.adb, "pair", lambda *a: "")
    pairing.pair()
    assert seen == [pairing.CHROMECAST_IP]
