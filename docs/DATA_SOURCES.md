# Data sources and provenance

This is an implementation inventory, not a grant of commercial-use rights. The
repository's MIT license covers its code, not third-party data. Do not enable a
public or commercial refresh until each source has a documented review, required
attribution, and any required written permission.

| Input | Current behavior | Stored data | Review status |
|---|---|---|---|
| `data/static_specs.json` | Bundled offline baseline; always seeded by the local fetcher | Hardware-spec fields, `source=static`, local fetch timestamp | Original provenance, version, and license are not yet recorded; not eligible for public/commercial refresh. |
| [Kimovil](https://www.kimovil.com/fr/info/terms-and-conditions) | Private/local staging adapter attempts a Cloudflare-gated prefetch endpoint | Hardware specs when reachable | Commercial reproduction/reuse approval is not recorded; disabled for API refresh. |
| [Reddit Data API Terms](https://redditinc.com/policies/data-api-terms) | Private/local staging adapter can request subreddit JSON; bundled sample listings are also loaded by `--sample-reddit` | Listing metadata, source URL, timestamps | Commercial approval is not recorded; disabled for API refresh. |
| [eBay Browse API](https://developer.ebay.com/api-docs/buy/browse/overview.html) | Adapter runs only when the operator supplies credentials | Listing metadata if a configured account retrieves it | Developer license, display, attribution, and redistribution terms require account-holder review. |
| [Frankfurter](https://frankfurter.dev/) | Optional USD-to-CAD auxiliary FX adapter | Rate and provider `as_of` date | Frankfurter permits commercial API use, but underlying-provider terms and attribution still require review. |

Kijiji, Facebook Marketplace, and eBay.ca URLs in bundled sample rows are link
targets/fixtures, not live ingestion sources. RapidAPI is a proposed distribution
channel, not a data source.

The API exposes exact stored maxima in `freshness`; a timestamp only describes
the cache, not source authorization, market completeness, or current availability.
