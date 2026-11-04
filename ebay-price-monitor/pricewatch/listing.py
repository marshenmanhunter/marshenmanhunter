"""Turn raw eBay Browse API item summaries into clean Listing objects and filter out junk."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

FOR_PARTS_CONDITION_ID = 7000


@dataclass
class Listing:
    item_id: str
    title: str
    url: str
    price: float
    shipping: float | None
    total: float
    currency: str
    condition: str = ""
    condition_id: int | None = None
    buying_options: list[str] = field(default_factory=list)
    seller_score: int | None = None
    seller_pct: float | None = None
    is_variation_group: bool = False


def _money(obj: Any) -> float | None:
    if not isinstance(obj, dict) or obj.get("value") in (None, ""):
        return None
    try:
        return float(obj["value"])
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize(raw: dict[str, Any], include_shipping: bool = True) -> Listing | None:
    """Return a Listing, or None when the summary has no usable price."""
    item_id = raw.get("itemId")
    price_obj = raw.get("price") or raw.get("currentBidPrice")
    price = _money(price_obj)
    if not item_id or price is None:
        return None

    costs = [
        c
        for c in (_money(opt.get("shippingCost")) for opt in raw.get("shippingOptions") or [])
        if c is not None
    ]
    shipping = min(costs) if costs else None
    total = price + (shipping or 0.0) if include_shipping else price

    seller = raw.get("seller") or {}
    return Listing(
        item_id=item_id,
        title=raw.get("title", ""),
        url=raw.get("itemWebUrl", ""),
        price=price,
        shipping=shipping,
        total=round(total, 2),
        currency=(price_obj or {}).get("currency", ""),
        condition=raw.get("condition", ""),
        condition_id=_int(raw.get("conditionId")),
        buying_options=list(raw.get("buyingOptions") or []),
        seller_score=_int(seller.get("feedbackScore")),
        seller_pct=_float(seller.get("feedbackPercentage")),
        is_variation_group=bool(raw.get("itemGroupType") or raw.get("itemGroupHref")),
    )


def _clean(text: str) -> str:
    return text.lower().replace("'", "").replace("’", "")


def _phrase_regex(phrase: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in _clean(phrase).split()]
    return re.compile(r"(?<![a-z0-9])" + r"[\s\-_/]+".join(parts) + r"(?![a-z0-9])")


class ListingFilter:
    """Decides which listings count as the real item. Returns a reason string for rejects."""

    def __init__(
        self,
        require_words: list[str],
        exclude_words: list[str],
        currency: str,
        min_price: float | None = None,
        max_price: float | None = None,
    ):
        self.require = [_clean(w) for w in require_words]
        self.exclude = [(w, _phrase_regex(w)) for w in exclude_words]
        self.currency = currency
        self.min_price = min_price
        self.max_price = max_price

    def reject_reason(self, listing: Listing) -> str | None:
        if listing.currency and self.currency and listing.currency != self.currency:
            return f"currency {listing.currency}"
        if listing.condition_id == FOR_PARTS_CONDITION_ID:
            return "condition: for parts"
        if listing.is_variation_group:
            return "multi-variation listing (shown price is the cheapest variant)"
        title = _clean(listing.title)
        for word in self.require:
            if word not in title:
                return f"missing '{word}'"
        for word, rx in self.exclude:
            if rx.search(title):
                return f"title has '{word}'"
        if self.min_price is not None and listing.total < self.min_price:
            return f"below min_price {self.min_price}"
        if self.max_price is not None and listing.total > self.max_price:
            return f"above max_price {self.max_price}"
        return None
