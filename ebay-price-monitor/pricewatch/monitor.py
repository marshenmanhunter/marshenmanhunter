"""One scan of one item: fetch, clean, measure, store, and flag outliers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from .config import ItemConfig
from .ebay import SearchResult
from .listing import Listing, ListingFilter, normalize
from .stats import Summary, robust_z, summarize
from .store import Store


class Source(Protocol):
    def search(self, item: ItemConfig) -> SearchResult: ...


@dataclass
class Candidate:
    listing: Listing
    kind: str  # "deal" or "suspicious"
    pct_below: float
    z: float
    baseline: float
    baseline_label: str
    flags: list[str] = field(default_factory=list)


@dataclass
class ItemReport:
    item: ItemConfig
    ts: datetime
    total_available: int = 0
    fetched: int = 0
    complete: bool = True
    asking: Summary | None = None
    sold: Summary | None = None
    baseline_label: str | None = None
    learning: bool = False  # True while alerts wait for enough likely-sold data
    kept: list[Listing] = field(default_factory=list)
    excluded: list[tuple[Listing, str]] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    new_alerts: list[Candidate] = field(default_factory=list)
    gone_now: int = 0
    warnings: list[str] = field(default_factory=list)


def choose_baseline(
    item: ItemConfig, asking: Summary | None, sold: Summary | None
) -> tuple[Summary | None, str, bool]:
    """Pick the price outliers are measured against. Returns (summary, label, alerts_allowed).

    Asking prices run high because overpriced listings sit unsold and pile up. So by default
    alerts wait for the likely-sold baseline. baseline: asking skips the wait.
    """
    if item.baseline == "asking":
        return asking, "asking median", asking is not None
    if sold is not None and sold.n >= item.sold_min_sample:
        return sold, "likely-sold median", True
    return asking, "asking median", False


def classify(listing: Listing, base: Summary, label: str, item: ItemConfig) -> Candidate | None:
    if base.median <= 0:
        return None
    pct = 1 - listing.total / base.median
    if pct < item.deal_pct:
        return None
    z = robust_z(listing.total, base)
    if z < item.deal_min_z:
        return None

    warn = []
    if pct >= item.suspicious_pct:
        warn.append(f"{pct:.0%} below market is too good to be true")
    if listing.seller_score is not None and listing.seller_score < item.min_seller_score:
        warn.append(f"seller has {listing.seller_score} feedback")
    if listing.seller_pct is not None and listing.seller_pct < item.min_seller_pct:
        warn.append(f"seller positive feedback {listing.seller_pct:g}%")
    if "FIXED_PRICE" not in listing.buying_options and "AUCTION" in listing.buying_options:
        warn.append("auction: current bid, final price will be higher")
    kind = "suspicious" if warn else "deal"

    flags = list(warn)
    if item.include_shipping and listing.shipping is None:
        flags.append("shipping not included (calculated at checkout)")
    return Candidate(listing, kind, pct, z, base.median, label, flags)


def run_item(item: ItemConfig, source: Source, store: Store, now: datetime, currency: str) -> ItemReport:
    rep = ItemReport(item=item, ts=now)
    result = source.search(item)
    rep.total_available = result.total
    rep.complete = result.complete

    main_ids = {raw.get("itemId") for raw in result.main}
    seen: dict[str, Listing] = {}
    for raw in result.main + result.extra:
        listing = normalize(raw, include_shipping=item.include_shipping)
        if listing and listing.item_id not in seen:
            seen[listing.item_id] = listing
    rep.fetched = len(seen)

    flt = ListingFilter(item.require_words, item.all_excludes(), currency, item.min_price, item.max_price)
    for listing in seen.values():
        reason = flt.reject_reason(listing)
        if reason:
            rep.excluded.append((listing, reason))
        else:
            rep.kept.append(listing)

    sample = [l for l in rep.kept if l.item_id in main_ids]
    if len(sample) >= item.min_sample:
        rep.asking = summarize([l.total for l in sample])
    else:
        rep.warnings.append(
            f"only {len(sample)} clean listings (min_sample={item.min_sample}). "
            "Stats skipped. Loosen filters or broaden the query."
        )
    if not result.complete:
        rep.warnings.append(
            f"{result.total} listings match but only {len(main_ids)} were fetched. "
            "Stats use a sample and sold tracking is paused. Narrow the query or raise max_pages."
        )

    store.record_run(item.key, now, result.total, len(sample), result.complete, rep.asking)
    store.upsert_listings(item.key, sample, now)
    if result.complete:
        rep.gone_now = store.mark_gone(item.key, main_ids, now)

    sold_prices = store.gone_totals(item.key, since=now - timedelta(days=item.sold_window_days))
    rep.sold = summarize(sold_prices)

    base, label, alerts_ok = choose_baseline(item, rep.asking, rep.sold)
    if base is None:
        return rep
    rep.baseline_label = label
    rep.learning = not alerts_ok
    if rep.learning:
        n = rep.sold.n if rep.sold else 0
        rep.warnings.append(
            f"learning: likely-sold baseline has {n}/{item.sold_min_sample} listings. "
            "Outliers below are shown but not alerted. Set baseline: asking to alert now."
        )
    for listing in rep.kept:
        cand = classify(listing, base, label, item)
        if cand:
            rep.candidates.append(cand)
    rep.candidates.sort(key=lambda c: c.pct_below, reverse=True)
    if alerts_ok:
        for cand in rep.candidates:
            if store.should_alert(item.key, cand.listing.item_id, cand.kind, cand.listing.total, now):
                rep.new_alerts.append(cand)
    return rep
