import json
import plistlib
import tempfile
import unittest
from pathlib import Path

from paper_trading_engine import refresh_paper_trading
from refresh_paper_trading import main as refresh_command_main
from tests.test_paper_trading_engine import FakeMarketDataService, quote
from tests.test_refresh_paper_trading import open_position_fixture


def snapshot_payload(price=100, status="DELAYED", generated_at="2026-07-01T10:05:00-04:00"):
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "valuation_generated_at": generated_at,
        "valuation_batch_id": "valuation_test_1005",
        "refresh_cadence_seconds": 300,
        "market_state": "OPEN",
        "provider": "fake",
        "quote_status": status,
        "tickers_requested": ["TEST"],
        "tickers_updated": 1 if status in {"LIVE", "DELAYED"} else 0,
        "tickers_stale": 0 if status in {"LIVE", "DELAYED"} else 1,
        "quotes": {
            "TEST": quote(
                ticker="TEST",
                price=price,
                status=status,
                timestamp=generated_at,
            )
        },
        "errors": [],
    }


class FiveMinutePaperRefreshTest(unittest.TestCase):
    def test_launchd_interval_is_five_minutes(self):
        with open("automation/launchd/com.aistockhunter.paper-refresh.plist", "rb") as f:
            payload = plistlib.load(f)
        self.assertEqual(payload["StartInterval"], 300)

    def test_refresh_command_consumes_snapshot_batch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = open_position_fixture(temp_dir, hold_days=99)
            (root / "out" / "daily_picks.json").write_text(json.dumps(payload))
            snapshot_path = root / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot_payload()))
            code = refresh_command_main([
                "--state-dir", str(root / "state"),
                "--output-dir", str(root / "out"),
                "--daily-picks", str(root / "out" / "daily_picks.json"),
                "--market-snapshot", str(snapshot_path),
            ])
            self.assertEqual(code, 0)
            summary = json.loads((root / "out" / "portfolio_summary.json").read_text())
            positions = json.loads((root / "out" / "open_positions.json").read_text())
            self.assertEqual(summary["valuation_batch_id"], "valuation_test_1005")
            self.assertEqual(positions["valuation_batch_id"], "valuation_test_1005")
            self.assertEqual(positions["positions"][0]["current_price"], 100)
            self.assertEqual(summary["summary"]["total_equity"], 25000.0)

    def test_no_duplicate_equity_point_for_same_batch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir)
            root = Path(temp_dir)
            market_data = FakeMarketDataService({
                "TEST": quote(price=105, timestamp="2026-07-02T10:05:00-04:00")
            })
            first = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=market_data,
                generated_at="2026-07-02T10:05:00",
            )
            refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=market_data,
                generated_at="2026-07-02T10:05:00",
            )
            points = json.loads((root / "out" / "equity_curve.json").read_text())["points"]
            self.assertLessEqual(len(points), 2)
            self.assertEqual(first["positions_updated"], 1)

    def test_no_equity_point_when_no_prices_update(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir)
            root = Path(temp_dir)
            before = json.loads((root / "out" / "equity_curve.json").read_text())["points"]
            refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({}),
                generated_at="2026-07-02T10:05:00",
            )
            after = json.loads((root / "out" / "equity_curve.json").read_text())["points"]
            self.assertEqual(len(after), len(before))

    def test_daily_picks_and_web_snapshot_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir)
            root = Path(temp_dir)
            daily = root / "out" / "daily_picks.json"
            web = root / "web_snapshot.json"
            daily.write_text(json.dumps(payload))
            web.write_text(json.dumps({"top": "unchanged"}))
            before_daily = daily.read_text()
            before_web = web.read_text()
            refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=105, timestamp="2026-07-02T10:05:00-04:00")
                }),
                generated_at="2026-07-02T10:05:00",
            )
            self.assertEqual(daily.read_text(), before_daily)
            self.assertEqual(web.read_text(), before_web)


if __name__ == "__main__":
    unittest.main()
