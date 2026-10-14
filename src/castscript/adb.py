"""Wrapper around the adb command-line tool.

ppadb talks to the adb server but supports neither `pair` nor `mdns`, so
pairing, discovery and connection go through the CLI.
"""

import shutil
import subprocess

from castscript.errors import CastscriptError

ADB = shutil.which("adb") or ""

# mDNS services advertised by Android wireless debugging
PAIRING_SERVICE = "_adb-tls-pairing"
CONNECT_SERVICE = "_adb-tls-connect"


def run(*args: str, timeout: float = 15) -> str:
    """Run an adb command and return its combined output ("" on timeout)."""
    try:
        result = subprocess.run(
            [ADB, *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return ""
    return (result.stdout + result.stderr).strip()


def start_server() -> None:
    if not ADB:
        raise CastscriptError(
            "adb not found in PATH: install the Android platform-tools"
        )
    # No capture_output: the adb server keeps running in the background and,
    # inheriting the pipes, would keep subprocess.run waiting for them to close
    subprocess.run(
        [ADB, "start-server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def mdns_port(ip: str, service: str) -> int | None:
    """Port advertised via mDNS by `ip` for `service`, if any."""
    # Lines look like: adb-XXXX  _adb-tls-connect._tcp  192.168.1.14:39667
    for line in run("mdns", "services").splitlines():
        parts = line.split()
        if (
            len(parts) == 3
            and parts[1].startswith(service)
            and parts[2].startswith(f"{ip}:")
        ):
            return int(parts[2].rsplit(":", 1)[1])
    return None


def connect(ip: str, port: int) -> str | None:
    """Connect to `ip:port` and return its serial, or None if it fails."""
    serial = f"{ip}:{port}"
    run("connect", serial, timeout=10)
    if run("-s", serial, "get-state", timeout=5) == "device":
        return serial
    # A failed connect leaves an "offline" transport that would make the next
    # attempt answer "already connected": remove it
    run("disconnect", serial, timeout=5)
    return None


def pair(ip: str, port: int, code: str) -> str:
    """Pair with `ip:port` using the 6-digit code and return adb's output."""
    output = run("pair", f"{ip}:{port}", code, timeout=30)
    if "Successfully paired" not in output:
        raise CastscriptError(
            f"{output}\nPairing failed: reopen the pairing dialog on the TV and retry"
        )
    return output
