"""The /chrome-web-store/* endpoint functions (route_glue's route_table
calls them with the schema's loaded kwargs).

extensions/details caches the parsed xY2Ddd record under
chrome-web-store.item keyed on (extension, language); publishers/details
given an extension link reads the publisher id off that same cached
record, and extensions/reviews confirms an empty first page against it, so
a client walking details -> publisher -> reviews pays one details fetch.

Paging: the store pages search, category lists and reviews with opaque
continuation tokens. The API exposes plain `page` numbers: page N is
reached by following the tokens from the nearest page already seen, and
every (query, page) -> token hop is remembered in a process-level memo, so
a client reading pages in order costs one upstream call per page. Search
and reviews publish a total; category lists do not (has_next only).
"""
import math
import threading

from cache import cached_call
from chrome_web_store import cache_config as ttl
from chrome_web_store import fetch, parsers, refs, schemas
from chrome_web_store.fetch import ChromeWebStoreNotFound, ChromeWebStoreRemoved


# ---- continuation-token memo --------------------------------------------------------

_TOKEN_MEMO_MAX = 20000
_tokens_lock = threading.Lock()
_tokens = {}   # (key, page) -> token that fetches that page (page 1 = None)


def _remember(key, page, token):
    with _tokens_lock:
        if len(_tokens) >= _TOKEN_MEMO_MAX:
            _tokens.clear()
        _tokens[(key, page)] = token


def _known_start(key, page):
    """The nearest page <= `page` whose token is known -> (page, token)."""
    with _tokens_lock:
        for known in range(page, 1, -1):
            token = _tokens.get((key, known))
            if token:
                return known, token
    return 1, None


def walk_pages(key, page, fetch_page):
    """Serve page `page` of a token-paged list. fetch_page(token) ->
    (result, next_token); the result of the requested page (or None past
    the end) is returned, and every token met on the way is memoised."""
    current, token = _known_start(key, page)
    while True:
        result, next_token = fetch_page(token)
        if next_token:
            _remember(key, current + 1, next_token)
        if current == page:
            return result, next_token
        if not next_token:
            return None, None
        current, token = current + 1, next_token


def _pages(total, per_page):
    return math.ceil(total / per_page) if isinstance(total, int) and total > 0 else 0


def _pagination(page, per_page, next_token, max_page, total=None, has_total=True):
    """The pagination block, capped at the schema's page limit: the next
    link never points past `max_page` (a page the schema rejects with a
    400) and total_pages counts only reachable pages, while total_count
    stays the store's own number (20,274 Grammarly reviews read as 200 pages
    of 100). Category lists publish no total: has_next only."""
    block = {"page": page, "items_per_page": per_page,
             "has_next": bool(next_token) and page < max_page,
             "total_pages": None, "total_count": None}
    if has_total and total is not None:
        block["total_pages"] = min(_pages(total, per_page), max_page)
        block["total_count"] = total
    return block


# ---- the shared item record ---------------------------------------------------------

def _item_record(extension, language):
    """xY2Ddd parsed; a removed item raises ChromeWebStoreRemoved carrying the
    store's suggested replacements (route_glue puts them in the 404 body)."""
    try:
        payload = fetch.fetch_details(extension, language)
    except ChromeWebStoreRemoved as e:
        try:
            replacements = parsers.parse_replacements(fetch.fetch_replacements(extension, language))
        except Exception:
            replacements = []
        e.reason = "removed"
        e.details = {"extension": extension, "link": refs.item_link(extension),
                     "replacements": [{"id": r["id"], "name": r["name"], "link": r["link"]} for r in replacements]}
        raise
    record = parsers.parse_details(payload, extension)
    if record is None:
        raise ChromeWebStoreNotFound(f"extension {extension} not found")
    return record


def _record(extension, language):
    return cached_call("chrome-web-store.item", {"extension": extension, "language": language},
                       _item_record, ttl.DETAILS_CACHE)


# ---- extensions/details -------------------------------------------------------------

def extension_details(extension, language):
    """Everything the store shows for one extension or theme: the listing
    card, description, media, version / size / languages, developer
    contacts and publisher, privacy practices, the full manifest and the
    store's related items."""
    return _record(extension, language)


# ---- extensions/search --------------------------------------------------------------

def _search(query, type, min_rating, featured, established_publisher, language, page):
    per_page = schemas.SEARCH_PAGE_SIZE
    kind = schemas.ITEM_TYPES.get(type)
    key = ("search", query, kind, min_rating, bool(featured), bool(established_publisher), language)

    def fetch_page(token):
        payload = fetch.fetch_search(query, per_page, token=token, min_rating=min_rating, kind=kind,
                                     featured=featured, established=established_publisher, language=language)
        parsed = parsers.parse_search(payload, start=1)
        return parsed, parsed["next_token"]

    parsed, next_token = walk_pages(key, page, fetch_page)
    items = parsed["items"] if parsed else []
    for offset, row in enumerate(items):
        row["rank"] = (page - 1) * per_page + offset + 1
    total = parsed["total"] if parsed else None
    return {
        "query": query,
        "type": type,
        "results": items,
        "pagination": _pagination(page, per_page, next_token, schemas.MAX_SEARCH_PAGE, total=total),
    }


def extensions_search(**data):
    return cached_call("chrome-web-store.search", data, _search, ttl.SEARCH_CACHE)


# ---- extensions/reviews -------------------------------------------------------------

def _reviews(extension, sort, rating, language, page):
    per_page = schemas.REVIEWS_PAGE_SIZE
    review_language = None if language == "all" else language
    key = ("reviews", extension, sort, rating, language)

    def fetch_page(token):
        payload = fetch.fetch_reviews(extension, per_page, token=token, sort=sort, rating=rating,
                                      review_language=review_language or "all")
        parsed = parsers.parse_reviews(payload)
        return parsed, parsed["next_token"]

    parsed, next_token = walk_pages(key, page, fetch_page)
    reviews = parsed["reviews"] if parsed else []
    total = parsed["total"] if parsed else None
    if not reviews and page == 1:
        # the store answers an unknown item with `[]`; an item with no
        # reviews does the same, so confirm the item exists (404 otherwise)
        _record(extension, "en")
    sort_name = next(k for k, v in schemas.REVIEW_SORTS.items() if v == sort)
    return {
        "extension": extension,
        "link": refs.reviews_link(extension),
        "sort": sort_name,
        "rating": rating,
        "language": language,
        "reviews": reviews,
        "pagination": _pagination(page, per_page, next_token, schemas.MAX_REVIEWS_PAGE, total=total),
    }


def extension_reviews(**data):
    return cached_call("chrome-web-store.reviews", data, _reviews, ttl.REVIEWS_CACHE)


# ---- extensions/download ------------------------------------------------------------

def _download(extension):
    parsed = parsers.parse_updatecheck(fetch.fetch_updatecheck(extension))
    if parsed is None:
        raise ChromeWebStoreNotFound(f"extension {extension} not found")
    if not parsed["link"]:
        raise ChromeWebStoreNotFound(f"extension {extension} has no downloadable package "
                                     "(removed from the Chrome Web Store)")
    return {
        "extension": extension,
        "store_link": refs.item_link(extension),
        "version": parsed["version"],
        "size_bytes": parsed["size_bytes"],
        "sha256": parsed["sha256"],
        "format": "crx3",
        "download_link": parsed["link"],
    }


def extension_download(**data):
    return cached_call("chrome-web-store.download", data, _download, ttl.DOWNLOAD_CACHE)


# ---- publishers/details -------------------------------------------------------------

def _publisher(publisher, language):
    kind, ref = publisher
    if kind == "item":
        record = _record(ref, language)
        publisher_id = ((record.get("developer") or {}).get("publisher") or {}).get("id")
        if not publisher_id:
            raise ChromeWebStoreNotFound(f"extension {ref} has no publisher page")
    else:
        publisher_id = ref
    parsed = parsers.parse_publisher(fetch.fetch_publisher(publisher_id, language))
    if parsed is None:
        raise ChromeWebStoreNotFound(f"publisher {publisher_id} not found")
    return parsed


def publisher_details(**data):
    return cached_call("chrome-web-store.publisher", data, _publisher, ttl.PUBLISHER_CACHE)


# ---- categories/list ----------------------------------------------------------------

def _categories(type):
    kinds = [1, 2] if type == "all" else [schemas.CATEGORY_TYPES[type]]
    rows = []
    for kind in kinds:
        rows.extend(parsers.parse_categories(fetch.fetch_categories(kind), kind))
    return {"type": type, "count": len(rows), "categories": rows}


def categories_list(**data):
    return cached_call("chrome-web-store.categories", data, _categories, ttl.CATEGORIES_CACHE)


# ---- categories/extensions ----------------------------------------------------------

def _category_items(category, sort, featured, established_publisher, language, page):
    kind, slug = category
    per_page = schemas.CATEGORY_PAGE_SIZE
    key = ("category", kind, slug, sort, bool(featured), bool(established_publisher), language)

    def fetch_page(token):
        payload = fetch.fetch_category(kind, slug, per_page, token=token, sort=sort, featured=featured,
                                       established=established_publisher, language=language)
        parsed = parsers.parse_category(payload, start=1)
        if parsed is None:
            raise ChromeWebStoreNotFound(f"category {slug} not found")
        return parsed, parsed["next_token"]

    parsed, next_token = walk_pages(key, page, fetch_page)
    items = parsed["items"] if parsed else []
    for offset, row in enumerate(items):
        row["rank"] = (page - 1) * per_page + offset + 1
    sort_name = next(k for k, v in schemas.CATEGORY_SORTS.items() if v == sort)
    return {
        "category": {"slug": slug, "name": refs.category_label(slug),
                     "type": "theme" if kind == refs.CATEGORY_KIND_THEME else "extension",
                     "link": refs.category_link(slug)},
        "sort": sort_name,
        "results": items,
        # the store publishes no total for a category: has_next drives the next link
        "pagination": _pagination(page, per_page, next_token, schemas.MAX_CATEGORY_PAGE, has_total=False),
    }


def category_extensions(**data):
    return cached_call("chrome-web-store.category", data, _category_items, ttl.CATEGORY_CACHE)


# ---- charts/list --------------------------------------------------------------------

def _chart(chart, language):
    rows = parsers.parse_chart(fetch.fetch_chart(chart, language))
    chart_name = next(k for k, v in schemas.CHARTS.items() if v == chart)
    return {"chart": chart_name, "count": len(rows), "results": rows}


def charts_list(**data):
    return cached_call("chrome-web-store.chart", data, _chart, ttl.CHARTS_CACHE)


# ---- collections/list ---------------------------------------------------------------

def _collections():
    rows = [{"slug": slug, "title": title, "description": description, "link": refs.collection_link(slug)}
            for slug, (title, description) in sorted(refs.COLLECTIONS.items())]
    return {"count": len(rows), "collections": rows}


def collections_list(**data):
    return _collections()


# ---- collections/extensions ---------------------------------------------------------

def _collection_items(collection, language):
    rows = parsers.parse_collection(fetch.fetch_collection(collection, language))
    if rows is None:
        raise ChromeWebStoreNotFound(f"collection {collection} not found")
    title, description = refs.COLLECTIONS.get(collection, (None, None))
    return {
        "collection": {"slug": collection, "title": title, "description": description,
                       "link": refs.collection_link(collection)},
        "count": len(rows),
        "results": rows,
    }


def collection_extensions(**data):
    return cached_call("chrome-web-store.collection", data, _collection_items, ttl.COLLECTIONS_CACHE)
