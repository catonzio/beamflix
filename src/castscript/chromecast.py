"""Connection to the Chromecast and app launching through adb."""

from ppadb.client import Client as AdbClient

from castscript import adb
from castscript.config import ADB_HOST, ADB_PORT, CHROMECAST_IP, CHROMECAST_PORT
from castscript.errors import CastscriptError, ConnectionFailed


class Chromecast:
    def __init__(self, serial: str) -> None:
        device = AdbClient(host=ADB_HOST, port=ADB_PORT).device(serial)
        if device is None:
            raise CastscriptError(f"Device {serial} not found after connecting")
        self.serial = serial
        self._device = device

    def wake(self) -> None:
        # Also turns the TV on through HDMI-CEC
        self._device.shell("input keyevent KEYCODE_WAKEUP")

    def stop_app(self, package: str) -> None:
        self._device.shell(f"am force-stop {package}")

    def open_deeplink(self, deeplink: str) -> str:
        # JustWatch links are intent:// URIs that already include package and
        # extras (for Netflix S.source=30 skips the profile picker)
        return self._device.shell(f"am start '{deeplink}'").strip()

    def launch(self, package: str, deeplink: str) -> str:
        """Wake the device and open `deeplink` in a fresh instance of `package`."""
        self.wake()
        # If the app is already running it would just come back to the
        # foreground on its current screen, ignoring the link
        self.stop_app(package)
        return self.open_deeplink(deeplink)


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
