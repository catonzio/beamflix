"""Choice of the streaming app to open among the offers of a title."""

import re
from dataclasses import dataclass

from beamflix.config import PROVIDERS
from beamflix.errors import BeamflixError
from beamflix.justwatch import Title


@dataclass
class AppLink:
    provider: str
    package: str
    deeplink: str


def choose(title: Title, providers: dict[str, str] = PROVIDERS) -> AppLink:
    """Pick the first offer, in order of preference, among the installed apps."""
    links = {offer.provider: offer.deeplink for offer in title.offers}
    provider = next((p for p in providers if p in links), None)
    if provider is None:
        available = ", ".join(links) or "none"
        raise BeamflixError(f"Not available on your apps (offers: {available})")
    return AppLink(provider, providers[provider], _autoplay(links[provider]))


# `"action":"PDP"` inside a deep link, with the JSON URL-encoded or not
# (e.g. %22action%22%3A%22PDP%22, hex digits in any case, optional spaces)
_PDP_ACTION = re.compile(
    r'((?:%22|")action(?:%22|")\s*(?i:%3A|:)(?:\s|%20)*(?:%22|"))PDP(%22|")'
)


def _autoplay(deeplink: str) -> str:
    # NOW links open the title page (PDP action): with PLAY the linked episode starts
    return _PDP_ACTION.sub(r"\1PLAY\2", deeplink)
