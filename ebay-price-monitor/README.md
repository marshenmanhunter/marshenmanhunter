# pricewatch: eBay price monitor

Scans eBay on a schedule for items you pick. For each item it:

1. Tracks the market price over time: asking-price median, spread, daily trend, and a **likely-sold** price estimate.
2. Flags listings priced well below market and pushes an alert to your phone (ntfy) or Discord.

Uses the official eBay Browse API. No scraping.

## Try it now, no keys needed

```bash
pip install -r requirements.txt
python -m pricewatch demo
```

The demo simulates 30 days of scans on a fake market (listings arrive, sell, expire, plus planted junk, scams and real deals) and runs it through the real pipeline. Sample result:

```
asking   median $481.55  middle half $449.81 to $514.56  (n=224)
sold*    median $414.66  middle half $390.69 to $442.12  (n=195, last 14d)
gap      asking median is +16.1% vs likely-sold
(simulator's real median sale price, last 14d: $410.46)
```

The asking median is 17% above what items sell for. The likely-sold estimate lands within 1%. That gap is the reason this tool exists.

## Read this before trusting any number

**Asking price is not market price.** Overpriced listings sit unsold and pile up. Well-priced listings sell within hours and vanish. A snapshot of active listings skews high. Flag "20% below the asking median" and you get alerts for normal prices.

**eBay does not give you sold prices.** The old Finding API (`findCompletedItems`) shut down in February 2025. The Marketplace Insights API (sold history) is limited to developers eBay approves. The Browse API returns active listings only.

**How this tool estimates sold prices:** it remembers every listing it sees. When a fixed-price listing disappears between two complete scans, it most likely sold. Its last price goes into the likely-sold pool. Some vanished listings were ended or relisted by the seller, so the estimate leans a little high. That errs toward fewer false alerts. It only works when a scan fetches every matching listing, so keep queries narrow.

**Default behavior:** alerts stay off until the likely-sold pool has 8 listings (`sold_min_sample`). In a busy market that takes hours to a day. For rare items where few listings vanish, set `baseline: asking` on that item and raise `deal_pct`.

**Junk is the real enemy.** A $40 "Steam Deck" is a box, a case, or a broken unit. Filters remove:

- titles with phrases like `for parts`, `box only`, `broken`, `as is`, `untested`, `replacement` (full list in `pricewatch/config.py`)
- your own `exclude_words` per item
- titles missing any of your `require_words`
- the "For parts" condition
- multi-variation listings (eBay shows the cheapest variant's price, so a $99 case option makes a $500 console look cheap)

Run with `--show-excluded` to audit what got dropped and why.

## Setup for real data

1. Create a free account at [developer.ebay.com](https://developer.ebay.com).
2. Create a **Production** keyset. You get an App ID (client ID) and Cert ID (client secret).
3. eBay requires production keysets to handle Marketplace Account Deletion notifications or claim an exemption. This tool stores no buyer or seller personal data (only item ID, title, URL, condition, price), which matches the exemption. Read eBay's wording and decide for yourself.
4. Configure:

```bash
cp config.example.yaml config.yaml          # edit items, filters, alert channels
export EBAY_CLIENT_ID="YourApp-PRD-..."
export EBAY_CLIENT_SECRET="PRD-..."
python -m pricewatch check                  # verifies keys with one search
python -m pricewatch run --no-notify --show-excluded   # first scan, tune filters
```

5. Alerts: install the free [ntfy](https://ntfy.sh) app, subscribe to a hard-to-guess topic, put that topic in `notify.ntfy_topic`. Or paste a Discord webhook URL.

## Commands

| Command | What it does |
|---|---|
| `python -m pricewatch run` | One scan of every item. Prints stats and outliers, sends alerts. |
| `python -m pricewatch run --item deck` | One item only (matches part of the name). |
| `python -m pricewatch loop --every 60` | Scan every 60 minutes until Ctrl+C. |
| `python -m pricewatch report` | Trend per item: daily median sparkline, 1d/7d/30d change, likely-sold median, cheapest listings. |
| `python -m pricewatch report --csv prices.csv` | Export every scan for charting in a spreadsheet. |
| `python -m pricewatch check` | Test credentials. |
| `python -m pricewatch demo` | Fake-market simulation. |

## Scheduling

`loop` works while your computer stays on. For a set-and-forget schedule use cron (Mac/Linux):

```cron
0 * * * * cd /path/to/ebay-price-monitor && EBAY_CLIENT_ID=... EBAY_CLIENT_SECRET=... /usr/bin/python3 -m pricewatch run >> pricewatch.log 2>&1
```

On Windows, Task Scheduler running `python -m pricewatch run` hourly in this folder does the same. A $5/month VPS or a Raspberry Pi keeps it running when your laptop sleeps.

Hourly is the sweet spot. Faster scans catch deals sooner and sharpen the likely-sold estimate. Slower scans miss listings that sell in under an hour.

**API budget:** the Browse API allows 5,000 calls per day by default. One scan costs 1 call per 200 listings, plus 1 extra call when a search has more listings than `max_pages` covers. 10 items x 3 pages x 24 scans = 720 calls per day.

## How a listing becomes an alert

A listing is a **deal** when all of these hold:

- price + shipping is at least `deal_pct` (20%) below the baseline median
- it sits at least `deal_min_z` (2.0) robust standard deviations below the median, so a wide-spread market does not fire on normal variation (spread = 1.4826 x median absolute deviation, floored at 2% of the median)
- the seller has at least `min_seller_score` feedback and `min_seller_pct` positive
- it sits less than `suspicious_pct` (55%) below the median

Anything failing the seller or "too cheap" rules becomes **check carefully**. It shows in the scan output and only gets pushed when `notify_suspicious: true`. Each listing alerts once, then again only if its price drops another 3%.

## Tuning

- **No alerts ever:** check for "learning" or "only N were fetched" warnings in `run` output. Narrow the query, add `min_price`/`max_price`, or raise `max_pages`.
- **Too many alerts:** raise `deal_pct` to 0.25 or 0.30, add exclude words, split new and used into separate items with `condition_ids`.
- **Mixed models in results:** add the model number to `require_words`, add sibling models (`xm4`, `lcd`) to `exclude_words`.
- **Bundles skew prices:** add `bundle`, `lot`, `with games` to `exclude_words`, or track bundles as their own item.

## Files

```
pricewatch/
  ebay.py      Browse API client (OAuth, paging, cheapest-first pass)
  listing.py   normalize API results, junk filters
  stats.py     medians, percentiles, robust z-score, trend helpers
  store.py     SQLite history (runs, listings, alerts)
  monitor.py   one scan: fetch, filter, measure, track sold, flag outliers
  notify.py    ntfy and Discord alerts
  report.py    terminal output, CSV export
  demo.py      fake market simulator
  cli.py       commands
tests/         python -m unittest discover -s tests
```
