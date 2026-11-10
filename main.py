"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. Params are validated by the same schemas the API uses, so an
extension id or any chromewebstore.google.com link both work.
"""
import json
import os

from chrome_web_store import api, schemas

os.makedirs("output", exist_ok=True)


def run(schema_cls, fn, **params):
    """Validate params like the API does, then call the scraper function."""
    return fn(**schema_cls().load(params))


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # an extension id or any chromewebstore.google.com item link
    save("extension_grammarly.json", run(schemas.ExtensionSchema, api.extension_details,
                                         extension="kbfnbcaeplbcioakkpcpgfkobkghlhen"))

    # 50 results per page, filter by type, rating and badges
    save("search_ad_blocker.json", run(schemas.SearchSchema, api.extensions_search, query="ad blocker"))

    # 100 reviews per page, lowest rated first, every language
    save("reviews_grammarly_lowest.json", run(schemas.ReviewsSchema, api.extension_reviews,
                                              extension="kbfnbcaeplbcioakkpcpgfkobkghlhen", sort="lowest"))
