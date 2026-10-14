"""Command-line entry point: search a title and play it on the Chromecast."""

import argparse
import sys

from castscript import chromecast, justwatch, pairing, profiles, providers
from castscript.chromecast import Chromecast
from castscript.config import PROFILES
from castscript.errors import CastscriptError, ConnectionFailed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="castscript",
        description="Play a movie or series on the Chromecast with Google TV.",
    )
    parser.add_argument("title", nargs="+", help="title of a movie or series")
    args = parser.parse_args(argv)

    try:
        play(" ".join(args.title))
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


def connect() -> Chromecast:
    print("Connecting to the Chromecast...")
    try:
        return chromecast.connect()
    except ConnectionFailed:
        # With wireless debugging on, a refused connection means we are not paired
        pairing.pair()
        return chromecast.connect()
