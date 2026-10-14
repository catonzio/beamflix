class CastscriptError(Exception):
    """Expected failure, reported to the user without a traceback."""


class ConnectionFailed(CastscriptError):
    """The Chromecast refused the adb connection (usually: not paired yet)."""
