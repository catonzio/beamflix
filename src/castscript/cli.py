"""Command-line entry point: play a title or send a remote-control command."""

import argparse
import sys

from castscript import chromecast, justwatch, pairing, profiles, providers
from castscript.chromecast import REMOTE_KEYS, WIRELESS_DEBUGGING_PATH, Chromecast
from castscript.config import PROFILES
from castscript.errors import CastscriptError, ConnectionFailed

COMMANDS = [*REMOTE_KEYS, "clean", "restart"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="castscript",
        description="Play a movie or series on the Chromecast with Google TV.",
        epilog=f"remote-control commands: {', '.join(COMMANDS)}",
    )
    parser.add_argument(
        "words",
        nargs="+",
        metavar="title|command",
        help="title of a movie or series, or a remote-control command",
    )
    args = parser.parse_args(argv)

    try:
        # A single word matching a command is a command, anything else a title
        if len(args.words) == 1 and args.words[0].lower() in COMMANDS:
            remote(args.words[0].lower())
        else:
            play(" ".join(args.words))
    except CastscriptError as error:
        sys.exit(str(error))


def play(query: str) -> None:
    title = justwatch.search(query)
    if title is None:
        raise CastscriptError(f"No results for '{query}'")
    print(f"Found: {title.name} ({title.year})")

    link = providers.choose(title)
    print(f"Opening on {link.provider}: {link.deeplink}")

    device = connect()
    print(f"Connected to {device.serial}")
    print(device.launch(link.package, link.deeplink))

    profile = PROFILES.get(link.provider)
    if profile and profiles.select(device, link.package, profile):
        print(f"Selected profile: {profile}")


def remote(command: str) -> None:
    device = connect()
    if command == "clean":
        device.clean()
    elif command == "restart":
        device.clean()
        device.reboot()
    else:
        device.press(REMOTE_KEYS[command])
    print(f"Sent {command} to {device.serial}")

    if command == "restart":
        print(
            "The Chromecast is rebooting: once it is back, enable wireless "
            f"debugging again in {WIRELESS_DEBUGGING_PATH}"
        )


def connect() -> Chromecast:
    print("Connecting to the Chromecast...")
    try:
        return chromecast.connect()
    except ConnectionFailed:
        # With wireless debugging on, a refused connection means we are not paired
        pairing.pair()
        return chromecast.connect()
