from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import ONTARIO_HST, Weights
from src.db import all_listings, all_specs, init_db
from src.normalize import ComponentScores, quality_score

log = logging.getLogger("score")


def _row_get(row, key, default=None):
    if hasattr(row, "get"):
        return row.get(key) if row.get(key) is not None else default
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def net_cost(listing, hst: float = ONTARIO_HST) -> float:
    price = float(_row_get(listing, "price_cad") or 0.0)
    ship = float(_row_get(listing, "shipping_cad") or 0.0)
    return round((price + ship) * (1.0 + hst), 2)


def spec_to_dict(row) -> dict:
    d = dict(row)
    return d


def build_index(specs: list) -> dict[str, dict]:
    return {s["slug"]: spec_to_dict(s) for s in specs}


def score_listing(
    listing,
    spec: dict | None,
    weights: Weights,
    hst: float = ONTARIO_HST,
) -> dict[str, Any]:
    cost = net_cost(listing, hst=hst)
    quality = 0.0
    components = None
    if spec:
        components = ComponentScores.from_spec(spec)
        quality = quality_score(components, weights)
    deal = (quality / cost) * 1000.0 if cost > 0 else 0.0
    return {
        "id": _row_get(listing, "id"),
        "source": _row_get(listing, "source"),
        "title": _row_get(listing, "title"),
        "url": _row_get(listing, "url"),
        "price_cad": float(_row_get(listing, "price_cad") or 0.0),
        "shipping_cad": float(_row_get(listing, "shipping_cad") or 0.0),
        "net_cost_cad": cost,
        "condition": _row_get(listing, "condition"),
        "seller_location": _row_get(listing, "seller_location"),
        "slug": _row_get(listing, "slug") or (spec["slug"] if spec else None),
        "brand": spec["brand"] if spec else None,
        "model": spec["model"] if spec else None,
        "quality": round(quality, 2),
        "deal_score": round(deal, 2),
        "components": components.__dict__ if components else None,
    }


def rank_listings(
    listings: list,
    spec_index: dict[str, dict],
    weights: Weights,
    *,
    require_quality: bool = True,
    top: int | None = None,
) -> list[dict]:
    out: list[dict] = []
    for lst in listings:
        slug = _row_get(lst, "slug")
        spec = spec_index.get(slug) if slug else None
        if require_quality and not spec:
            continue
        out.append(score_listing(lst, spec, weights))
    out.sort(key=lambda r: r["deal_score"], reverse=True)
    if top is not None:
        out = out[:top]
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--weights", type=str, default=None, help='JSON, e.g. {"cpu":0.5,"battery":0.2,"camera":0.3}')
    p.add_argument("--include-unknown", action="store_true", help="include listings without a matching spec")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()
    weights = Weights()
    if args.weights:
        overrides = json.loads(args.weights)
        weights = Weights(**{**{k: v for k, v in weights.__dict__.items() if not k.startswith("_")}, **overrides})
    print(f"weights: {weights.normalized().__dict__}")
    listings = all_listings()
    specs = all_specs()
    spec_index = build_index(specs)
    print(f"indexed {len(listings)} listings against {len(spec_index)} specs")
    ranked = rank_listings(listings, spec_index, weights, require_quality=not args.include_unknown, top=args.top)
    print()
    print(f"{'rank':>4} {'model':<26} {'src':<28} {'price':>8} {'ship':>6} {'net':>8} {'qual':>6} {'deal':>8}")
    print("-" * 100)
    for i, r in enumerate(ranked, 1):
        model = (r.get("model") or "?")[:26]
        print(f"{i:>4} {model:<26} {r['source'][:28]:<28} {r['price_cad']:>8.0f} {r['shipping_cad']:>6.0f} {r['net_cost_cad']:>8.0f} {r['quality']:>6.1f} {r['deal_score']:>8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
