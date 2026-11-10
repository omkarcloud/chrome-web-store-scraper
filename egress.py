"""The one egress helper the chrome_web_store module asks for: the
Accept-Language its requests announce. The Chrome Web Store picks the
language from the `hl` query parameter (the `language` param of every
endpoint), not from this header, so the kit always sends US English."""

ACCEPT_LANGUAGE = "en-US,en;q=0.9"


def accept_language(proxy=None, country=None):
    return ACCEPT_LANGUAGE


def site_accept_language(site):
    return ACCEPT_LANGUAGE
