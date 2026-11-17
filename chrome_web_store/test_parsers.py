"""Offline tests for the Chrome Web Store parsers, reference resolvers and
value helpers.

    python -m pytest chrome_web_store/test_parsers.py -q

Fixtures are real batchexecute payloads / updatecheck XML captured
2026-11-07 (chrome_web_store/fixtures/, see parsers.py). No network.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chrome_web_store import api, parsers as P, refs  # noqa: E402
from scraper_utils.testing import hosted_only

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
DR = "eimadpbcbfnmbkopoojfekhnkhdbieeh"


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


@pytest.fixture(scope="module")
def dark_reader():
    return P.parse_details(fixture("details_dark_reader.json"), DR)


@pytest.fixture(scope="module")
def honey():
    return P.parse_details(fixture("details_honey.json"))


@pytest.fixture(scope="module")
def theme():
    return P.parse_details(fixture("details_theme_material_dark_grey.json"))


@pytest.fixture(scope="module")
def sparse():
    return P.parse_details(fixture("details_shade_sparse.json"))


# ---- refs ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (DR, DR),
    (DR.upper(), DR),
    (f"https://chromewebstore.google.com/detail/dark-reader/{DR}", DR),
    (f"https://chromewebstore.google.com/detail/dark-reader/{DR}/reviews?hl=en", DR),
    (f"https://chromewebstore.google.com/detail/{DR}", DR),
    (f"https://chrome.google.com/webstore/detail/dark-reader/{DR}?hl=en", DR),
    (f"//chromewebstore.google.com/detail/x/{DR}", DR),
])
def test_resolve_item(value, expected):
    assert refs.resolve_item(value) == expected


@pytest.mark.parametrize("value", ["", "dark reader", "abc", "a" * 31, "q" * 32,
                                   "https://example.com/detail/x/" + DR,
                                   "https://chromewebstore.google.com/category/extensions"])
def test_resolve_item_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_item(value)


def test_resolve_publisher():
    pid = "u98cf52c4498e6ec420afdeb6bfdb56db"
    assert refs.resolve_publisher(pid) == ("publisher", pid)
    assert refs.resolve_publisher(pid.upper()) == ("publisher", pid)
    assert refs.resolve_publisher(f"https://chromewebstore.google.com/publisher/dark-reader-ltd/{pid}?hl=en") == \
        ("publisher", pid)
    assert refs.resolve_publisher(DR) == ("item", DR)
    assert refs.resolve_publisher(f"https://chromewebstore.google.com/detail/dark-reader/{DR}") == ("item", DR)
    for bad in ("", "u123", "https://chromewebstore.google.com/", "https://example.com/publisher/x/" + pid):
        with pytest.raises(ValueError):
            refs.resolve_publisher(bad)


@pytest.mark.parametrize("value,expected", [
    ("productivity/developer", (3, "productivity/developer")),
    ("Productivity/Developer", (3, "productivity/developer")),
    ("developer", (3, "productivity/developer")),
    ("extensions/lifestyle/games", (3, "lifestyle/games")),
    ("themes/dark", (4, "dark")),
    ("dark", (4, "dark")),
    ("games", (3, "lifestyle/games")),          # the extension category wins the bare name
    ("themes/games", (4, "games")),
    ("https://chromewebstore.google.com/category/extensions/make_chrome_yours/privacy?hl=en",
     (3, "make_chrome_yours/privacy")),
    ("https://chromewebstore.google.com/category/themes/space", (4, "space")),
])
def test_resolve_category(value, expected):
    assert refs.resolve_category(value) == expected


@pytest.mark.parametrize("value", ["", "productivity", "productivity/nope", "themes/nope",
                                   "https://chromewebstore.google.com/detail/x/" + DR,
                                   "https://example.com/category/extensions/productivity/developer"])
def test_resolve_category_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_category(value)


def test_resolve_collection():
    assert refs.resolve_collection("writing_essentials") == "writing_essentials"
    assert refs.resolve_collection("Writing_Essentials") == "writing_essentials"
    assert refs.resolve_collection("https://chromewebstore.google.com/collection/ai_assistants?hl=en") == \
        "ai_assistants"
    for bad in ("", "a b", "https://chromewebstore.google.com/detail/x/" + DR, "https://example.com/collection/x"):
        with pytest.raises(ValueError):
            refs.resolve_collection(bad)


def test_links_and_slugs():
    assert refs.slugify("AdBlock — block ads across the web") == "adblock-block-ads-across"
    assert refs.slugify("Dark Reader") == "dark-reader"
    assert refs.item_link(DR, "Dark Reader") == f"https://chromewebstore.google.com/detail/dark-reader/{DR}"
    assert refs.item_link(DR) == f"https://chromewebstore.google.com/detail/{DR}"
    assert refs.category_link("dark") == "https://chromewebstore.google.com/category/themes/dark"
    assert refs.category_link("productivity/tools").endswith("/category/extensions/productivity/tools")
    # 127 in the store's JS, 26 retired (no items on 2026-11-10) left out
    assert len(refs.COLLECTIONS) == 101
    assert not {"2020_gems", "wfh", "wordle", "test-collection"} & set(refs.COLLECTIONS)
    assert refs.COLLECTIONS["writing_essentials"] == ("Write like a pro", "Eliminate typos and grammatical errors")
    assert refs.category_label("lifestyle/well_being") == "Well-being"
    assert set(refs.CATEGORY_IDS[i] for i in (3, 25)) == {"productivity/communication", "dark"}


# ---- value helpers --------------------------------------------------------------------

def test_value_helpers():
    assert P.timestamp_to_iso([1404715859, 441000000]) == "2014-07-07T06:50:59Z"
    assert P.timestamp_to_iso(1404715859) == "2014-07-07T06:50:59Z"
    assert P.timestamp_to_iso(None) is None
    assert P.timestamp_to_iso([0, 0]) is None
    assert P.size_to_bytes("839KiB") == 859136
    assert P.size_to_bytes("76.22MiB") == 79922462
    assert P.size_to_bytes("1.5GB") == 1500000000
    assert P.size_to_bytes("abc") is None
    assert P.size_to_bytes(None) is None
    assert P.parse_manifest('{"version": "1.0"}') == {"version": "1.0"}
    assert P.parse_manifest("not json") is None
    assert P.parse_manifest(None) is None
    assert P.is_card(["a" * 32, None, "Name"] + [None] * 17)
    assert not P.is_card(["a" * 31, None, "Name"] + [None] * 17)
    assert not P.is_card("x")


# ---- details ----------------------------------------------------------------------------

def test_details_identity_and_card_fields(dark_reader):
    d = dark_reader
    assert d["id"] == DR
    assert d["name"] == "Dark Reader"
    assert d["link"] == f"https://chromewebstore.google.com/detail/dark-reader/{DR}"
    assert d["type"] == "extension"
    assert d["summary"].startswith("Dark mode for every website")
    assert d["rating"] == 4.3 and d["rating_count"] == 13280 and d["users"] == 7000000
    assert d["category"] == {"id": 20, "slug": "make_chrome_yours/accessibility", "name": "Accessibility",
                             "link": "https://chromewebstore.google.com/category/extensions/make_chrome_yours/accessibility"}
    assert d["is_featured"] is True and d["is_established_publisher"] is True and d["is_by_google"] is False
    assert d["website"] == "https://darkreader.org/"
    assert d["images"]["icon"].startswith("https://lh3.googleusercontent.com/")
    assert d["published_at"] == "2014-07-07T06:50:59Z"
    assert "rank" not in d


def test_details_version_block(dark_reader):
    d = dark_reader
    assert d["version"] == "4.9.135"
    assert d["manifest_version"] == 3
    assert d["minimum_chrome_version"] == "106.0.0.0"
    assert d["updated_at"] == "2026-11-06T11:24:40Z"
    assert d["size"] == "839KiB" and d["size_bytes"] == 859136
    assert "Deutsch" in d["languages"] and len(d["languages"]) == 39
    assert "pt-BR" in d["language_codes"] and len(d["language_codes"]) == 39
    assert d["permissions"] == ["alarms", "fontSettings", "scripting", "storage"]
    assert d["host_permissions"] == ["*://*/*"]
    assert d["optional_permissions"] == ["contextMenus"]
    assert d["manifest"]["name"] == "Dark Reader"
    assert d["manifest"]["update_url"] == "https://clients2.google.com/service/update2/crx"


def test_details_description_media_links(dark_reader):
    d = dark_reader
    assert d["description"].startswith("This eye-care extension")
    assert d["media"][0] == {"type": "video", "link": "https://www.youtube.com/embed/849mznBKmIQ?rel=0&wmode=opaque&enablejsapi=1"}
    assert len(d["media"]) == 5 and d["media"][1]["type"] == "image"
    assert d["links"] == {
        "store": d["link"],
        "reviews": d["link"] + "/reviews",
        "support": d["link"] + "/support",
        "privacy": d["link"] + "/privacy",
    }


def test_details_developer_and_privacy(dark_reader):
    dev = dark_reader["developer"]
    assert dev == {
        "name": "Alexander Shutau",
        "legal_name": "Alexander Shutau",
        "email": "support@darkreader.org",
        "phone": "+447585769555",
        "address": "Office 40 Unit 5\n399-405 Oxford Street\nLondon W1C 2BU\nGB",
        "website": "https://darkreader.org/",
        "duns_number": "227992692",
        "is_trader": True,
        "publisher": {"id": "u98cf52c4498e6ec420afdeb6bfdb56db", "name": "Dark Reader Ltd",
                      "link": "https://chromewebstore.google.com/publisher/dark-reader-ltd/u98cf52c4498e6ec420afdeb6bfdb56db"},
    }
    assert dark_reader["privacy"] == {"policy_link": "https://darkreader.org/privacy/",
                                      "collects_data": False, "data_collected": []}


def test_details_related(dark_reader):
    related = dark_reader["related"]
    assert dark_reader["related_count"] == len(related) == 12
    assert related[0]["id"] == "dmghijelimhndkbmpgbldicpogfkceaj" and related[0]["name"] == "Dark Mode"
    assert "rank" not in related[0]
    assert related[0]["version"] == "0.5.9"


def test_details_honey_privacy_codes(honey):
    assert honey["privacy"]["collects_data"] is True
    assert honey["privacy"]["data_collected"] == [
        "personally_identifiable_information", "financial_and_payment_information", "location",
        "web_history", "user_activity", "website_content"]
    assert honey["developer"]["duns_number"] is None and honey["developer"]["phone"] is None
    assert honey["developer"]["is_trader"] is False
    assert honey["developer"]["publisher"]["name"] == "PayPal Inc."


def test_details_theme(theme):
    assert theme["type"] == "theme"
    assert theme["name"] == "Material Simple Dark Grey"
    assert theme["permissions"] == [] and theme["host_permissions"] == []
    assert theme["manifest_version"] == 2
    assert theme["media"] == [{"type": "image", "link": theme["media"][0]["link"]}]
    assert theme["developer"]["name"] == "bd" and theme["developer"]["email"] is None
    assert theme["developer"]["publisher"]["link"].endswith("/publisher/bd/ub5209f72cc15902d562cf8fc1d140f98")
    assert theme["languages"] == ["English (United States)"]
    assert theme["privacy"] == {"policy_link": None, "collects_data": False, "data_collected": []}


def test_details_sparse_developer(sparse):
    dev = sparse["developer"]
    assert dev["name"] == "Cherish Aguirre"
    assert dev["email"] == "cherishago6062@gmail.com"
    assert dev["legal_name"] is None and dev["address"] is None and dev["website"] is None
    assert dev["publisher"]["link"].endswith("/publisher/cherish-aguirre/ud059cc2a09f1225105f8b41b483f8a7f")
    assert sparse["is_featured"] is True and sparse["is_established_publisher"] is False


def test_details_localized():
    de = P.parse_details(fixture("details_dark_reader_de.json"))
    assert de["summary"].startswith("Dunkler Modus")
    assert de["name"] == "Dark Reader"


def test_details_never_crashes_on_junk():
    assert P.parse_details([]) is None
    assert P.parse_details(None) is None
    assert P.parse_details([["x"]]) is None
    tiny = P.parse_details([["a" * 32, None, "Tiny"] + [None] * 17])
    assert tiny["name"] == "Tiny" and tiny["developer"] is None and tiny["manifest"] is None
    assert tiny["privacy"]["collects_data"] is False and tiny["media"] == [] and tiny["related"] == []


def test_replacements():
    rows = P.parse_replacements(fixture("replacements_ublock_origin.json"))
    assert [r["name"] for r in rows][:2] == ["uBlock Origin Lite", "AdBlock — block ads across the web"]
    assert "rank" not in rows[0]


# ---- reviews ------------------------------------------------------------------------------

def test_reviews_lowest_all_languages():
    parsed = P.parse_reviews(fixture("reviews_dark_reader_lowest_all.json"))
    assert len(parsed["reviews"]) == 100
    assert parsed["total"] == 8170
    assert parsed["next_token"].startswith("AdY0PI")
    assert {r["rating"] for r in parsed["reviews"]} == {1}
    assert len({r["language"] for r in parsed["reviews"]}) > 3
    with_reply = [r for r in parsed["reviews"] if r["developer_reply"]]
    assert len(with_reply) == 7
    r = next(x for x in with_reply if x["id"] == "c2324ce9-949b-42c7-bcfd-03060c0c8f21")
    assert r == {
        "id": "c2324ce9-949b-42c7-bcfd-03060c0c8f21",
        "link": f"https://chromewebstore.google.com/detail/{DR}/reviews/c2324ce9-949b-42c7-bcfd-03060c0c8f21",
        "rating": 1,
        "text": "Crashing GPUs now. Please fix!",
        "author": {"name": "Nikhil Kundra", "avatar": r["author"]["avatar"]},
        "created_at": "2026-09-11T15:33:04Z",
        "updated_at": "2026-09-11T15:33:04Z",
        "helpful_count": 4,
        "unhelpful_count": 3,
        "version": "4.9.130",
        "language": "en",
        "developer_reply": {
            "id": "023d47e2-e9a3-48b5-a3d9-16a39e0ba45c",
            "author": {"name": "Alexander Shutau", "avatar": r["developer_reply"]["author"]["avatar"]},
            "text": "Please submit more details to support@darkreader.org",
            "created_at": "2026-09-14T18:56:53Z",
            "updated_at": "2026-09-14T18:56:53Z",
            "language": "en",
        },
    }
    assert r["author"]["avatar"].startswith("https://lh3.googleusercontent.com/")


def test_reviews_recent_first_page_and_named_links():
    parsed = P.parse_reviews(fixture("reviews_dark_reader_recent_page1.json"), item_name="Dark Reader")
    assert len(parsed["reviews"]) == 10
    assert parsed["total"] == 5624     # English only (no language filter follows hl=en)
    first = parsed["reviews"][0]
    assert first["link"].startswith(f"https://chromewebstore.google.com/detail/dark-reader/{DR}/reviews/")
    assert first["developer_reply"] is None
    assert first["helpful_count"] >= 0


def test_reviews_unknown_item_is_an_empty_page():
    assert P.parse_reviews(fixture("reviews_unknown_item.json")) == {"reviews": [], "next_token": None, "total": None}
    assert P.parse_reviews(None) == {"reviews": [], "next_token": None, "total": None}
    assert P.parse_review([None]) is None


# ---- lists ---------------------------------------------------------------------------------

def test_search_pages():
    page1 = P.parse_search(fixture("search_ad_blocker_page1.json"))
    page2 = P.parse_search(fixture("search_ad_blocker_page2.json"))
    assert page1["total"] == 368 and page2["total"] == 368
    assert len(page1["items"]) == 20 and len(page2["items"]) == 20
    assert page1["next_token"] and page2["next_token"]
    assert not ({r["id"] for r in page1["items"]} & {r["id"] for r in page2["items"]})
    top = page1["items"][0]
    assert top["rank"] == 1 and top["id"] == "gighmmpiobklfepjocnamgkkbiglidom"
    assert top["name"] == "AdBlock — block ads across the web"
    assert top["link"] == "https://chromewebstore.google.com/detail/adblock-block-ads-across/gighmmpiobklfepjocnamgkkbiglidom"
    assert top["version"] == "6.52.0" and top["manifest_version"] == 3
    assert "alarms" in top["permissions"] and top["users"] == 65000000
    assert top["is_established_publisher"] is True and top["is_featured"] is False
    assert "manifest" not in top and "description" not in top
    assert [r["rank"] for r in page1["items"]] == list(range(1, 21))


def test_search_no_results_and_themes():
    assert P.parse_search(fixture("search_no_results.json")) == {"items": [], "next_token": None, "total": 0}
    themes = P.parse_search(fixture("search_themes_dark_min4.json"))
    assert themes["items"] and all(r["type"] == "theme" and r["rating"] >= 4 for r in themes["items"])
    assert P.parse_search(None) == {"items": [], "next_token": None, "total": None}


def test_category_pages():
    parsed = P.parse_category(fixture("category_developer_highest.json"))
    assert len(parsed["items"]) == 20 and parsed["next_token"]
    assert parsed["items"][0]["name"] == "ColorZilla"
    assert all(r["category"]["slug"] == "productivity/developer" for r in parsed["items"])
    themes = P.parse_category(fixture("category_theme_dark.json"))
    assert len(themes["items"]) == 10 and all(r["type"] == "theme" for r in themes["items"])
    assert P.parse_category(fixture("category_unknown.json")) is None
    assert P.parse_category(None) is None


def test_chart_and_collection():
    chart = P.parse_chart(fixture("chart_popular.json"))
    assert len(chart) == 25 and chart[0]["rank"] == 1 and chart[0]["name"] == "Volume Master"
    rows = P.parse_collection(fixture("collection_ai_assistants.json"))
    assert len(rows) == 10 and rows[0]["rank"] == 1
    assert [r["name"] for r in rows][:2] == ["Monica: All-In-One AI Assist & Smartest  AI Agent",
                                             "Sider: Chat with all AI: GPT-5, Claude, DeepSeek, Gemini, Grok"]
    assert P.parse_collection(fixture("collection_unknown.json")) is None
    assert P.parse_collection(None) == []


# ---- publisher / categories / update check ------------------------------------------------------

def test_publisher():
    pub = P.parse_publisher(fixture("publisher_dark_reader_ltd.json"))
    assert pub["id"] == "u98cf52c4498e6ec420afdeb6bfdb56db"
    assert pub["name"] == "Dark Reader Ltd"
    assert pub["display_name"] == "Alexander Shutau"
    assert pub["link"] == "https://chromewebstore.google.com/publisher/dark-reader-ltd/u98cf52c4498e6ec420afdeb6bfdb56db"
    assert pub["email"] == "support@darkreader.org" and pub["duns_number"] == "227992692" and pub["is_trader"] is True
    assert pub["items_count"] == 2 and [r["name"] for r in pub["items"]] == ["Dark Reader", "Replacer"]
    assert "rank" not in pub["items"][0] and "website" not in pub
    assert P.parse_publisher(fixture("publisher_unknown.json")) is None
    assert P.parse_publisher([]) is None


def test_categories():
    ext = P.parse_categories(fixture("categories_extensions.json"), 1)
    themes = P.parse_categories(fixture("categories_themes.json"), 2)
    assert len(ext) == 18 and len(themes) == 12
    assert ext[0] == {"id": 3, "slug": "productivity/communication", "name": "Communication", "type": "extension",
                      "group": {"id": 2, "slug": "productivity", "name": "Productivity"},
                      "link": "https://chromewebstore.google.com/category/extensions/productivity/communication"}
    assert themes[0]["slug"] == "dark" and themes[0]["group"]["slug"] == "themes" and themes[0]["type"] == "theme"
    assert all(r["name"] for r in ext + themes)
    assert P.parse_categories([], 1) == []


def test_updatecheck():
    ok = P.parse_updatecheck(fixture("updatecheck_dark_reader.xml"))
    assert ok["status"] == "ok" and ok["version"] == "4.9.135" and ok["size_bytes"] == 858730
    assert ok["sha256"] == "0b7857ae92fd3aeab4292bb755aa0f108de6b68bc12f18d0c87fe757cdd40a9d"
    assert ok["link"].endswith("/EIMADPBCBFNMBKOPOOJFEKHNKHDBIEEH_4_9_135_0.crx")
    assert P.parse_updatecheck(fixture("updatecheck_unknown.xml")) is None
    removed = P.parse_updatecheck(fixture("updatecheck_removed_ublock_origin.xml"))
    assert removed["status"] == "noupdate" and removed["link"] is None
    assert P.parse_updatecheck("") is None


# ---- api: the token walk ----------------------------------------------------------------------

def test_walk_pages_follows_and_remembers_tokens():
    calls = []

    def fetch_page(token):
        calls.append(token)
        n = 1 if token is None else int(token[1:])
        return {"page": n}, (f"t{n + 1}" if n < 3 else None)

    key = ("test", id(calls))
    assert api.walk_pages(key, 3, fetch_page) == ({"page": 3}, None)
    assert calls == [None, "t2", "t3"]
    # the memo: page 2 now costs one call
    assert api.walk_pages(key, 2, fetch_page) == ({"page": 2}, "t3")
    assert calls[-1] == "t2"
    # past the end: an empty page, not an error
    assert api.walk_pages(key, 5, fetch_page) == (None, None)


def test_pagination_stops_at_the_page_cap():
    # 20,274 Grammarly reviews: 203 store pages, but the schema allows 200
    assert api._pagination(200, 100, "tok", 200, total=20274) == {
        "page": 200, "items_per_page": 100, "has_next": False, "total_pages": 200, "total_count": 20274}
    assert api._pagination(199, 100, "tok", 200, total=20274)["has_next"] is True
    block = api._pagination(2, 50, "tok", 20, total=369)
    assert block["has_next"] is True and block["total_pages"] == 8 and block["total_count"] == 369
    # category lists publish no total
    assert api._pagination(80, 50, "tok", 80, has_total=False) == {
        "page": 80, "items_per_page": 50, "has_next": False, "total_pages": None, "total_count": None}
    assert api._pagination(3, 50, "tok", 80, has_total=False)["has_next"] is True
    assert api._pagination(1, 50, None, 20, total=0) == {
        "page": 1, "items_per_page": 50, "has_next": False, "total_pages": 0, "total_count": 0}


@hosted_only
def test_consent_cookies_ride_the_gateway_sessions_own_jar():
    # exit_gateway.Session passes a per-request cookies= to the inner curl
    # session, whose jar belongs to the gateway's own host
    from chrome_web_store import fetch
    state = fetch._new_state("gateway")
    try:
        assert state["cookies"] is None
        header = state["session"].cookies.header_for("chromewebstore.google.com")
        assert all(f"{name}={value}" in header for name, value in fetch.CONSENT_COOKIES.items())
        assert state["session"].cookies.header_for("clients2.google.com") is None
    finally:
        state["session"].close()
    state = fetch._new_state(None)
    try:
        assert state["cookies"] == fetch.CONSENT_COOKIES and len(state["session"].cookies) == 0
    finally:
        state["session"].close()
