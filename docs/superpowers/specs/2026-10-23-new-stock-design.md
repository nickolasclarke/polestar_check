# New-car stock in polestar_check — design

## Intent

Nick wants the cheapest Polestar 3/4 available anywhere in the US, new or
pre-owned, shown per model alongside the existing pre-owned results. Location
doesn't matter. Polestar 2 is pre-owned only.

## Goals / non-goals

- Goal: list every new PS3/PS4 listed at any US dealer, with a working link.
- Goal: within each model section, new and pre-owned share one list sorted by
  price, so the cheapest option is at the top.
- Non-goal: filtering by distance or dealer.
- Non-goal: deduplicating identical configs across dealers. The API exposes no
  VIN, so identical lines at different dealers can't be told apart, and each
  dealer's link is distinct.
- Anti-goal: hammering the API. Requests stay serial and few.

## Constraints (verified against the live API on 2026-10-23)

- Source: `filteredStockCars` on
  `https://pc-api.polestar.com/eu-north-1/preconfigured-cars/`, no auth.
- The US market requires `partnerId`, so all 30 dealers come from
  `getAllRetailersFunction` (1 call). Then 1 `filteredStockCars` call per
  dealer, with both model codes in a single filter (OR'd), so about 31 calls
  and about 30s at roughly 1s each.
- Model codes: PS3 = `359`, PS4 = `814`.
- Detail URL: `https://www.polestar.com/us/stock-cars/<slug>/<pno34 url-encoded>/?year=<modelYear>&structureweek=<startStructureWeek>&partnerid=<partnerId>`,
  with slugs `polestar-3` and `polestar-4-coupe`. Taken from a real page Nick
  captured.

## Approaches considered

1. **One line per dealer listing — chosen.** Each line maps to a real,
   clickable listing at a specific dealer. Simplest code. Repeated configs
   sort next to each other by price.
2. One line per config with its dealer list. Shorter, but any single link
   would be arbitrary, and the grouping code adds complexity for something
   cosmetic.
3. Nearest dealers by ZIP. Faster, but Nick doesn't care about location and
   it would miss the cheapest car if that car is far away.

## Decided

- Per model section: pre-owned and new combined, sorted by price, each line
  tagged `New`, `CPO` or `Pre-owned`. Builder's call: the existing pre-owned
  line format stays, and new lines show price, MSRP, model year, a short
  config (motor, colour), dealer and link.
- New-car price is the discounted "due at delivery" total, which includes the
  $1,400 destination charge. That's what the site shows, so comparing it with
  pre-owned dealer prices is fair enough for "find the cheapest".
- PS2 gets no new-stock query, since it has no known stock-cars slug and
  there's no inventory.
- Rate limiting: requests are serial with no concurrency, and there are no
  retries (YAGNI). A failed dealer request prints a one-line warning to stderr
  naming the dealer, and the run continues. A partial report is better than
  none, and the warning makes the gap visible. A 90-request sweep during
  exploration hit no errors or throttling. Polestar's actual limits are
  unknown.

## Left to the builder

- Function boundaries and names, which should follow the existing
  `fetch_vehicles` / `vehicle_url` style.
- Tests: real-API end-to-end tests, matching the existing suite.
