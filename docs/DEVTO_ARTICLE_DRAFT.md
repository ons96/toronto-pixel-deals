# Draft: an offline Pixel deal-scoring prototype

> Do not publish this draft yet. The project is private staging, not a public or
> paid API. It serves bundled specifications and listing fixtures; live refresh is
> disabled pending source-rights, provenance, attribution, and retention review.

## The prototype

This project explores a simple question: how can a used-phone comparison rank
hardware quality against an estimated cost? It stores a small offline baseline in
SQLite and scores each row with caller-selectable CPU, battery, camera, display,
and form-factor weights.

The implementation intentionally stays small: Python, SQLite, Flask for local
browsing, and FastAPI for a private API layer. One process and one database are
enough for local evaluation; no separate cache or queue is needed.

## Scoring

`EstimatedCost = (Asking + Shipping) * 1.13` is an Ontario HST assumption where
applicable, not a checkout quote. Sellers, platforms, and private transactions
can apply different taxes, fees, shipping, and availability.

Hardware values are normalized against fixed baselines rather than the current
dataset. That prevents a newly added weak device from changing every existing
score. The final value is `QualityScore / EstimatedCost * 1000`; higher values
only compare the cached fixture rows supplied to the prototype.

## API mechanics

The FastAPI layer reuses the scoring and SQLite modules. It has test-only API-key
tiers and daily counters so integration behavior can be evaluated without adding
external infrastructure. The API returns exact cache timestamps, and its refresh
route deliberately returns `503 refresh_unavailable` rather than fetching or
publishing unreviewed third-party data.

## What must happen before publication

Before this can become a public product, every input needs documented commercial
rights, provenance, attribution, retention, and refresh behavior. It also needs
an approved recurring refresh workflow, public HTTPS ingress, and an external
end-to-end test. Until then, this remains an offline/private-staging engineering
prototype rather than a market feed or buying recommendation.
