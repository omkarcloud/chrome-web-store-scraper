"""The one egress helper the chrome_web_store module asks for: the
Accept-Language its requests announce. The Chrome Web Store picks the
language from the `hl` query parameter (the `language` param of every
endpoint), not from this header, so the kit always sends US English."""

ACCEPT_LANGUAGE = "en-US,en;q=0.9"


def accept_language(proxy=None, country=None):
    return ACCEPT_LANGUAGE


def site_accept_language(site):
    return ACCEPT_LANGUAGE


def exit_proxy(exit=None):
    return exit if exit and "://" in str(exit) else None


def new_session(exit=None, impersonate="chrome", **kw):
    from curl_cffi import requests as curl
    sess = curl.Session(impersonate=impersonate, **kw)
    proxy = exit_proxy(exit)
    if proxy:
        sess.proxies = {"http": proxy, "https": proxy}
    return sess
