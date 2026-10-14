import json
import urllib.request
from dataclasses import dataclass

# API GraphQL pubblica ma non ufficiale di JustWatch: può cambiare senza preavviso
API_URL = "https://apis.justwatch.com/graphql"
COUNTRY = "IT"
LANGUAGE = "it"

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


@dataclass
class Offer:
    provider: str
    deeplink: str  # URI intent:// pronto per `am start`


@dataclass
class Title:
    name: str
    year: int | None
    offers: list[Offer]


def search(query: str) -> Title | None:
    body = json.dumps(
        {
            "query": QUERY,
            "variables": {"q": query, "country": COUNTRY, "language": LANGUAGE},
        }
    ).encode()
    req = urllib.request.Request(
        API_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        edges = json.load(r)["data"]["popularTitles"]["edges"]
    if not edges:
        return None

    node = edges[0]["node"]
    offers = [
        Offer(o["package"]["clearName"], o["deeplinkURL"])
        for o in node["offers"]
        # Solo i contenuti inclusi nell'abbonamento, gratuiti o con pubblicità
        if o["deeplinkURL"] and o["monetizationType"] in ("FLATRATE", "FREE", "ADS")
    ]
    return Title(
        node["content"]["title"], node["content"]["originalReleaseYear"], offers
    )
