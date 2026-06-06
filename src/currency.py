from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests

from .config import FRANKFURTER_CURRENCIES, FRANKFURTER_LATEST, FX_CACHE_HOURS
from .db import latest_fx, upsert_fx

log = logging.getLogger("currency")

SUPPORTED_QUOTES = ("CAD", "USD", "EUR", "GBP")


def fetch_latest_rates(base: str = "USD", symbols: Iterable[str] | None = None) -> dict:
    symbols = list(symbols) if symbols else ["CAD"]
    params = {"base": base.upper()}
    if symbols:
        params["symbols"] = ",".join(s.upper() for s in symbols)
    r = requests.get(FRANKFURTER_LATEST, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def list_supported_currencies() -> list[dict]:
    r = requests.get(FRANKFURTER_CURRENCIES, timeout=15)
    r.raise_for_status()
    return r.json()


def get_fx_rate(base: str, quote: str, *, force_refresh: bool = False) -> float:
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return 1.0
    if not force_refresh:
        cached = latest_fx(base, quote)
        if cached:
            rate, as_of = cached
            try:
                parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - parsed
            except ValueError:
                age = timedelta(days=999)
            if age < timedelta(hours=FX_CACHE_HOURS):
                return float(rate)
    payload = fetch_latest_rates(base=base, symbols=[quote])
    rate = float(payload["rates"][quote])
    upsert_fx(base, quote, rate, payload["date"])
    return rate


def usd_to_cad(amount: float, *, force_refresh: bool = False) -> float:
    return round(float(amount) * get_fx_rate("USD", "CAD", force_refresh=force_refresh), 2)


def refresh_all(quotes: Iterable[str] = ("CAD",)) -> int:
    n = 0
    for q in quotes:
        try:
            get_fx_rate("USD", q, force_refresh=True)
            n += 1
        except Exception as e:
            log.warning("FX refresh failed USD->%s: %s", q, e)
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("USD->CAD:", get_fx_rate("USD", "CAD", force_refresh=True))
    print("USD->EUR:", get_fx_rate("USD", "EUR", force_refresh=True))
    print("Supported:", len(list_supported_currencies()), "currencies")
