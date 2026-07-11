import json
import tempfile
import unittest
from pathlib import Path

from paper_trading_engine import refresh_paper_trading
from refresh_paper_trading import main as refresh_command_main
from tests.test_paper_trading_engine import (
    FakeMarketDataService,
    daily_picks,
    pick,
    quote,
    raw_rows_from,
)
from paper_trading_engine import process_paper_trading
from portfolio_governance import set_mode


def open_position_fixture(temp_dir, ticker="TEST", entry_price=100, hold_days=5):
    root = Path(temp_dir)
    set_mode("ai_managed", f"fixture-{ticker.lower()}-0001", root / "state", generated_at="2026-07-01T09:59:00")
    item = pick(ticker=ticker, price=entry_price, hold_days=hold_days)
    payload = daily_picks([item])
    process_paper_trading(
        daily_picks=payload,
        raw_rows=raw_rows_from([item]),
        output_dir=root / "out",
        state_dir=root / "state",
        generated_at="2026-07-01T10:00:00",
        market_data_service=FakeMarketDataService({
            ticker.upper(): quote(ticker=ticker, price=entry_price, timestamp="2026-07-01T10:00:00-04:00")
        }),
    )
    return payload


class RefreshPaperTradingTest(unittest.TestCase):
    def test_empty_ledger_writes_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                market_data_service=FakeMarketDataService({}),
                generated_at="2026-07-02T10:00:00",
            )
            self.assertEqual(result["open_positions"], 0)
            self.assertEqual(result["positions_updated"], 0)
            self.assertTrue((root / "out" / "portfolio_summary.json").exists())

    def test_one_open_position_updated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir)
            root = Path(temp_dir)
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=105, timestamp="2026-07-02T10:00:00-04:00")
                }),
                generated_at="2026-07-02T10:00:00",
            )
            self.assertEqual(result["positions_updated"], 1)
            with open(root / "out" / "open_positions.json") as f:
                position = json.load(f)["positions"][0]
            self.assertEqual(position["current_price"], 105)
            self.assertGreater(position["unrealized_pnl"], 0)

    def test_multiple_positions_updated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            items = [pick("AAA", price=50), pick("BBB", price=100)]
            payload = daily_picks(items)
            set_mode("ai_managed", "fixture-multi-0001", root / "state", generated_at="2026-07-01T09:59:00")
            process_paper_trading(
                daily_picks=payload,
                raw_rows=raw_rows_from(items),
                output_dir=root / "out",
                state_dir=root / "state",
                generated_at="2026-07-01T10:00:00",
                market_data_service=FakeMarketDataService({
                    "AAA": quote("AAA", 50, timestamp="2026-07-01T10:00:00-04:00"),
                    "BBB": quote("BBB", 100, timestamp="2026-07-01T10:00:00-04:00"),
                }),
            )
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "AAA": quote("AAA", 51, timestamp="2026-07-02T10:00:00-04:00"),
                    "BBB": quote("BBB", 102, timestamp="2026-07-02T10:00:00-04:00"),
                }),
                generated_at="2026-07-02T10:00:00",
            )
            self.assertEqual(result["positions_updated"], 2)

    def test_quote_failure_marks_stale_and_retains_price(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir)
            root = Path(temp_dir)
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({}),
                generated_at="2026-07-02T10:00:00",
            )
            self.assertGreaterEqual(result["positions_stale"], 1)
            with open(root / "out" / "open_positions.json") as f:
                position = json.load(f)["positions"][0]
            self.assertEqual(position["current_price"], 100)
            self.assertEqual(position["price_status"], "unavailable")

    def test_stale_quote_does_not_exit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir, hold_days=1)
            root = Path(temp_dir)
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=90, status="stale", timestamp="2026-07-02T10:00:00-04:00")
                }),
                generated_at="2026-07-03T10:00:00",
            )
            self.assertEqual(result["positions_closed"], 0)
            self.assertEqual(result["open_positions"], 1)

    def test_stop_loss_closure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir, hold_days=10)
            root = Path(temp_dir)
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=94, timestamp="2026-07-02T10:00:00-04:00")
                }),
                generated_at="2026-07-02T10:00:00",
            )
            self.assertEqual(result["positions_closed"], 1)
            with open(root / "out" / "closed_trades.json") as f:
                self.assertEqual(json.load(f)["trades"][0]["exit_reason"], "stop_loss")

    def test_take_profit_closure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir, hold_days=10)
            root = Path(temp_dir)
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=111, timestamp="2026-07-02T10:00:00-04:00")
                }),
                generated_at="2026-07-02T10:00:00",
            )
            self.assertEqual(result["positions_closed"], 1)
            with open(root / "out" / "closed_trades.json") as f:
                self.assertEqual(json.load(f)["trades"][0]["exit_reason"], "take_profit")

    def test_hold_period_closure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir, hold_days=1)
            root = Path(temp_dir)
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=101, timestamp="2026-07-02T10:00:00-04:00")
                }),
                generated_at="2026-07-02T10:00:00",
            )
            self.assertEqual(result["positions_closed"], 1)
            with open(root / "out" / "closed_trades.json") as f:
                self.assertEqual(json.load(f)["trades"][0]["exit_reason"], "planned_hold_period")

    def test_repeated_refresh_idempotency(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir, hold_days=1)
            root = Path(temp_dir)
            market_data = FakeMarketDataService({
                "TEST": quote(price=101, timestamp="2026-07-02T10:00:00-04:00")
            })
            refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=market_data,
                generated_at="2026-07-02T10:00:00",
            )
            refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=market_data,
                generated_at="2026-07-02T10:00:00",
            )
            with open(root / "out" / "closed_trades.json") as f:
                self.assertEqual(len(json.load(f)["trades"]), 1)
            with open(root / "out" / "equity_curve.json") as f:
                self.assertEqual(len(json.load(f)["points"]), 2)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir)
            root = Path(temp_dir)
            state_before = (root / "state" / "open_positions_ledger.json").read_text()
            output_before = (root / "out" / "open_positions.json").read_text()
            result = refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=105, timestamp="2026-07-02T10:00:00-04:00")
                }),
                generated_at="2026-07-02T10:00:00",
                dry_run=True,
            )
            self.assertTrue(result["dry_run"])
            self.assertEqual((root / "state" / "open_positions_ledger.json").read_text(), state_before)
            self.assertEqual((root / "out" / "open_positions.json").read_text(), output_before)

    def test_output_json_regeneration_leaves_daily_picks_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = open_position_fixture(temp_dir)
            root = Path(temp_dir)
            daily_path = root / "out" / "daily_picks.json"
            daily_path.write_text(json.dumps(payload, indent=2))
            before = daily_path.read_text()
            refresh_paper_trading(
                output_dir=root / "out",
                state_dir=root / "state",
                daily_picks=payload,
                market_data_service=FakeMarketDataService({
                    "TEST": quote(price=105, timestamp="2026-07-02T10:00:00-04:00")
                }),
                generated_at="2026-07-02T10:00:00",
            )
            for name in [
                "open_positions.json",
                "closed_trades.json",
                "portfolio_summary.json",
                "equity_curve.json",
                "performance_statistics.json",
            ]:
                with open(root / "out" / name) as f:
                    json.load(f)
            self.assertEqual(daily_path.read_text(), before)

    def test_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            code = refresh_command_main([
                "--dry-run",
                "--state-dir",
                str(root / "state"),
                "--output-dir",
                str(root / "out"),
                "--daily-picks",
                str(root / "missing_daily_picks.json"),
            ])
            self.assertEqual(code, 0)

            corrupt = root / "bad_state"
            corrupt.mkdir()
            (corrupt / "account_state.json").write_text("{bad json")
            code = refresh_command_main([
                "--state-dir",
                str(corrupt),
                "--output-dir",
                str(root / "out"),
            ])
            self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
