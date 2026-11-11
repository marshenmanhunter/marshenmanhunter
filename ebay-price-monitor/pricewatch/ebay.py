"""Minimal client for the official eBay Browse API (active listings only)."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

from .config import AppConfig, ItemConfig

PAGE_SIZE = 200  # Browse API maximum
MAX_OFFSET = 9_800  # Browse API caps offset + limit at 10,000
SCOPE = "https://api.ebay.com/oauth/api_scope"
RETRY_STATUS = {429, 500, 502, 503, 504}


class EbayError(RuntimeError):
    pass


class EbayAuthError(EbayError):
    pass


AUTH_HELP = """eBay rejected your keys (invalid_client). The usual causes, most common first:
  1. Production keyset still disabled. eBay switches it on only after the Marketplace
     Account Deletion step. On developer.ebay.com > Application Keys, look for a notice
     beside your Production keyset and complete it (the exemption option fits this tool).
  2. Wrong value pasted. client_id = App ID (Client ID). client_secret = Cert ID
     (Client Secret). The Dev ID goes nowhere.
  3. Sandbox keys. Copy from the Production column, not Sandbox.
  4. A brand-new or just-enabled keyset. Wait a few minutes and try again.
Run "python -m pricewatch check" to see which keys this tool read and where from."""


@dataclass
class SearchResult:
    total: int
    main: list[dict[str, Any]]  # unbiased sample, used for price stats
    extra: list[dict[str, Any]] = field(default_factory=list)  # cheapest-first page, deal hunting only
    complete: bool = True  # True when `main` holds every matching listing


class EbayClient:
    def __init__(self, cfg: AppConfig, session: requests.Session | None = None):
        if not cfg.client_id or not cfg.client_secret:
            raise EbayError(
                "missing eBay credentials. Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET,"
                " or ebay.client_id / ebay.client_secret in config.yaml."
            )
        host = "api.sandbox.ebay.com" if cfg.sandbox else "api.ebay.com"
        self.token_url = f"https://{host}/identity/v1/oauth2/token"
        self.search_url = f"https://{host}/buy/browse/v1/item_summary/search"
        self.cfg = cfg
        self.session = session or requests.Session()
        self._token: str | None = None
        self._token_expiry = 0.0
        self.calls = 0

    # --- auth ---------------------------------------------------------------

    def token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        basic = base64.b64encode(f"{self.cfg.client_id}:{self.cfg.client_secret}".encode()).decode()
        resp = self.session.post(
            self.token_url,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": SCOPE},
            timeout=30,
        )
        if resp.status_code == 401 and "invalid_client" in resp.text:
            raise EbayAuthError(AUTH_HELP)
        if resp.status_code != 200:
            raise EbayError(f"token request failed ({resp.status_code}): {resp.text[:300]}")
        body = resp.json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + int(body.get("expires_in", 7200))
        return self._token

    # --- search -------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.token()}",
            "X-EBAY-C-MARKETPLACE-ID": self.cfg.marketplace,
            "Accept": "application/json",
        }
        if self.cfg.ship_to_country:
            loc = f"country={self.cfg.ship_to_country}"
            if self.cfg.ship_to_zip:
                loc += f",zip={self.cfg.ship_to_zip}"
            h["X-EBAY-C-ENDUSERCTX"] = "contextualLocation=" + quote(loc, safe="")
        return h

    def filter_string(self, item: ItemConfig) -> str:
        parts = []
        if item.buying_options:
            parts.append("buyingOptions:{" + "|".join(item.buying_options) + "}")
        if item.condition_ids:
            parts.append("conditionIds:{" + "|".join(str(c) for c in item.condition_ids) + "}")
        if item.min_price is not None or item.max_price is not None:
            lo = "" if item.min_price is None else f"{item.min_price:g}"
            hi = "" if item.max_price is None else f"{item.max_price:g}"
            parts.append(f"price:[{lo}..{hi}]")
            parts.append(f"priceCurrency:{self.cfg.currency}")
        if item.item_location_country:
            parts.append(f"itemLocationCountry:{item.item_location_country}")
        return ",".join(parts)

    def search_page(self, item: ItemConfig, offset: int = 0, sort: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"q": item.query, "limit": PAGE_SIZE, "offset": offset}
        flt = self.filter_string(item)
        if flt:
            params["filter"] = flt
        if item.category_id:
            params["category_ids"] = str(item.category_id)
        if sort:
            params["sort"] = sort

        for attempt in range(4):
            resp = self.session.get(self.search_url, headers=self._headers(), params=params, timeout=30)
            self.calls += 1
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401 and attempt == 0:
                self._token = None  # expired token, refresh once
                continue
            if resp.status_code in RETRY_STATUS and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise EbayError(f"search failed ({resp.status_code}) for '{item.query}': {resp.text[:300]}")
        raise EbayError(f"search failed for '{item.query}' after retries")

    def search(self, item: ItemConfig) -> SearchResult:
        main: dict[str, dict[str, Any]] = {}
        total = 0
        for page in range(item.max_pages):
            offset = page * PAGE_SIZE
            if offset > MAX_OFFSET:
                break
            data = self.search_page(item, offset=offset)
            total = int(data.get("total", 0))
            batch = data.get("itemSummaries") or []
            for raw in batch:
                main.setdefault(raw["itemId"], raw)
            if len(batch) < PAGE_SIZE or offset + PAGE_SIZE >= total:
                break

        complete = len(main) >= total
        extra: list[dict[str, Any]] = []
        if not complete:
            # The default sort is a sample. Pull the cheapest page too so no low price slips by.
            extra = self.search_page(item, sort="price").get("itemSummaries") or []
        return SearchResult(total=total, main=list(main.values()), extra=extra, complete=complete)
