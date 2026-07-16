"""FastAPI service exposing the Pixel deal scoring logic with RapidAPI-style usage caps.

This is an *additive* API layer. It imports and reuses the existing scoring
pipeline (score.py / db.py / config.py / normalize.py) without duplicating it.
The Flask UI (app.py) stays functional for browsing.

Run locally:
    uv run uvicorn src.api:app --port 8100
or:
    uv run python -m src.api
"""
from __future__ import annotations

import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from src.db import (
    DEMO_KEY,
    all_listings,
    all_specs,
    counts,
    freshness,
    get_api_key,
    incr_usage,
    init_db,
    tier_limit,
    today_usage,
)
from src.config import Weights
from src.score import build_index, rank_listings

log = logging.getLogger("api")

API_VERSION = "1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the schema + demo key exist when the server boots."""
    init_db()
    yield


app = FastAPI(
    title="Toronto Pixel Deal Score API",
    version=API_VERSION,
    description="Rank used/refurbished Google Pixel (and mid-range alt) deals by quality-per-CAD with Ontario HST.",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Auth + usage-cap dependency
# ---------------------------------------------------------------------------
# ponytail: SQLite single-writer is the ceiling. Single uvicorn process on the
# VPS = no write contention. Upgrade path: Redis INCR/EXPIRE for counters if
# multi-worker; keep SQLite as the key/tier source of truth.

# RapidAPI injects X-RapidAPI-Proxy-Secret; direct/own customers use X-API-Key.
_API_KEY_HEADERS = ("x-api-key", "x-rapidapi-proxy-secret")


def _resets_at_iso() -> str:
    """Next midnight UTC as an ISO-8601 string."""
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.isoformat()


def require_api_key(request: Request) -> dict:
    """Resolve the caller's key+tier and enforce the daily usage cap.

    Reads X-RapidAPI-Proxy-Secret (RapidAPI) or X-API-Key (direct customers).
    Unknown / missing key -> 401. Over daily limit -> 429. Otherwise returns
    a dict describing the caller and increments today's counter.
    """
    key: Optional[str] = None
    for h in _API_KEY_HEADERS:
        v = request.headers.get(h)
        if v:
            key = v.strip()
            break
    if not key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_api_key",
                "message": "Provide X-API-Key (direct) or X-RapidAPI-Proxy-Secret (RapidAPI).",
            },
        )

    row = get_api_key(key)
    if row is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_api_key", "message": "Unknown or inactive API key."},
        )

    tier = row["tier"]
    limit = tier_limit(tier)
    used = today_usage(key)

    # None limit = unlimited (ultra tier); skip both the check and the increment
    # so ultra callers never touch the usage table.
    if limit is not None:
        if used >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "daily_limit_exceeded",
                    "limit": limit,
                    "used": used,
                    "tier": tier,
                    "resets_at": _resets_at_iso(),
                },
            )
        used = incr_usage(key)

    return {"key": key, "tier": tier, "limit": limit, "used": used}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WEIGHT_FIELDS = ("cpu", "battery", "camera", "display", "form_factor")


def _weights_from_query(
    cpu: float,
    battery: float,
    camera: float,
    display: float,
    form_factor: float,
) -> Weights:
    return Weights(
        cpu=cpu,
        battery=battery,
        camera=camera,
        display=display,
        form_factor=form_factor,
    )


def _spec_to_public(s) -> dict:
    """Same shape as the Flask /api/specs endpoint."""
    return {
        "slug": s["slug"],
        "brand": s["brand"],
        "model": s["model"],
        "antutu": s["antutu"],
        "battery_mah": s["battery_mah"],
        "camera_main_mp": s["camera_main_mp"],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Liveness + DB row counts. Not auth-gated, not rate-counted."""
    return {
        "status": "ok",
        "db": counts(),
        "freshness": freshness(),
        "version": API_VERSION,
    }


@app.get("/deals/top")
def deals_top(
    request: Request,
    n: int = Query(20, ge=1, le=500),
    cpu: float = Query(0.40, ge=0, le=1),
    battery: float = Query(0.25, ge=0, le=1),
    camera: float = Query(0.25, ge=0, le=1),
    display: float = Query(0.05, ge=0, le=1),
    form_factor: float = Query(0.05, ge=0, le=1),
    include_unknown: bool = Query(False),
    caller: dict = Depends(require_api_key),
) -> dict:
    """Top-N ranked deals by DealScore for the given weights."""
    weights = _weights_from_query(cpu, battery, camera, display, form_factor)
    ranked = rank_listings(
        all_listings(),
        build_index(all_specs()),
        weights,
        require_quality=not include_unknown,
        top=n,
    )
    return {
        "weights": weights.normalized().__dict__,
        "count": len(ranked),
        "deals": ranked,
        "freshness": freshness(),
        "tier": caller["tier"],
        "used": caller["used"],
        "limit": caller["limit"],
    }


@app.get("/deals/refresh")
def deals_refresh(
    request: Request,
    caller: dict = Depends(require_api_key),
) -> JSONResponse:
    """Trigger a data fetch (paid feature: pro/ultra tiers only).

    Shells out to ``python -m src.fetch --sample-reddit`` so the fetcher's
    argparse entrypoint stays the single source of fetch behaviour. Returns
    503 with a clear message if the fetch fails (offline / CF block).
    """
    if caller["tier"] not in ("pro", "ultra"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tier_required",
                "message": "Deals refresh is a Pro+ feature. Upgrade your tier.",
                "tier": caller["tier"],
            },
        )

    root = Path(__file__).resolve().parent.parent
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src.fetch", "--sample-reddit"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=503,
            detail={"error": "fetch_timeout", "message": "Data fetch timed out (120s)."},
        )
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=503,
            detail={"error": "fetch_failed", "message": f"Could not run fetch: {e}"},
        )

    if proc.returncode != 0:
        # Fetcher exited non-zero (network down, CF block, etc.) -> 503, do not crash.
        raise HTTPException(
            status_code=503,
            detail={
                "error": "fetch_failed",
                "message": "Data fetch did not complete. The service is still serving cached data.",
                "returncode": proc.returncode,
                "stderr_tail": (proc.stderr or "").strip().splitlines()[-1] if proc.stderr else "",
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "refreshed",
            "db": counts(),
            "freshness": freshness(),
            "stdout_tail": (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else "",
        },
    )


@app.get("/specs/{slug}")
def spec_one(
    slug: str,
    request: Request,
    caller: dict = Depends(require_api_key),
) -> dict:
    """Spec for one phone model, 404 if not found."""
    for s in all_specs():
        if s["slug"] == slug:
            return _spec_to_public(s)
    raise HTTPException(status_code=404, detail={"error": "not_found", "slug": slug})


@app.get("/specs")
def specs_all(
    request: Request,
    caller: dict = Depends(require_api_key),
) -> dict:
    """All specs (same shape as the Flask /api/specs endpoint)."""
    rows = [_spec_to_public(s) for s in all_specs()]
    return {"count": len(rows), "specs": rows}


# ---------------------------------------------------------------------------
# Boot / smoke
# ---------------------------------------------------------------------------

def _smoke() -> None:
    """Tiny inline smoke using FastAPI TestClient (no network)."""
    from fastapi.testclient import TestClient

    init_db()
    # Seed offline sample data so the reported JSON shows real ranked deals.
    from src import kimovil, reddit
    kimovil.seed_static()
    reddit.load_sample_data()

    client = TestClient(app)

    h = client.get("/health")
    assert h.status_code == 200, h.text
    body = h.json()
    assert body["status"] == "ok"
    assert "db" in body and "version" in body
    print("health OK:", body)

    # No key -> 401
    noauth = client.get("/deals/top?n=3")
    assert noauth.status_code == 401, noauth.text
    print("no-auth 401 OK")

    # Demo key -> 200
    r = client.get("/deals/top?n=3", headers={"X-API-Key": DEMO_KEY})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "weights" in j and "deals" in j and "count" in j
    print("deals/top OK: count=%d tier=%s used=%s" % (j["count"], j["tier"], j["used"]))

    # specs list
    s = client.get("/specs", headers={"X-API-Key": DEMO_KEY})
    assert s.status_code == 200, s.text
    print("specs OK: count=%d" % s.json()["count"])

    print("SMOKE PASS")


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Toronto Pixel Deal Score API")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8100)
    p.add_argument("--smoke", action="store_true", help="run inline smoke and exit")
    p.add_argument("--reload", action="store_true")
    args = p.parse_args()

    if args.smoke:
        _smoke()
        return 0

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    init_db()
    import uvicorn

    print(f"Toronto Pixel Deal Score API: http://{args.host}:{args.port}  (docs at /docs)")
    uvicorn.run("src.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
