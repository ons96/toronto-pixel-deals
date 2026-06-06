# Pixel Deal Aggregator (Toronto/GTA)

Local used/refurbished smartphone deal aggregator for Google Pixel (4a-9) and
mid-range alternatives (OnePlus, Samsung). Scores deals by quality-per-dollar
in CAD, factoring Ontario HST (13%) and a user-tunable weight slider for
CPU / Battery / Camera.

## Stack (chosen for low-spec hardware)

- **Python 3.12** + **uv** for env management
- **SQLite** (stdlib, zero server) for local storage
- **Flask** (10MB RAM) + vanilla JS for the UI
- **curl-cffi** for Kimovil Cloudflare bypass when running from residential IP
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

# Fetch live data (Kimovil + Reddit + FX; eBay if creds set)
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
The Kimovil scraper will update those prices when reachable, but the app
is fully functional offline.

## Data sources

| Source | Auth | Notes |
|---|---|---|
| Kimovil | None | Cloudflare-gated; tries `curl-cffi` Chrome impersonation, falls back to static |
| eBay Browse | OAuth client_id/secret | Free tier, 5k calls/day |
| Reddit JSON | None | `.json` suffix on any URL; identifies via User-Agent |
| Frankfurter | None | ECB-backed FX rates |

## Scoring

`NetCost = (Asking + Shipping) * 1.13` (Ontario HST)
`QualityScore = 100 * (w_cpu*N(cpu) + w_bat*N(bat) + w_cam*N(cam))`
where weights `w_*` sum to 1 and `N(*)` is min-max normalized [0,1] against
**static** baselines (e.g. AnTuTu min=200k, max=2.5M) so the score never
inflates as new weaker devices enter the database.

`DealScore = (QualityScore / NetCost) * 1000` (higher = better deal).
