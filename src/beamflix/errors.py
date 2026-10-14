class BeamflixError(Exception):
    """Expected failure, reported to the user without a traceback."""


class ConnectionFailed(BeamflixError):
    """The Chromecast refused the adb connection (usually: not paired yet)."""
