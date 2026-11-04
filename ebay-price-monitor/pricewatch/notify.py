"""Alert channels: ntfy (free phone push, no account) and Discord webhooks."""

from __future__ import annotations

import requests

from .config import AppConfig, ItemConfig
from .monitor import Candidate

SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$", "AUD": "A$"}


def money(value: float, currency: str = "USD") -> str:
    sym = SYMBOLS.get(currency)
    return f"{sym}{value:,.2f}" if sym else f"{value:,.2f} {currency}"


def format_candidate(item: ItemConfig, c: Candidate, currency: str) -> tuple[str, str]:
    l = c.listing
    label = "DEAL" if c.kind == "deal" else "CHECK CAREFULLY"
    title = f"{label}: {item.name} at {money(l.total, currency)}"
    if l.shipping:
        price_line = f"{money(l.total, currency)} total ({money(l.price, currency)} + {money(l.shipping, currency)} ship)"
    else:
        price_line = f"{money(l.total, currency)} total" + (" (free ship)" if l.shipping == 0 else "")
    lines = [
        price_line,
        f"{c.pct_below:.0%} below {c.baseline_label} {money(c.baseline, currency)} (robust z {c.z:.1f})",
        l.title,
    ]
    if l.condition:
        lines.append(f"Condition: {l.condition}")
    if l.seller_score is not None:
        pct = f", {l.seller_pct:g}% positive" if l.seller_pct is not None else ""
        lines.append(f"Seller feedback: {l.seller_score}{pct}")
    lines += [f"! {f}" for f in c.flags]
    lines.append(l.url)
    return title, "\n".join(lines)


def should_push(item: ItemConfig, c: Candidate) -> bool:
    return c.kind == "deal" or item.notify_suspicious


def send(cfg: AppConfig, item: ItemConfig, candidates: list[Candidate]) -> list[str]:
    """Push alerts. Returns error strings instead of raising so one bad channel never stops a scan."""
    errors: list[str] = []
    for c in candidates:
        if not should_push(item, c):
            continue
        title, body = format_candidate(item, c, cfg.currency)
        if cfg.ntfy_topic:
            try:
                r = requests.post(
                    cfg.ntfy_server,
                    json={
                        "topic": cfg.ntfy_topic,
                        "title": title,
                        "message": body,
                        "click": c.listing.url,
                        "tags": ["moneybag"] if c.kind == "deal" else ["warning"],
                        "priority": 4 if c.kind == "deal" else 3,
                    },
                    timeout=15,
                )
                r.raise_for_status()
            except requests.RequestException as exc:
                errors.append(f"ntfy: {exc}")
        if cfg.discord_webhook:
            try:
                r = requests.post(cfg.discord_webhook, json={"content": f"**{title}**\n{body}"[:1900]}, timeout=15)
                r.raise_for_status()
            except requests.RequestException as exc:
                errors.append(f"discord: {exc}")
    return errors
