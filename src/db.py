from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS specs (
    slug TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    release_year INTEGER,
    cpu TEXT,
    cpu_score INTEGER,
    antutu INTEGER,
    geekbench5_single INTEGER,
    geekbench5_multi INTEGER,
    geekbench6_single INTEGER,
    geekbench6_multi INTEGER,
    battery_mah INTEGER,
    camera_main_mp INTEGER,
    camera_count INTEGER,
    ram_gb INTEGER,
    storage_gb INTEGER,
    display_in REAL,
    refresh_hz INTEGER,
    weight_g INTEGER,
    five_g INTEGER DEFAULT 0,
    source TEXT,
    fetched_at TEXT,
    data_json TEXT
);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT,
    title TEXT,
    url TEXT,
    price_cad REAL,
    shipping_cad REAL,
    condition TEXT,
    seller_location TEXT,
    posted_at TEXT,
    raw_json TEXT,
    slug TEXT,
    fetched_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_slug ON listings(slug);
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);

CREATE TABLE IF NOT EXISTS fx_rates (
    base TEXT NOT NULL,
    quote TEXT NOT NULL,
    rate REAL NOT NULL,
    as_of TEXT NOT NULL,
    PRIMARY KEY (base, quote, as_of)
);

CREATE TABLE IF NOT EXISTS api_keys (
    key TEXT PRIMARY KEY,
    tier TEXT NOT NULL,
    contact TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS api_usage (
    key TEXT NOT NULL,
    date TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, date)
);
CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(date);
"""


DEMO_KEY = "demo-free-key"


def init_db(path: Path = DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        # Seed a demo free key so the API works out-of-the-box for testing.
        n = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
        if n == 0:
            conn.execute(
                "INSERT INTO api_keys(key, tier, contact) VALUES (?,?,?)",
                (DEMO_KEY, "free", "demo/test key, intentionally public"),
            )
        conn.commit()


@contextmanager
def conn_ctx(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def upsert_specs(rows: list[dict], source: str = "static") -> int:
    if not rows:
        return 0
    n = 0
    with conn_ctx() as c:
        for r in rows:
            data_json = json.dumps(r, ensure_ascii=False)
            c.execute(
                """
                INSERT INTO specs (
                    slug, brand, model, release_year, cpu, cpu_score,
                    antutu, geekbench5_single, geekbench5_multi,
                    geekbench6_single, geekbench6_multi,
                    battery_mah, camera_main_mp, camera_count,
                    ram_gb, storage_gb, display_in, refresh_hz,
                    weight_g, five_g, source, fetched_at, data_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?)
                ON CONFLICT(slug) DO UPDATE SET
                    brand=excluded.brand,
                    model=excluded.model,
                    release_year=excluded.release_year,
                    cpu=excluded.cpu,
                    cpu_score=excluded.cpu_score,
                    antutu=excluded.antutu,
                    geekbench5_single=excluded.geekbench5_single,
                    geekbench5_multi=excluded.geekbench5_multi,
                    geekbench6_single=excluded.geekbench6_single,
                    geekbench6_multi=excluded.geekbench6_multi,
                    battery_mah=excluded.battery_mah,
                    camera_main_mp=excluded.camera_main_mp,
                    camera_count=excluded.camera_count,
                    ram_gb=excluded.ram_gb,
                    storage_gb=excluded.storage_gb,
                    display_in=excluded.display_in,
                    refresh_hz=excluded.refresh_hz,
                    weight_g=excluded.weight_g,
                    five_g=excluded.five_g,
                    source=excluded.source,
                    fetched_at=excluded.fetched_at,
                    data_json=excluded.data_json
                """,
                (
                    r["slug"], r["brand"], r["model"], r.get("release_year"),
                    r.get("cpu"), r.get("cpu_score"), r.get("antutu"),
                    r.get("geekbench5_single"), r.get("geekbench5_multi"),
                    r.get("geekbench6_single"), r.get("geekbench6_multi"),
                    r.get("battery_mah"), r.get("camera_main_mp"),
                    r.get("camera_count"), r.get("ram_gb"),
                    r.get("storage_gb"), r.get("display_in"),
                    r.get("refresh_hz"), r.get("weight_g"),
                    1 if r.get("five_g") else 0,
                    source, data_json,
                ),
            )
            n += 1
    return n


def upsert_listing(listing: dict) -> bool:
    if not listing.get("external_id"):
        listing = {**listing, "external_id": f"{listing['source']}-{hash(listing.get('url') or listing.get('title',''))}"}
    with conn_ctx() as c:
        cur = c.execute(
            """
            INSERT INTO listings (
                source, external_id, title, url, price_cad, shipping_cad,
                condition, seller_location, posted_at, raw_json, slug
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source, external_id) DO UPDATE SET
                price_cad=excluded.price_cad,
                shipping_cad=excluded.shipping_cad,
                condition=excluded.condition,
                raw_json=excluded.raw_json,
                slug=COALESCE(excluded.slug, listings.slug)
            """,
            (
                listing["source"], listing["external_id"],
                listing.get("title"), listing.get("url"),
                listing.get("price_cad"), listing.get("shipping_cad"),
                listing.get("condition"), listing.get("seller_location"),
                listing.get("posted_at"),
                json.dumps(listing, ensure_ascii=False),
                listing.get("slug"),
            ),
        )
    return cur.rowcount > 0


def upsert_fx(base: str, quote: str, rate: float, as_of: str) -> None:
    with conn_ctx() as c:
        c.execute(
            "INSERT OR REPLACE INTO fx_rates(base, quote, rate, as_of) VALUES (?,?,?,?)",
            (base.upper(), quote.upper(), rate, as_of),
        )


def latest_fx(base: str, quote: str) -> tuple[float, str] | None:
    with conn_ctx() as c:
        row = c.execute(
            "SELECT rate, as_of FROM fx_rates WHERE base=? AND quote=? ORDER BY as_of DESC LIMIT 1",
            (base.upper(), quote.upper()),
        ).fetchone()
    return (row["rate"], row["as_of"]) if row else None


def all_listings(limit: int = 500) -> list[sqlite3.Row]:
    with conn_ctx() as c:
        return c.execute(
            "SELECT * FROM listings ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def all_specs() -> list[sqlite3.Row]:
    with conn_ctx() as c:
        return c.execute("SELECT * FROM specs").fetchall()


def counts() -> dict[str, int]:
    with conn_ctx() as c:
        return {
            "specs": c.execute("SELECT COUNT(*) FROM specs").fetchone()[0],
            "listings": c.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
            "fx": c.execute("SELECT COUNT(*) FROM fx_rates").fetchone()[0],
        }


def freshness() -> dict[str, str | None]:
    """Latest stored source timestamps, or None where the table has no rows."""
    with conn_ctx() as c:
        row = c.execute(
            """
            SELECT
                (SELECT MAX(fetched_at) FROM listings) AS listings_fetched_at,
                (SELECT MAX(fetched_at) FROM specs) AS specs_fetched_at,
                (SELECT MAX(as_of) FROM fx_rates) AS fx_rates_as_of
            """
        ).fetchone()
    return {
        "listings_fetched_at": row["listings_fetched_at"],
        "specs_fetched_at": row["specs_fetched_at"],
        "fx_rates_as_of": row["fx_rates_as_of"],
    }


# --- API key + usage helpers (RapidAPI-style usage caps) ---
# ponytail: SQLite single-writer is the ceiling here. The VPS deploy is a
# single uvicorn process, so there is no write contention. Upgrade path: move
# usage counting to Redis (INCR + EXPIRE) if you scale to multiple workers or
# need sub-millisecond counters; SQLite stays the source of truth for keys/tiers.

# Tier -> daily request cap. None means unlimited (ultra tier).
TIER_LIMITS: dict[str, int | None] = {
    "free": 100,
    "basic": 5000,
    "pro": 50000,
    "ultra": None,
}


def get_api_key(key: str) -> sqlite3.Row | None:
    """Return the api_keys row for ``key`` if active, else None."""
    with conn_ctx() as c:
        return c.execute(
            "SELECT * FROM api_keys WHERE key=? AND active=1",
            (key,),
        ).fetchone()


def _today_utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def today_usage(key: str) -> int:
    """Today's (UTC) request count for ``key`` (0 if none yet)."""
    with conn_ctx() as c:
        row = c.execute(
            "SELECT count FROM api_usage WHERE key=? AND date=?",
            (key, _today_utc()),
        ).fetchone()
    return int(row["count"]) if row else 0


def incr_usage(key: str) -> int:
    """Atomically increment today's counter and return the new value."""
    today = _today_utc()
    with conn_ctx() as c:
        c.execute(
            """
            INSERT INTO api_usage(key, date, count) VALUES (?,?,1)
            ON CONFLICT(key, date) DO UPDATE SET count = count + 1
            """,
            (key, today),
        )
        row = c.execute(
            "SELECT count FROM api_usage WHERE key=? AND date=?",
            (key, today),
        ).fetchone()
    return int(row["count"]) if row else 1


def tier_limit(tier: str) -> int | None:
    """Daily request cap for ``tier`` (None = unlimited)."""
    return TIER_LIMITS.get(tier)
