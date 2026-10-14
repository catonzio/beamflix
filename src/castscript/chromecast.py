"""Connection to the Chromecast and remote control through adb."""

import xml.etree.ElementTree as ET

from castscript import adb
from castscript.config import CHROMECAST_IP, CHROMECAST_PORT
from castscript.errors import ConnectionFailed

UI_DUMP_PATH = "/sdcard/castscript-ui.xml"


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
    port = adb.mdns_port(ip, adb.CONNECT_SERVICE) or fallback_port
    serial = adb.connect(ip, port)
    if serial is None:
        raise ConnectionFailed(
            f"Cannot connect to {ip}:{port}: check the port on the main "
            "Wireless debugging screen"
        )
    return Chromecast(serial)
