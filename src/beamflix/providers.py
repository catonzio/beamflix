"""Choice of the streaming app to open among the offers of a title."""

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


def _autoplay(deeplink: str) -> str:
    # NOW links open the title page (PDP action): with PLAY the linked episode starts
    return deeplink.replace("%22action%22%3A%22PDP%22", "%22action%22%3A%22PLAY%22")
