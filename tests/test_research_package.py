import csv
import json
import tempfile
import unittest
from pathlib import Path

import main as scanner_main
from research_package import resolve_research_package


REPORT_HEADER = list(scanner_main.REPORT_COLUMNS)


def sample_row(ticker: str, action: str = "WATCH") -> dict:
    return {
        "ticker": ticker,
        "latest_open": 10,
        "latest_close": 11,
        "open_to_close_change": 1,
        "five_day_change": 2,
        "twenty_day_change": 3,
        "relative_strength": 4,
        "avg_volume": 1000000,
        "volume_ratio": 1.2,
        "pre_score": 40,
        "expected_return": 5,
        "win_probability": 60,
        "confidence": 60,
        "risk": "Medium",
        "action": action,
        "reason": "Evidence-based reason.",
        "sector": "Technology",
        "sector_rank": 1,
        "sentiment_score": 50,
        "sentiment_label": "Neutral",
        "analysis_brief": "Evidence is available.",
        "confidence_score": 75,
        "confidence_reasons": ["Momentum"],
        "risk_flags": [],
        "historical_matches": 20,
        "best_hold_period": "10 days",
        "best_avg_return": 5,
        "historical_summary": "Similar setups.",
        "pattern_1d_avg_return": 0,
        "pattern_3d_avg_return": 0,
        "pattern_5d_avg_return": 0,
        "pattern_7d_avg_return": 0,
        "pattern_10d_avg_return": 5,
        "pattern_1d_win_rate": 50,
        "pattern_3d_win_rate": 50,
        "pattern_5d_win_rate": 50,
        "pattern_7d_win_rate": 50,
        "pattern_10d_win_rate": 60,
        "score": 50,
    }


def write_report(path: Path, ticker: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_HEADER)
        writer.writeheader()
        writer.writerow(sample_row(ticker))
    return path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def web_snapshot(source: str, top: str, rank_one: str | None = None) -> dict:
    return {
        "generated_at": "2026-07-13T18:00:00",
        "source_file": source,
        "top_opportunity": {"ticker": top},
        "ranked_candidates": [{"ticker": rank_one or top}],
    }


def daily_picks(source: str, date: str, top: str, action: str = "WATCH") -> dict:
    return {
        "generated_at": "2026-07-13T18:00:00",
        "source_file": source,
        "trade_date": date,
        "picks": [{"ticker": top, "action": action}],
    }


def changes(source: str, date: str, top: str) -> dict:
    return {
        "generated_at": "2026-07-13T18:01:00",
        "status": "ready",
        "current_date": date,
        "current_source": source,
        "top_opportunity_change": {"current": {"ticker": top}},
    }


class ResearchPackageTests(unittest.TestCase):
    def test_matching_package_is_ready_and_top_matches_rank_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(report), "SE"))
            write_json(root / "data" / "paper_trading" / "daily_picks.json", daily_picks(str(report), "2026-07-13", "SE"))
            write_json(root / "data" / "research_changes.json", changes(str(report), "2026-07-13", "SE"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["top_opportunity_ticker"], "SE")
            self.assertEqual(result["mismatches"], [])

    def test_stale_hims_snapshot_with_newer_se_daily_picks_is_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_report = write_report(root / "reports" / "2026-07-06_v2.csv", "HIMS")
            new_report = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(old_report), "HIMS"))
            write_json(root / "data" / "paper_trading" / "daily_picks.json", daily_picks(str(new_report), "2026-07-13", "SE"))
            write_json(root / "data" / "research_changes.json", changes(str(new_report), "2026-07-13", "SE"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "mismatch")
            self.assertTrue(any("web_snapshot_source_mismatch" in item for item in result["mismatches"]))

    def test_web_top_must_match_rank_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(report), "HIMS", rank_one="SE"))
            write_json(root / "data" / "paper_trading" / "daily_picks.json", daily_picks(str(report), "2026-07-13", "SE"))
            write_json(root / "data" / "research_changes.json", changes(str(report), "2026-07-13", "SE"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "mismatch")
            self.assertTrue(any("top_opportunity_rank_mismatch" in item for item in result["mismatches"]))

    def test_research_change_current_date_must_match_displayed_package_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(report), "SE"))
            write_json(root / "data" / "paper_trading" / "daily_picks.json", daily_picks(str(report), "2026-07-13", "SE"))
            write_json(root / "data" / "research_changes.json", changes(str(report), "2026-07-12", "SE"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "mismatch")
            self.assertTrue(any("research_changes_current_date_mismatch" in item for item in result["mismatches"]))

    def test_manual_weekend_report_cannot_replace_official_production_hero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prod = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            manual = write_report(root / "reports" / "manual-tests" / "2026-07-14_v2.csv", "HIMS")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(manual), "HIMS"))
            write_json(root / "data" / "paper_trading" / "daily_picks.json", daily_picks(str(prod), "2026-07-13", "SE"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "mismatch")
            self.assertEqual(result["official_market_date"], "2026-07-13")

    def test_failed_report_cannot_replace_official_production_hero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prod = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            failed = write_report(root / "reports" / "failed" / "2026-07-14_v2.csv", "HIMS")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(failed), "HIMS"))
            write_json(root / "data" / "paper_trading" / "daily_picks.json", daily_picks(str(prod), "2026-07-13", "SE"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "mismatch")
            self.assertEqual(result["official_market_date"], "2026-07-13")

    def test_missing_strategy_signal_is_honest_not_backfilled_from_old_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(report), "SE"))
            write_json(root / "data" / "paper_trading" / "daily_picks.json", daily_picks(str(report), "2026-07-13", "HIMS"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "mismatch")
            self.assertTrue(any("daily_picks_rank_mismatch" in item for item in result["mismatches"]))

    def test_last_consistent_package_is_preserved_when_export_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = write_report(root / "reports" / "2026-07-13_v2.csv", "SE")
            write_json(root / "data" / "web_snapshot.json", web_snapshot(str(report), "SE"))

            result = resolve_research_package(data_dir=root / "data", reports_dir=root / "reports")

            self.assertEqual(result["status"], "mismatch")
            self.assertIn("missing_daily_picks", result["mismatches"])


if __name__ == "__main__":
    unittest.main()
