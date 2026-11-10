"""Chrome Web Store transport: plain curl_cffi with chrome TLS. No browser,
no login, no tokens, no cookies beyond the EU consent skip. Egress: one
sticky proxy exit per thread session when config.chrome_web_store_proxy()
returns one (in production a datacenter exit, owner decision 2026-11-07),
direct otherwise. A retryable failure drops the session, so the retry rides
a fresh exit.

Everything the store shows is served by ONE cookie-free endpoint, the same
batchexecute RPC its own JavaScript calls (validated 2026-11-07, no
anti-bot on any surface, 60 RPCs at concurrency 10 in 5.7 s all 200):

  RPC   POST /_/ChromeWebStoreConsumerFeUi/data/batchexecute?rpcids=<id>&hl=<lang>&rt=c
        form f.req=[[["<id>","<json>",null,"generic"]]]
          zTyKYc  search / category list / charts / collection (card lists
                  with a continuation token; search also carries the total)
          xY2Ddd  item details (the 20-field card + description, media,
                  developer block, version, size, languages, privacy, manifest)
          x1DgCd  reviews (sort, star filter, language filter, page size up
                  to 500, token, total)
          N3gGhc  publisher profile + every listed item
          CWFOxc  the category vocabulary (1 extensions, 2 themes)
          GApdCe  the store's suggested replacements for a removed item
        rt=c chunked replies: )]}' then length-prefixed JSON lines of
        envelopes ["wrb.fr", rpcid, "<payload json>"] or an error envelope
        ["wrb.fr", rpcid, null, null, null, [code, ...]]: 3 = malformed id
        (INVALID_ARGUMENT), 5 = unknown item (NOT_FOUND), 7 = the item was
        removed from the store. An unknown publisher id answers `[[]]`, an
        unknown category / collection slug an empty payload, and reviews of
        an unknown item (or with a bad token) `[]`.

  CRX   GET clients2.google.com/service/update2/crx?response=updatecheck&x=id%3D<id>%26v%3D0.0%26uc
        the installer's own update check: version, size, sha256 and the
        download link of the current package (XML). An unknown id answers
        status="error-unknownApplication", a removed item "noupdate".

`gl` has no effect on any RPC; `hl` localizes names, summaries and
descriptions and, without an explicit language filter, the reviews. From an
EU exit the HTML pages redirect to consent.google.com; the RPC never does,
and the consent cookies are sent anyway (harmless on a US exit).

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  ChromeWebStoreUpstreamError  transport failure / 5xx / unparseable  — retryable
  ChromeWebStoreBlocked        403 / 429 / captcha / consent wall     — retryable on a fresh exit
  ChromeWebStoreBadRequest     RPC code 3 (malformed id)              — never retried
  ChromeWebStoreNotFound       RPC code 5 / empty answer for an id    — never retried
  ChromeWebStoreRemoved        RPC code 7 (delisted item)             — never retried (a NotFound)
"""
import json
import os
import re
import sys
import threading
import time
from urllib.parse import urlencode

# Allow direct execution (python chrome_web_store/fetch.py): flat imports
# resolve like under the server. Idempotent when imported normally.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import egress
import fastjson
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from chrome_web_store.refs import SITE

IMPERSONATE = "chrome"
RPC_TIMEOUT = 40
CRX_TIMEOUT = 20
BATCH_PATH = "/_/ChromeWebStoreConsumerFeUi/data/batchexecute"
UPDATE_URL = "https://clients2.google.com/service/update2/crx"

RPC_LIST = "zTyKYc"
RPC_DETAILS = "xY2Ddd"
RPC_REVIEWS = "x1DgCd"
RPC_PUBLISHER = "N3gGhc"
RPC_CATEGORIES = "CWFOxc"
RPC_REPLACEMENTS = "GApdCe"

# The EU consent interstitial skip (the same cookies the Google Play module
# sends); the RPC never needs them, the cookies are harmless on a US exit.
CONSENT_COOKIES = {"CONSENT": "YES+cb", "SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmVuIAEaBgiA_LyaBg"}

RPC_HEADERS = {
    "accept": "*/*",
    "accept-language": egress.site_accept_language("chrome-web-store"),
    "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    "origin": SITE,
    "referer": SITE + "/",
    "x-same-domain": "1",
}
CRX_HEADERS = {
    "accept": "*/*",
    "accept-language": egress.site_accept_language("chrome-web-store"),
}

_BLOCK_MARKERS = ("unusual traffic", "/sorry/", "recaptcha", "captcha-form")


class ChromeWebStoreUpstreamError(UpstreamError):
    """Transport failure, 5xx, empty or unparseable answer — retryable."""


class ChromeWebStoreBlocked(ChromeWebStoreUpstreamError, Blocked):
    """403 / 429 / captcha / consent wall — retried on a fresh exit."""


class ChromeWebStoreBadRequest(BadRequest):
    """The store rejected the request parameters (RPC code 3) — never retried."""


class ChromeWebStoreNotFound(NotFound):
    """No such item / publisher / category / collection — never retried."""


class ChromeWebStoreRemoved(ChromeWebStoreNotFound):
    """The item existed but was removed from the store (RPC code 7). The
    details endpoint turns this into a 404 that names the replacements."""


# ---- the wire format ---------------------------------------------------------------

def decode_chunks(text):
    """rt=c body -> (payloads, errors). payloads: decoded wrb.fr payloads in
    order; errors: [(code, has_details)] from error envelopes, plus
    ('http', status) from "er" envelopes."""
    payloads, errors = [], []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("[["):
            continue
        try:
            envelopes = fastjson.loads(line)
        except ValueError:
            continue
        for env in envelopes:
            if not isinstance(env, list) or not env:
                continue
            if env[0] == "wrb.fr":
                raw = env[2] if len(env) > 2 else None
                if isinstance(raw, str):
                    try:
                        payloads.append(fastjson.loads(raw))
                    except ValueError:
                        pass
                elif len(env) > 5 and isinstance(env[5], list) and env[5]:
                    errors.append((env[5][0], len(env[5]) > 2 and bool(env[5][2])))
            elif env[0] == "er":
                errors.append(("http", env[5] if len(env) > 5 else None))
    return payloads, errors


# ---- sessions ------------------------------------------------------------------------

# One curl session per cheroot worker thread (a curl handle must not be
# shared across threads); its Accept-Language is the exit's.
_local = threading.local()


def _new_state(proxy):
    from curl_cffi import requests as curl_requests
    sess = curl_requests.Session(impersonate=IMPERSONATE)
    if proxy:
        sess.proxies = {"http": proxy, "https": proxy}
    language = egress.accept_language(proxy)
    return {
        "session": sess,
        "proxy": proxy,
        "rpc_headers": {**RPC_HEADERS, "accept-language": language},
        "crx_headers": {**CRX_HEADERS, "accept-language": language},
    }


def _state():
    state = getattr(_local, "state", None)
    if state is None:
        state = _local.state = _new_state(config.chrome_web_store_proxy())
    return state


def _drop_session():
    """Close the thread's session so the retry rides a fresh exit."""
    state = getattr(_local, "state", None)
    _local.state = None
    if state is not None:
        try:
            state["session"].close()
        except Exception:
            pass


def _retrying(fn, label):
    """Run fn() under the shared retry policy (ChromeWebStoreUpstreamError
    only, Blocked included, each retry on a fresh session / exit; BadRequest
    and NotFound surface immediately)."""
    last = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return fn()
        except ChromeWebStoreUpstreamError as e:
            last = e
            _drop_session()
        print(f"chrome-web-store: {label} attempt {attempt}/{config.MAX_RETRIES} failed: {last}")
        if attempt < config.MAX_RETRIES:
            time.sleep(config.RETRY_BACKOFF * attempt)
    raise last


def _classify(resp, label):
    """Map an HTTP response to the error taxonomy; return the body text."""
    if resp.status_code == 404:
        raise ChromeWebStoreNotFound(f"{label} not found")
    if resp.status_code == 400:
        raise ChromeWebStoreBadRequest(f"the store rejected {label}")
    if resp.status_code in (401, 403, 429):
        raise ChromeWebStoreBlocked(f"HTTP {resp.status_code} for {label}")
    if resp.status_code != 200:
        raise ChromeWebStoreUpstreamError(f"HTTP {resp.status_code} for {label}")
    text = resp.text
    final = str(resp.url)
    if "consent.google" in final:
        raise ChromeWebStoreBlocked(f"consent interstitial for {label}")
    if "/sorry/" in final or any(m in text[:20000] for m in _BLOCK_MARKERS[:1]):
        raise ChromeWebStoreBlocked(f"captcha page for {label}")
    return text


# ---- RPCs ----------------------------------------------------------------------------

def _raise_rpc_errors(errors, rpcid, label):
    """batchexecute error envelopes -> taxonomy (gRPC canonical codes, with
    the store's own meaning for 7)."""
    for err in errors:
        if err[0] == "http":
            status = err[1]
            if status in (401, 403, 429):
                raise ChromeWebStoreBlocked(f"{label}: HTTP {status}")
            raise ChromeWebStoreUpstreamError(f"{label}: HTTP {status}")
        code = err[0]
        if code == 3:
            raise ChromeWebStoreBadRequest(f"the store rejected {label} (malformed id)")
        if code == 5:
            raise ChromeWebStoreNotFound(f"{label} not found")
        if code == 7:
            raise ChromeWebStoreRemoved(f"{label} was removed from the Chrome Web Store")
        if code in (8, 14, 16):
            raise ChromeWebStoreBlocked(f"{label}: error {code}")
        raise ChromeWebStoreUpstreamError(f"{label}: error {code}")
    raise ChromeWebStoreUpstreamError(f"{label}: empty response")


def rpc(rpcid, inner, language=None, label=None):
    """One batchexecute RPC -> its decoded payload (a nested list; an empty
    list when the store has nothing for the id)."""
    label = label or rpcid
    freq = json.dumps([[[rpcid, json.dumps(inner, separators=(",", ":"), ensure_ascii=False), None, "generic"]]],
                      separators=(",", ":"), ensure_ascii=False)
    query = {"rpcids": rpcid, "source-path": "/", "f.sid": "-1", "hl": language or "en",
             "authuser": "", "soc-app": "1", "soc-platform": "1", "soc-device": "1", "rt": "c"}
    url = f"{SITE}{BATCH_PATH}?{urlencode(query)}"

    def once():
        state = _state()
        try:
            resp = state["session"].post(url, data={"f.req": freq}, headers=state["rpc_headers"],
                                         cookies=CONSENT_COOKIES, timeout=RPC_TIMEOUT)
        except Exception as e:
            raise ChromeWebStoreUpstreamError(f"{label}: request failed: {type(e).__name__}: {e}")
        text = _classify(resp, label)
        payloads, errors = decode_chunks(text)
        if payloads:
            return payloads[0] if isinstance(payloads[0], list) else []
        _raise_rpc_errors(errors, rpcid, label)
    return _retrying(once, label)


# ---- the item RPCs -------------------------------------------------------------------

def fetch_details(item_id, language=None):
    """xY2Ddd -> the raw details payload. Raises ChromeWebStoreRemoved for a
    delisted item, ChromeWebStoreNotFound for an unknown one."""
    return rpc(RPC_DETAILS, [item_id], language, label=f"item {item_id}")


def fetch_replacements(item_id, language=None):
    """GApdCe -> the store's suggested replacements for a removed item."""
    return rpc(RPC_REPLACEMENTS, [item_id], language, label=f"replacements of {item_id}")


def fetch_reviews(item_id, size, token=None, sort=2, rating=None, review_language=None, language=None):
    """x1DgCd -> the raw reviews payload. sort: 1 relevant, 2 recent,
    3 lowest, 4 highest; rating 1-5 keeps one star; review_language "all"
    or an ISO code (None follows `language`)."""
    filters = [review_language] if review_language else None
    inner = [item_id, [size, token], sort, rating, None, filters, 0]
    return rpc(RPC_REVIEWS, inner, language, label=f"reviews of {item_id}")


def fetch_publisher(publisher_id, language=None):
    """N3gGhc -> the raw publisher payload (`[[]]` for an unknown id)."""
    return rpc(RPC_PUBLISHER, [publisher_id], language, label=f"publisher {publisher_id}")


def fetch_categories(kind, language=None):
    """CWFOxc -> the category vocabulary (kind 1 extensions, 2 themes)."""
    return rpc(RPC_CATEGORIES, [kind], language, label="categories")


# ---- the list RPC (search / category / charts / collection) --------------------------

def fetch_search(query, size, token=None, min_rating=None, kind=None, featured=None, established=None,
                 language=None):
    """zTyKYc search mode. kind: "EXTENSION" / "THEME" / None for both. The
    page size is capped at 150 by the store; d[2] = [token, , , total]."""
    kinds = [kind] if kind else None
    inner = [[None, [None, None, None, [query, [size, token], min_rating, kinds,
                                        1 if featured else None, 1 if established else None]]]]
    return rpc(RPC_LIST, inner, language, label=f"search {query!r}")


def fetch_category(kind, slug, size, token=None, sort=2, featured=None, established=None, language=None):
    """zTyKYc category mode. kind 3 = an extension category, 4 = a theme
    category; sort 1 trending, 2 relevant (the store's default), 3 highest
    rated, 4 newest. An unknown slug answers an empty payload."""
    inner = [[None, [[kind, slug, 1 if featured else None, 1 if established else None, sort, [size, token]]]]]
    return rpc(RPC_LIST, inner, language, label=f"category {slug}")


def fetch_chart(chart, language=None):
    """zTyKYc charts mode: 1 trending, 2 popular, 3 new & notable; a fixed
    list of 25 items."""
    inner = [[None, [None, None, None, None, None, None, None, [chart]]]]
    return rpc(RPC_LIST, inner, language, label=f"chart {chart}")


def fetch_collection(slug, language=None):
    """zTyKYc collection mode: the curated list behind /collection/<slug>."""
    inner = [[None, [None, None, None, None, [slug]]]]
    return rpc(RPC_LIST, inner, language, label=f"collection {slug}")


# ---- the installer's update check -----------------------------------------------------

def fetch_updatecheck(item_id):
    """GET the update2/crx updatecheck XML for one item id."""
    query = {"response": "updatecheck", "prodversion": "131.0", "acceptformat": "crx2,crx3",
             "x": f"id={item_id}&v=0.0&uc"}
    url = f"{UPDATE_URL}?{urlencode(query)}"
    label = f"package of {item_id}"

    def once():
        state = _state()
        try:
            resp = state["session"].get(url, headers=state["crx_headers"], timeout=CRX_TIMEOUT)
        except Exception as e:
            raise ChromeWebStoreUpstreamError(f"{label}: request failed: {type(e).__name__}: {e}")
        text = _classify(resp, label)
        if "<gupdate" not in text:
            raise ChromeWebStoreUpstreamError(f"{label}: unexpected answer: {text[:120]}")
        return text
    return _retrying(once, label)
