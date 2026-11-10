"""Configuration for the Chrome Web Store Scraper. Everything can be set with
an environment variable; the defaults work out of the box.

    PORT                     port the API listens on (default 8000)
    CHROME_WEB_STORE_PROXY   proxy URL for every request, e.g.
                             http://user:pass@host:port (default: none — direct).
                             The Chrome Web Store answered 60 back-to-back
                             requests from one IP without a single block, so
                             you very likely don't need this. Set it only if
                             you start seeing failures at high volume.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

CHROME_WEB_STORE_PROXY = os.environ.get("CHROME_WEB_STORE_PROXY") or None


def chrome_web_store_proxy():
    """The proxy for one HTTP session (None = direct)."""
    return os.environ.get("CHROME_WEB_STORE_PROXY") or None
