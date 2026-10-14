"""Title search on JustWatch, returning the Android TV deep links of each offer."""

import json
import urllib.request
from dataclasses import dataclass

from castscript.config import JUSTWATCH_COUNTRY, JUSTWATCH_LANGUAGE

# Public but unofficial JustWatch GraphQL API: it may change without notice
API_URL = "https://apis.justwatch.com/graphql"

QUERY = """
query ($q: String!, $country: Country!, $language: Language!) {
  popularTitles(country: $country, first: 1, filter: {searchQuery: $q}) {
    edges {
      node {
        ... on MovieOrShow {
          content(country: $country, language: $language) {
            title
            originalReleaseYear
          }
        }
        offers(country: $country, platform: WEB) {
          monetizationType
          package { clearName }
          deeplinkURL(platform: ANDROID_TV)
        }
      }
    }
  }
}
"""

# Only content included in a subscription, free or ad-supported (no rent/buy)
INCLUDED_MONETIZATION_TYPES = ("FLATRATE", "FREE", "ADS")


@dataclass
class Offer:
    provider: str
    deeplink: str  # intent:// URI, ready for `am start`


@dataclass
class Title:
    name: str
    year: int | None
    offers: list[Offer]


def search(
    query: str,
    country: str = JUSTWATCH_COUNTRY,
    language: str = JUSTWATCH_LANGUAGE,
) -> Title | None:
    """Return the most popular title matching `query`, or None if nothing matches."""
    data = _graphql(QUERY, {"q": query, "country": country, "language": language})
    edges = data["popularTitles"]["edges"]
    if not edges:
        return None
    return _parse_title(edges[0]["node"])


def _graphql(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(
        API_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)["data"]


def _parse_title(node: dict) -> Title:
    offers = [
        Offer(offer["package"]["clearName"], offer["deeplinkURL"])
        for offer in node["offers"]
        if offer["deeplinkURL"]
        and offer["monetizationType"] in INCLUDED_MONETIZATION_TYPES
    ]
    content = node["content"]
    return Title(content["title"], content["originalReleaseYear"], offers)
