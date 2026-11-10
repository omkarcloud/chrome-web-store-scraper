"""Cache TTL per /chrome-web-store/* endpoint (cache.py, keyed on the
validated params). The store's numbers move slowly: user counts are
rounded (7,000,000) and rating averages shift by a review at a time, so an
hour-scale cache never serves a materially stale record.
"""
from datetime import timedelta

# The full details record: version bumps land every few days at most.
DETAILS_CACHE = timedelta(hours=12)
# Reviews: the newest page moves with every new review, the sorted-by-rating
# pages hardly at all; one TTL for both keeps the key simple.
REVIEWS_CACHE = timedelta(hours=6)
# Search ranking reshuffles slowly; a new upload rarely enters the first pages.
SEARCH_CACHE = timedelta(hours=6)
# Category rankings and charts are recomputed by the store about daily.
CATEGORY_CACHE = timedelta(hours=6)
CHARTS_CACHE = timedelta(hours=6)
# A publisher's item list changes when they publish or unpublish something.
PUBLISHER_CACHE = timedelta(hours=12)
# The category vocabulary is a static table on the store's side.
CATEGORIES_CACHE = timedelta(days=7)
# Curated collections are edited by the Chrome team a few times a year.
COLLECTIONS_CACHE = timedelta(hours=24)
# The package version + download link: follows the version cadence.
DOWNLOAD_CACHE = timedelta(hours=6)
