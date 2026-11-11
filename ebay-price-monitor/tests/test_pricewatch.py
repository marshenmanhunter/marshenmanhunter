import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from pricewatch.config import AppConfig, build_item, credential_problems, load_config, mask
from pricewatch.ebay import EbayClient, SearchResult
from pricewatch.listing import ListingFilter, normalize
from pricewatch.monitor import choose_baseline, classify, run_item
from pricewatch.stats import daily_medians, pct_change, percentile, robust_z, summarize
from pricewatch.store import Store

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


def raw(iid, price, title="Steam Deck OLED 512GB", ship=0.0, score=500, pct=99.8, **extra):
    r = {
        "itemId": f"v1|{iid}|0",
        "title": title,
        "price": {"value": f"{price:.2f}", "currency": "USD"},
        "shippingOptions": [] if ship is None else [{"shippingCostType": "FIXED", "shippingCost": {"value": f"{ship:.2f}", "currency": "USD"}}],
        "condition": "Used",
        "conditionId": "3000",
        "buyingOptions": ["FIXED_PRICE"],
        "seller": {"username": "x", "feedbackScore": score, "feedbackPercentage": str(pct)},
        "itemWebUrl": f"https://www.ebay.com/itm/{iid}",
    }
    r.update(extra)
    return r


class FakeSource:
    def __init__(self):
        self.listings = []
        self.complete = True

    def search(self, item):
        return SearchResult(total=len(self.listings), main=list(self.listings), complete=self.complete)


class StatsTest(unittest.TestCase):
    def test_percentile_matches_numpy_linear(self):
        vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.assertAlmostEqual(percentile(vals, 0.5), 5.5)
        self.assertAlmostEqual(percentile(vals, 0.25), 3.25)
        self.assertAlmostEqual(percentile(vals, 0.9), 9.1)
        self.assertEqual(percentile([42], 0.5), 42)

    def test_summary_resists_junk_tail(self):
        prices = [400, 410, 420, 430, 440, 450, 460, 9999, 5]
        s = summarize(prices)
        self.assertEqual(s.median, 430)
        self.assertEqual(s.n, 9)

    def test_scale_floor_when_all_prices_equal(self):
        s = summarize([549.0] * 20)
        self.assertEqual(s.mad, 0)
        self.assertAlmostEqual(s.scale, 549 * 0.02)
        self.assertGreater(robust_z(430, s), 10)

    def test_trend_helpers(self):
        rows = [((T0 + timedelta(days=d, hours=h)).isoformat(), 100 + d) for d in range(10) for h in (0, 12)]
        series = daily_medians(rows)
        self.assertEqual(len(series), 10)
        self.assertAlmostEqual(pct_change(series, 7), (109 - 102) / 102)
        self.assertIsNone(pct_change(series, 30))


class ListingTest(unittest.TestCase):
    def test_normalize_adds_cheapest_shipping(self):
        r = raw(1, 100, ship=None)
        r["shippingOptions"] = [
            {"shippingCost": {"value": "15.00", "currency": "USD"}},
            {"shippingCost": {"value": "9.50", "currency": "USD"}},
        ]
        l = normalize(r)
        self.assertEqual(l.shipping, 9.5)
        self.assertEqual(l.total, 109.5)
        self.assertEqual(normalize(r, include_shipping=False).total, 100)

    def test_normalize_unknown_shipping_and_auction(self):
        r = raw(2, 0, ship=None)
        del r["price"]
        r["currentBidPrice"] = {"value": "55.00", "currency": "USD"}
        l = normalize(r)
        self.assertIsNone(l.shipping)
        self.assertEqual(l.total, 55)
        self.assertIsNone(normalize({"itemId": "x"}))

    def test_variation_group_detected(self):
        self.assertTrue(normalize(raw(3, 100, itemGroupType="SELLER_DEFINED_VARIATIONS")).is_variation_group)

    def test_filter_rules(self):
        f = ListingFilter(["oled", "512"], ["as is", "box only", "carrying case"], "USD", min_price=100)

        def reason(title, price=400, **kw):
            return f.reject_reason(normalize(raw(9, price, title=title, **kw)))

        self.assertIsNone(reason("Valve Steam Deck OLED 512GB"))
        self.assertIsNone(reason("Steam Deck OLED 512GB w/ Case"))
        self.assertIn("missing", reason("Steam Deck LCD 512GB"))
        self.assertIn("as is", reason("Steam Deck OLED 512GB AS-IS"))
        self.assertIn("as is", reason("steam deck oled 512gb sold as is"))
        self.assertIn("box only", reason("Steam Deck OLED 512GB Box Only"))
        self.assertIsNone(reason("Steam Deck OLED 512GB oasis edition"))  # 'as is' must not match inside words
        self.assertIn("min_price", reason("Steam Deck OLED 512GB", price=50))
        self.assertIn("parts", f.reject_reason(normalize(raw(9, 400, conditionId="7000"))))


class DealRulesTest(unittest.TestCase):
    def setUp(self):
        self.item = build_item({}, {"name": "Deck", "query": "deck"})
        self.base = summarize([480, 490, 500, 500, 505, 510, 520, 530, 540, 500])

    def test_deal_needs_pct_and_z(self):
        good = normalize(raw(1, 380))
        c = classify(good, self.base, "x", self.item)
        self.assertEqual(c.kind, "deal")
        self.assertAlmostEqual(c.pct_below, 1 - 380 / 502.5)  # median of the base set is 502.5
        self.assertIsNone(classify(normalize(raw(2, 430)), self.base, "x", self.item))

    def test_wide_market_blocks_weak_outliers(self):
        wide = summarize([250, 300, 350, 400, 500, 600, 700, 800, 900, 1000])
        # 22% below the median but well inside a very wide spread: not an outlier
        self.assertIsNone(classify(normalize(raw(1, 350)), wide, "x", self.item))

    def test_suspicious_rules(self):
        scam = classify(normalize(raw(1, 150, score=0, pct=0)), self.base, "x", self.item)
        self.assertEqual(scam.kind, "suspicious")
        self.assertTrue(any("feedback" in f for f in scam.flags))
        low_fb = classify(normalize(raw(2, 380, score=2)), self.base, "x", self.item)
        self.assertEqual(low_fb.kind, "suspicious")
        no_ship = classify(normalize(raw(3, 380, ship=None)), self.base, "x", self.item)
        self.assertEqual(no_ship.kind, "deal")
        self.assertTrue(any("shipping" in f for f in no_ship.flags))

    def test_baseline_choice(self):
        sold_small = summarize([400] * 3)
        sold_big = summarize([400] * 10)
        _, label, ok = choose_baseline(self.item, self.base, sold_small)
        self.assertEqual((label, ok), ("asking median", False))
        _, label, ok = choose_baseline(self.item, self.base, sold_big)
        self.assertEqual((label, ok), ("likely-sold median", True))
        asking_item = build_item({}, {"name": "D", "query": "d", "baseline": "asking"})
        _, label, ok = choose_baseline(asking_item, self.base, sold_big)
        self.assertEqual((label, ok), ("asking median", True))


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.tmp.name, "t.db"))
        self.item = build_item({}, {"name": "Deck", "query": "deck", "require_words": ["oled"], "sold_min_sample": 4})
        self.src = FakeSource()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_full_cycle(self):
        normal = [raw(i, 500 + i * 3) for i in range(15)]
        junk = [raw(100, 40, title="Steam Deck OLED box only"), raw(101, 300, title="Steam Deck LCD")]
        self.src.listings = normal + junk
        rep = run_item(self.item, self.src, self.store, T0, "USD")
        self.assertEqual(len(rep.kept), 15)
        self.assertEqual(len(rep.excluded), 2)
        self.assertEqual(rep.asking.n, 15)
        self.assertTrue(rep.learning)
        self.assertEqual(rep.new_alerts, [])

        # The four cheapest sell. A complete scan marks them gone.
        self.src.listings = normal[4:] + junk
        rep = run_item(self.item, self.src, self.store, T0 + timedelta(hours=6), "USD")
        self.assertEqual(rep.gone_now, 4)
        self.assertEqual(rep.sold.n, 4)
        self.assertFalse(rep.learning)
        self.assertEqual(rep.baseline_label, "likely-sold median")

        # A cheap listing shows up: alert once, stay quiet on the next scan, re-alert on a price drop.
        self.src.listings = normal[4:] + [raw(200, 390)]
        rep = run_item(self.item, self.src, self.store, T0 + timedelta(hours=12), "USD")
        self.assertEqual([c.listing.item_id for c in rep.new_alerts], ["v1|200|0"])
        rep = run_item(self.item, self.src, self.store, T0 + timedelta(hours=18), "USD")
        self.assertEqual(rep.new_alerts, [])
        self.src.listings = normal[4:] + [raw(200, 360)]
        rep = run_item(self.item, self.src, self.store, T0 + timedelta(hours=24), "USD")
        self.assertEqual(len(rep.new_alerts), 1)

    def test_incomplete_scan_never_marks_gone(self):
        self.src.listings = [raw(i, 500 + i) for i in range(12)]
        run_item(self.item, self.src, self.store, T0, "USD")
        self.src.listings = self.src.listings[:5]
        self.src.complete = False
        rep = run_item(self.item, self.src, self.store, T0 + timedelta(hours=1), "USD")
        self.assertEqual(rep.gone_now, 0)
        self.assertTrue(any("sold tracking is paused" in w for w in rep.warnings))

    def test_reappearing_listing_is_not_sold(self):
        ls = [raw(i, 500 + i) for i in range(12)]
        self.src.listings = ls
        run_item(self.item, self.src, self.store, T0, "USD")
        self.src.listings = ls[1:]
        run_item(self.item, self.src, self.store, T0 + timedelta(hours=1), "USD")
        self.src.listings = ls
        rep = run_item(self.item, self.src, self.store, T0 + timedelta(hours=2), "USD")
        self.assertIsNone(rep.sold)


class ConfigTest(unittest.TestCase):
    def test_example_config_loads_and_filters_work(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = load_config(os.path.join(here, "config.example.yaml"))
        deck = cfg.items[0]
        self.assertEqual(deck.require_words, ["oled", "512"])  # 512 parsed by YAML as int, coerced to text
        self.assertIn("for parts", deck.all_excludes())
        self.assertIn("carrying case", deck.all_excludes())
        f = ListingFilter(deck.require_words, deck.all_excludes(), cfg.currency)
        self.assertIsNone(f.reject_reason(normalize(raw(1, 400, title="Steam Deck OLED 512GB"))))
        self.assertTrue(cfg.database.endswith("pricewatch.db"))

    def test_defaults_merge_exclude_lists(self):
        item = build_item({"exclude_words": ["a"], "deal_pct": 0.3}, {"name": "X", "query": "x", "exclude_words": ["b"]})
        self.assertEqual(item.exclude_words, ["a", "b"])
        self.assertEqual(item.deal_pct, 0.3)
        with self.assertRaises(ValueError):
            build_item({}, {"name": "X", "query": "x", "deal_pct_typo": 1})


class CredentialTest(unittest.TestCase):
    GOOD_ID = "Marshall-pricewat-PRD-1a2b3c4d5-6e7f8a9b"
    GOOD_SECRET = "PRD-1a2b3c4d5e6f-7a8b-9c0d-1e2f-3a4b"

    def probs(self, cid, sec, **kw):
        return " | ".join(credential_problems(AppConfig(items=[], client_id=cid, client_secret=sec, **kw)))

    def test_well_formed_keys_pass(self):
        self.assertEqual(self.probs(self.GOOD_ID, self.GOOD_SECRET), "")

    def test_common_mistakes(self):
        self.assertIn("placeholder", self.probs("YourApp-PRD-xxxxxxxx-xxxxxxxx", self.GOOD_SECRET))
        self.assertIn("Dev ID", self.probs(self.GOOD_ID, "0a1b2c3d-4e5f-6789-abcd-ef0123456789"))
        self.assertIn("Sandbox", self.probs("Marshall-pricewat-SBX-1a2b3c4d5-6e7f8a9b", "SBX-1a2b3c4d5e6f-7a8b"))
        self.assertEqual(self.probs("Marshall-pricewat-SBX-1a2b3c4d5-6e7f8a9b", "SBX-1a2b", sandbox=True), "")
        self.assertIn("quotes", self.probs("\u201c" + self.GOOD_ID + "\u201d", self.GOOD_SECRET))
        self.assertIn("identical", self.probs(self.GOOD_ID, self.GOOD_ID))
        self.assertIn("empty", self.probs(None, self.GOOD_SECRET))

    def test_env_var_overrides_file_and_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.yaml")
            with open(path, "w") as fh:
                fh.write(f"ebay:\n  client_id: {self.GOOD_ID}\n  client_secret: {self.GOOD_SECRET}\n"
                         "items:\n  - {name: X, query: x}\n")
            old = os.environ.get("EBAY_CLIENT_ID")
            os.environ["EBAY_CLIENT_ID"] = "stale-value"
            try:
                cfg = load_config(path)
            finally:
                if old is None:
                    del os.environ["EBAY_CLIENT_ID"]
                else:
                    os.environ["EBAY_CLIENT_ID"] = old
            self.assertEqual(cfg.client_id, "stale-value")
            self.assertIn("environment variable", cfg.client_id_source)
            self.assertEqual(cfg.client_secret_source, "config.yaml")
            self.assertIn("override config.yaml", " ".join(credential_problems(cfg)))

    def test_mask_hides_middle(self):
        self.assertEqual(mask(self.GOOD_SECRET), "PRD-...3a4b (36 characters)")
        self.assertEqual(mask(None), "(empty)")

    def test_libressl_warning_is_silenced(self):
        # A fresh interpreter: importing pricewatch must hide urllib3's LibreSSL warning.
        code = "import pricewatch, warnings; warnings.warn('urllib3 v2 only supports OpenSSL 1.1.1+')"
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run([sys.executable, "-c", code], cwd=here, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertNotIn("OpenSSL", out.stderr)


class OutputEncodingTest(unittest.TestCase):
    """Windows writes redirected output in cp1252, which has no sparkline characters."""

    def test_demo_survives_legacy_encoding(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONIOENCODING="cp1252")
            db = os.path.join(tmp, "d.db")
            proc = subprocess.run([sys.executable, "-m", "pricewatch", "demo", "--db", db, "--days", "3"],
                                  cwd=here, env=env, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            self.assertIn("daily median", proc.stdout.decode("utf-8"))

    def test_config_with_bom_and_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.yaml")
            with open(path, "w", encoding="utf-8-sig") as fh:
                fh.write("items:\n  - name: Pokémon Booster Box\n    query: pokemon booster box\n")
            self.assertEqual(load_config(path).items[0].name, "Pokémon Booster Box")


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, total):
        self.total = total
        self.gets = []

    def post(self, url, **kw):
        return FakeResp(200, {"access_token": "tok", "expires_in": 7200})

    def get(self, url, headers=None, params=None, timeout=None):
        self.gets.append((headers, dict(params)))
        start, limit = params["offset"], params["limit"]
        n = max(0, min(limit, self.total - start))
        items = [raw(start + i, 100 + start + i) for i in range(n)]
        return FakeResp(200, {"total": self.total, "itemSummaries": items})


class RejectingSession(FakeSession):
    def post(self, url, **kw):
        return FakeResp(401, {"error": "invalid_client", "error_description": "client authentication failed"})


class EbayClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self.tmp.name, "c.yaml")
        with open(path, "w") as fh:
            fh.write(
                "ebay:\n  client_id: id\n  client_secret: secret\n  ship_to: {country: US, zip: '10001'}\n"
                "items:\n  - name: Deck\n    query: steam deck\n    min_price: 150\n    max_price: 900\n"
                "    condition_ids: [3000, 1500]\n    max_pages: 3\n"
            )
        self.cfg = load_config(path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_request_shape(self):
        sess = FakeSession(total=50)
        client = EbayClient(self.cfg, session=sess)
        res = client.search(self.cfg.items[0])
        self.assertTrue(res.complete)
        self.assertEqual(len(res.main), 50)
        headers, params = sess.gets[0]
        self.assertEqual(headers["Authorization"], "Bearer tok")
        self.assertEqual(headers["X-EBAY-C-MARKETPLACE-ID"], "EBAY_US")
        self.assertEqual(headers["X-EBAY-C-ENDUSERCTX"], "contextualLocation=country%3DUS%2Czip%3D10001")
        self.assertEqual(
            params["filter"],
            "buyingOptions:{FIXED_PRICE},conditionIds:{3000|1500},price:[150..900],priceCurrency:USD",
        )

    def test_invalid_client_explains_causes(self):
        from pricewatch.ebay import EbayAuthError
        client = EbayClient(self.cfg, session=RejectingSession(total=0))
        with self.assertRaises(EbayAuthError) as ctx:
            client.token()
        self.assertIn("Account Deletion", str(ctx.exception))
        self.assertIn("Cert ID", str(ctx.exception))

    def test_pagination_and_cheap_pass(self):
        sess = FakeSession(total=1000)
        client = EbayClient(self.cfg, session=sess)
        res = client.search(self.cfg.items[0])
        self.assertFalse(res.complete)
        self.assertEqual(len(res.main), 600)
        self.assertEqual([p["offset"] for _, p in sess.gets], [0, 200, 400, 0])
        self.assertEqual(sess.gets[-1][1]["sort"], "price")
        self.assertEqual(client.calls, 4)


if __name__ == "__main__":
    unittest.main()
