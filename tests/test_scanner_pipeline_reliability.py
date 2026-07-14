import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as scanner_main
import scanner_status
import system_status_exporter
import web_exporter


REPORT_HEADER = list(scanner_main.REPORT_COLUMNS)


def sample_candidate(ticker: str = "HIMS"):
    return {
        "ticker": ticker,
        "latest_open": 36.75,
        "latest_close": 38.51,
        "open_to_close_change": 4.79,
        "five_day_change": 15.33,
        "twenty_day_change": 47.04,
        "relative_strength": 44.81,
        "avg_volume": 18758802,
        "volume_ratio": 0.58,
        "pre_score": 41.67,
        "expected_return": 8.0,
        "win_probability": 67.8,
        "confidence": 67.8,
        "risk": "Medium",
        "action": "WATCH",
        "reason": "Evidence-based scanner reason.",
        "sector": "Consumer Health",
        "sector_rank": 1,
        "sentiment_score": 50,
        "sentiment_label": "Neutral",
        "analysis_brief": "Scanner evidence is available.",
        "confidence_score": 75,
        "confidence_reasons": ["Positive momentum"],
        "risk_flags": [],
        "historical_matches": 61,
        "best_hold_period": "10 days",
        "best_avg_return": 5.79,
        "historical_summary": "Found similar setups.",
        "pattern_1d_avg_return": 0.21,
        "pattern_3d_avg_return": 1.3,
        "pattern_5d_avg_return": 2.4,
        "pattern_7d_avg_return": 3.82,
        "pattern_10d_avg_return": 5.79,
        "pattern_1d_win_rate": 44.26,
        "pattern_3d_win_rate": 59.02,
        "pattern_5d_win_rate": 54.1,
        "pattern_7d_win_rate": 59.02,
        "pattern_10d_win_rate": 57.38,
        "score": 51.59,
    }


def market_ok():
    index = {
        "trend": "Bullish",
        "price": 100,
        "score": 75,
        "ma20": 95,
        "ma50": 90,
        "return_20d": 3.2,
    }
    return {
        "regime": "Risk-On",
        "market_score": 75,
        "description": "Healthy test market.",
        "spy": dict(index),
        "qqq": dict(index),
        "iwm": dict(index),
    }


def sectors_ok():
    return [
        {
            "sector": "Technology",
            "etf": "XLK",
            "five_day_return": 1,
            "twenty_day_return": 2,
            "sector_score": 1.6,
        }
        for _ in range(len(scanner_main.SECTOR_ETFS))
    ]


class TempCwd:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = os.getcwd()
        os.chdir(self.tmp.name)
        Path("data").mkdir()
        Path("reports").mkdir()
        Path("performance").mkdir()
        return Path(self.tmp.name)

    def __exit__(self, exc_type, exc, tb):
        os.chdir(self.previous)
        self.tmp.cleanup()


def write_report(path: Path, rows=None, header=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        if not header:
            f.write("")
            return
        writer = csv.DictWriter(f, fieldnames=REPORT_HEADER)
        writer.writeheader()
        for row in rows or []:
            writer.writerow(row)


class ScannerPipelineReliabilityTests(unittest.TestCase):
    def test_report_validation_rejects_empty_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-10_v2.csv"
            path.write_text("")
            result = scanner_status.report_validation(path)
            self.assertFalse(result["valid"])
            self.assertEqual(result["reason"], "empty_file")

    def test_header_only_zero_candidate_csv_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-10_v2.csv"
            write_report(path, [])
            result = scanner_status.report_validation(path)
            self.assertTrue(result["valid"])
            self.assertEqual(result["row_count"], 0)

    def test_latest_valid_report_skips_newer_invalid_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            write_report(reports / "2026-07-09_v2.csv", [sample_candidate()])
            (reports / "2026-07-10_v2.csv").write_text("")
            self.assertEqual(
                scanner_status.latest_valid_report(reports),
                reports / "2026-07-09_v2.csv",
            )

    def test_failure_classification_cases(self):
        self.assertIsNone(scanner_status.scanner_failure_reason(
            coverage_pct=80,
            benchmark_data_status="ok",
            sector_data_status="ok",
        ))
        self.assertEqual(
            scanner_status.scanner_failure_reason(
                coverage_pct=59,
                benchmark_data_status="ok",
                sector_data_status="ok",
            ),
            "insufficient_ticker_data_coverage",
        )
        self.assertEqual(
            scanner_status.scanner_failure_reason(
                coverage_pct=80,
                benchmark_data_status="failed",
                sector_data_status="ok",
            ),
            "benchmark_or_regime_data_unavailable",
        )
        self.assertEqual(
            scanner_status.scanner_failure_reason(
                coverage_pct=80,
                benchmark_data_status="ok",
                sector_data_status="failed",
            ),
            "sector_data_unavailable",
        )

    def test_healthy_scan_with_candidates_writes_valid_report(self):
        with TempCwd() as cwd, patch.object(scanner_main, "send_email"), patch.object(
            scanner_main, "get_market_regime", return_value=market_ok()
        ), patch.object(scanner_main, "rank_sectors", return_value=sectors_ok()), patch.object(
            scanner_main,
            "scan_market_with_health",
            return_value={
                "results": [sample_candidate()],
                "health": {
                    "tickers_requested": 10,
                    "tickers_succeeded": 9,
                    "tickers_failed": 1,
                    "data_coverage_pct": 90,
                    "benchmark_data_status": "ok",
                    "benchmark_failure_reason": None,
                    "failed_tickers": [],
                },
            },
        ), patch.object(scanner_main, "add_final_scoring", return_value=[sample_candidate()]):
            self.assertEqual(scanner_main.main(["--allow-non-trading-day-production"]), 0)
            report = cwd / "reports" / f"{scanner_main.market_date()}_v2.csv"
            self.assertTrue(scanner_status.report_validation(report)["valid"])
            status = json.loads((cwd / "data" / "scanner_status.json").read_text())
            self.assertEqual(status["last_attempt_status"], "success")
            self.assertEqual(status["last_attempt_type"], "production")
            self.assertEqual(status["candidates_found"], 1)

    def test_healthy_scan_with_zero_candidates_writes_header_only_report(self):
        with TempCwd() as cwd, patch.object(scanner_main, "send_email"), patch.object(
            scanner_main, "get_market_regime", return_value=market_ok()
        ), patch.object(scanner_main, "rank_sectors", return_value=sectors_ok()), patch.object(
            scanner_main,
            "scan_market_with_health",
            return_value={
                "results": [],
                "health": {
                    "tickers_requested": 10,
                    "tickers_succeeded": 10,
                    "tickers_failed": 0,
                    "data_coverage_pct": 100,
                    "benchmark_data_status": "ok",
                    "benchmark_failure_reason": None,
                    "failed_tickers": [],
                },
            },
        ):
            self.assertEqual(scanner_main.main(["--allow-non-trading-day-production"]), 0)
            report = cwd / "reports" / f"{scanner_main.market_date()}_v2.csv"
            validation = scanner_status.report_validation(report)
            self.assertTrue(validation["valid"])
            self.assertEqual(validation["row_count"], 0)

    def test_forced_weekend_run_defaults_to_manual_test(self):
        with TempCwd() as cwd, patch.object(scanner_main, "send_email"), patch.object(
            scanner_main, "is_trading_weekday", return_value=False
        ), patch.object(scanner_main, "get_market_regime", return_value=market_ok()), patch.object(
            scanner_main, "rank_sectors", return_value=sectors_ok()
        ), patch.object(
            scanner_main,
            "scan_market_with_health",
            return_value={
                "results": [sample_candidate()],
                "health": {
                    "tickers_requested": 10,
                    "tickers_succeeded": 10,
                    "tickers_failed": 0,
                    "data_coverage_pct": 100,
                    "benchmark_data_status": "ok",
                    "benchmark_failure_reason": None,
                    "failed_tickers": [],
                },
            },
        ), patch.object(scanner_main, "add_final_scoring", return_value=[sample_candidate()]):
            self.assertEqual(scanner_main.main([]), 0)
            self.assertFalse((cwd / "reports" / f"{scanner_main.market_date()}_v2.csv").exists())
            self.assertTrue((cwd / "reports" / "manual-tests" / f"{scanner_main.market_date()}_v2.csv").exists())
            status = json.loads((cwd / "data" / "scanner_status.json").read_text())
            self.assertEqual(status["last_attempt_type"], "manual_test")
            self.assertIsNone(status.get("last_success_market_date"))
            self.assertEqual(status["latest_manual_test_market_date"], scanner_main.market_date())

    def test_total_provider_failure_does_not_write_valid_report(self):
        with TempCwd() as cwd, patch.object(
            scanner_main, "get_market_regime", return_value=market_ok()
        ), patch.object(scanner_main, "rank_sectors", return_value=sectors_ok()), patch.object(
            scanner_main,
            "scan_market_with_health",
            return_value={
                "results": [],
                "health": {
                    "tickers_requested": 10,
                    "tickers_succeeded": 0,
                    "tickers_failed": 10,
                    "data_coverage_pct": 0,
                    "benchmark_data_status": "failed",
                    "benchmark_failure_reason": "dns failure",
                    "failed_tickers": [{"ticker": "HIMS", "reason": "dns failure"}],
                },
            },
        ):
            self.assertEqual(scanner_main.main(), 2)
            self.assertFalse(list((cwd / "reports").glob("*_v2.csv")))
            self.assertTrue(list((cwd / "reports" / "failed").glob("*_scanner_failure.json")))
            status = json.loads((cwd / "data" / "scanner_status.json").read_text())
            self.assertEqual(status["last_attempt_status"], "failed_data_unavailable")
            self.assertEqual(status["last_attempt_type"], "failed")

    def test_reconcile_from_mixed_report_folders(self):
        with TempCwd() as cwd:
            write_report(cwd / "reports" / "2026-07-09_v2.csv", [sample_candidate()])
            write_report(cwd / "reports" / "manual-tests" / "2026-07-11_v2.csv", [sample_candidate("HOOD")])
            write_report(cwd / "reports" / "failed" / "2026-07-10_v2.csv", [sample_candidate("CELH")])
            status = scanner_status.reconcile_status(cwd / "reports", cwd / "data" / "scanner_status.json")
            self.assertEqual(status["last_success_market_date"], "2026-07-09")
            self.assertEqual(status["latest_valid_report"], str(cwd / "reports" / "2026-07-09_v2.csv"))
            self.assertEqual(status["latest_manual_test_market_date"], "2026-07-11")
            self.assertEqual(status["latest_failed_attempt_market_date"], "2026-07-10")
            self.assertEqual(status["last_attempt_type"], "manual_test")

    def test_latest_production_remains_older_than_manual_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            write_report(reports / "2026-07-09_v2.csv", [sample_candidate()])
            write_report(reports / "manual-tests" / "2026-07-11_v2.csv", [sample_candidate()])
            self.assertEqual(scanner_status.latest_valid_report(reports), reports / "2026-07-09_v2.csv")

    def test_web_exporter_preserves_snapshot_when_downstream_export_fails(self):
        with TempCwd() as cwd, patch.object(web_exporter, "export_paper_trading_snapshot", side_effect=RuntimeError("boom")):
            write_report(cwd / "reports" / "2026-07-09_v2.csv", [sample_candidate()])
            snapshot = cwd / "data" / "web_snapshot.json"
            snapshot.write_text('{"previous": true}\n')
            with self.assertRaises(RuntimeError):
                web_exporter.export_snapshot()
            self.assertEqual(json.loads(snapshot.read_text()), {"previous": True})

    def test_web_exporter_refreshes_public_snapshot_after_newer_official_export(self):
        with TempCwd() as cwd, patch.object(
            web_exporter,
            "export_paper_trading_snapshot",
            return_value={
                "daily_picks": "data/paper_trading/daily_picks.json",
                "portfolio_summary": "data/paper_trading/portfolio_summary.json",
            },
        ):
            write_report(cwd / "reports" / "2026-07-12_v2.csv", [sample_candidate("HIMS")])
            write_report(cwd / "reports" / "2026-07-13_v2.csv", [sample_candidate("SE")])
            public_snapshot = cwd / "ai-stock-hunter-web" / "public" / "web_snapshot.json"
            public_snapshot.parent.mkdir(parents=True)
            public_snapshot.write_text(json.dumps({
                "source_file": "reports/2026-07-06_v2.csv",
                "top_opportunity": {"ticker": "HIMS"},
                "ranked_candidates": [{"ticker": "HIMS"}],
            }))

            web_exporter.export_snapshot()

            data_snapshot = json.loads((cwd / "data" / "web_snapshot.json").read_text())
            public_payload = json.loads(public_snapshot.read_text())
            changes = json.loads((cwd / "data" / "research_changes.json").read_text())
            self.assertEqual(data_snapshot["top_opportunity"]["ticker"], "SE")
            self.assertEqual(public_payload["top_opportunity"]["ticker"], "SE")
            self.assertEqual(changes["current_date"], "2026-07-13")

    def test_mission_control_reports_attempt_and_success_separately(self):
        with TempCwd():
            scanner_status.write_status({
                "last_attempt_at": "2026-07-10T18:00:00-04:00",
                "last_attempt_market_date": "2026-07-10",
                "last_attempt_status": "failed_data_unavailable",
                "last_attempt_type": "failed",
                "last_failure_reason": "insufficient_ticker_data_coverage",
                "last_success_at": "2026-07-09T18:00:00-04:00",
                "last_success_market_date": "2026-07-09",
                "data_coverage_pct": 0,
                "exporter_completed": False,
                "production_pipeline_completed": False,
            })
            status = system_status_exporter.daily_pipeline_status(None)
            self.assertEqual(status["status"], "failed")
            self.assertEqual(status["last_attempt_market_date"], "2026-07-10")
            self.assertEqual(status["last_market_date"], "2026-07-09")

    def test_automation_success_marker_created_after_required_stages(self):
        script = Path("automation/scripts/run_daily_pipeline.sh").read_text()
        self.assertIn("trap on_pipeline_error ERR", script)
        marker_write = script.index('printf "completed_at=%s')
        self.assertLess(script.index('"${PYTHON_BIN}" web_exporter.py'), marker_write)
        self.assertLess(script.index('"${PYTHON_BIN}" system_status_exporter.py'), marker_write)

    def test_manual_test_does_not_create_production_marker_or_export(self):
        script = Path("automation/scripts/run_daily_pipeline.sh").read_text()
        manual_block = script[script.index('log_line "Manual test completed'):script.index('log_line "Stage 2/5')]
        self.assertIn("main.py --manual-test", script)
        self.assertIn("success marker", manual_block.lower())
        self.assertIn("exit 0", manual_block)
        self.assertNotIn("web_exporter.py", manual_block)


if __name__ == "__main__":
    unittest.main()
