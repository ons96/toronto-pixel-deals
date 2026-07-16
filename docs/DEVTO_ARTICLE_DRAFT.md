# How I Built a Used-Pixel Deal Scoring API on a Free Oracle VPS

<!-- TODO: add your dev.to username -->

There is no good way to rank used phone deals by quality-per-dollar in Canada.
You scroll r/CanadianHardwareSwap and Kijiji, open eight tabs, mentally add
shipping and 13% HST, try to remember whether a Pixel 7's camera is meaningfully
better than a Pixel 6a's, and then you guess. I got tired of guessing, so I built
a small scoring engine and then wrapped it in a FastAPI service I could sell
access to. This is how it works.

## The problem

I live in Toronto and I buy and occasionally flip used Google Pixels. The
listings are scattered across Reddit, Kijiji, and eBay. The asking price is in
CAD but never includes tax. There is no single field that tells you "this is a
better deal than that one" because "better" depends on what you care about --
battery life, camera, CPU -- and on the real checkout price after HST and
shipping. Every comparison site I found ranks new phones by MSRP. Nobody ranks
*used* phones by quality-per-dollar in the buyer's actual currency.

## The data

I pull from four free sources. Kimovil gives me hardware specs (AnTuTu,
Geekbench, battery mAh, camera MP) via a JSON prefetch endpoint that is
Cloudflare-gated; I use `curl-cffi` with Chrome impersonation from a residential
IP and fall back to a curated static spec file when that fails, so the app works
offline. Reddit's `.json` endpoints give me r/CanadianHardwareSwap and similar
listings with no auth, just a honest User-Agent. eBay's Browse API needs a free
OAuth client credential pair. Frankfurter gives me ECB-backed USD-to-CAD rates
with no key. Everything lands in one SQLite file: a `specs` table, a `listings`
table, and an `fx_rates` table. SQLite because I am on a 1GB RAM VPS and there is
no reason to run Postgres for a few hundred rows.

## The scoring math

Net cost is the part everyone gets wrong: `NetCost = (Asking + Shipping) * 1.13`,
so the number already includes Ontario HST. Quality is normalized against fixed
baselines, not against the current dataset -- AnTuTu maps to a 0-1 score between
200k and 2.5M, battery between 2500 and 6000 mAh, and so on. Fixed baselines
matter: if I normalized against the current pool, adding a weak phone would make
every other phone look better without anything actually changing. The quality
score is a weighted sum the caller controls: `100 * (w_cpu*N(cpu) +
w_battery*N(battery) + ...)`. The deal score is `QualityScore / NetCost * 1000`.
Higher is a better deal. The whole thing is maybe forty lines of Python and it is
the part I am most happy with, because it is auditable.

## The API and the usage caps

The scoring engine was a CLI first. Turning it into something sellable meant a
REST layer with hard usage caps, RapidAPI-style. I added FastAPI on top without
touching the scoring code -- the endpoints just import `rank_listings` and
`build_index` and call them. Auth reads an `X-RapidAPI-Proxy-Secret` header (which
RapidAPI injects automatically) or an `X-API-Key` header for direct customers.
Each key maps to a tier in an `api_keys` SQLite table, and every counted call
increments a date-partitioned `api_usage` row. Free is 100 calls a day, Basic is
5000, Pro is 50000, Ultra is unlimited. Over the limit returns a 429 with the
limit, how many you have used, your tier, and when it resets (next midnight UTC).
Health checks are not counted, so uptime monitoring does not burn quota.

I deliberately did not reach for Redis or a rate-limit library. The deploy is a
single uvicorn worker on one VPS, so SQLite is a perfectly good single-writer.
There is a comment in the code naming that ceiling and the upgrade path: move the
counters to Redis `INCR` with a daily `EXPIRE` if I ever scale to multiple
workers. Until then, one file, one process, zero external dependencies.

## The deploy

The whole thing runs on Oracle Cloud's free tier -- the Always Eligible Ampere
instance with 1GB of RAM. A bash script clones the repo, sets up a `uv` venv,
seeds the SQLite DB with offline sample data so the API has content even without
eBay credentials or a working Cloudflare bypass, installs a systemd unit running
`uvicorn src.api:app --port 8100`, and starts it. Port 8100 because 8000 is
already the LLM gateway on the same box and 5000 is the local Flask UI. The
firewall only exposes 8000 to my Tailscale network today, so I documented the one
`iptables` line to open 8100 to Tailscale rather than running it blindly. The
scoring engine is open-source; the API key tiering and the RapidAPI listing are
the income part.

## What I learned

The scoring is the easy part and the honest part. The interesting work was
building usage caps that feel like a real product -- 429 with a `resets_at`
timestamp, a tier-gated paid endpoint, a public demo key so the free tier is
actually usable for evaluation -- without pulling in infrastructure I do not
need. SQLite and a single FastAPI dependency got me a sellable API on a free VPS.
If I ever need more than one worker, the comment in the code tells the next me
exactly where Redis goes.
