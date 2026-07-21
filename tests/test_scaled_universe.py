from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.pipeline.run_scaled_pipeline import main as pipeline_main
from scripts.sec.sec_client import SecClient
from scripts.universe.limits import parse_optional_limit
from scripts.universe.build_universe import build_scaled_universe, write_universe
from scripts.universe.normalize_symbols import normalize_cik, normalize_ticker
from scripts.universe.universe_filters import classify_security


SEC_FIXTURE = [
    {"cik": 320193, "name": "Apple Inc.", "ticker": "AAPL", "exchange": "Nasdaq"},
    {"cik": 789019, "name": "Microsoft Corp.", "ticker": "MSFT", "exchange": "Nasdaq"},
    {"cik": 1, "name": "Example ETF Trust", "ticker": "ETF", "exchange": "NYSE"},
    {"cik": 2, "name": "Example Warrants", "ticker": "ABC-W", "exchange": "Nasdaq"},
    {"cik": 3, "name": "OTC Example", "ticker": "OTC", "exchange": "OTC"},
]


class ScaledUniverseTests(unittest.TestCase):
    def test_normalization(self) -> None:
        self.assertEqual(normalize_cik(320193), "0000320193")
        self.assertEqual(normalize_ticker("brk.b"), "BRK-B")

    def test_unsupported_security_marking(self) -> None:
        self.assertFalse(classify_security("ABC-W", "Example Warrants", "Nasdaq").is_supported)
        self.assertFalse(classify_security("ETF", "Example ETF Trust", "NYSE").is_supported)
        self.assertFalse(classify_security("OTC", "OTC Example", "OTC").is_supported)
        self.assertFalse(classify_security("AACBU", "Artius II Acquisition Inc. Unit", "Nasdaq").is_supported)
        self.assertTrue(classify_security("AAPL", "Apple Inc.", "Nasdaq").is_supported)
        self.assertTrue(classify_security("LOW", "Lowe's Companies Inc.", "NYSE").is_supported)

    def test_starter_universe_uses_existing_seed(self) -> None:
        rows = build_scaled_universe(mode="starter", limit=2)
        self.assertEqual([row["ticker"] for row in rows], ["AAPL", "MSFT"])
        self.assertTrue(all(row["cik"].isdigit() and len(row["cik"]) == 10 for row in rows))

    def test_sec_listed_core_keeps_unsupported_rows_marked(self) -> None:
        rows = build_scaled_universe(mode="sec_listed_core", sec_records=SEC_FIXTURE)
        supported = [row for row in rows if row["isSupported"]]
        unsupported = [row for row in rows if not row["isSupported"]]
        self.assertEqual([row["ticker"] for row in supported], ["AAPL", "MSFT"])
        self.assertTrue(unsupported)
        self.assertTrue(all(row["excludeReason"] for row in unsupported))

    def test_sec_listed_core_limit_bounds_supported_rows(self) -> None:
        rows = build_scaled_universe(mode="sec_listed_core", limit=1, sec_records=SEC_FIXTURE)
        self.assertEqual([row["ticker"] for row in rows if row["isSupported"]], ["AAPL"])

    def test_scaled_universe_can_preserve_starter_preview(self) -> None:
        sec_records = SEC_FIXTURE + [
            {"cik": 4, "name": "Zooming Example Inc.", "ticker": "ZZZ", "exchange": "NYSE"},
        ]
        rows = build_scaled_universe(mode="sec_listed_core", limit=11, sec_records=sec_records, include_starter=True)
        tickers = [row["ticker"] for row in rows if row["isSupported"]]

        self.assertEqual(tickers[:10], ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "JNJ", "XOM", "F", "KO", "INTC"])
        self.assertEqual(len(tickers), 11)
        self.assertEqual(tickers.count("AAPL"), 1)
        self.assertIn("ZZZ", tickers)

    def test_optional_limit_supports_omitted_and_all(self) -> None:
        self.assertIsNone(parse_optional_limit(None))
        self.assertIsNone(parse_optional_limit("all"))
        self.assertEqual(parse_optional_limit("500"), 500)

    def test_omitted_limit_does_not_cap_fixture_universe(self) -> None:
        rows = build_scaled_universe(mode="sec_listed_core", sec_records=SEC_FIXTURE)
        self.assertEqual(len([row for row in rows if row["isSupported"]]), 2)

    def test_write_universe_manifest(self) -> None:
        rows = build_scaled_universe(mode="starter", limit=1)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = write_universe(rows, mode="starter", limit=1, output_dir=Path(tmp), batch_size=250, offset=0, resume=True)
            self.assertEqual(manifest["supportedCount"], 1)
            self.assertEqual(manifest["batchSize"], 250)
            self.assertTrue(manifest["resume"])
            self.assertTrue((Path(tmp) / "universe.json").exists())
            self.assertTrue((Path(tmp) / "universe_manifest.json").exists())

    def test_scaled_pipeline_dry_run_report(self) -> None:
        with patch("sys.argv", ["run_scaled_pipeline.py", "--mode", "starter", "--limit", "2", "--dry-run"]):
            pipeline_main()

    def test_scaled_pipeline_parses_all_limit_for_staged_batch(self) -> None:
        with patch("sys.argv", ["run_scaled_pipeline.py", "--mode", "starter", "--limit", "all", "--batch-size", "2", "--dry-run"]):
            pipeline_main()


class SecClientTests(unittest.TestCase):
    def test_user_agent_requires_contact(self) -> None:
        with self.assertRaises(ValueError):
            SecClient(user_agent="ValueSignal")

    def test_cache_hit_avoids_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = SecClient(user_agent="ValueSignal test@example.com", cache_dir=tmp)
            path = client.cache_path("https://example.test/data.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"ok": True}), encoding="utf-8")
            payload, meta = client.get_json("https://example.test/data.json")
            self.assertEqual(payload, {"ok": True})
            self.assertTrue(meta["cacheHit"])


if __name__ == "__main__":
    unittest.main()
