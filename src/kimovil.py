from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable

from .config import KIMOVIL_HEADERS, KIMOVIL_PREFETCH, STATIC_SPECS_PATH, TARGET_MODELS
from .db import init_db, upsert_specs

log = logging.getLogger("kimovil")

SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def load_static_specs(path: Path = STATIC_SPECS_PATH) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for slug, body in raw.items():
        if slug.startswith("_"):
            continue
        if not SLUG_RE.match(slug):
            continue
        row = {"slug": slug, **{k: v for k, v in body.items() if not k.startswith("_")}}
        rows.append(row)
    return rows


def seed_static(targets: Iterable[str] | None = None) -> int:
    init_db()
    rows = load_static_specs()
    if targets is not None:
        target_set = set(targets)
        rows = [r for r in rows if r["slug"] in target_set]
    return upsert_specs(rows, source="static")


def _try_curl_cffi() -> object:
    try:
        from curl_cffi import requests as cc
        return cc
    except ImportError:
        return None


def _map_kimovil_phone(phone: dict) -> dict | None:
    slug = (phone.get("slug") or "").lower()
    if not slug:
        return None
    name = phone.get("full_name") or phone.get("name") or ""
    brand = phone.get("brand") or name.split()[0] if name else ""
    if not brand:
        return None
    antutu = phone.get("antutu_score") or phone.get("antutu")
    return {
        "slug": slug,
        "brand": brand,
        "model": name,
        "release_year": int(phone["released_unix"]) if phone.get("released_unix") else None,
        "antutu": int(antutu) if antutu else None,
    }


def fetch_kimovil_prefetch(timeout: int = 30) -> list[dict]:
    cc = _try_curl_cffi()
    if cc is None:
        log.warning("curl_cffi not installed; skipping live Kimovil fetch")
        return []
    headers = {**KIMOVIL_HEADERS, "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
    try:
        r = cc.get(KIMOVIL_PREFETCH, impersonate="chrome124", headers=headers, timeout=timeout)
    except Exception as e:
        log.warning("Kimovil fetch error: %s", e)
        return []
    if r.status_code != 200:
        log.warning("Kimovil HTTP %s (%d bytes) - likely Cloudflare gate", r.status_code, len(r.content))
        return []
    try:
        data = r.json()
    except json.JSONDecodeError:
        log.warning("Kimovil returned non-JSON")
        return []
    phones = data.get("smartphones") or data.get("phones") or []
    target_set = set(TARGET_MODELS)
    rows: list[dict] = []
    for phone in phones:
        row = _map_kimovil_phone(phone)
        if not row:
            continue
        if target_set and row["slug"] not in target_set:
            continue
        rows.append(row)
    return rows


def merge_live_with_static(live_rows: list[dict]) -> list[dict]:
    static = {r["slug"]: r for r in load_static_specs()}
    for live in live_rows:
        s = static.get(live["slug"])
        if s is None:
            static[live["slug"]] = live
            continue
        for k, v in live.items():
            if v is not None:
                s[k] = v
    return list(static.values())


def refresh(targets: Iterable[str] | None = None, live: bool = True) -> dict:
    init_db()
    static_rows = load_static_specs()
    if targets is not None:
        target_set = set(targets)
        static_rows = [r for r in static_rows if r["slug"] in target_set]
    written = upsert_specs(static_rows, source="static")
    info = {"static": written, "live": 0, "source": "static"}
    if live:
        live_rows = fetch_kimovil_prefetch()
        if live_rows:
            merged = merge_live_with_static(live_rows)
            written = upsert_specs(merged, source="kimovil+static")
            info = {"static": len(merged), "live": len(live_rows), "source": "kimovil+static"}
    return info


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-live", action="store_true")
    p.add_argument("--slug", action="append", default=None)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(refresh(targets=a.slug, live=not a.no_live))
