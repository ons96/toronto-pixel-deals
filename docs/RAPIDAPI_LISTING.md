# RapidAPI Listing Draft: Toronto Pixel Deal Score API

> Draft only. The current deployment is private staging, not publish-ready, and
> must not be listed on RapidAPI yet. Before a RapidAPI listing, public HTTPS
> ingress, a verified recurring refresh, source-terms review, and an external
> end-to-end test are required. No secrets are included here; `demo-free-key` is
> an intentionally public free-tier test key for private evaluation.

## API name

**PixelDealScore** (Toronto Pixel Deal Score API)

## Tagline

Rank used Google Pixel deals by quality-per-dollar, in CAD with Ontario HST built in.

## Description

Buying a used phone in Canada means scrolling r/CanadianHardwareSwap, Kijiji, and
eBay listings, mentally comparing a Pixel 7 at $280 against a Pixel 8 Pro at $650,
and guessing which is actually the better deal once tax and shipping are included.
PixelDealScore does that math for you.

The API scores every cached used/refurbished smartphone listing (Google Pixel 4a
through 9 Pro, plus mid-range OnePlus and Samsung alternatives) on a single
quality-per-dollar scale. The net cost is the asking price plus shipping, all
multiplied by 1.13 to bake in Ontario HST, so the number you get back is what you
would actually pay at checkout in Toronto. The quality score normalizes each
phone's CPU, battery, camera, display, and weight against fixed baselines, so a
newly added weak device never inflates the rankings. The final DealScore is
`(QualityScore / NetCost) * 1000` -- higher is a better deal.

You can reweight the score on every call: care more about battery and less about
the camera? Pass `battery=0.5&camera=0.1` and the rankings re-sort instantly
against the same cached listings, no re-fetch required. Available adapters can
populate cached hardware specs, listings, and USD-to-CAD FX data. The proposed
Pro-tier refresh endpoint is not a freshness guarantee: clients must inspect the
returned `freshness` values before treating cached data as current.

Target audience: used-phone buyers and resellers in Canada who want a single,
honest quality-per-dollar ranking instead of guessing. There is no clean Google
source for "used Pixel quality-per-dollar in CAD with tax" -- that gap is what
this API fills.

## Use cases

- **Deal-alerts bot**: poll `/deals/top?n=10` hourly; push a notification when a
  new listing crosses a DealScore threshold you set.
- **Resale pricing tool**: before you list a phone, call `/deals/top` with the
  same model's spec weights to see what the market's current quality-per-dollar
  baseline is, then price yours competitively.
- **Personal shopper / comparison site**: embed the rankings in a price-comparison
  page so visitors see "best deal right now" rather than just "cheapest listing".
- **Weight-tuning research**: hit `/deals/top` with different weight profiles
  (camera-heavy vs. battery-heavy) to see how the top deals shift for different
  buyer personas.

## Endpoints

| Method | Path | Auth | Key params | Sample response |
|---|---|---|---|---|
| GET | `/health` | none | -- | `{"status":"ok","db":{"specs":22,"listings":3,"fx":0},"freshness":{"listings_fetched_at":"...","specs_fetched_at":"...","fx_rates_as_of":"..."},"version":"1.0"}` |
| GET | `/deals/top` | counted | `n` (1-500), `cpu`,`battery`,`camera`,`display`,`form_factor` (0-1), `include_unknown` (bool) | `{"weights":{...},"count":3,"deals":[{...}],"freshness":{...},"tier":"free","used":1,"limit":100}` |
| GET | `/deals/refresh` | counted + Pro+ | -- | `{"status":"refreshed","db":{...},"freshness":{...}}` or `403 tier_required` |
| GET | `/specs/{slug}` | counted | `slug` e.g. `google-pixel-7` | `{"slug":"google-pixel-7","brand":"Google","model":"Pixel 7","antutu":875000,"battery_mah":4355,"camera_main_mp":50.0}` |
| GET | `/specs` | counted | -- | `{"count":22,"specs":[{...}]}` |

Auth: send `X-RapidAPI-Proxy-Secret` (RapidAPI injects this automatically) or
`X-API-Key` for direct/own customers. Missing or unknown key returns `401`.
Over the daily limit returns `429` with `limit`, `used`, `tier`, and `resets_at`
(the next midnight UTC).

`freshness` exposes the exact stored `MAX(listings.fetched_at)`,
`MAX(specs.fetched_at)`, and `MAX(fx_rates.as_of)` values. Fields are `null`
when their respective tables are empty.

## Pricing tiers

| Tier | Daily requests | RapidAPI suggested price | Notes |
|---|---|---|---|
| Free | 100 / day | $0 | Demo + evaluation. Public key `demo-free-key` works for testing. |
| Basic | 5,000 / day | $9 / month | Personal bots, light comparison sites. |
| Pro | 50,000 / day | $29 / month | Includes `/deals/refresh` (on-demand fetch). Power resellers. |
| Ultra | Unlimited | $99 / month | Unlimited + refresh. High-volume comparison platforms. |

> Suggested prices are a starting point; adjust to your market. The free tier is
> intentionally generous (100/day) so developers can build and demo against it.

## Sample code

### Python (requests)

```python
import requests

BASE = "https://your-rapidapi-host.p.rapidapi.com"   # RapidAPI
# or BASE = "https://your-api-host.example"          # HTTPS only, after launch gates

HEADERS = {
    "X-RapidAPI-Proxy-Secret": "YOUR_RAPIDAPI_KEY",   # RapidAPI injects this
    # "X-API-Key": "your-direct-key",                 # ...or use this for direct
}

# Top 5 deals, battery-weighted
r = requests.get(
    f"{BASE}/deals/top",
    params={"n": 5, "battery": 0.5, "camera": 0.1, "cpu": 0.3,
            "display": 0.05, "form_factor": 0.05},
    headers=HEADERS,
    timeout=15,
)
r.raise_for_status()
data = r.json()
for d in data["deals"]:
    print(f"{d['model']:<20} ${d['net_cost_cad']:.0f} CAD  score={d['deal_score']}")
```

### JavaScript (fetch)

```javascript
const BASE = "https://your-rapidapi-host.p.rapidapi.com";
const headers = {
  "X-RapidAPI-Proxy-Secret": "YOUR_RAPIDAPI_KEY",
  // "X-API-Key": "your-direct-key",
};

const url = new URL(`${BASE}/deals/top`);
url.searchParams.set("n", "5");
url.searchParams.set("battery", "0.5");
url.searchParams.set("camera", "0.1");
url.searchParams.set("cpu", "0.3");

const res = await fetch(url, { headers });
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const data = await res.json();
console.log(data.weights, data.count);
for (const d of data.deals) {
  console.log(`${d.model}  $${d.net_cost_cad} CAD  score=${d.deal_score}`);
}
```

## Why this API

**Niche, defensible positioning.** There is no clean Google source for "used
Google Pixel quality-per-dollar, in CAD, with Ontario HST." The big comparison
sites focus on new-phone MSRP. Reddit and Kijiji are raw listings with no scoring.
PixelDealScore joins hardware specs (Kimovil) onto cached used listings and ranks
them on a single, re-weightable
quality-per-dollar scale in the buyer's actual currency and tax regime.

**The scoring is honest.** Quality is normalized against *fixed* baselines (AnTuTu
200k-2.5M, etc.), not against the current dataset, so the score never drifts as
weaker devices enter the pool. Net cost always includes 13% HST. The math is
open-source and documented in the repo README, so buyers can audit exactly why a
deal ranks where it does.

**Canadian focus = clear target market.** Used-phone buyers and resellers across
Canada who already think in CAD and already pay HST get a ranking that matches
their checkout total. No currency conversion surprises.

**Small deployment footprint.** The service uses FastAPI and SQLite. Availability,
hosting cost, and source coverage are not guaranteed; a public launch requires the
staging gates stated above.
