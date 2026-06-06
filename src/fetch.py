from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import currency, ebay, kimovil, reddit
from src.db import counts, init_db

log = logging.getLogger("fetch")


def main() -> int:
    p = argparse.ArgumentParser(description="Deal aggregator fetcher")
    p.add_argument("--no-kimovil", action="store_true")
    p.add_argument("--no-ebay", action="store_true")
    p.add_argument("--no-reddit", action="store_true")
    p.add_argument("--no-fx", action="store_true")
    p.add_argument("--sample-reddit", action="store_true", help="load sample Reddit listings (offline mode)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()
    print("== Kimovil ==")
    if not args.no_kimovil:
        info = kimovil.refresh(live=True)
        print(info)
    print("== Currency (Frankfurter) ==")
    if not args.no_fx:
        n = currency.refresh_all()
        rate = currency.get_fx_rate("USD", "CAD")
        print(f"USD->CAD = {rate} (refreshed {n} quotes)")
    print("== eBay ==")
    if not args.no_ebay:
        n = ebay.fetch_all_targets()
        print(f"ebay: {n} listings")
    print("== Reddit ==")
    if not args.no_reddit:
        n = reddit.fetch_all()
        if n == 0 or args.sample_reddit:
            log.info("reddit: live fetch returned 0, loading sample data")
            n = reddit.load_sample_data()
        print(f"reddit: {n} listings")
    print()
    print("DB counts:", counts())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
