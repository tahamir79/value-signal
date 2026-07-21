import unittest

from scripts.pipeline_health import _analyst_targets_stage, _balance_sheet_stage, _forecast_stage, _growth_spurt_stage, normalize_failure, public_summary


class PipelineHealthTests(unittest.TestCase):
    def test_normalizes_provider_404_as_non_retryable(self):
        reason, retryable = normalize_failure("ProviderError: Request failed after 3 attempts: HTTP Error 404: Not Found")
        self.assertEqual(reason, "PROVIDER_HTTP_404")
        self.assertFalse(retryable)

    def test_normalizes_429_as_retryable(self):
        reason, retryable = normalize_failure("HTTP Error 429: Too Many Requests")
        self.assertEqual(reason, "PROVIDER_RETRYABLE_HTTP_ERROR")
        self.assertTrue(retryable)

    def test_public_summary_removes_artifact_paths(self):
        report = {
            "schemaVersion": "1.0.0",
            "generatedAt": "2026-01-01T00:00:00+00:00",
            "overallStatus": "partial_success",
            "releaseReadiness": "ready_with_known_limitations",
            "criticalFailures": 0,
            "nonCriticalFailures": 1,
            "expectedUnavailable": 1,
            "dataQualityWarnings": 0,
            "warnings": 2,
            "stages": [{
                "name": "backtest",
                "status": "unavailable_expected",
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 1,
                "failedTickers": [],
                "commonReasons": [{"reason": "EXPECTED_BACKTEST_SKIPPED", "count": 1}],
                "artifactPaths": ["C:/local/path/should/not/leak"],
            }],
            "failedTickers": [{"ticker": "AAC", "stage": "ticker_pipeline", "reason": "PROVIDER_HTTP_404", "retryable": False}],
        }
        payload = public_summary(report)
        self.assertNotIn("artifactPaths", payload["stages"][0])
        self.assertEqual(payload["stages"][0]["status"], "unavailable_expected")

    def test_balance_sheet_stage_counts_successful_etl_coverage(self):
        stage = _balance_sheet_stage({
            "counts": {
                "scoreable_companies": 147,
                "balance_sheets_available": 19,
                "balance_sheets_partial": 180,
                "balance_sheets_unavailable": 46,
            }
        })
        self.assertEqual(stage["attempted"], 245)
        self.assertEqual(stage["succeeded"], 199)
        self.assertEqual(stage["skipped"], 46)
        self.assertEqual(stage["status"], "partial_success")

    def test_growth_spurt_stage_counts_unavailable_as_expected_gap(self):
        stage = _growth_spurt_stage({
            "growthSpurtCoverage": {
                "growthSpurtMode": "display",
                "stocksGrowthSpurtAttempted": 245,
                "stocksGrowthSpurtDetected": 12,
                "stocksGrowthSpurtEmerging": 31,
                "stocksGrowthSpurtNotDetected": 190,
                "stocksGrowthSpurtUnavailable": 12,
                "growthSpurtCalculationFailures": 0,
            }
        })
        self.assertEqual(stage["attempted"], 245)
        self.assertEqual(stage["succeeded"], 233)
        self.assertEqual(stage["skipped"], 12)
        self.assertEqual(stage["failed"], 0)
        self.assertEqual(stage["status"], "success")

    def test_forecast_insufficient_history_is_skipped_coverage_not_failure(self):
        stage = _forecast_stage({
            "count": 245,
            "displayProjectionSources": {"conservative_historical_scenario": 203, "unavailable": 42},
            "conservativeScenarioStatus": {"available": 203, "insufficient_data": 42, "stale": 0},
        })
        self.assertEqual(stage["attempted"], 245)
        self.assertEqual(stage["succeeded"], 203)
        self.assertEqual(stage["skipped"], 42)
        self.assertEqual(stage["failed"], 0)
        self.assertEqual(stage["status"], "success")

    def test_market_target_provider_unconfigured_is_expected_unavailable(self):
        stage = _analyst_targets_stage({"count": 245})
        self.assertEqual(stage["name"], "market_targets")
        self.assertEqual(stage["status"], "unavailable_expected")
        self.assertEqual(stage["skipped"], 245)
        self.assertEqual(stage["failed"], 0)


if __name__ == "__main__":
    unittest.main()
