"""Raw Chrome Web Store RPC payloads -> clean dicts. Pure functions, no I/O.

Fixtures (chrome_web_store/fixtures/, captured 2026-11-07 through
fetch.py on a datacenter proxy exit; the AI-assistants collection 2026-11-10):
  details_*.json                xY2Ddd: Dark Reader (full), Honey (privacy
                                data codes, no DUNS / phone), a theme, a
                                sparse one-person extension, Dark Reader in
                                German
  replacements_ublock_origin.json   GApdCe for a removed item
  reviews_*.json                x1DgCd: lowest-first all languages (with
                                developer replies), the recent first page,
                                an unknown item (`[]`)
  search_*.json                 zTyKYc search: two pages, no results, themes
                                with a rating floor
  category_*.json               zTyKYc category: highest rated developer
                                tools, a theme category, an unknown slug (`[]`)
  chart_popular.json            zTyKYc charts
  collection_*.json             zTyKYc collection: a real one, an unknown slug
  publisher_*.json              N3gGhc: Dark Reader Ltd, an unknown id (`[[]]`)
  categories_*.json             CWFOxc 1 / 2
  updatecheck_*.xml             update2/crx: current, unknown, removed

The card (the 20-field list every list and the details start with):
  0 id  1 icon  2 name  3 rating  4 rating count  5 small tile  6 summary
  7 website  8 established publisher  9 featured  10 by Google
  11 [category slug, , category id]  12 type (1 extension / 2 theme)
  14 users (rounded)  16 marquee image  17 first published [sec, nanos]
  18 the FULL manifest.json as a string  19 name again
Slots 13 and 15 are booleans whose meaning the store never labels (they do
not match the Featured / Established / "Follows recommended practices"
badges); they are not exposed.
"""
import json
import re
from datetime import datetime, timezone

from chrome_web_store import refs
from scraper_utils.text import stripped as _text

ITEM_TYPES = {1: "extension", 2: "theme"}

# xY2Ddd d[7]: the data types the developer declares to collect (the
# privacy practices section, in the store's own order and wording)
PRIVACY_DATA_TYPES = {
    1: "personally_identifiable_information",
    2: "health_information",
    3: "financial_and_payment_information",
    4: "authentication_information",
    5: "personal_communications",
    6: "location",
    7: "web_history",
    8: "user_activity",
    9: "website_content",
}

MEDIA_TYPES = {1: "image", 2: "video"}

_SIZE_UNITS = {"b": 1, "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3,
               "kb": 1000, "mb": 1000 ** 2, "gb": 1000 ** 3}
_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)\s*$")
_ITEM_ID_RE = re.compile(r"^[a-p]{32}$")


# ---- value helpers -------------------------------------------------------------

def _get(seq, index, default=None):
    """seq[index] when seq is a list long enough, else default."""
    if isinstance(seq, list) and -len(seq) <= index < len(seq):
        value = seq[index]
        return default if value is None else value
    return default


def _int(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _flag(value):
    """The store's booleans arrive as 1 / true / null."""
    return bool(value) if value is not None else False


def _rating(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 2)
    return None


def timestamp_to_iso(value):
    """[seconds, nanos] (or bare seconds) -> ISO 8601 UTC, else None."""
    seconds = value[0] if isinstance(value, list) and value else value
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(int(seconds), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def size_to_bytes(value):
    """'839KiB' / '76.22MiB' -> bytes, else None."""
    match = _SIZE_RE.match(value or "")
    if not match:
        return None
    unit = _SIZE_UNITS.get(match.group(2).lower())
    return int(float(match.group(1)) * unit) if unit else None


def parse_manifest(raw):
    """The manifest.json string the store embeds -> dict (None when it is
    missing or not JSON)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _str_list(values):
    if not isinstance(values, list):
        return []
    return [v for v in values if isinstance(v, str) and v]


def _website(value):
    value = _text(value)
    if not value:
        return None
    return value if "://" in value else "https://" + value


def is_card(value):
    return (isinstance(value, list) and len(value) >= 19 and isinstance(value[0], str)
            and bool(_ITEM_ID_RE.match(value[0])) and isinstance(value[2], str))


def find_cards(payload):
    """Every card in document order anywhere inside `payload` (list payloads
    nest them differently per mode; the order is the store's ranking)."""
    found = []

    def walk(node):
        if is_card(node):
            found.append(node)
            return
        if isinstance(node, list):
            for child in node:
                walk(child)
    walk(payload)
    return found


# ---- the card -------------------------------------------------------------------

def _category(value):
    slug = _text(_get(value, 0))
    if not slug:
        return None
    return {
        "id": _int(_get(value, 2)),
        "slug": slug,
        "name": refs.category_label(slug),
        "link": refs.category_link(slug),
    }


def _manifest_summary(manifest):
    """The fields a list row needs from the manifest; details carry it whole."""
    manifest = manifest or {}
    return {
        "version": _text(manifest.get("version")),
        "manifest_version": _int(manifest.get("manifest_version")),
        "minimum_chrome_version": _text(manifest.get("minimum_chrome_version")),
        "permissions": _str_list(manifest.get("permissions")),
        "host_permissions": _str_list(manifest.get("host_permissions")),
        "optional_permissions": _str_list(manifest.get("optional_permissions")),
    }


def parse_card(card, rank=None):
    """One 20-field card -> a list row."""
    if not is_card(card):
        return None
    item_id, name = card[0], _text(card[2]) or _text(_get(card, 19))
    manifest = parse_manifest(_get(card, 18))
    row = {
        "id": item_id,
        "name": name,
        "link": refs.item_link(item_id, name),
        "type": ITEM_TYPES.get(_int(_get(card, 12))),
        "summary": _text(_get(card, 6)),
        "rating": _rating(_get(card, 3)),
        "rating_count": _int(_get(card, 4)),
        "users": _int(_get(card, 14)),
        "category": _category(_get(card, 11)),
        "is_featured": _flag(_get(card, 9)),
        "is_established_publisher": _flag(_get(card, 8)),
        "is_by_google": _flag(_get(card, 10)),
        "website": _website(_get(card, 7)),
        "images": {
            "icon": _text(_get(card, 1)),
            "tile": _text(_get(card, 5)),
            "marquee": _text(_get(card, 16)),
        },
        **_manifest_summary(manifest),
        "published_at": timestamp_to_iso(_get(card, 17)),
    }
    if rank is not None:
        row = {"rank": rank, **row}
    return row


def parse_cards(cards, start=1):
    rows = []
    for card in cards:
        row = parse_card(card, rank=start + len(rows))
        if row:
            rows.append(row)
    return rows


# ---- list payloads (zTyKYc) -------------------------------------------------------

def _continuation(payload):
    """d[2] = [token, , , total] on search / category payloads."""
    meta = _get(payload, 2)
    token = _text(_get(meta, 0))
    total = _int(_get(meta, 3))
    return token, total


def parse_search(payload, start=1):
    """zTyKYc search -> {items, next_token, total}. The total is the store's
    own match count (0 when nothing matched)."""
    token, total = _continuation(payload)
    return {"items": parse_cards(find_cards(payload), start), "next_token": token, "total": total}


def parse_category(payload, start=1):
    """zTyKYc category -> {items, next_token} or None for an unknown slug
    (the store answers `[]`)."""
    if not isinstance(payload, list) or not payload:
        return None
    token, _ = _continuation(payload)
    return {"items": parse_cards(find_cards(payload), start), "next_token": token}


def parse_chart(payload):
    """zTyKYc charts -> the 25 ranked rows."""
    return parse_cards(find_cards(payload))


def parse_collection(payload):
    """zTyKYc collection -> rows, or None for an unknown slug (the items
    slot d[0][0][12][0][0] is null then)."""
    cell = _get(_get(_get(_get(_get(payload, 0), 0), 0), 12), 0)
    if isinstance(cell, list) and len(cell) >= 1 and cell[0] is None:
        return None
    return parse_cards(find_cards(payload))


# ---- details (xY2Ddd) ------------------------------------------------------------

def _developer(block, website):
    """d[10]: [email, address, , trader flag, , display name, legal name,
    publisher name, DUNS, phone, publisher id]."""
    if not isinstance(block, list):
        return None
    publisher_id = _text(_get(block, 10))
    publisher_name = _text(_get(block, 7)) or _text(_get(block, 5))
    return {
        "name": _text(_get(block, 5)),
        "legal_name": _text(_get(block, 6)),
        "email": _text(_get(block, 0)),
        "phone": _text(_get(block, 9)),
        "address": _text(_get(block, 1)),
        "website": website,
        "duns_number": _text(_get(block, 8)),
        "is_trader": _flag(_get(block, 3)),
        "publisher": {
            "id": publisher_id,
            "name": publisher_name,
            "link": refs.publisher_link(publisher_id, publisher_name) if publisher_id else None,
        },
    }


def _media(values):
    out = []
    for entry in values if isinstance(values, list) else []:
        link = _text(_get(entry, 1))
        if link:
            out.append({"type": MEDIA_TYPES.get(_int(_get(entry, 0)), "image"), "link": link})
    return out


def _privacy(d):
    codes = [c for c in (_get(d, 7) or []) if isinstance(c, int)]
    return {
        "policy_link": _text(_get(d, 33)),
        "collects_data": bool(codes),
        "data_collected": [PRIVACY_DATA_TYPES.get(c, f"type_{c}") for c in codes],
    }


def parse_details(payload, item_id=None):
    """xY2Ddd -> the full item record (the card fields first, then the
    description, media, version block, developer, privacy, manifest and the
    store's related items)."""
    card = _get(payload, 0)
    row = parse_card(card)
    if row is None:
        return None
    item_id = row["id"] or item_id
    name = row["name"]
    manifest = parse_manifest(_get(card, 18))
    size = _text(_get(payload, 15))
    links = {
        "store": row["link"],
        "reviews": refs.reviews_link(item_id, name),
        "support": row["link"] + "/support",
        "privacy": row["link"] + "/privacy",
    }
    related = parse_cards(_get(payload, 22) or [])
    for extra in related:
        extra.pop("rank", None)
    for key in ("version", "manifest_version", "minimum_chrome_version", "permissions",
                "host_permissions", "optional_permissions"):
        row.pop(key, None)
    return {
        **row,
        "description": _text(_get(payload, 6)),
        "media": _media(_get(payload, 5)),
        "version": _text(_get(payload, 13)) or _text((manifest or {}).get("version")),
        "manifest_version": _int((manifest or {}).get("manifest_version")),
        "minimum_chrome_version": _text(_get(payload, 27)) or _text((manifest or {}).get("minimum_chrome_version")),
        "updated_at": timestamp_to_iso(_get(payload, 14)),
        "size": size,
        "size_bytes": size_to_bytes(size),
        "languages": _str_list(_get(payload, 16)),
        "language_codes": _str_list(_get(payload, 38)),
        "permissions": _str_list((manifest or {}).get("permissions")),
        "host_permissions": _str_list((manifest or {}).get("host_permissions")),
        "optional_permissions": _str_list((manifest or {}).get("optional_permissions")),
        "developer": _developer(_get(payload, 10), row["website"]),
        "privacy": _privacy(payload),
        "manifest": manifest,
        "related": related,
        "related_count": len(related),
        "links": links,
    }


def parse_replacements(payload):
    """GApdCe -> the store's suggested replacements for a removed item."""
    rows = parse_cards(find_cards(payload))
    for row in rows:
        row.pop("rank", None)
    return rows


# ---- reviews (x1DgCd) ----------------------------------------------------------

def _person(value):
    return {"name": _text(_get(value, 0)), "avatar": _text(_get(value, 1))}


def _reply(value):
    """[id, [name, avatar], text, created, updated, …, language]."""
    if not isinstance(value, list) or not value:
        return None
    return {
        "id": _text(_get(value, 0)),
        "author": _person(_get(value, 1)),
        "text": _text(_get(value, 2)),
        "created_at": timestamp_to_iso(_get(value, 3)),
        "updated_at": timestamp_to_iso(_get(value, 4)),
        "language": _text(_get(value, 9)),
    }


def parse_review(value, item_name=None):
    """0 uuid, 1 [name, avatar], 2 stars, 3 text, 4 created, 5 updated,
    6 helpful, 7 unhelpful, 8 developer reply, 11 version, 13 language,
    14 item id."""
    review_id = _text(_get(value, 0))
    if not review_id:
        return None
    item_id = _text(_get(value, 14))
    return {
        "id": review_id,
        "link": refs.review_link(item_id, review_id, item_name) if item_id else None,
        "rating": _int(_get(value, 2)),
        "text": _text(_get(value, 3)),
        "author": _person(_get(value, 1)),
        "created_at": timestamp_to_iso(_get(value, 4)),
        "updated_at": timestamp_to_iso(_get(value, 5)),
        "helpful_count": _int(_get(value, 6)) or 0,
        "unhelpful_count": _int(_get(value, 7)) or 0,
        "version": _text(_get(value, 11)),
        "language": _text(_get(value, 13)),
        "developer_reply": _reply(_get(value, 8)),
    }


def parse_reviews(payload, item_name=None):
    """x1DgCd -> {reviews, next_token, total}; an unknown item (or a bad
    token) answers `[]`, which comes back as an empty page."""
    reviews = []
    for entry in _get(payload, 1) or []:
        review = parse_review(entry, item_name)
        if review:
            reviews.append(review)
    return {
        "reviews": reviews,
        "next_token": _text(_get(_get(payload, 0), 0)),
        "total": _int(_get(payload, 2)),
    }


# ---- publisher (N3gGhc) ----------------------------------------------------------

def parse_publisher(payload):
    """N3gGhc -> {profile, items} or None for an unknown id (`[[]]`)."""
    profile = _get(payload, 0)
    if not isinstance(profile, list) or not profile:
        return None
    items = parse_cards(find_cards(_get(payload, 2) or []))
    for row in items:
        row.pop("rank", None)
    developer = _developer(profile, None)
    publisher = developer.pop("publisher")
    developer.pop("website", None)   # the profile block carries no website
    return {
        "id": publisher["id"],
        "name": publisher["name"],
        "link": publisher["link"],
        "display_name": developer.pop("name"),
        **developer,
        "items": items,
        "items_count": len(items),
    }


# ---- categories (CWFOxc) ---------------------------------------------------------

def parse_categories(payload, kind):
    """CWFOxc -> rows [{id, slug, name, type, group}]; entries are
    [id, , group id, [1, 2], , slug]."""
    rows = []
    for entry in _get(_get(payload, 0), 4) or []:
        slug = _text(_get(entry, 5))
        if not slug:
            continue
        group_id = _int(_get(entry, 2))
        group = refs.CATEGORY_GROUPS.get(group_id)
        rows.append({
            "id": _int(_get(entry, 0)),
            "slug": slug,
            "name": refs.category_label(slug),
            "type": "theme" if kind == 2 else "extension",
            "group": {"id": group_id, "slug": group[0] if group else None, "name": group[1] if group else None},
            "link": refs.category_link(slug),
        })
    return rows


# ---- the installer's update check -------------------------------------------------

_APP_RE = re.compile(r"<app\b([^>]*)>", re.I)
_UPDATECHECK_RE = re.compile(r"<updatecheck\b([^>]*)/?>", re.I)
_ATTR_RE = re.compile(r'([A-Za-z_][\w.-]*)="([^"]*)"')


def _attrs(tag):
    return dict(_ATTR_RE.findall(tag or ""))


def parse_updatecheck(xml):
    """update2/crx XML -> {status, version, size_bytes, sha256, link} —
    status "ok" with a package, "noupdate" when the store has no package to
    serve (a removed item), None for an unknown id."""
    app = _attrs(next(iter(_APP_RE.findall(xml or "")), ""))
    status = app.get("status")
    if not status or status.startswith("error"):
        return None
    check = _attrs(next(iter(_UPDATECHECK_RE.findall(xml or "")), ""))
    size = check.get("size")
    return {
        "status": check.get("status") or status,
        "version": _text(check.get("version")),
        "size_bytes": int(size) if size and size.isdigit() else None,
        "sha256": _text(check.get("hash_sha256")),
        "link": _text(check.get("codebase")),
    }
