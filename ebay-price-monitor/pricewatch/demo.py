"""Fake eBay market for trying the tool without API keys.

It simulates listings arriving, selling and expiring. Cheap listings sell fast and
overpriced ones sit, the same survivorship effect you see on real eBay. It also plants
junk (box only, for parts, accessories), multi-variation listings, scams and real deals.
The output goes through the exact same pipeline as live data.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .config import ItemConfig, build_item
from .ebay import SearchResult


@dataclass
class MarketSpec:
    name: str
    query: str
    base: float
    daily_drift: float
    daily_vol: float
    target_active: int
    condition: str
    condition_id: int
    titles: list[str]
    junk: list[tuple[str, float]]  # (title, price as share of market)
    item_settings: dict = field(default_factory=dict)


SPECS = [
    MarketSpec(
        name="Steam Deck OLED 512GB",
        query="steam deck oled 512gb",
        base=470.0,
        daily_drift=-0.003,
        daily_vol=0.012,
        target_active=80,
        condition="Used",
        condition_id=3000,
        titles=[
            "Valve Steam Deck OLED 512GB Handheld Console",
            "Steam Deck OLED 512GB w/ Case Excellent",
            "Steam Deck OLED 512 GB Lightly Used",
            "Valve Steam Deck OLED 512GB Great Condition",
            "Steam Deck OLED 512GB + Charger",
        ],
        junk=[
            ("Steam Deck OLED 512GB BOX ONLY", 0.08),
            ("Valve Steam Deck OLED 512GB For Parts Not Working", 0.35),
            ("Steam Deck OLED 512GB Carrying Case", 0.05),
            ("Steam Deck OLED 512GB untested as-is", 0.45),
            ("Steam Deck LCD 256GB", 0.55),
        ],
        item_settings={
            "require_words": ["oled", "512"],
            "exclude_words": ["carrying case", "skin", "screen protector", "dock only"],
        },
    ),
    MarketSpec(
        name="Sony WH-1000XM5 Headphones",
        query="sony wh-1000xm5",
        base=215.0,
        daily_drift=0.001,
        daily_vol=0.010,
        target_active=110,
        condition="Used",
        condition_id=3000,
        titles=[
            "Sony WH-1000XM5 Wireless Noise Canceling Headphones Black",
            "Sony WH1000XM5 Silver Excellent Condition",
            "Sony WH-1000XM5 Over Ear Bluetooth Headphones",
            "SONY WH-1000XM5 Midnight Blue w/ Case",
        ],
        junk=[
            ("Sony WH-1000XM5 Replacement Ear Pads", 0.08),
            ("Sony WH-1000XM5 Case Only", 0.10),
            ("Sony WH-1000XM5 left side broken", 0.30),
            ("Sony WH-1000XM4 Headphones", 0.60),
        ],
        item_settings={"require_words": ["xm5"], "exclude_words": ["ear pads", "earpads", "cushions"]},
    ),
]


class DemoMarket:
    def __init__(self, spec: MarketSpec, rng: random.Random, start_id: int):
        self.spec = spec
        self.rng = rng
        self.base = spec.base
        self.active: dict[str, dict] = {}
        self.next_id = start_id
        self.clock = 0.0  # simulated hours
        self.sales: list[tuple[float, float]] = []  # (clock, total price) of real sales
        for _ in range(spec.target_active):
            self._add_normal()
        for title, share in spec.junk:
            self._add(title, self.base * share * rng.uniform(0.85, 1.15), score=rng.randint(20, 3000))

    # --- listing factories ----------------------------------------------------

    def _seller(self) -> tuple[int, float]:
        return int(math.exp(self.rng.gauss(5.0, 1.5))), round(self.rng.uniform(97.0, 100.0), 1)

    def _add(self, title: str, price: float, score: int | None = None, pct: float | None = None,
             kind: str = "junk", group: bool = False, condition_id: int | None = None) -> None:
        s_score, s_pct = self._seller()
        self.next_id += 1
        iid = f"v1|{self.next_id}|0"
        free_ship = self.rng.random() < 0.6
        self.active[iid] = {
            "id": iid,
            "title": title,
            "price": round(price, 2),
            "shipping": 0.0 if free_ship else round(self.rng.uniform(8, 20), 2),
            "score": s_score if score is None else score,
            "pct": s_pct if pct is None else pct,
            "kind": kind,
            "group": group,
            "condition_id": condition_id or self.spec.condition_id,
        }

    def _add_normal(self) -> None:
        # Sellers ask above the clearing price on average, with a long overpriced tail.
        ask = self.base * math.exp(self.rng.gauss(0.05, 0.11))
        self._add(self.rng.choice(self.spec.titles), ask, kind="normal")

    # --- time ---------------------------------------------------------------

    def step(self, hours: float) -> None:
        rng, days = self.rng, hours / 24
        self.base *= math.exp(self.spec.daily_drift * days + self.spec.daily_vol * math.sqrt(days) * rng.gauss(0, 1))

        self.clock += hours
        for iid, l in list(self.active.items()):
            if l["kind"] == "junk":
                continue
            if l["kind"] == "scam":
                if rng.random() < 1 - (1 - 0.5) ** days:  # reported and pulled, never sells
                    del self.active[iid]
                continue
            total = l["price"] + l["shipping"]
            p_day = 0.6 / (1 + math.exp((total / self.base - 1.0) / 0.05))  # price drives sell speed
            if rng.random() < 1 - (1 - p_day) ** days:
                self.sales.append((self.clock, total))
                del self.active[iid]
            elif rng.random() < 1 - (1 - 0.01) ** days:
                del self.active[iid]  # ended without a sale: noise for the sold estimate
            elif rng.random() < 0.02 * days:  # seller cuts the price
                l["price"] = round(l["price"] * 0.95, 2)

        arrivals = self._poisson(self.spec.target_active * 0.18 * days)
        for _ in range(arrivals):
            self._add_normal()
        if rng.random() < 0.12 * days:  # real deal, good seller
            self._add(rng.choice(self.spec.titles), self.base * rng.uniform(0.66, 0.78), score=rng.randint(80, 4000),
                      pct=round(rng.uniform(98.5, 100), 1), kind="normal")
        if rng.random() < 0.05 * days:  # scam bait: brand-new account, absurd price
            self._add(rng.choice(self.spec.titles), self.base * rng.uniform(0.30, 0.42), score=0, pct=0.0, kind="scam")
        if rng.random() < 0.05 * days and not any(l["group"] for l in self.active.values()):
            self._add(self.spec.titles[0] + " (choose color/bundle)", self.base * 0.5, kind="junk", group=True)

    def _poisson(self, lam: float) -> int:
        l, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.rng.random()
            if p <= l:
                return k
            k += 1

    # --- API-shaped output ----------------------------------------------------

    def snapshot(self) -> list[dict]:
        out = []
        for l in self.active.values():
            raw = {
                "itemId": l["id"],
                "title": l["title"],
                "price": {"value": f"{l['price']:.2f}", "currency": "USD"},
                "shippingOptions": [
                    {"shippingCostType": "FIXED", "shippingCost": {"value": f"{l['shipping']:.2f}", "currency": "USD"}}
                ],
                "condition": self.spec.condition,
                "conditionId": str(l["condition_id"]),
                "buyingOptions": ["FIXED_PRICE"],
                "seller": {"username": "demo_seller", "feedbackScore": l["score"], "feedbackPercentage": f"{l['pct']:.1f}"},
                "itemWebUrl": f"https://example.com/demo-item/{l['id'].split('|')[1]}",
            }
            if l["group"]:
                raw["itemGroupType"] = "SELLER_DEFINED_VARIATIONS"
            out.append(raw)
        self.rng.shuffle(out)
        return out


class DemoSource:
    def __init__(self, seed: int = 7, warmup_days: int = 30):
        self.rng = random.Random(seed)
        self.markets: dict[str, DemoMarket] = {}
        self.items: list[ItemConfig] = []
        for i, spec in enumerate(SPECS):
            item = build_item({}, {"name": spec.name, "query": spec.query, **spec.item_settings})
            self.items.append(item)
            self.markets[item.key] = DemoMarket(spec, self.rng, start_id=100000 * (i + 1))
        # Let stale overpriced listings pile up the way they do on a real site before scanning starts.
        for _ in range(warmup_days * 4):
            self.advance(6)

    def advance(self, hours: float) -> None:
        for m in self.markets.values():
            m.step(hours)

    def search(self, item: ItemConfig) -> SearchResult:
        raws = self.markets[item.key].snapshot()
        return SearchResult(total=len(raws), main=raws, extra=[], complete=True)

    def true_sold_median(self, item: ItemConfig, days: int) -> float | None:
        m = self.markets[item.key]
        prices = sorted(p for t, p in m.sales if t >= m.clock - days * 24)
        if not prices:
            return None
        mid = len(prices) // 2
        return prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2
