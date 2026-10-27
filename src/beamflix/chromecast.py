"""Connection to the Chromecast and remote control through adb."""

import xml.etree.ElementTree as ET

from beamflix import adb
from beamflix.config import CHROMECAST_IP, CHROMECAST_PORT
from beamflix.errors import BeamflixError, ConnectionFailed

UI_DUMP_PATH = "/sdcard/beamflix-ui.xml"

WIRELESS_DEBUGGING_PATH = "Settings > System > Developer options > Wireless debugging"

# Remote-control commands -> key sent to the Chromecast. Media keys go to the
# app that is playing; wake and sleep also turn the TV on/off through HDMI-CEC
REMOTE_KEYS = {
    "play": "KEYCODE_MEDIA_PLAY",
    "pause": "KEYCODE_MEDIA_PAUSE",
    "toggle": "KEYCODE_MEDIA_PLAY_PAUSE",
    "startup": "KEYCODE_WAKEUP",
    "shutdown": "KEYCODE_SLEEP",
}


class Chromecast:
    def __init__(self, serial: str) -> None:
        self.serial = serial

    def shell(self, command: str, timeout: float = 15) -> str:
        return adb.run("-s", self.serial, "shell", command, timeout=timeout)

    def press(self, keycode: str) -> None:
        self.shell(f"input keyevent {keycode}")

    def wake(self) -> None:
        # Also turns the TV on through HDMI-CEC
        self.press("KEYCODE_WAKEUP")

    def stop_app(self, package: str) -> None:
        self.shell(f"am force-stop {package}")

    def open_deeplink(self, deeplink: str) -> str:
        # JustWatch links are intent:// URIs that already include package and
        # extras (for Netflix S.source=30 skips the profile picker)
        return self.shell(f"am start '{deeplink}'")

    def launch(self, package: str, deeplink: str) -> str:
        """Wake the device and open `deeplink` in a fresh instance of `package`."""
        self.wake()
        # If the app is already running it would just come back to the
        # foreground on its current screen, ignoring the link
        self.stop_app(package)
        return self.open_deeplink(deeplink)

    def clean(self) -> None:
        """Close every installed app, clear all app caches and go home."""
        self.shell(
            "for p in $(pm list packages -3 | cut -d: -f2); do am force-stop $p; done",
            timeout=60,
        )
        # Asking for more free space than the storage has clears every app cache
        self.shell("pm trim-caches 999G", timeout=60)
        self.press("KEYCODE_HOME")

    def reboot(self) -> None:
        # Android turns wireless debugging off at boot, so the connection is
        # lost until it is enabled again on the TV
        adb.run("-s", self.serial, "reboot")

    def dump_ui(self) -> ET.Element | None:
        """Current screen as a uiautomator hierarchy, or None if unavailable."""
        xml = self.shell(
            f"uiautomator dump {UI_DUMP_PATH} >/dev/null && cat {UI_DUMP_PATH}"
        )
        try:
            return ET.fromstring(xml)
        except ET.ParseError:
            # uiautomator fails while the screen keeps changing (e.g. video playing)
            return None


def connect(
    ip: str = CHROMECAST_IP, fallback_port: int = CHROMECAST_PORT
) -> Chromecast:
    """Connect over wireless debugging, discovering the port via mDNS."""
    adb.start_server()
    discovered = adb.discover_port(ip, adb.CONNECT_SERVICE)
    port = discovered or fallback_port
    serial = adb.connect(ip, port)
    if serial is None and discovered is None:
        raise BeamflixError(
            f"Cannot reach {ip}: wireless debugging looks disabled (it turns off "
            f"at every reboot). Enable it on the TV in {WIRELESS_DEBUGGING_PATH}. "
            "To pair a new computer, run: beamflix connect"
        )
    if serial is None:
        raise ConnectionFailed(
            f"Cannot connect to {ip}:{port}: check the port on the main "
            "Wireless debugging screen"
        )
    return Chromecast(serial)
