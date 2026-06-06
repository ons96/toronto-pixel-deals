from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, render_template, request

from src.config import Weights
from src.db import all_listings, all_specs, counts, init_db
from src.score import build_index, rank_listings

log = logging.getLogger("app")

app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
)

DEFAULT_WEIGHTS = Weights()


def _weights_from_request() -> Weights:
    body = request.get_json(silent=True) or {}
    if not body and request.args:
        body = request.args.to_dict()
    overrides = {k: float(v) for k, v in body.items() if k in DEFAULT_WEIGHTS.__dict__}
    return Weights(**{**DEFAULT_WEIGHTS.__dict__, **overrides})


@app.route("/")
def index():
    return render_template(
        "index.html",
        weights=DEFAULT_WEIGHTS.normalized().__dict__,
        db=counts(),
    )


@app.route("/api/deals", methods=["GET", "POST"])
def api_deals():
    weights = _weights_from_request()
    top = int(request.args.get("top", 20))
    include_unknown = bool(request.args.get("include_unknown"))
    ranked = rank_listings(
        all_listings(),
        build_index(all_specs()),
        weights,
        require_quality=not include_unknown,
        top=top,
    )
    return jsonify(
        {
            "weights": weights.normalized().__dict__,
            "db": counts(),
            "count": len(ranked),
            "deals": ranked,
        }
    )


@app.route("/api/rerank", methods=["POST"])
def api_rerank():
    return api_deals()


@app.route("/api/specs")
def api_specs():
    specs = all_specs()
    return jsonify(
        {
            "count": len(specs),
            "specs": [
                {
                    "slug": s["slug"],
                    "brand": s["brand"],
                    "model": s["model"],
                    "antutu": s["antutu"],
                    "battery_mah": s["battery_mah"],
                    "camera_main_mp": s["camera_main_mp"],
                }
                for s in specs
            ],
        }
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()
    print(f"Deal aggregator UI: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
