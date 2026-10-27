"""Tests for automatic profile selection through uiautomator dumps."""

import itertools
import xml.etree.ElementTree as ET

import pytest

from beamflix import profiles
from beamflix.errors import BeamflixError

PKG = "com.disney.disneyplus"
PICKER_ID = "com.disney.disneyplus:id/profilesContent"


def _node(attrs="", children=""):
    return f"<node {attrs}>{children}</node>"


def _tile(name, bounds, focused=False):
    return _node(
        f'index="0" text="" resource-id="" class="android.widget.FrameLayout" '
        f'package="{PKG}" content-desc="Accedi al profilo di {name}" '
        f'focusable="true" focused="{str(focused).lower()}" bounds="{bounds}"'
    )


# Three tiles laid out in a row, 1920x1080 screen
TILES = {
    "mamma": "[215,356][460,717]",
    "dandi": "[715,356][960,717]",
    "papa": "[1215,356][1460,717]",
}


def screen(focus=None, tiles=TILES, picker_id=PICKER_ID):
    inner = "".join(_tile(n, b, n == focus) for n, b in tiles.items())
    picker = _node(
        f'resource-id="{picker_id}" package="{PKG}" bounds="[0,0][1920,1080]"', inner
    )
    return ET.fromstring(
        '<hierarchy rotation="0">'
        + _node(f'package="{PKG}" bounds="[0,0][1920,1080]"', picker)
        + "</hierarchy>"
    )


class FakeDevice:
    def __init__(self, screens):
        self._screens = list(screens)
        self.keys = []
        self.dumps = 0

    def dump_ui(self):
        self.dumps += 1
        # keep returning the last screen once the script is exhausted
        return self._screens.pop(0) if len(self._screens) > 1 else self._screens[0]

    def press(self, key):
        self.keys.append(key)


@pytest.fixture(autouse=True)
def fast_clock(monkeypatch):
    """No real sleeping; monotonic advances 1s per call so timeouts are quick."""
    sleeps = []
    ticks = itertools.count(0, 1)
    monkeypatch.setattr(profiles.time, "sleep", sleeps.append)
    monkeypatch.setattr(profiles.time, "monotonic", lambda: float(next(ticks)))
    return sleeps


def test_package_without_known_picker_returns_false_without_touching_device():
    device = FakeDevice([screen("dandi")])
    assert profiles.select(device, "com.netflix.ninja", "dandi") is False
    assert device.dumps == 0 and device.keys == []


def test_disney_plus_is_the_supported_picker():
    assert profiles.PROFILE_PICKERS[PKG] == PICKER_ID


def test_already_focused_profile_is_selected_with_dpad_center():
    device = FakeDevice([screen(focus="dandi")])
    assert profiles.select(device, PKG, "dandi") is True
    assert device.keys == ["KEYCODE_DPAD_CENTER"]


def test_focus_on_the_left_moves_right_then_selects():
    device = FakeDevice([screen("mamma"), screen("dandi")])
    assert profiles.select(device, PKG, "dandi") is True
    assert device.keys == ["KEYCODE_DPAD_RIGHT", "KEYCODE_DPAD_CENTER"]


def test_focus_on_the_right_moves_left_then_selects():
    device = FakeDevice([screen("papa"), screen("dandi")])
    assert profiles.select(device, PKG, "dandi") is True
    assert device.keys == ["KEYCODE_DPAD_LEFT", "KEYCODE_DPAD_CENTER"]


def test_multiple_steps_are_taken_to_reach_the_profile():
    device = FakeDevice([screen("mamma"), screen("dandi"), screen("papa")])
    assert profiles.select(device, PKG, "papa") is True
    assert device.keys == [
        "KEYCODE_DPAD_RIGHT",
        "KEYCODE_DPAD_RIGHT",
        "KEYCODE_DPAD_CENTER",
    ]


def test_profile_name_match_is_case_insensitive():
    device = FakeDevice([screen(focus="dandi")])
    assert profiles.select(device, PKG, "DANDI") is True


def test_profile_must_match_whole_trailing_name():
    # "andi" must not match the tile of "dandi"
    device = FakeDevice([screen(focus="dandi")])
    with pytest.raises(BeamflixError):
        profiles.select(device, PKG, "andi")


def test_profile_name_with_regex_characters_is_matched_literally():
    tiles = {"a.b": "[0,0][100,100]", "axb": "[200,0][300,100]"}
    device = FakeDevice([screen("axb", tiles), screen("a.b", tiles)])
    assert profiles.select(device, PKG, "a.b") is True
    assert device.keys == ["KEYCODE_DPAD_LEFT", "KEYCODE_DPAD_CENTER"]


def test_unknown_profile_raises_error_naming_the_profile():
    device = FakeDevice([screen("mamma")])
    with pytest.raises(BeamflixError, match="Profile 'luigi' not found on the TV"):
        profiles.select(device, PKG, "luigi")
    assert device.keys == []


def test_waits_until_picker_appears():
    splash = ET.fromstring(
        '<hierarchy><node package="x" bounds="[0,0][1,1]"/></hierarchy>'
    )
    device = FakeDevice([splash, splash, screen(focus="dandi")])
    assert profiles.select(device, PKG, "dandi") is True
    assert device.dumps == 3


def test_dump_ui_returning_none_is_retried(fast_clock):
    device = FakeDevice([None, screen(focus="dandi")])
    assert profiles.select(device, PKG, "dandi") is True
    assert fast_clock == [1]


def test_picker_never_appearing_returns_false_after_timeout(fast_clock):
    device = FakeDevice([None])
    assert profiles.select(device, PKG, "dandi") is False
    assert device.keys == []
    assert device.dumps >= 1 and len(fast_clock) == device.dumps


def test_picker_with_other_resource_id_is_not_recognized():
    device = FakeDevice([screen(focus="dandi", picker_id="other:id/x")])
    assert profiles.select(device, PKG, "dandi") is False
    assert device.keys == []


def test_waits_when_no_tile_has_focus_yet(fast_clock):
    device = FakeDevice([screen(None), screen("dandi")])
    assert profiles.select(device, PKG, "dandi") is True
    assert fast_clock == [1]
    assert device.keys == ["KEYCODE_DPAD_CENTER"]


def test_gives_up_when_focus_never_lands_on_a_tile():
    device = FakeDevice([screen(None)])
    assert profiles.select(device, PKG, "dandi") is False
    assert device.keys == []


def test_timeout_is_respected(monkeypatch):
    # clock jumps past the deadline immediately: no dump at all
    values = iter([0.0, profiles.PICKER_TIMEOUT + 1])
    monkeypatch.setattr(profiles.time, "monotonic", lambda: next(values))
    device = FakeDevice([screen("dandi")])
    assert profiles.select(device, PKG, "dandi") is False
    assert device.dumps == 0


@pytest.mark.parametrize("bounds", ["", "[715,356]", "garbage", "[a,b][c,d]"])
def test_unusable_bounds_never_crash_and_give_up_without_pressing(bounds):
    # uiautomator dumps taken mid-layout can lack positions: no ValueError
    device = FakeDevice([screen("dandi", tiles={**TILES, "dandi": bounds})])
    assert profiles.select(device, PKG, "dandi") is False
    assert device.keys == []


def test_target_tile_without_bounds_is_retried_until_positions_are_known(fast_clock):
    device = FakeDevice(
        [
            screen("mamma", tiles={**TILES, "dandi": ""}),
            screen("mamma"),
            screen("dandi"),
        ]
    )
    assert profiles.select(device, PKG, "dandi") is True
    assert fast_clock == [1]
    assert device.keys == ["KEYCODE_DPAD_RIGHT", "KEYCODE_DPAD_CENTER"]


def test_focused_tile_without_bounds_is_retried_until_positions_are_known(fast_clock):
    device = FakeDevice(
        [screen("mamma", tiles={**TILES, "mamma": ""}), screen("dandi")]
    )
    assert profiles.select(device, PKG, "dandi") is True
    assert fast_clock == [1]
    assert device.keys == ["KEYCODE_DPAD_CENTER"]
