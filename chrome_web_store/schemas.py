"""Marshmallow request schemas for every /chrome-web-store/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair):

    extension    a 32-character item id (cjpalhdlnbpafiamejdnhcphjbkeiagm)
                 OR any chromewebstore.google.com item link (themes too)
    publisher    a publisher id (u + 32 hex), a publisher link, OR an
                 extension id / link of one of the publisher's items
    category     a category slug (productivity/developer, developer,
                 themes/dark, dark) OR a store category link
    collection   a collection slug (writing_essentials) OR a collection link
    query        free text

`language` is the store's `hl`: it localizes names, summaries and
descriptions. The store has no country dimension (gl is ignored).
"""
from marshmallow import ValidationError

from schema_fields import (BaseSchema, ChoiceField, Flag, LanguageCodeField, PageField, PositiveInt,
                           QueryField, RefField, StrippedString, LANGUAGE_CODES)
from chrome_web_store import refs

# page sizes served by api.py (the store itself allows 150 per search page,
# 500 per review page; these keep a page readable)
SEARCH_PAGE_SIZE = 50
CATEGORY_PAGE_SIZE = 50
REVIEWS_PAGE_SIZE = 100
# the store pages search to the end (1,000 results = 20 pages), category
# lists to about 4,000 items, reviews without a cap seen (6,500 = 65 pages)
MAX_SEARCH_PAGE = 20
MAX_CATEGORY_PAGE = 80
MAX_REVIEWS_PAGE = 200

ITEM_TYPES = {"all": None, "extension": "EXTENSION", "theme": "THEME"}
REVIEW_SORTS = {"recent": 2, "helpful": 1, "highest": 4, "lowest": 3}
CATEGORY_SORTS = {"relevant": 2, "highest_rated": 3, "newest": 4, "trending": 1}
CHARTS = {"popular": 2, "trending": 1, "new_notable": 3}
CATEGORY_TYPES = {"all": None, "extension": 1, "theme": 2}


class ExtensionRefField(RefField):
    resolver = staticmethod(refs.resolve_item)


class PublisherRefField(RefField):
    resolver = staticmethod(refs.resolve_publisher)


class CategoryRefField(RefField):
    resolver = staticmethod(refs.resolve_category)


class CollectionRefField(RefField):
    resolver = staticmethod(refs.resolve_collection)


class LanguageField(LanguageCodeField):
    """The store's hl: ISO 639-1 code or a locale (en, de, pt-BR), default en."""

    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", "en")
        kwargs.setdefault("allow_locale", True)
        kwargs.setdefault("metadata", {
            "description": "language of names, summaries and descriptions (en, de, fr, ja, pt-BR, ...; default en)"})
        super().__init__(**kwargs)


class ReviewLanguageField(StrippedString):
    """`all` (every language, the default) or one ISO 639-1 code."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", "all")
        kwargs.setdefault("metadata", {
            "description": "language the reviews were written in: all (default) or an ISO code (en, de, fr, ...)"})
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value is None:
            return "all"
        low = value.lower().replace("_", "-")
        if low == "all":
            return "all"
        if low.split("-")[0] in LANGUAGE_CODES and len(low) <= 7:
            return low
        raise ValidationError("Must be all or an ISO 639-1 language code (en, de, fr, ...).")


_EXTENSION_HELP = "32-character extension / theme id (cjpalhdlnbpafiamejdnhcphjbkeiagm) or a chromewebstore.google.com item link"


# ---- extensions/search ----------------------------------------------------------

class SearchSchema(BaseSchema):
    query = QueryField(metadata={"description": "search term (extension name, keyword)"})
    type = ChoiceField(list(ITEM_TYPES), load_default="all", metadata={
        "description": "all (default), extension or theme"})
    min_rating = PositiveInt(max_value=5, metadata={
        "description": "only items rated this many stars and up, 1-5 (default all)"})
    featured = Flag(metadata={"description": "true keeps only items with the store's Featured badge"})
    established_publisher = Flag(metadata={
        "description": "true keeps only items from publishers with the Established publisher badge"})
    language = LanguageField()
    page = PageField(max_page=MAX_SEARCH_PAGE, metadata={
        "description": f"page of {SEARCH_PAGE_SIZE} results, 1-{MAX_SEARCH_PAGE} (default 1)"})


# ---- extensions/details + extensions/download -----------------------------------

class ExtensionSchema(BaseSchema):
    extension = ExtensionRefField(metadata={"description": _EXTENSION_HELP})
    language = LanguageField()


class DownloadSchema(BaseSchema):
    extension = ExtensionRefField(metadata={"description": _EXTENSION_HELP})


# ---- extensions/reviews ---------------------------------------------------------

class ReviewsSchema(BaseSchema):
    extension = ExtensionRefField(metadata={"description": _EXTENSION_HELP})
    sort = ChoiceField(dict(REVIEW_SORTS), load_default=REVIEW_SORTS["recent"], metadata={
        "description": "recent (default), helpful, highest or lowest"})
    rating = PositiveInt(max_value=5, metadata={
        "description": "only reviews with this star rating, 1-5 (default all)"})
    language = ReviewLanguageField()
    page = PageField(max_page=MAX_REVIEWS_PAGE, metadata={
        "description": f"page of {REVIEWS_PAGE_SIZE} reviews, 1-{MAX_REVIEWS_PAGE} (default 1)"})


# ---- publishers/details ---------------------------------------------------------

class PublisherSchema(BaseSchema):
    publisher = PublisherRefField(metadata={
        "description": "publisher id (u + 32 hex), a chromewebstore.google.com publisher link, "
                       "or the id / link of one of the publisher's extensions"})
    language = LanguageField()


# ---- categories/list + categories/extensions ------------------------------------

class CategoriesSchema(BaseSchema):
    type = ChoiceField(list(CATEGORY_TYPES), load_default="all", metadata={
        "description": "all (default), extension or theme"})


class CategoryItemsSchema(BaseSchema):
    category = CategoryRefField(metadata={
        "description": "category slug (productivity/developer, developer, themes/dark, dark; "
                       "see /chrome-web-store/categories/list) or a store category link"})
    sort = ChoiceField(dict(CATEGORY_SORTS), load_default=CATEGORY_SORTS["relevant"], metadata={
        "description": "relevant (the store's order, default), highest_rated, newest or trending"})
    featured = Flag(metadata={"description": "true keeps only items with the store's Featured badge"})
    established_publisher = Flag(metadata={
        "description": "true keeps only items from publishers with the Established publisher badge"})
    language = LanguageField()
    page = PageField(max_page=MAX_CATEGORY_PAGE, metadata={
        "description": f"page of {CATEGORY_PAGE_SIZE} items, 1-{MAX_CATEGORY_PAGE} (default 1)"})


# ---- charts/list ----------------------------------------------------------------

class ChartSchema(BaseSchema):
    chart = ChoiceField(dict(CHARTS), load_default=CHARTS["popular"], metadata={
        "description": "popular (default), trending or new_notable: the store's 25-item shelves"})
    language = LanguageField()


# ---- collections/list + collections/extensions ----------------------------------

class CollectionsSchema(BaseSchema):
    """No parameters: the collection catalogue is a static table."""


class CollectionItemsSchema(BaseSchema):
    collection = CollectionRefField(metadata={
        "description": "collection slug (writing_essentials; see /chrome-web-store/collections/list) "
                       "or a store collection link"})
    language = LanguageField()
