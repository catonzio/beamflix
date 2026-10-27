"""Tests for the JustWatch search: request shape, offer filtering, no-result handling."""

import io
import json
from unittest.mock import MagicMock

import pytest

from beamflix import justwatch
from beamflix.justwatch import Offer, Title


def _offer(kind, provider, link="intent://x#Intent;end"):
    return {
        "monetizationType": kind,
        "package": {"clearName": provider},
        "deeplinkURL": link,
    }


def _response(offers, title="Stranger Things", year=2016):
    return {
        "data": {
            "popularTitles": {
                "edges": [
                    {
                        "node": {
                            "content": {"title": title, "originalReleaseYear": year},
                            "offers": offers,
                        }
                    }
                ]
            }
        }
    }


@pytest.fixture
def urlopen(monkeypatch):
    """Patch urllib.request.urlopen; set `.payload` to the JSON the API returns."""
    mock = MagicMock()
    mock.payload = {}

    def fake(request, timeout=None):
        response = io.BytesIO(json.dumps(mock.payload).encode())
        mock.requests.append(request)
        return MagicMock(__enter__=lambda s: response, __exit__=lambda *a: False)

    mock.requests = []
    mock.side_effect = fake
    monkeypatch.setattr(justwatch.urllib.request, "urlopen", mock)
    return mock


def test_search_returns_title_name_year_and_offers(urlopen):
    urlopen.payload = _response(
        [_offer("FLATRATE", "Netflix", "intent://netflix#Intent;end")]
    )
    assert justwatch.search("stranger things") == Title(
        "Stranger Things", 2016, [Offer("Netflix", "intent://netflix#Intent;end")]
    )


def test_search_sends_json_post_to_graphql_api(urlopen):
    urlopen.payload = _response([])
    justwatch.search("the bear")
    (request,) = urlopen.requests
    assert request.full_url == "https://apis.justwatch.com/graphql"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    body = json.loads(request.data)
    assert body["query"] == justwatch.QUERY
    assert body["variables"]["q"] == "the bear"


def test_search_uses_configured_country_and_language_by_default(urlopen, monkeypatch):
    urlopen.payload = _response([])
    monkeypatch.setattr(justwatch, "JUSTWATCH_COUNTRY", "IT", raising=True)
    justwatch.search("x")
    variables = json.loads(urlopen.requests[0].data)["variables"]
    assert variables["country"] == "IT"
    assert variables["language"] == "it"


def test_search_explicit_country_and_language_are_sent(urlopen):
    urlopen.payload = _response([])
    justwatch.search("x", country="US", language="en")
    variables = json.loads(urlopen.requests[0].data)["variables"]
    assert variables == {"q": "x", "country": "US", "language": "en"}


def test_search_sets_a_network_timeout(urlopen):
    urlopen.payload = _response([])
    justwatch.search("x")
    assert urlopen.call_args.kwargs["timeout"] > 0


def test_search_returns_none_when_there_are_no_results(urlopen):
    urlopen.payload = {"data": {"popularTitles": {"edges": []}}}
    assert justwatch.search("zzzz no such title") is None


def test_search_uses_only_the_first_result(urlopen):
    first = _response([_offer("FLATRATE", "Netflix")], title="First")
    second = _response([_offer("FLATRATE", "Disney Plus")], title="Second")
    first["data"]["popularTitles"]["edges"] += second["data"]["popularTitles"]["edges"]
    urlopen.payload = first
    assert justwatch.search("x").name == "First"


@pytest.mark.parametrize("kind", ["FLATRATE", "FREE", "ADS"])
def test_included_monetization_types_are_kept(urlopen, kind):
    urlopen.payload = _response([_offer(kind, "Netflix")])
    assert [o.provider for o in justwatch.search("x").offers] == ["Netflix"]


@pytest.mark.parametrize("kind", ["RENT", "BUY", "CINEMA", "CINEMA_TICKET"])
def test_rent_and_buy_offers_are_dropped(urlopen, kind):
    urlopen.payload = _response([_offer(kind, "Apple TV")])
    assert justwatch.search("x").offers == []


@pytest.mark.parametrize("link", [None, ""])
def test_offers_without_deeplink_are_dropped(urlopen, link):
    urlopen.payload = _response([_offer("FLATRATE", "Netflix", link)])
    assert justwatch.search("x").offers == []


def test_mixed_offers_keep_order_of_the_included_ones(urlopen):
    urlopen.payload = _response(
        [
            _offer("BUY", "Apple TV", "intent://apple"),
            _offer("ADS", "Pluto", "intent://pluto"),
            _offer("FLATRATE", "Netflix", "intent://nf"),
            _offer("RENT", "Google Play", "intent://gp"),
        ]
    )
    assert [o.provider for o in justwatch.search("x").offers] == ["Pluto", "Netflix"]


def test_year_may_be_missing(urlopen):
    urlopen.payload = _response([], year=None)
    assert justwatch.search("x").year is None
