from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .config import EBAY_BROWSE_URL, EBAY_OAUTH_URL, eba_creds
from .currency import usd_to_cad
from .db import upsert_listing

log = logging.getLogger("ebay")

SLUG_HINTS = [
    ("pixel 9 pro xl", "google-pixel-9-pro-xl"),
    ("pixel 9 pro", "google-pixel-9-pro"),
    ("pixel 9", "google-pixel-9"),
    ("pixel 8 pro", "google-pixel-8-pro"),
    ("pixel 8a", "google-pixel-8a"),
    ("pixel 8", "google-pixel-8"),
    ("pixel 7 pro", "google-pixel-7-pro"),
    ("pixel 7a", "google-pixel-7a"),
    ("pixel 7", "google-pixel-7"),
    ("pixel 6 pro", "google-pixel-6-pro"),
    ("pixel 6a", "google-pixel-6a"),
    ("pixel 6", "google-pixel-6"),
    ("pixel 5a", "google-pixel-5a-5g"),
    ("pixel 5", "google-pixel-5"),
    ("pixel 4a 5g", "google-pixel-4a-5g"),
    ("pixel 4a", "google-pixel-4a"),
    ("nord ce 3 lite", "oneplus-nord-ce-3-lite"),
    ("nord 2t", "oneplus-nord-2t"),
    ("oneplus 8t", "oneplus-8t"),
    ("galaxy a54", "samsung-galaxy-a54"),
    ("galaxy a34", "samsung-galaxy-a34"),
    ("galaxy s21 fe", "samsung-galaxy-s21-fe"),
]


def detect_slug(title: str) -> str | None:
    if not title:
        return None
    t = title.lower()
    for hint, slug in SLUG_HINTS:
        if hint in t:
            return slug
    return None


class _TokenCache:
    def __init__(self) -> None:
        self.token: str | None = None
        self.expires_at: float = 0.0


_TOKENS = _TokenCache()


def get_app_token(client_id: str, client_secret: str, scope: str = "https://api.ebay.com/oauth/api_scope/buy.item.feed") -> str:
    if _TOKENS.token and time.time() < _TOKENS.expires_at - 60:
        return _TOKENS.token
    creds = (client_id, client_secret)
    data = {"grant_type": "client_credentials", "scope": scope}
    r = requests.post(EBAY_OAUTH_URL, data=data, auth=creds, timeout=15)
    r.raise_for_status()
    body = r.json()
    _TOKENS.token = body["access_token"]
    _TOKENS.expires_at = time.time() + int(body.get("expires_in", 7200))
    return _TOKENS.token


def to_listing(item: dict) -> dict | None:
    title = item.get("title") or ""
    price_info = item.get("price") or {}
    value = price_info.get("value")
    currency = price_info.get("currency") or "USD"
    if value is None:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    shipping = 0.0
    for opt in (item.get("shippingOptions") or []):
        sc = opt.get("shippingCost") or {}
        try:
            shipping = float(sc.get("value") or 0)
        except (TypeError, ValueError):
            shipping = 0.0
        break
    cond = (item.get("condition") or "").lower()
    if "refurbished" in cond or "certified" in cond:
        condition = "refurbished"
    elif "new" in cond:
        condition = "new"
    else:
        condition = "used"
    item_id = item.get("itemId") or item.get("legacyItemId")
    url = item.get("itemWebUrl") or ""
    loc = ((item.get("itemLocation") or {}).get("country") or "").upper()
    if loc and loc != "CA":
        return None
    price_cad = price if currency == "CAD" else None
    raw_price_usd = price if currency == "USD" else None
    return {
        "source": "ebay",
        "external_id": f"ebay-{item_id}" if item_id else None,
        "title": title,
        "url": url,
        "price_cad": price_cad,
        "shipping_cad": shipping,
        "condition": condition,
        "seller_location": "CA",
        "posted_at": item.get("itemCreationDate") or item.get("itemEndDate"),
        "raw_json": item,
        "slug": detect_slug(title),
        "_raw_currency": currency,
        "_raw_price_usd": raw_price_usd,
    }


def fetch_ebay_browse(
    query: str = "pixel",
    *,
    limit: int = 50,
    condition: str = "USED|REFURBISHED",
    location: str = "CA",
    postal_code: str = "M5V",
    radius_km: int = 100,
    persist: bool = True,
) -> list[dict]:
    client_id, client_secret = eba_creds()
    if not client_id or not client_secret:
        log.info("ebay: EBAY_CLIENT_ID/SECRET not set, skipping live fetch")
        return []
    try:
        token = get_app_token(client_id, client_secret)
    except Exception as e:
        log.warning("ebay token fetch failed: %s", e)
        return []
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA",
        "X-EBAY-C-ENDUSERCTX": "contextualLocation=country=CA",
        "Accept": "application/json",
    }
    params = {
        "q": query,
        "limit": min(limit, 200),
        "filter": f"conditionIds:{{{condition}}},itemLocationCountry:{{{location}}},buyerPostalCode:{postal_code},maxDistance:{radius_km}",
        "sort": "price",
    }
    try:
        r = requests.get(EBAY_BROWSE_URL, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            log.warning("ebay browse HTTP %s: %s", r.status_code, r.text[:200])
            return []
        data = r.json()
    except Exception as e:
        log.warning("ebay browse fetch error: %s", e)
        return []
    items = data.get("itemSummaries") or []
    listings: list[dict] = []
    for it in items:
        lst = to_listing(it)
        if lst is None:
            continue
        if lst.get("price_cad") is None and lst.get("_raw_price_usd") is not None:
            try:
                lst["price_cad"] = usd_to_cad(lst["_raw_price_usd"])
            except Exception:
                continue
        for k in ("_raw_currency", "_raw_price_usd"):
            lst.pop(k, None)
        if persist:
            upsert_listing(lst)
        listings.append(lst)
    log.info("ebay: %d listings for query=%r", len(listings), query)
    return listings


def fetch_all_targets(queries: list[str] | None = None, *, persist: bool = True) -> int:
    qs = queries or ["pixel", "google pixel", "oneplus", "galaxy"]
    total = 0
    for q in qs:
        try:
            total += len(fetch_ebay_browse(q, persist=persist))
        except Exception as e:
            log.warning("ebay query %r failed: %s", q, e)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(fetch_all_targets())
