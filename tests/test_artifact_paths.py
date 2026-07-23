from __future__ import annotations

import unittest

from scripts.artifact_paths import ticker_artifact_stem, ticker_from_artifact_stem


class ArtifactPathTests(unittest.TestCase):
    def test_windows_reserved_tickers_are_prefixed_only_on_disk(self) -> None:
        self.assertEqual(ticker_artifact_stem("CON"), "_CON")
        self.assertEqual(ticker_artifact_stem("prn"), "_PRN")
        self.assertEqual(ticker_artifact_stem("COM1"), "_COM1")
        self.assertEqual(ticker_from_artifact_stem("_CON"), "CON")
        self.assertEqual(ticker_from_artifact_stem("_COM1"), "COM1")

    def test_normal_tickers_are_unchanged(self) -> None:
        self.assertEqual(ticker_artifact_stem("AAPL"), "AAPL")
        self.assertEqual(ticker_artifact_stem("BRK-B"), "BRK-B")
        self.assertEqual(ticker_from_artifact_stem("BRK-B"), "BRK-B")


if __name__ == "__main__":
    unittest.main()
