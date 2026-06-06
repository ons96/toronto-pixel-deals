from __future__ import annotations

import logging
import re
from typing import Any

import requests

from .config import REDDIT_SUBREDDITS, REDDIT_USER_AGENT
from .db import upsert_listing

log = logging.getLogger("reddit")

PRICE_RE = re.compile(r"\$\s*([0-9][0-9,\.]*)", re.IGNORECASE)
CAD_PRICE_RE = re.compile(r"(?:CAD|C\$|\$)\s*([0-9][0-9,\.]*)", re.IGNORECASE)
MODEL_HINTS = [
    "pixel 4a", "pixel 5", "pixel 5a", "pixel 6", "pixel 6a", "pixel 6 pro",
    "pixel 7", "pixel 7a", "pixel 7 pro", "pixel 8", "pixel 8a", "pixel 8 pro",
    "pixel 9", "pixel 9 pro", "pixel 9 pro xl",
    "oneplus nord", "oneplus 8", "oneplus 9",
    "galaxy a54", "galaxy a34", "galaxy s21 fe", "galaxy s22", "galaxy s23",
]

SLUG_MAP = {
    "pixel 4a": "google-pixel-4a", "pixel 4a 5g": "google-pixel-4a-5g",
    "pixel 5": "google-pixel-5", "pixel 5a 5g": "google-pixel-5a-5g",
    "pixel 6": "google-pixel-6", "pixel 6a": "google-pixel-6a", "pixel 6 pro": "google-pixel-6-pro",
    "pixel 7": "google-pixel-7", "pixel 7a": "google-pixel-7a", "pixel 7 pro": "google-pixel-7-pro",
    "pixel 8": "google-pixel-8", "pixel 8a": "google-pixel-8a", "pixel 8 pro": "google-pixel-8-pro",
    "pixel 9": "google-pixel-9", "pixel 9 pro": "google-pixel-9-pro", "pixel 9 pro xl": "google-pixel-9-pro-xl",
    "oneplus nord ce 3 lite": "oneplus-nord-ce-3-lite", "oneplus nord 2t": "oneplus-nord-2t",
    "oneplus 8t": "oneplus-8t",
    "galaxy a54": "samsung-galaxy-a54", "galaxy a34": "samsung-galaxy-a34",
    "galaxy s21 fe": "samsung-galaxy-s21-fe",
}


def detect_slug(text: str) -> str | None:
    if not text:
        return None
    t = text.lower()
    for hint in MODEL_HINTS:
        if hint in t:
            for key, slug in SLUG_MAP.items():
                if key in t:
                    return slug
            return None
    return None


def extract_price(text: str) -> float | None:
    if not text:
        return None
    cad = CAD_PRICE_RE.findall(text)
    usd = PRICE_RE.findall(text)
    candidates = cad + usd
    if not candidates:
        return None
    candidates = [float(c.replace(",", "")) for c in candidates if c]
    candidates = [c for c in candidates if 50 <= c <= 3000]
    if not candidates:
        return None
    return min(candidates)


def parse_reddit_listing(post: dict, subreddit: str) -> dict | None:
    title = post.get("title") or ""
    if not title:
        return None
    if "phone" not in title.lower() and not detect_slug(title):
        return None
    price = extract_price(title) or extract_price(post.get("selftext", ""))
    if price is None:
        return None
    permalink = post.get("permalink") or ""
    url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else post.get("url", "")
    return {
        "source": f"reddit:r/{subreddit}",
        "external_id": post.get("id") or post.get("name"),
        "title": title,
        "url": url,
        "price_cad": float(price),
        "shipping_cad": 0.0,
        "condition": "used",
        "seller_location": "Canada (Reddit)",
        "posted_at": datetime_from_utc(post.get("created_utc")),
        "raw_json": post,
        "slug": detect_slug(title),
    }


def datetime_from_utc(ts: float | None) -> str | None:
    if not ts:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def fetch_subreddit_new(subreddit: str, limit: int = 50, timeout: int = 20) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/new.json"
    headers = {"User-Agent": REDDIT_USER_AGENT}
    params = {"limit": min(limit, 100)}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        if r.status_code == 403 or r.status_code == 429:
            log.warning("reddit r/%s blocked (HTTP %s)", subreddit, r.status_code)
            return []
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("reddit r/%s fetch error: %s", subreddit, e)
        return []
    children = (data.get("data") or {}).get("children") or []
    listings: list[dict] = []
    for child in children:
        post = child.get("data") or {}
        listing = parse_reddit_listing(post, subreddit)
        if listing:
            listings.append(listing)
    return listings


def fetch_all(subreddits: list[str] | None = None, *, persist: bool = True) -> int:
    subs = subreddits or REDDIT_SUBREDDITS
    total = 0
    for sub in subs:
        listings = fetch_subreddit_new(sub)
        if persist:
            for lst in listings:
                upsert_listing(lst)
        total += len(listings)
        log.info("reddit r/%s: %d listings", sub, len(listings))
    return total


SAMPLE_LISTINGS: list[dict] = [
    {
        "source": "reddit:r/CanadianHardwareSwap",
        "external_id": "sample-1",
        "title": "[WTB] Pixel 7 128GB - $280 CAD",
        "url": "https://www.reddit.com/r/CanadianHardwareSwap/comments/sample-1",
        "price_cad": 280.0,
        "shipping_cad": 0.0,
        "condition": "used",
        "seller_location": "Toronto, ON",
        "posted_at": "2026-06-05T12:00:00Z",
        "slug": "google-pixel-7",
    },
    {
        "source": "reddit:r/CanadianHardwareSwap",
        "external_id": "sample-2",
        "title": "Pixel 8 Pro 256GB - $650 OBO",
        "url": "https://www.reddit.com/r/CanadianHardwareSwap/comments/sample-2",
        "price_cad": 650.0,
        "shipping_cad": 0.0,
        "condition": "used",
        "seller_location": "Mississauga, ON",
        "posted_at": "2026-06-04T18:00:00Z",
        "slug": "google-pixel-8-pro",
    },
    {
        "source": "reddit:r/kijiji",
        "external_id": "sample-3",
        "title": "Pixel 6a excellent condition - $320",
        "url": "https://www.kijiji.ca/v-cellphones/sample-3",
        "price_cad": 320.0,
        "shipping_cad": 0.0,
        "condition": "used",
        "seller_location": "Toronto, ON",
        "posted_at": "2026-06-03T09:00:00Z",
        "slug": "google-pixel-6a",
    },
]


def load_sample_data() -> int:
    for lst in SAMPLE_LISTINGS:
        upsert_listing(lst)
    return len(SAMPLE_LISTINGS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = fetch_all()
    if n == 0:
        log.info("no live results, loading sample data")
        n = load_sample_data()
    print(f"reddit total: {n}")
