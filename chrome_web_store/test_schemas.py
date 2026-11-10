"""Offline tests for the /chrome-web-store/* request schemas.

    python -m pytest chrome_web_store/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chrome_web_store import schemas  # noqa: E402

DR = "eimadpbcbfnmbkopoojfekhnkhdbieeh"
LINK = f"https://chromewebstore.google.com/detail/dark-reader/{DR}?hl=en"


def test_extension_schema_accepts_id_and_link():
    assert schemas.ExtensionSchema().load({"extension": DR}) == {"extension": DR, "language": "en"}
    assert schemas.ExtensionSchema().load({"extension": LINK, "language": "pt-br"}) == \
        {"extension": DR, "language": "pt-BR"}
    assert schemas.DownloadSchema().load({"extension": LINK}) == {"extension": DR}


@pytest.mark.parametrize("value", ["", "dark reader", "https://example.com/detail/x/" + DR])
def test_extension_schema_rejects(value):
    with pytest.raises(ValidationError) as e:
        schemas.ExtensionSchema().load({"extension": value})
    assert "extension" in e.value.messages


def test_extension_schema_rejects_sibling_params_and_bad_language():
    with pytest.raises(ValidationError):
        schemas.ExtensionSchema().load({"extension": DR, "id": DR})
    with pytest.raises(ValidationError):
        schemas.ExtensionSchema().load({"extension": DR, "url": LINK})
    with pytest.raises(ValidationError) as e:
        schemas.ExtensionSchema().load({"extension": DR, "language": "english"})
    assert "language" in e.value.messages


def test_search_schema():
    loaded = schemas.SearchSchema().load({"query": " ad blocker "})
    assert loaded == {"query": "ad blocker", "type": "all", "min_rating": None, "featured": None,
                      "established_publisher": None, "language": "en", "page": 1}
    loaded = schemas.SearchSchema().load({"query": "dark", "type": "Theme", "min_rating": "4", "featured": "yes",
                                          "established_publisher": "0", "page": "3"})
    assert loaded["type"] == "theme" and loaded["min_rating"] == 4
    assert loaded["featured"] is True and loaded["established_publisher"] is False and loaded["page"] == 3
    for bad in ({}, {"query": "x", "type": "app"}, {"query": "x", "min_rating": "6"}, {"query": "x", "page": "21"},
                {"query": "x", "featured": "maybe"}, {"query": "x", "limit": "5"}):
        with pytest.raises(ValidationError):
            schemas.SearchSchema().load(bad)


def test_reviews_schema():
    loaded = schemas.ReviewsSchema().load({"extension": DR})
    assert loaded == {"extension": DR, "sort": 2, "rating": None, "language": "all", "page": 1}
    loaded = schemas.ReviewsSchema().load({"extension": LINK, "sort": "Lowest", "rating": "1", "language": "DE",
                                           "page": "2"})
    assert loaded == {"extension": DR, "sort": 3, "rating": 1, "language": "de", "page": 2}
    assert schemas.ReviewsSchema().load({"extension": DR, "language": "ALL"})["language"] == "all"
    assert schemas.ReviewsSchema().load({"extension": DR, "language": "pt-BR"})["language"] == "pt-br"
    for bad in ({"extension": DR, "sort": "oldest"}, {"extension": DR, "rating": "0"},
                {"extension": DR, "language": "klingon"}, {"extension": DR, "page": "201"}):
        with pytest.raises(ValidationError):
            schemas.ReviewsSchema().load(bad)


def test_publisher_schema():
    pid = "u98cf52c4498e6ec420afdeb6bfdb56db"
    assert schemas.PublisherSchema().load({"publisher": pid}) == {"publisher": ("publisher", pid), "language": "en"}
    assert schemas.PublisherSchema().load({"publisher": LINK})["publisher"] == ("item", DR)
    assert schemas.PublisherSchema().load(
        {"publisher": f"https://chromewebstore.google.com/publisher/dark-reader-ltd/{pid}"})["publisher"] == \
        ("publisher", pid)
    with pytest.raises(ValidationError) as e:
        schemas.PublisherSchema().load({"publisher": "dark reader ltd"})
    assert "publisher" in e.value.messages
    with pytest.raises(ValidationError):
        schemas.PublisherSchema().load({})


def test_categories_schemas():
    assert schemas.CategoriesSchema().load({}) == {"type": "all"}
    assert schemas.CategoriesSchema().load({"type": "Theme"}) == {"type": "theme"}
    with pytest.raises(ValidationError):
        schemas.CategoriesSchema().load({"type": "apps"})
    loaded = schemas.CategoryItemsSchema().load({"category": "developer"})
    assert loaded == {"category": (3, "productivity/developer"), "sort": 2, "featured": None,
                      "established_publisher": None, "language": "en", "page": 1}
    loaded = schemas.CategoryItemsSchema().load(
        {"category": "https://chromewebstore.google.com/category/themes/dark", "sort": "highest_rated",
         "featured": "true", "page": "80"})
    assert loaded["category"] == (4, "dark") and loaded["sort"] == 3 and loaded["featured"] is True
    for bad in ({}, {"category": "nope"}, {"category": "developer", "sort": "popular"},
                {"category": "developer", "page": "81"}):
        with pytest.raises(ValidationError):
            schemas.CategoryItemsSchema().load(bad)


def test_chart_schema():
    assert schemas.ChartSchema().load({}) == {"chart": 2, "language": "en"}
    assert schemas.ChartSchema().load({"chart": "New_Notable", "language": "fr"}) == {"chart": 3, "language": "fr"}
    with pytest.raises(ValidationError):
        schemas.ChartSchema().load({"chart": "top"})


def test_collection_schemas():
    assert schemas.CollectionsSchema().load({}) == {}
    with pytest.raises(ValidationError):
        schemas.CollectionsSchema().load({"page": "2"})
    assert schemas.CollectionItemsSchema().load({"collection": "Writing_Essentials"}) == \
        {"collection": "writing_essentials", "language": "en"}
    assert schemas.CollectionItemsSchema().load(
        {"collection": "https://chromewebstore.google.com/collection/dark_mode?hl=de"})["collection"] == "dark_mode"
    with pytest.raises(ValidationError) as e:
        schemas.CollectionItemsSchema().load({"collection": "no such thing"})
    assert "collection" in e.value.messages


def test_every_field_documents_itself():
    for schema_cls in (schemas.SearchSchema, schemas.ExtensionSchema, schemas.DownloadSchema, schemas.ReviewsSchema,
                       schemas.PublisherSchema, schemas.CategoriesSchema, schemas.CategoryItemsSchema,
                       schemas.ChartSchema, schemas.CollectionItemsSchema):
        for name, field in schema_cls().fields.items():
            assert field.metadata.get("description"), f"{schema_cls.__name__}.{name} has no description"
