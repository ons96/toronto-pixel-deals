# Pixel Deal Aggregator (Toronto/GTA)

Local used/refurbished smartphone deal aggregator for Google Pixel (4a-9) and
mid-range alternatives (OnePlus, Samsung). Scores deals by quality-per-dollar
in CAD, factoring Ontario HST (13%) and a user-tunable weight slider for
CPU / Battery / Camera.

## Stack (chosen for low-spec hardware)

- **Python 3.12** + **uv** for env management
- **SQLite** (stdlib, zero server) for local storage
- **Flask** (10MB RAM) + vanilla JS for the UI
- **curl-cffi** for private/local Kimovil staging experiments
- **ebay_rest** (Mate Csaj, MIT) for eBay Browse API
- **Frankfurter API** for free no-auth USD->CAD FX
- **Reddit JSON** (`.json` suffix) for r/CanadianHardwareSwap

No streamlit, no pandas, no playwright, no docker. Runs on 1GB RAM comfortably.

## Quick start

```bash
cd deal_aggregator
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt

# Optional: set eBay creds (free, register at https://developer.ebay.com)
export EBAY_CLIENT_ID="..."
export EBAY_CLIENT_SECRET="..."

# Private/local staging only; do not use fetched data in a public or commercial
# service until each source's rights and provenance are documented.
uv run python -m src.fetch

# Score the cached data
uv run python -m src.score --top 20

# Launch the UI
uv run python -m src.app
# -> http://127.0.0.1:5000
```

## Architecture

```
fetch  -> SQLite (data/deals.db) <- score -> Flask UI
  |            |                          |
  |            +-- spec rows joined       +-- weight sliders
  +-- Kimovil (live, CF-protected)            re-rank w/o re-fetch
  +-- eBay Browse (creds needed)
  +-- Reddit JSON
  +-- Frankfurter FX
```

Static spec baseline lives in `data/static_specs.json` (curated, offline-first).
The local staging fetcher can attempt external adapters, but the app remains
functional offline. See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) before
using any external data in a public or commercial service.

## Data sources

| Source | Auth | Notes |
|---|---|---|
| Kimovil | None | Private/local staging adapter; not enabled for commercial API refresh |
| eBay Browse | OAuth client_id/secret | Adapter is inactive without credentials; commercial display/reuse review pending |
| Reddit JSON | None | Private/local staging adapter; not enabled for commercial API refresh |
| Frankfurter | None | Auxiliary FX adapter; underlying provider terms still require review |

## Scoring

`NetCost = (Asking + Shipping) * 1.13` (Ontario HST)
`QualityScore = 100 * (w_cpu*N(cpu) + w_bat*N(bat) + w_cam*N(cam))`
where weights `w_*` sum to 1 and `N(*)` is min-max normalized [0,1] against
**static** baselines (e.g. AnTuTu min=200k, max=2.5M) so the score never
inflates as new weaker devices enter the database.

`DealScore = (QualityScore / NetCost) * 1000` (higher = better deal).

## API mode (FastAPI service)

A FastAPI service (`src/api.py`) exposes the scoring logic as REST endpoints
with RapidAPI-style usage caps. It is **additive** -- it imports and reuses
`score.py` / `db.py` / `config.py` without duplicating them, and the Flask UI
(`app.py`) stays functional for browsing.

**Deployment status:** the current service is private staging, not
publish-ready. Before creating a RapidAPI listing, it needs public HTTPS
ingress, a verified recurring refresh, a source-terms review, and an external
end-to-end test.

### Run

```bash
uv pip install -r requirements.txt
uv run uvicorn src.api:app --port 8100          # server
# or
uv run python -m src.api                          # same, via __main__
uv run python -m src.api --smoke                  # inline TestClient smoke
```

Interactive docs at `http://localhost:8100/docs`.

### Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | none (not counted) | row counts plus exact database freshness metadata |
| GET | `/deals/top` | counted | `n` (1-500), weight overrides `cpu/battery/camera/display/form_factor` (0-1), `include_unknown`; response includes freshness metadata |
| GET | `/deals/refresh` | counted | always `503 refresh_unavailable`; live refresh is disabled while commercial data rights are documented |
| GET | `/specs/{slug}` | counted | 404 if slug not found |
| GET | `/specs` | counted | all specs |

### Auth and usage caps

Send one header per request:
- `X-RapidAPI-Proxy-Secret` -- injected by RapidAPI in production.
- `X-API-Key` -- for direct / own customers.

Missing or unknown key returns `401`. Over the daily limit returns `429` with
`limit`, `used`, `tier`, and `resets_at` (next midnight UTC). `/health` is not
counted, so uptime checks do not burn quota.

`freshness` preserves the exact stored database values: `MAX(listings.fetched_at)`,
`MAX(specs.fetched_at)`, and `MAX(fx_rates.as_of)`. Its fields are
`listings_fetched_at`, `specs_fetched_at`, and `fx_rates_as_of`; each is `null`
when its table has no rows.

### Tiers

| Tier | Daily limit | Demo key |
|---|---|---|
| free | 100 | `demo-free-key` (public, for testing) |
| basic | 5,000 | -- |
| pro | 50,000 | -- (cached data only) |
| ultra | unlimited | -- (cached data only) |

The demo key `demo-free-key` is seeded automatically by `init_db()` and is
intentionally public so the API works out-of-the-box for evaluation. Real keys
are added to the `api_keys` table (never commit real secrets). Counters live in
an `api_usage` table partitioned by date; SQLite is the single source of truth on
this single-process deploy (see the `ponytail:` note in `src/api.py` for the
upgrade path to Redis if you scale to multiple workers).

### Deployment status

The current deployment is private staging and is not publish-ready. Do not
create a RapidAPI listing until public HTTPS ingress, a verified recurring
refresh, source-terms review, and an external end-to-end test are complete.
`deploy/vps40-deploy.sh` remains a private deployment reference; see the draft
listing copy at `docs/RAPIDAPI_LISTING.md`.

### Tests

```bash
uv run pytest tests/test_api.py -v
```
