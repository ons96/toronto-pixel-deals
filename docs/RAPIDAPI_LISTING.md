# Future RapidAPI listing draft

> Not for publication. PixelDealScore is private staging and currently serves
> bundled specifications and listing fixtures only. There is no public endpoint,
> RapidAPI listing, or paid plan.

## Intended product

If rights and provenance are resolved, the API could rank a documented cached
dataset with configurable quality weights. An `EstimatedCost` calculation may use
an Ontario HST assumption where applicable; it is not a checkout quote.

## Current behavior

- `/health` reports row counts and exact cache timestamps.
- `/deals/top` ranks the local cached fixture rows for authenticated evaluation.
- `/deals/refresh` always returns `503 refresh_unavailable`.
- The private staging deployment is loopback-only and is not reachable by
  RapidAPI or other external clients.

## Required launch gates

Do not create a listing until all of these are complete:

1. Record source-specific commercial rights, provenance, attribution, retention,
   and refresh rules in `docs/DATA_SOURCES.md`.
2. Replace fixtures with an approved, repeatable refresh workflow and verify it
   externally.
3. Add a deliberately reviewed public HTTPS ingress path; never expose the raw
   application port.
4. Complete an external end-to-end test and publish accurate availability,
   pricing, tax, refund, and support terms.

`demo-free-key` is intentionally public for private evaluation only; it is not a
customer credential or a promise of a future free tier.
