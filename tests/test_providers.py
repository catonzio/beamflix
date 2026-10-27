"""Tests for the choice of the streaming app among a title's offers."""

import pytest

from beamflix.errors import BeamflixError
from beamflix.justwatch import Offer, Title
from beamflix.providers import AppLink, choose

PROVIDERS = {
    "Netflix": "com.netflix.ninja",
    "Disney Plus": "com.disney.disneyplus",
    "Now TV": "com.nowtv.it",
}


def _title(*offers):
    return Title("Movie", 2020, [Offer(p, link) for p, link in offers])


def test_choose_returns_package_and_link_of_the_only_matching_provider():
    link = choose(_title(("Disney Plus", "intent://disney")), PROVIDERS)
    assert link == AppLink("Disney Plus", "com.disney.disneyplus", "intent://disney")


def test_choose_follows_provider_preference_not_offer_order():
    title = _title(("Now TV", "intent://now"), ("Netflix", "intent://nf"))
    assert choose(title, PROVIDERS).provider == "Netflix"


def test_choose_ignores_offers_from_apps_not_in_providers():
    title = _title(("Hulu", "intent://hulu"), ("Now TV", "intent://now"))
    assert choose(title, PROVIDERS).provider == "Now TV"


def test_choose_uses_configured_providers_by_default(monkeypatch):
    from beamflix import providers

    monkeypatch.setitem(providers.PROVIDERS, "Netflix", "pkg.test")
    assert choose(_title(("Netflix", "intent://nf"))).package == "pkg.test"


def test_choose_raises_listing_offers_when_no_provider_matches():
    title = _title(("Hulu", "intent://h"), ("Peacock", "intent://p"))
    with pytest.raises(BeamflixError) as exc:
        choose(title, PROVIDERS)
    assert str(exc.value) == "Not available on your apps (offers: Hulu, Peacock)"


def test_choose_raises_with_none_when_title_has_no_offers():
    with pytest.raises(BeamflixError, match=r"offers: none\)"):
        choose(_title(), PROVIDERS)


NOW_PDP = (
    "intent://www.nowtv.it/watch/vod/123"
    "?extra=%7B%22action%22%3A%22PDP%22%2C%22id%22%3A%22123%22%7D"
    "#Intent;scheme=https;package=com.nowtv.it;end"
)


def test_now_link_is_changed_from_title_page_to_play():
    link = choose(_title(("Now TV", NOW_PDP)), PROVIDERS).deeplink
    assert link == NOW_PDP.replace("%22PDP%22", "%22PLAY%22")
    assert "PDP" not in link
    assert "%22action%22%3A%22PLAY%22" in link


def test_links_without_pdp_action_are_left_untouched():
    other = "intent://www.netflix.com/title/80057281#Intent;package=com.netflix.ninja;end"
    assert choose(_title(("Netflix", other)), PROVIDERS).deeplink == other


def test_only_the_action_field_is_rewritten():
    link = "intent://x?a=%22PDP%22&b=%22action%22%3A%22PDP%22#Intent;end"
    out = choose(_title(("Netflix", link)), PROVIDERS).deeplink
    assert out == "intent://x?a=%22PDP%22&b=%22action%22%3A%22PLAY%22#Intent;end"


# Deep link returned by JustWatch for a NOW episode (October 2026)
NOW_REAL = (
    "intent://tv.client.ott.sky.com/deeplink?deeplinkData=%7B%22pvid%22%3A"
    "%22R_160706_HD%22%2C%22type%22%3A%22EPISODE%22%2C%22action%22%3A%22PDP%22%7D"
    "#Intent;launchFlags=0x00800000;scheme=https;end"
)


def test_real_justwatch_now_link_is_changed_to_play():
    link = choose(_title(("Now TV", NOW_REAL)), PROVIDERS).deeplink
    assert link == NOW_REAL.replace("%22action%22%3A%22PDP%22", "%22action%22%3A%22PLAY%22")


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ('"action":"PDP"', '"action":"PLAY"'),  # JSON not URL-encoded
        ("%22action%22%3a%22PDP%22", "%22action%22%3a%22PLAY%22"),  # lowercase hex
        ('"action": "PDP"', '"action": "PLAY"'),  # space after the colon
        ("%22action%22%3A%20%22PDP%22", "%22action%22%3A%20%22PLAY%22"),  # encoded space
        ('%22action%22:"PDP"', '%22action%22:"PLAY"'),  # mixed encoding
    ],
)
def test_pdp_action_is_rewritten_in_any_encoding_keeping_the_rest(action, expected):
    link = f"intent://x?data={{{action},%22id%22:1}}#Intent;end"
    out = choose(_title(("Now TV", link)), PROVIDERS).deeplink
    assert out == f"intent://x?data={{{expected},%22id%22:1}}#Intent;end"


@pytest.mark.parametrize(
    "action",
    ['"action":"PDPX"', '"action":"XPDP"', '"type":"PDP"', '"action":"PLAY"'],
)
def test_values_other_than_the_pdp_action_are_left_untouched(action):
    link = f"intent://x?data={{{action}}}#Intent;end"
    assert choose(_title(("Now TV", link)), PROVIDERS).deeplink == link
