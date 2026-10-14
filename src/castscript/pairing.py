"""Interactive pairing between this computer and the Chromecast."""

import time

from castscript import adb
from castscript.config import CHROMECAST_IP
from castscript.errors import CastscriptError

DISCOVERY_ATTEMPTS = 30
DISCOVERY_INTERVAL = 2  # seconds


def pair(ip: str = CHROMECAST_IP) -> None:
    print(
        "This computer is not paired with the TV.\n"
        "On the TV go to Settings > System > Developer options > "
        "Wireless debugging > Pair device with pairing code."
    )
    port = _ask_port(_discover_pairing_port(ip))
    code = input("6-digit pairing code: ").strip()
    print(adb.pair(ip, port, code))


def _discover_pairing_port(ip: str) -> int | None:
    print("Waiting for the pairing dialog...", end="", flush=True)
    try:
        for _ in range(DISCOVERY_ATTEMPTS):
            port = adb.mdns_port(ip, adb.PAIRING_SERVICE)
            if port:
                return port
            print(".", end="", flush=True)
            time.sleep(DISCOVERY_INTERVAL)
        return None
    finally:
        print()


def _ask_port(discovered: int | None) -> int:
    """Ask for the pairing port, defaulting to the discovered one."""
    hint = f" [{discovered}]" if discovered else ""
    answer = input(f"Pairing port shown on the TV{hint}: ").strip()
    if answer:
        if not answer.isdigit():
            raise CastscriptError(f"Invalid port: {answer}")
        return int(answer)
    if discovered is None:
        raise CastscriptError("Missing pairing port")
    return discovered
