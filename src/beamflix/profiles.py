"""Automatic choice of the profile in apps that ask "Who's watching?" at launch."""

import re
import time
import xml.etree.ElementTree as ET

from beamflix.chromecast import Chromecast
from beamflix.errors import BeamflixError

# App package -> resource id of its profile picker screen
PROFILE_PICKERS = {
    "com.disney.disneyplus": "com.disney.disneyplus:id/profilesContent",
}

PICKER_TIMEOUT = 20  # seconds


def select(device: Chromecast, package: str, profile: str) -> bool:
    """Wait for the profile picker of `package` and choose `profile`.

    Returns False if the app has no known picker or it never shows up.
    Profiles protected by a PIN are not supported.
    """
    picker_id = PROFILE_PICKERS.get(package)
    if picker_id is None:
        return False

    deadline = time.monotonic() + PICKER_TIMEOUT
    while time.monotonic() < deadline:
        picker = _find_picker(device.dump_ui(), picker_id)
        if picker is None:
            time.sleep(1)
            continue

        tile = _profile_tile(picker, profile)
        if tile is None:
            raise BeamflixError(f"Profile '{profile}' not found on the TV")
        focused = next(
            (n for n in picker.iter("node") if n.get("focused") == "true"), None
        )
        tile_range = _x_range(tile)
        focused_range = None if focused is None else _x_range(focused)
        if tile_range is None or focused_range is None:
            # No focus yet, or a dump taken mid-layout without positions: retry
            time.sleep(1)
            continue

        # Profiles are laid out in a row: move the focus until it is on the tile
        target_x = sum(tile_range) // 2
        left, right = focused_range
        if left <= target_x <= right:
            device.press("KEYCODE_DPAD_CENTER")
            return True
        device.press("KEYCODE_DPAD_RIGHT" if target_x > right else "KEYCODE_DPAD_LEFT")
    return False


def _find_picker(ui: ET.Element | None, picker_id: str) -> ET.Element | None:
    if ui is None:
        return None
    return next((n for n in ui.iter("node") if n.get("resource-id") == picker_id), None)


def _profile_tile(picker: ET.Element, profile: str) -> ET.Element | None:
    # Tiles are described like "Accedi al profilo di dandi": match the trailing name
    pattern = re.compile(rf"(^|\s){re.escape(profile)}$", re.IGNORECASE)
    return next(
        (n for n in picker.iter("node") if pattern.search(n.get("content-desc", ""))),
        None,
    )


def _x_range(node: ET.Element) -> tuple[int, int] | None:
    """Horizontal extent of `node`, or None if its bounds are missing or malformed."""
    # Bounds look like: [715,356][960,717]
    match = re.fullmatch(r"\[(\d+),\d+\]\[(\d+),\d+\]", node.get("bounds", ""))
    if match is None:
        return None
    return int(match[1]), int(match[2])
