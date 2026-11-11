"""Config loading. One YAML file lists your credentials, alert channels and watched items."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

# Title phrases that almost always mean "not the real item" or "not a working item".
# Matched case-insensitively on word boundaries. "as is" also matches "as-is" and "AS IS".
BUILTIN_EXCLUDES = [
    "for parts",
    "parts only",
    "not working",
    "doesnt work",
    "does not work",
    "no power",
    "broken",
    "cracked",
    "damaged",
    "faulty",
    "defective",
    "for repair",
    "needs repair",
    "as is",
    "untested",
    "read description",
    "please read",
    "box only",
    "empty box",
    "case only",
    "manual only",
    "shell only",
    "housing only",
    "replacement",
    "icloud locked",
    "activation locked",
    "bad esn",
    "blacklisted",
    "photo of",
    "picture of",
    "lot of",
]

MARKETPLACE_CURRENCY = {
    "EBAY_US": "USD",
    "EBAY_CA": "CAD",
    "EBAY_GB": "GBP",
    "EBAY_AU": "AUD",
    "EBAY_DE": "EUR",
    "EBAY_FR": "EUR",
    "EBAY_IT": "EUR",
    "EBAY_ES": "EUR",
    "EBAY_IE": "EUR",
    "EBAY_NL": "EUR",
}

BASELINES = ("auto", "asking")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclass
class ItemConfig:
    name: str
    query: str
    # eBay search filters
    buying_options: list[str] = field(default_factory=lambda: ["FIXED_PRICE"])
    condition_ids: list[int] | None = None
    category_id: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    item_location_country: str | None = None
    max_pages: int = 3
    # Title filters
    require_words: list[str] = field(default_factory=list)
    exclude_words: list[str] = field(default_factory=list)
    use_builtin_excludes: bool = True
    # Price math
    include_shipping: bool = True
    min_sample: int = 10
    # Deal rules
    deal_pct: float = 0.20
    deal_min_z: float = 2.0
    suspicious_pct: float = 0.55
    min_seller_score: int = 5
    min_seller_pct: float = 95.0
    baseline: str = "auto"
    sold_window_days: int = 14
    sold_min_sample: int = 8
    notify_suspicious: bool = False

    @property
    def key(self) -> str:
        return slugify(self.name)

    def all_excludes(self) -> list[str]:
        base = BUILTIN_EXCLUDES if self.use_builtin_excludes else []
        return list(base) + list(self.exclude_words)

    def validate(self) -> None:
        if not self.name or not self.query:
            raise ValueError("every item needs a 'name' and a 'query'")
        if self.baseline not in BASELINES:
            raise ValueError(f"{self.name}: baseline must be one of {BASELINES}")
        if not 0 < self.deal_pct < 1:
            raise ValueError(f"{self.name}: deal_pct must be between 0 and 1 (0.20 means 20% below)")
        if self.suspicious_pct <= self.deal_pct:
            raise ValueError(f"{self.name}: suspicious_pct must be larger than deal_pct")
        if self.max_pages < 1:
            raise ValueError(f"{self.name}: max_pages must be at least 1")


ITEM_FIELDS = {f.name for f in fields(ItemConfig)}
MERGED_LIST_FIELDS = {"exclude_words"}


def build_item(defaults: dict[str, Any], raw: dict[str, Any]) -> ItemConfig:
    unknown = set(raw) - ITEM_FIELDS
    unknown |= set(defaults) - ITEM_FIELDS
    if unknown:
        raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")
    merged = dict(defaults)
    for k, v in raw.items():
        if k in MERGED_LIST_FIELDS:
            merged[k] = list(defaults.get(k) or []) + list(v or [])
        else:
            merged[k] = v
    # YAML turns bare numbers like 512 into ints. Titles are text, so coerce.
    for k in ("require_words", "exclude_words"):
        merged[k] = [str(w) for w in merged.get(k) or []]
    if merged.get("condition_ids"):
        merged["condition_ids"] = [int(c) for c in merged["condition_ids"]]
    if merged.get("buying_options"):
        merged["buying_options"] = [str(b).upper() for b in merged["buying_options"]]
    if merged.get("category_id") is not None:
        merged["category_id"] = str(merged["category_id"])
    item = ItemConfig(**merged)
    item.validate()
    return item


@dataclass
class AppConfig:
    items: list[ItemConfig]
    database: str = "pricewatch.db"
    marketplace: str = "EBAY_US"
    client_id: str | None = None
    client_secret: str | None = None
    client_id_source: str = "not set"
    client_secret_source: str = "not set"
    env_overrides_file: bool = False
    sandbox: bool = False
    ship_to_country: str | None = None
    ship_to_zip: str | None = None
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"
    discord_webhook: str | None = None

    @property
    def currency(self) -> str:
        return MARKETPLACE_CURRENCY.get(self.marketplace, "USD")

    def find_items(self, name: str | None) -> list[ItemConfig]:
        if not name:
            return self.items
        wanted = slugify(name)
        found = [i for i in self.items if i.key == wanted or wanted in i.key]
        if not found:
            raise SystemExit(f"no item matches '{name}'. Items: {', '.join(i.name for i in self.items)}")
        return found


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise SystemExit(
            f"config file not found: {path}\n"
            "Copy config.example.yaml to config.yaml and edit it."
        )
    # utf-8-sig: Windows defaults to a legacy encoding, and some editors add a BOM.
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    ebay = data.get("ebay") or {}
    notify = data.get("notify") or {}
    defaults = data.get("defaults") or {}
    raw_items = data.get("items") or []
    if not raw_items:
        raise SystemExit("config has no items to watch")

    items = []
    for raw in raw_items:
        try:
            items.append(build_item(defaults, raw))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"bad item config {raw.get('name', raw)!r}: {exc}") from exc
    keys = [i.key for i in items]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        raise SystemExit(f"item names must be unique, duplicates: {', '.join(dupes)}")

    db = Path(data.get("database") or "pricewatch.db")
    if not db.is_absolute():
        db = path.parent / db

    ship_to = ebay.get("ship_to") or {}
    cid, cid_src = _credential("EBAY_CLIENT_ID", ebay.get("client_id"))
    sec, sec_src = _credential("EBAY_CLIENT_SECRET", ebay.get("client_secret"))
    file_has_keys = bool(ebay.get("client_id") or ebay.get("client_secret"))
    return AppConfig(
        items=items,
        database=str(db),
        marketplace=ebay.get("marketplace", "EBAY_US"),
        client_id=cid,
        client_secret=sec,
        client_id_source=cid_src,
        client_secret_source=sec_src,
        env_overrides_file=file_has_keys and "environment" in (cid_src + sec_src),
        sandbox=bool(ebay.get("sandbox", False)),
        ship_to_country=ship_to.get("country"),
        ship_to_zip=str(ship_to["zip"]) if ship_to.get("zip") else None,
        ntfy_topic=os.environ.get("PRICEWATCH_NTFY_TOPIC") or notify.get("ntfy_topic") or None,
        ntfy_server=notify.get("ntfy_server", "https://ntfy.sh").rstrip("/"),
        discord_webhook=os.environ.get("PRICEWATCH_DISCORD_WEBHOOK") or notify.get("discord_webhook") or None,
    )


def _credential(env_name: str, file_value) -> tuple[str | None, str]:
    """Environment variable wins over config.yaml. Returns (value, where it came from)."""
    env = os.environ.get(env_name)
    if env:
        return env, f"environment variable {env_name}"
    if file_value not in (None, ""):
        return str(file_value), "config.yaml"
    return None, "not set"


PLACEHOLDER_MARKERS = ("xxxxxxxx", "YourApp")
QUOTE_CHARS = "\"'\u201c\u201d\u2018\u2019"


def mask(value: str | None) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 10:
        return f"({len(value)} characters)"
    return f"{value[:4]}...{value[-4:]} ({len(value)} characters)"


def credential_problems(cfg: AppConfig) -> list[str]:
    """Likely reasons eBay would reject these keys, found without calling eBay."""
    cid, sec = cfg.client_id or "", cfg.client_secret or ""
    probs = []
    if cfg.env_overrides_file:
        probs.append(
            "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are set in this terminal and override config.yaml. "
            "Open a new terminal window, or run: unset EBAY_CLIENT_ID EBAY_CLIENT_SECRET"
        )
    for label, v in (("client_id", cid), ("client_secret", sec)):
        if not v:
            probs.append(f"{label} is empty.")
            continue
        if any(m in v for m in PLACEHOLDER_MARKERS):
            probs.append(f"{label} is still the example placeholder. Paste your real key.")
        if any(c in v for c in QUOTE_CHARS) or any(c.isspace() for c in v):
            probs.append(f"{label} contains quotes or spaces. Paste the bare key with nothing around it.")
    if cid and cid == sec:
        probs.append("client_id and client_secret are identical. They are two different keys.")
    if not cfg.sandbox and cid and sec:
        if "-SBX-" in cid.upper() or sec.upper().startswith("SBX-"):
            probs.append(
                "these look like Sandbox keys (SBX). Sandbox keys only work on eBay's test site. "
                "Copy the keys from the Production column instead."
            )
        else:
            if "-PRD-" not in cid.upper():
                probs.append("client_id should be the App ID (Client ID). Production App IDs contain -PRD-.")
            if not sec.upper().startswith("PRD-"):
                probs.append(
                    "client_secret should be the Cert ID (Client Secret). Production Cert IDs start with PRD-. "
                    "A common mix-up is pasting the Dev ID here."
                )
    return probs
