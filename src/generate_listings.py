from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, DEFAULT_SHIP_CAD
from src.db import init_db, upsert_listing


GTA_AREAS = [
    "Toronto, ON", "North York, ON", "Scarborough, ON", "Etobicoke, ON",
    "Mississauga, ON", "Brampton, ON", "Markham, ON", "Vaughan, ON",
    "Richmond Hill, ON", "Oakville, ON", "Burlington, ON", "Pickering, ON",
    "Ajax, ON", "Whitby, ON", "Oshawa, ON",
]

LISTINGS: list[dict] = [
    {"source": "kijiji",  "slug": "google-pixel-9",       "title": "Google Pixel 9 128GB Obsidian - Unlocked - Excellent",  "price_cad": 720, "shipping_cad": 0,  "condition": "Excellent"},
    {"source": "kijiji",  "slug": "google-pixel-9",       "title": "Google Pixel 9 Pro 256GB Hazel - Like New",            "price_cad": 980, "shipping_cad": 0,  "condition": "Like New"},
    {"source": "ebay",    "slug": "google-pixel-9",       "title": "Google Pixel 9 128GB - Porcelain - Used - Free Ship",  "price_cad": 680, "shipping_cad": 0,  "condition": "Used"},
    {"source": "kijiji",  "slug": "google-pixel-8-pro",   "title": "Google Pixel 8 Pro 256GB Bay - Unlocked",              "price_cad": 650, "shipping_cad": 0,  "condition": "Excellent"},
    {"source": "facebook","slug": "google-pixel-8-pro",   "title": "Pixel 8 Pro 128GB Obsidian - Mint condition",          "price_cad": 620, "shipping_cad": 0,  "condition": "Like New"},
    {"source": "ebay",    "slug": "google-pixel-8-pro",   "title": "Google Pixel 8 Pro 128GB Unlocked - Refurb",           "price_cad": 580, "shipping_cad": 0,  "condition": "Refurbished"},
    {"source": "kijiji",  "slug": "google-pixel-8",       "title": "Google Pixel 8 128GB Hazel - Unlocked - 8/10",         "price_cad": 450, "shipping_cad": 0,  "condition": "Good"},
    {"source": "ebay",    "slug": "google-pixel-8",       "title": "Google Pixel 8 128GB - Used - Ships from Mississauga",  "price_cad": 420, "shipping_cad": 0,  "condition": "Used"},
    {"source": "reddit",  "slug": "google-pixel-8",       "title": "[ONT] Pixel 8 128GB Obsidian - Excellent",             "price_cad": 430, "shipping_cad": 15, "condition": "Excellent"},
    {"source": "kijiji",  "slug": "google-pixel-8a",      "title": "Google Pixel 8a 128GB - Like New - Unlocked",           "price_cad": 380, "shipping_cad": 0,  "condition": "Like New"},
    {"source": "ebay",    "slug": "google-pixel-8a",      "title": "Google Pixel 8a 128GB Bay - Refurbished",               "price_cad": 340, "shipping_cad": 0,  "condition": "Refurbished"},
    {"source": "kijiji",  "slug": "google-pixel-7a",      "title": "Google Pixel 7a 128GB Charcoal - Unlocked",             "price_cad": 300, "shipping_cad": 0,  "condition": "Good"},
    {"source": "ebay",    "slug": "google-pixel-7a",      "title": "Google Pixel 7a 128GB - Used - Ships Canada",           "price_cad": 280, "shipping_cad": 0,  "condition": "Used"},
    {"source": "kijiji",  "slug": "google-pixel-7",       "title": "Google Pixel 7 128GB Snow - Unlocked",                  "price_cad": 320, "shipping_cad": 0,  "condition": "Excellent"},
    {"source": "reddit",  "slug": "google-pixel-7",       "title": "[GTA] Pixel 7 128GB Lemongrass - 9/10",                 "price_cad": 300, "shipping_cad": 0,  "condition": "Excellent"},
    {"source": "kijiji",  "slug": "google-pixel-7-pro",   "title": "Google Pixel 7 Pro 256GB Hazel - Unlocked",             "price_cad": 480, "shipping_cad": 0,  "condition": "Good"},
    {"source": "ebay",    "slug": "google-pixel-7-pro",   "title": "Google Pixel 7 Pro 128GB - Refurbished",                "price_cad": 440, "shipping_cad": 0,  "condition": "Refurbished"},
    {"source": "kijiji",  "slug": "google-pixel-6-pro",   "title": "Google Pixel 6 Pro 256GB Stormy Black",                 "price_cad": 380, "shipping_cad": 0,  "condition": "Good"},
    {"source": "ebay",    "slug": "google-pixel-6-pro",   "title": "Google Pixel 6 Pro 128GB - Used - Ships CA",            "price_cad": 340, "shipping_cad": 0,  "condition": "Used"},
    {"source": "kijiji",  "slug": "google-pixel-6",       "title": "Google Pixel 6 128GB Sorta Seafoam",                    "price_cad": 260, "shipping_cad": 0,  "condition": "Good"},
    {"source": "kijiji",  "slug": "google-pixel-6a",      "title": "Google Pixel 6a 128GB Charcoal - Unlocked",              "price_cad": 230, "shipping_cad": 0,  "condition": "Good"},
    {"source": "ebay",    "slug": "google-pixel-6a",      "title": "Google Pixel 6a 128GB - Refurbished",                   "price_cad": 210, "shipping_cad": 0,  "condition": "Refurbished"},
    {"source": "kijiji",  "slug": "google-pixel-5a-5g",   "title": "Google Pixel 5a 5G 128GB - Unlocked",                   "price_cad": 180, "shipping_cad": 0,  "condition": "Good"},
    {"source": "kijiji",  "slug": "google-pixel-5",       "title": "Google Pixel 5 128GB Just Black",                       "price_cad": 200, "shipping_cad": 0,  "condition": "Good"},
    {"source": "ebay",    "slug": "google-pixel-4a-5g",   "title": "Google Pixel 4a 5G 128GB - Used",                       "price_cad": 140, "shipping_cad": 0,  "condition": "Used"},
    {"source": "kijiji",  "slug": "google-pixel-4a",      "title": "Google Pixel 4a 128GB Just Black - Unlocked",           "price_cad": 110, "shipping_cad": 0,  "condition": "Good"},
    {"source": "kijiji",  "slug": "oneplus-nord-ce-3-lite","title": "OnePlus Nord CE 3 Lite 128GB - Unlocked",             "price_cad": 220, "shipping_cad": 0,  "condition": "Good"},
    {"source": "kijiji",  "slug": "samsung-galaxy-a54",   "title": "Samsung Galaxy A54 128GB - Unlocked",                   "price_cad": 280, "shipping_cad": 0,  "condition": "Good"},
    {"source": "ebay",    "slug": "samsung-galaxy-s21-fe","title": "Samsung Galaxy S21 FE 128GB - Refurbished",             "price_cad": 320, "shipping_cad": 0,  "condition": "Refurbished"},
]

SOURCE_URLS = {
    "kijiji": "https://www.kijiji.ca/b-cell-phone/gta-greater-toronto-area/cellphones/q-{slug}/",
    "ebay":   "https://www.ebay.ca/sch/i.html?_nkw={slug}&_sacat=0&LH_ItemCondition=3000",
    "reddit": "https://www.reddit.com/r/CanadianHardwareSwap/search/?q={slug}&restrict_sr=on",
    "facebook": "https://www.facebook.com/marketplace/toronto/search/?query={slug}",
}


def jitter(price: int, pct: float = 0.07) -> int:
    delta = price * pct
    return int(price + random.uniform(-delta, delta))


def to_utc(days_ago_max: int = 14) -> str:
    delta = timedelta(days=random.randint(0, days_ago_max), hours=random.randint(0, 23))
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--clear-existing", action="store_true")
    args = p.parse_args()
    random.seed(args.seed)
    init_db()
    if args.clear_existing:
        import sqlite3
        with sqlite3.connect(DB_PATH) as c:
            c.execute("DELETE FROM listings WHERE source IN ('kijiji','ebay','reddit','facebook')")
    n = 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for base in LISTINGS:
        slug = base["slug"]
        ext = f"{base['source']}-{slug}-{random.randint(10000,99999)}"
        price = jitter(base["price_cad"])
        ship = base.get("shipping_cad", DEFAULT_SHIP_CAD)
        listing = {
            "source": base["source"],
            "external_id": ext,
            "title": base["title"],
            "url": SOURCE_URLS[base["source"]].format(slug=slug),
            "price_cad": float(price),
            "shipping_cad": float(ship),
            "condition": base["condition"],
            "seller_location": random.choice(GTA_AREAS),
            "posted_at": to_utc(),
            "slug": slug,
        }
        upsert_listing(listing)
        n += 1
    print(f"inserted/updated {n} sample listings (seed={args.seed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
