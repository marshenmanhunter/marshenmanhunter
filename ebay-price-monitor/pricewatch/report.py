"""Terminal output for scans and price history."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import ItemConfig
from .monitor import ItemReport
from .notify import format_candidate, money
from .stats import daily_medians, pct_change, sparkline, summarize
from .store import Store


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:+.1%}"


def format_scan(rep: ItemReport, currency: str, show_excluded: bool = False) -> str:
    out = [f"== {rep.item.name} ==  ({rep.ts:%Y-%m-%d %H:%M} UTC)"]
    out.append(
        f"matched {rep.total_available} | fetched {rep.fetched} | clean {len(rep.kept)}"
        f" | excluded {len(rep.excluded)} | gone since last scan {rep.gone_now}"
    )
    a = rep.asking
    if a:
        out.append(
            f"asking   median {money(a.median, currency)}  middle half {money(a.p25, currency)}"
            f" to {money(a.p75, currency)}  low {money(a.min, currency)}  (n={a.n})"
        )
    s = rep.sold
    if s:
        out.append(
            f"sold*    median {money(s.median, currency)}  middle half {money(s.p25, currency)}"
            f" to {money(s.p75, currency)}  (n={s.n}, last {rep.item.sold_window_days}d)"
        )
    if a and s and s.n >= rep.item.sold_min_sample:
        out.append(f"gap      asking median is {(a.median / s.median - 1):+.1%} vs likely-sold")
    for w in rep.warnings:
        out.append(f"warning: {w}")

    if rep.excluded:
        reasons = Counter(r for _, r in rep.excluded)
        out.append("excluded by: " + ", ".join(f"{k} x{v}" for k, v in reasons.most_common()))
        if show_excluded:
            for l, r in sorted(rep.excluded, key=lambda x: x[0].total):
                out.append(f"   x {money(l.total, currency):>10}  [{r}]  {l.title[:70]}")

    if rep.candidates:
        status = "learning, not alerted" if rep.learning else f"{len(rep.new_alerts)} new"
        out.append(f"outliers below {rep.baseline_label} ({status}):")
        new_ids = {c.listing.item_id for c in rep.new_alerts}
        for c in rep.candidates:
            title, body = format_candidate(rep.item, c, currency)
            tag = "NEW " if c.listing.item_id in new_ids else "    "
            out.append(f"  {tag}{title}")
            out += [f"       {line}" for line in body.splitlines()]
    elif rep.baseline_label:
        out.append(f"no outliers below {rep.baseline_label}")
    return "\n".join(out)


def format_history(store: Store, item: ItemConfig, currency: str, days: int = 30, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    rows = store.runs(item.key, since=now - timedelta(days=days))
    out = [f"== {item.name} ==  history, last {days} days"]
    if not rows:
        out.append("no scans yet. Run: python -m pricewatch run")
        return "\n".join(out)

    series = daily_medians([(r["ts"], r["median"]) for r in rows])
    last = next((r for r in reversed(rows) if r["median"] is not None), None)
    if last:
        out.append(
            f"asking now   median {money(last['median'], currency)}  middle half"
            f" {money(last['p25'], currency)} to {money(last['p75'], currency)}  (n={last['sample_size']})"
        )
    if series:
        vals = [v for _, v in series]
        out.append(
            f"daily median {sparkline(vals)}  {money(vals[0], currency)} -> {money(vals[-1], currency)}"
            f"  (range {money(min(vals), currency)} to {money(max(vals), currency)})"
        )
        out.append(
            f"change       1d {_pct(pct_change(series, 1))} | 7d {_pct(pct_change(series, 7))}"
            f" | 30d {_pct(pct_change(series, 30))}"
        )

    sold = store.gone_totals(item.key, since=now - timedelta(days=item.sold_window_days))
    if sold:
        s = summarize(sold)
        out.append(
            f"likely sold* median {money(s.median, currency)}  (n={s.n}, listings gone in last {item.sold_window_days}d)"
        )
        if last and s.n >= item.sold_min_sample:
            out.append(f"gap          asking median is {(last['median'] / s.median - 1):+.1%} vs likely-sold")

    cheap = store.cheapest_active(item.key)
    if cheap:
        out.append("cheapest clean listings right now:")
        for r in cheap:
            out.append(f"   {money(r['last_total'], currency):>10}  {r['title'][:60]}  {r['url']}")
    return "\n".join(out)


SOLD_FOOTNOTE = (
    "* likely sold = last price of listings that vanished between complete scans. "
    "Most sold. Some were ended or relisted by the seller. Treat it as an estimate."
)


def export_csv(store: Store, items: list[ItemConfig], path: str | Path) -> int:
    count = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel reads UTF-8
        w = csv.writer(fh)
        w.writerow(["item", "ts", "total_available", "sample_size", "complete", "median", "p10", "p25", "p75", "p90", "min", "max"])
        for item in items:
            for r in store.runs(item.key):
                w.writerow([item.name, r["ts"], r["total_available"], r["sample_size"], r["complete"],
                            r["median"], r["p10"], r["p25"], r["p75"], r["p90"], r["min"], r["max"]])
                count += 1
    return count
