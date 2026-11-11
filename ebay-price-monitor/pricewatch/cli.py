"""Command line entry point: python -m pricewatch <command>"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from . import notify
from .config import AppConfig, credential_problems, load_config, mask
from .ebay import EbayClient, EbayError
from .monitor import run_item
from .report import SOLD_FOOTNOTE, export_csv, format_history, format_scan
from .store import Store


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    store = Store(cfg.database)
    try:
        client = EbayClient(cfg)
        client.token()
    except EbayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        for p in credential_problems(cfg):
            print(f"  ! {p}", file=sys.stderr)
        store.close()
        return 2

    failures = 0
    for item in cfg.find_items(args.item):
        try:
            rep = run_item(item, client, store, _now(), cfg.currency)
        except (EbayError, OSError) as exc:
            failures += 1
            print(f"== {item.name} ==\nerror: {exc}\n", file=sys.stderr)
            continue
        print(format_scan(rep, cfg.currency, show_excluded=args.show_excluded))
        if rep.new_alerts and not args.no_notify:
            for err in notify.send(cfg, item, rep.new_alerts):
                print(f"notify error: {err}", file=sys.stderr)
        print()
    print(f"eBay API calls this run: {client.calls}")
    store.close()
    return 1 if failures else 0


def cmd_loop(args: argparse.Namespace) -> int:
    print(f"scanning every {args.every} minutes. Ctrl+C to stop.")
    try:
        while True:
            cmd_run(args)
            time.sleep(args.every * 60)
    except KeyboardInterrupt:
        return 0


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    store = Store(cfg.database)
    items = cfg.find_items(args.item)
    if args.csv:
        n = export_csv(store, items, args.csv)
        print(f"wrote {n} rows to {args.csv}")
        return 0
    for item in items:
        print(format_history(store, item, cfg.currency, days=args.days))
        print()
    print(SOLD_FOOTNOTE)
    return 0


def _print_credentials(cfg: AppConfig) -> list[str]:
    print(f"marketplace:   {cfg.marketplace}{'  (sandbox)' if cfg.sandbox else ''}")
    print(f"client_id:     {mask(cfg.client_id)}  from {cfg.client_id_source}")
    print(f"client_secret: {mask(cfg.client_secret)}  from {cfg.client_secret_source}")
    problems = credential_problems(cfg)
    for p in problems:
        print(f"  ! {p}")
    if not problems:
        print("  keys look well-formed")
    print()
    return problems


def cmd_check(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    _print_credentials(cfg)
    try:
        client = EbayClient(cfg)
        client.token()
        print("credentials OK, token received")
        item = cfg.items[0]
        data = client.search_page(item)
        print(f"search OK: '{item.query}' matches {data.get('total', 0)} listings")
        for raw in (data.get("itemSummaries") or [])[:3]:
            print(f"   {raw.get('price', {}).get('value', '?'):>8}  {raw.get('title', '')[:70]}")
    except EbayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from .demo import DemoSource

    if os.path.exists(args.db):
        os.remove(args.db)
    store = Store(args.db)
    source = DemoSource(seed=args.seed)
    end = _now().replace(minute=0, second=0)
    t = end - timedelta(days=args.days)
    step = timedelta(hours=args.every_hours)
    last = {}
    alerts = []
    while t <= end:
        for item in source.items:
            rep = run_item(item, source, store, t, "USD")
            last[item.key] = rep
            alerts += [(item, c, t) for c in rep.new_alerts]
        source.advance(args.every_hours)
        t += step

    print(f"Simulated {args.days} days of scans every {args.every_hours}h on a fake market.\n")
    print("LATEST SCAN")
    for item in source.items:
        print(format_scan(last[item.key], "USD", show_excluded=args.show_excluded))
        true = source.true_sold_median(item, item.sold_window_days)
        print(f"(simulator's real median sale price, last {item.sold_window_days}d: ${true:,.2f})\n")
    print("HISTORY")
    for item in source.items:
        print(format_history(store, item, "USD", days=args.days, now=end))
        print()
    deals = sum(1 for _, c, _ in alerts if c.kind == "deal")
    print(f"ALERTS OVER {args.days} DAYS: {deals} deals pushed, {len(alerts) - deals} held back as suspicious. Last 12:")
    for item, c, ts in alerts[-12:]:
        print(f"  {ts:%m-%d %H:%M}  {c.kind:<10}  ${c.listing.total:>7,.2f}  {c.pct_below:>4.0%} below {c.baseline_label:<18}  {item.name}")
    print()
    print(SOLD_FOOTNOTE)
    print(f"Demo database: {args.db}")
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pricewatch", description="Track eBay prices and flag underpriced listings.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_config(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("-c", "--config", default="config.yaml", help="config file (default: config.yaml)")
        sp.add_argument("--item", help="only this item (name or part of it)")

    sp = sub.add_parser("run", help="scan once, print results, send alerts")
    add_config(sp)
    sp.add_argument("--show-excluded", action="store_true", help="list every filtered-out listing and why")
    sp.add_argument("--no-notify", action="store_true", help="print only, send no alerts")
    sp.add_argument("--log", help="append output to this file instead of the screen (for scheduled runs)")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("loop", help="scan forever on a fixed interval")
    add_config(sp)
    sp.add_argument("--every", type=int, default=60, help="minutes between scans (default 60)")
    sp.add_argument("--show-excluded", action="store_true")
    sp.add_argument("--no-notify", action="store_true")
    sp.add_argument("--log", help="append output to this file instead of the screen")
    sp.set_defaults(func=cmd_loop)

    sp = sub.add_parser("report", help="price history and trend per item")
    add_config(sp)
    sp.add_argument("--days", type=int, default=30)
    sp.add_argument("--csv", help="export every scan to this CSV file instead")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("check", help="test your eBay credentials with one search")
    sp.add_argument("-c", "--config", default="config.yaml")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("demo", help="simulate 30 days on a fake market, no API keys needed")
    sp.add_argument("--db", default="demo.db")
    sp.add_argument("--days", type=int, default=30)
    sp.add_argument("--every-hours", type=int, default=6)
    sp.add_argument("--seed", type=int, default=7)
    sp.add_argument("--show-excluded", action="store_true")
    sp.set_defaults(func=cmd_demo)
    return p


def _setup_output(log_path: str | None) -> None:
    """Always write UTF-8. Windows defaults to a legacy encoding that crashes on the trend
    chart and on emoji in listing titles whenever output goes to a file."""
    if log_path:
        fh = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = fh
        return
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_output(getattr(args, "log", None))
    return args.func(args)
