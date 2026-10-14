"""Automatic choice of the profile in apps that ask "Who's watching?" at launch."""

import re
import time
import xml.etree.ElementTree as ET

from castscript.chromecast import Chromecast
from castscript.errors import CastscriptError

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
            raise CastscriptError(f"Profile '{profile}' not found on the TV")
        focused = next(
            (n for n in picker.iter("node") if n.get("focused") == "true"), None
        )
        if focused is None:
            time.sleep(1)
            continue

        # Profiles are laid out in a row: move the focus until it is on the tile
        target_x = _center_x(tile)
        left, right = _x_range(focused)
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


def _x_range(node: ET.Element) -> tuple[int, int]:
    # Bounds look like: [715,356][960,717]
    x0, _, x1, _ = map(int, re.findall(r"\d+", node.get("bounds", "")))
    return x0, x1


def _center_x(node: ET.Element) -> int:
    x0, x1 = _x_range(node)
    return (x0 + x1) // 2
