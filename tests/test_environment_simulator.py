from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from environment_simulator import (
    load_trade_stream,
    run_comparison,
    run_environment_simulation,
    run_sensitivity,
    save_simulation_result,
)
from strategy_lab_exporter import run_strategy_lab_request
from trading_environment import environment_from_overrides, validate_environment


class EnvironmentSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stream = self.root / "trades.csv"
        self.write_stream(
            [
                ["V8_CHAMPION", "2024-01-02", "2024-01-04", "AAA", "Software", 100, 110, 10, 10, 1],
                ["V8_CHAMPION", "2024-01-02", "2024-01-05", "BBB", "Health", 100, 95, -5, -5, 1],
                ["V8_CHAMPION", "2024-01-03", "2024-01-09", "CCC", "Software", 100, 120, 20, 20, 1],
                ["V9_DEFENSIVE", "2024-01-02", "2024-01-04", "DDD", "Software", 100, 101, 1, 1, 1],
            ]
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_stream(self, rows: list[list[object]]) -> None:
        with self.stream.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["strategy", "entry_date", "exit_date", "ticker", "sector", "entry_value", "exit_value", "return_pct", "raw_return_pct", "weight"])
            writer.writerows(rows)

    def run_sim(self, env=None, strategy="V8"):
        return run_environment_simulation(environment=env, strategy=strategy, trade_stream_path=self.stream)

    def test_loads_only_selected_strategy(self):
        self.assertEqual(len(load_trade_stream(self.stream, "V8")), 3)

    def test_v9_stream_is_experimental_available(self):
        result = self.run_sim(strategy="V9")
        self.assertEqual(result["strategy"]["status"], "Experimental")

    def test_v8_is_champion(self):
        self.assertEqual(self.run_sim()["strategy"]["status"], "Champion")

    def test_simulation_does_not_mutate_trade_stream(self):
        before = self.stream.read_text()
        self.run_sim()
        self.assertEqual(before, self.stream.read_text())

    def test_records_disclaimer(self):
        self.assertIn("does not modify V8", self.run_sim()["disclaimer"])

    def test_environment_validation_rejects_negative_capital(self):
        errors, _ = validate_environment(environment_from_overrides({"account_rules": {"starting_capital": -1}}))
        self.assertTrue(errors)

    def test_cash_account_blocks_over_allocation(self):
        result = self.run_sim({"account_rules": {"starting_capital": 1000, "maximum_position_allocation_pct": 90, "minimum_cash_reserve_pct": 10, "maximum_open_positions": 1}})
        self.assertGreater(result["metrics"]["missed_opportunities"], 0)

    def test_max_open_positions_blocks_extra_entries(self):
        result = self.run_sim({"account_rules": {"maximum_open_positions": 1}})
        reasons = {miss["reason"] for miss in result["missed_opportunities"]}
        self.assertIn("max_open_positions", reasons)

    def test_daily_entry_limit_blocks_entries(self):
        result = self.run_sim({"trading_restrictions": {"maximum_new_positions_per_day": 1}})
        self.assertIn("daily_entry_limit", {miss["reason"] for miss in result["missed_opportunities"]})

    def test_restricted_ticker_blocks_entry(self):
        result = self.run_sim({"trading_restrictions": {"restricted_tickers": ["AAA"]}})
        self.assertIn("restricted_ticker", {miss["reason"] for miss in result["missed_opportunities"]})

    def test_no_overnight_blocks_overnight_stream(self):
        result = self.run_sim({"trading_restrictions": {"overnight_holding_allowed": False, "forced_end_of_day_liquidation": False}})
        self.assertEqual(result["metrics"]["trades_taken"], 0)

    def test_forced_end_of_day_conflict_rejected(self):
        with self.assertRaises(ValueError):
            self.run_sim({"trading_restrictions": {"overnight_holding_allowed": True, "forced_end_of_day_liquidation": True}})

    def test_no_weekend_blocks_weekend_hold(self):
        result = self.run_sim({"trading_restrictions": {"weekend_holding_allowed": False}})
        self.assertIn("weekend_not_allowed", {miss["reason"] for miss in result["missed_opportunities"]})

    def test_sector_exposure_blocks_sector_concentration(self):
        result = self.run_sim({"risk_limits": {"maximum_sector_exposure_pct": 10}})
        self.assertGreater(result["metrics"]["missed_opportunities"], 0)

    def test_cash_reserve_is_respected(self):
        result = self.run_sim({"account_rules": {"starting_capital": 1000, "minimum_cash_reserve_pct": 50, "maximum_position_allocation_pct": 60}})
        self.assertGreaterEqual(result["accounting"]["cash"], 0)

    def test_transaction_fee_reduces_profit(self):
        no_fee = self.run_sim()
        fee = self.run_sim({"account_rules": {"fixed_transaction_fee": 10}})
        self.assertLess(fee["metrics"]["ending_equity"], no_fee["metrics"]["ending_equity"])

    def test_slippage_reduces_profit(self):
        low = self.run_sim({"account_rules": {"slippage_pct": 0}})
        high = self.run_sim({"account_rules": {"slippage_pct": 5}})
        self.assertLess(high["metrics"]["ending_equity"], low["metrics"]["ending_equity"])

    def test_take_profit_caps_returns(self):
        uncapped = self.run_sim({"account_rules": {"slippage_pct": 0}})
        capped = self.run_sim({"account_rules": {"slippage_pct": 0}, "execution_overrides": {"take_profit_override_pct": 2}})
        self.assertLess(capped["metrics"]["ending_equity"], uncapped["metrics"]["ending_equity"])

    def test_stop_loss_caps_losses(self):
        result = self.run_sim({"account_rules": {"slippage_pct": 0}, "execution_overrides": {"stop_loss_override_pct": 1}})
        self.assertTrue(any(trade["return_pct"] >= -1.1 for trade in result["closed_trades"]))

    def test_daily_loss_violation_can_fail(self):
        result = self.run_sim({"risk_limits": {"daily_loss_limit_pct": 0.01}})
        self.assertTrue(any(v["rule"] == "daily_loss_limit" for v in result["violations"]))

    def test_drawdown_violation_can_fail(self):
        result = self.run_sim({"risk_limits": {"overall_max_drawdown_pct": 0.01}})
        self.assertTrue(any(rule["rule"] == "overall_drawdown" for rule in result["rule_results"]))

    def test_trailing_drawdown_violation_can_fail(self):
        result = self.run_sim({"risk_limits": {"trailing_drawdown_amount": 1}})
        self.assertTrue(any(rule["rule"] == "trailing_drawdown" for rule in result["rule_results"]))

    def test_profit_target_progress_is_reported(self):
        self.assertIn("target_progress_pct", self.run_sim()["metrics"])

    def test_equity_curve_is_chronological(self):
        dates = [point["date"] for point in self.run_sim()["equity_curve"]]
        self.assertEqual(dates, sorted(dates))

    def test_timeline_contains_entries_and_exits(self):
        types = {event["type"] for event in self.run_sim()["timeline"]}
        self.assertIn("entry", types)
        self.assertIn("exit", types)

    def test_missed_opportunities_include_source_rows(self):
        result = self.run_sim({"account_rules": {"maximum_open_positions": 1}})
        self.assertTrue(all("source_row" in miss for miss in result["missed_opportunities"]))

    def test_result_is_json_serializable(self):
        json.dumps(self.run_sim())

    def test_save_result_is_atomic_enough_for_latest(self):
        result = self.run_sim()
        path = save_simulation_result(result, self.root / "out")
        self.assertTrue(path.exists())
        self.assertTrue((self.root / "out" / "latest_result.json").exists())

    def test_comparison_returns_multiple_environments(self):
        result = run_comparison(["personal_cash_account", "conservative_swing_account"], trade_stream_path=self.stream)
        self.assertEqual(result["mode"], "environment_comparison")
        self.assertEqual(len(result["results"]), 2)

    def test_sensitivity_returns_all_values(self):
        result = run_sensitivity(environment_from_overrides(), "risk_limits.daily_loss_limit_pct", [1, 2, 3], trade_stream_path=self.stream)
        self.assertEqual(len(result["results"]), 3)

    def test_exporter_request_historical_replay(self):
        result = run_strategy_lab_request({"mode": "historical_replay", "preset_id": "personal_cash_account"}, persist=False)
        self.assertEqual(result["mode"], "historical_replay")

    def test_exporter_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            run_strategy_lab_request({"mode": "danger"}, persist=False)

    def test_exporter_rejects_unknown_trade_stream(self):
        with self.assertRaises(ValueError):
            run_strategy_lab_request({"trade_stream": "../bad"}, persist=False)

    def test_missing_trade_stream_raises(self):
        with self.assertRaises(FileNotFoundError):
            run_environment_simulation(trade_stream_path=self.root / "missing.csv")

    def test_header_validation_rejects_bad_stream(self):
        bad = self.root / "bad.csv"
        bad.write_text("ticker,return_pct\nAAA,1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_trade_stream(bad, "V8")

    def test_pass_fail_is_structured(self):
        self.assertIn(self.run_sim()["pass_fail"], {"passed", "failed", "in_progress"})


if __name__ == "__main__":
    unittest.main()
