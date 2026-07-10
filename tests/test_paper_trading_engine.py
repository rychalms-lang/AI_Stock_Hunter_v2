import json
import tempfile
import unittest
from pathlib import Path

from market_data_service import market_state
from paper_trading_engine import (
    DEFAULT_CONFIG,
    PaperTradingStateError,
    PaperTradingStore,
    max_drawdown,
    process_paper_trading,
)


class FakeMarketDataService:
    def __init__(self, quotes=None, state="OPEN"):
        self.quotes = quotes or {}
        self.state = state
        self.calls = {}

    def get_market_state(self):
        return self.state

    def get_quote(self, ticker):
        normalized = ticker.upper()
        self.calls[normalized] = self.calls.get(normalized, 0) + 1
        return self.quotes.get(
            normalized,
            {
                "ticker": normalized,
                "price": None,
                "previous_close": None,
                "price_change_today": None,
                "market_state": self.state,
                "last_price_update": "2026-07-01T10:00:00-04:00",
                "price_source": "fake",
                "price_status": "unavailable",
            },
        )


def quote(ticker="TEST", price=100.0, status="fresh", timestamp="2026-07-01T10:00:00-04:00"):
    return {
        "ticker": ticker,
        "price": price,
        "previous_close": price - 1 if price else None,
        "price_change_today": 1.0 if price else None,
        "market_state": "OPEN",
        "last_price_update": timestamp,
        "price_source": "fake",
        "price_status": status,
    }


def pick(
    ticker="TEST",
    action="BUY",
    price=100.0,
    trade_date="2026-07-01",
    hold_days=5,
):
    return {
        "pick_id": f"{trade_date}_{ticker}",
        "trade_date": trade_date,
        "ticker": ticker,
        "sector": "Software",
        "sector_rank": 1,
        "rank": 1,
        "action": action,
        "score": 80.0,
        "confidence": 90.0,
        "risk": "Low",
        "expected_return_pct": 4.0,
        "win_probability_pct": 65.0,
        "best_hold_period_days": hold_days,
        "historical_matches": 120,
        "historical_best_avg_return_pct": 4.0,
        "latest_open": price,
        "latest_close": price,
        "five_day_change_pct": 1.0,
        "twenty_day_change_pct": 2.0,
        "relative_strength_pct": 1.5,
        "volume_ratio": 1.2,
        "paper_trade_candidate": True,
        "paper_trade_decision": "eligible_scanner_export",
        "paper_trade_decision_reason": "Test pick.",
        "strategy": {"name": "V8", "version": "8.0", "status": "Champion"},
        "research_metadata": {
            "scanner_version": "current",
            "strategy_version": "V8",
            "feature_version": "current",
            "market_regime_version": "current",
            "generated_from": "daily_scanner",
        },
        "ai_explanation": {
            "summary": "Test evidence.",
            "strengths": ["High confidence."],
            "risks": [],
            "similar_historical_cases": [],
        },
    }


def daily_picks(picks, trade_date="2026-07-01"):
    return {
        "schema_version": "1.0",
        "generated_at": f"{trade_date}T10:00:00",
        "source_file": "reports/test_v2.csv",
        "trade_date": trade_date,
        "mock_data": False,
        "market_regime": {"label": "Risk-On", "score": 80, "description": "Test"},
        "picks": picks,
        "disclaimer": "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice.",
    }


def raw_rows_from(picks, action="BUY"):
    rows = []
    for item in picks:
        rows.append({
            "ticker": item["ticker"],
            "action": action,
            "sector": item["sector"],
            "confidence_score": str(item["confidence"]),
            "confidence": str(item["confidence"]),
            "score": str(item["score"]),
            "risk": item["risk"],
        })
    return rows


class PaperTradingEngineTest(unittest.TestCase):
    def market_data_from_payload(self, payload, status="fresh", timestamp=None):
        return FakeMarketDataService({
            item["ticker"]: quote(
                ticker=item["ticker"],
                price=item["latest_close"],
                status=status,
                timestamp=timestamp or f"{payload['trade_date']}T10:00:00-04:00",
            )
            for item in payload["picks"]
        })

    def run_engine(
        self,
        payload,
        rows,
        temp_dir,
        config=None,
        generated_at=None,
        market_data_service=None,
    ):
        root = Path(temp_dir)
        return process_paper_trading(
            daily_picks=payload,
            raw_rows=rows,
            output_dir=root / "out",
            state_dir=root / "state",
            config=config,
            generated_at=generated_at or payload["generated_at"],
            market_data_service=market_data_service or self.market_data_from_payload(payload),
        )

    def test_first_run_opens_buy_and_writes_json_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick()
            result = self.run_engine(daily_picks([item]), raw_rows_from([item]), temp_dir)

            self.assertEqual(result["open_positions"], 1)
            for name in [
                "open_positions.json",
                "closed_trades.json",
                "portfolio_summary.json",
                "equity_curve.json",
                "performance_statistics.json",
            ]:
                with open(Path(temp_dir) / "out" / name) as f:
                    json.load(f)

    def test_rerun_same_pick_does_not_duplicate_position(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick()
            payload = daily_picks([item])
            rows = raw_rows_from([item])
            self.run_engine(payload, rows, temp_dir)
            result = self.run_engine(payload, rows, temp_dir)
            self.assertEqual(result["open_positions"], 1)

    def test_only_buy_opens_position(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            items = [
                pick("BUYME", "BUY", 100),
                pick("WATCHME", "WATCH", 50),
                pick("HOLDME", "HOLD", 40),
                pick("AVOIDME", "AVOID", 30),
            ]
            rows = [
                {"ticker": "BUYME", "action": "BUY", "sector": "Software", "confidence_score": "90", "score": "80", "risk": "Low"},
                {"ticker": "WATCHME", "action": "WATCH", "sector": "Software", "confidence_score": "90", "score": "80", "risk": "Low"},
                {"ticker": "HOLDME", "action": "HOLD", "sector": "Software", "confidence_score": "90", "score": "80", "risk": "Low"},
                {"ticker": "AVOIDME", "action": "AVOID", "sector": "Software", "confidence_score": "90", "score": "80", "risk": "Low"},
            ]
            result = self.run_engine(daily_picks(items), rows, temp_dir)
            self.assertEqual(result["open_positions"], 1)

    def test_raw_action_is_authoritative_when_exported_action_differs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("MISMATCH", action="BUY", price=100)
            result = self.run_engine(
                daily_picks([item]),
                raw_rows_from([item], action="WATCH"),
                temp_dir,
            )
            self.assertEqual(result["open_positions"], 0)
            with open(Path(temp_dir) / "state" / "processed_picks.json") as f:
                processed = json.load(f)["picks"][item["pick_id"]]
            self.assertEqual(processed["status"], "skipped_not_buy")
            self.assertEqual(processed["action"], "WATCH")

    def test_watch_never_opens_even_with_promotional_display_label(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("PROMO", action="BUY", price=100)
            item["paper_trade_decision"] = "eligible_scanner_export"
            item["paper_trade_decision_reason"] = "Promotional frontend label only."
            result = self.run_engine(
                daily_picks([item]),
                raw_rows_from([item], action="WATCH"),
                temp_dir,
                generated_at="2026-07-01T11:00:00",
            )
            self.assertEqual(result["open_positions"], 0)

    def test_insufficient_cash_blocks_trade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick(price=100000)
            result = self.run_engine(daily_picks([item]), raw_rows_from([item]), temp_dir)
            self.assertEqual(result["open_positions"], 0)

    def test_stale_report_price_blocks_new_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick(price=100, trade_date="2026-07-01")
            payload = daily_picks([item], "2026-07-01")
            result = self.run_engine(
                payload,
                raw_rows_from([item]),
                temp_dir,
                generated_at="2026-07-10T10:00:00",
                market_data_service=self.market_data_from_payload(
                    payload,
                    status="stale",
                    timestamp="2026-07-01T16:00:00-04:00",
                ),
            )
            self.assertEqual(result["open_positions"], 0)
            self.assertEqual(result["price_data_status"], "waiting_for_fresh_market_prices")
            with open(Path(temp_dir) / "state" / "processed_picks.json") as f:
                processed = json.load(f)["picks"][item["pick_id"]]
            self.assertEqual(processed["status"], "skipped_stale_price")

    def test_hold_period_exit_and_realized_pnl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = pick(price=100, hold_days=1)
            self.run_engine(daily_picks([first], "2026-07-01"), raw_rows_from([first]), temp_dir)
            second = pick(price=104, trade_date="2026-07-02", hold_days=1)
            result = self.run_engine(
                daily_picks([second], "2026-07-02"),
                raw_rows_from([second]),
                temp_dir,
                generated_at="2026-07-02T10:00:00",
            )
            self.assertEqual(result["closed_trades"], 1)
            with open(Path(temp_dir) / "out" / "closed_trades.json") as f:
                trade = json.load(f)["trades"][0]
            self.assertEqual(trade["exit_reason"], "planned_hold_period")
            self.assertGreater(trade["realized_pnl"], 0)

    def test_cash_reconciles_after_exit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = pick(price=100, hold_days=1)
            self.run_engine(daily_picks([first], "2026-07-01"), raw_rows_from([first]), temp_dir)
            second = pick(price=104, trade_date="2026-07-02", hold_days=1)
            self.run_engine(
                daily_picks([second], "2026-07-02"),
                raw_rows_from([second], action="WATCH"),
                temp_dir,
            )
            with open(Path(temp_dir) / "out" / "portfolio_summary.json") as f:
                summary = json.load(f)["summary"]
            with open(Path(temp_dir) / "out" / "closed_trades.json") as f:
                trade = json.load(f)["trades"][0]
            expected_cash = round(25000 - trade["cost_basis"] + trade["proceeds"], 2)
            self.assertEqual(summary["cash"], expected_cash)
            self.assertEqual(summary["total_equity"], summary["cash"] + summary["invested_value"])

    def test_stop_loss_exit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = pick(price=100, hold_days=10)
            self.run_engine(daily_picks([first], "2026-07-01"), raw_rows_from([first]), temp_dir)
            second = pick(price=94, trade_date="2026-07-02", hold_days=10)
            result = self.run_engine(daily_picks([second], "2026-07-02"), raw_rows_from([second]), temp_dir)
            self.assertEqual(result["closed_trades"], 1)
            with open(Path(temp_dir) / "out" / "closed_trades.json") as f:
                self.assertEqual(json.load(f)["trades"][0]["exit_reason"], "stop_loss")

    def test_take_profit_exit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = pick(price=100, hold_days=10)
            self.run_engine(daily_picks([first], "2026-07-01"), raw_rows_from([first]), temp_dir)
            second = pick(price=111, trade_date="2026-07-02", hold_days=10)
            result = self.run_engine(daily_picks([second], "2026-07-02"), raw_rows_from([second]), temp_dir)
            self.assertEqual(result["closed_trades"], 1)
            with open(Path(temp_dir) / "out" / "closed_trades.json") as f:
                self.assertEqual(json.load(f)["trades"][0]["exit_reason"], "take_profit")

    def test_unrealized_pnl_and_equity_curve_update(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = pick(price=100, hold_days=10)
            self.run_engine(daily_picks([first], "2026-07-01"), raw_rows_from([first]), temp_dir)
            second = pick(price=102, trade_date="2026-07-02", hold_days=10)
            self.run_engine(daily_picks([second], "2026-07-02"), raw_rows_from([second]), temp_dir)
            with open(Path(temp_dir) / "out" / "open_positions.json") as f:
                position = json.load(f)["positions"][0]
            with open(Path(temp_dir) / "out" / "equity_curve.json") as f:
                points = json.load(f)["points"]
            self.assertGreater(position["unrealized_pnl"], 0)
            self.assertEqual(len(points), 2)

    def test_repeated_stale_runs_do_not_duplicate_equity_points(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick(price=100, trade_date="2026-07-01")
            payload = daily_picks([item], "2026-07-01")
            rows = raw_rows_from([item])
            market_data = self.market_data_from_payload(
                payload,
                status="stale",
                timestamp="2026-07-01T16:00:00-04:00",
            )
            self.run_engine(
                payload,
                rows,
                temp_dir,
                generated_at="2026-07-10T10:00:00",
                market_data_service=market_data,
            )
            self.run_engine(
                payload,
                rows,
                temp_dir,
                generated_at="2026-07-11T10:00:00",
                market_data_service=market_data,
            )
            with open(Path(temp_dir) / "out" / "equity_curve.json") as f:
                points = json.load(f)["points"]
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]["price_data_status"], "waiting_for_fresh_market_prices")

    def test_stale_prices_do_not_trigger_exits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = pick(price=100, hold_days=1)
            self.run_engine(daily_picks([first], "2026-07-01"), raw_rows_from([first]), temp_dir)
            stale_stop = pick(price=94, trade_date="2026-07-02", hold_days=1)
            payload = daily_picks([stale_stop], "2026-07-02")
            result = self.run_engine(
                payload,
                raw_rows_from([stale_stop]),
                temp_dir,
                generated_at="2026-07-10T10:00:00",
                market_data_service=self.market_data_from_payload(
                    payload,
                    status="stale",
                    timestamp="2026-07-02T16:00:00-04:00",
                ),
            )
            self.assertEqual(result["closed_trades"], 0)
            self.assertEqual(result["open_positions"], 1)
            with open(Path(temp_dir) / "out" / "open_positions.json") as f:
                position = json.load(f)["positions"][0]
            self.assertEqual(position["status"], "stale_price_data")
            self.assertEqual(position["current_price"], 100)
            self.assertEqual(position["days_held"], 0)

    def test_market_data_service_is_cached_during_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick(price=100, hold_days=10)
            payload = daily_picks([item], "2026-07-01")
            market_data = self.market_data_from_payload(payload)
            self.run_engine(payload, raw_rows_from([item]), temp_dir, market_data_service=market_data)
            self.run_engine(payload, raw_rows_from([item]), temp_dir, market_data_service=market_data)
            self.assertLessEqual(market_data.calls["TEST"], 2)

    def test_max_drawdown_calculation(self):
        points = [
            {"total_equity": 25000},
            {"total_equity": 26000},
            {"total_equity": 24700},
        ]
        self.assertEqual(max_drawdown(points), -5.0)

    def test_corrupt_state_fails_safely(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            state_dir.mkdir()
            (state_dir / "account_state.json").write_text("{bad json")
            store = PaperTradingStore(state_dir)
            with self.assertRaises(PaperTradingStateError):
                store.load()

    def test_minimum_cash_reserve_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            items = [pick(f"T{i}", price=10) for i in range(1, 8)]
            result = self.run_engine(
                daily_picks(items),
                raw_rows_from(items),
                temp_dir,
                config={**DEFAULT_CONFIG, "max_positions": 7, "max_position_pct": 20.0},
            )
            with open(Path(temp_dir) / "out" / "portfolio_summary.json") as f:
                summary = json.load(f)["summary"]
            self.assertGreaterEqual(summary["cash"], 2500)
            self.assertLessEqual(result["open_positions"], 7)

    def test_market_state_helper_classifies_closed_weekend(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        state = market_state(datetime(2026, 7, 11, 12, 0, tzinfo=ZoneInfo("America/New_York")))
        self.assertEqual(state, "CLOSED")


if __name__ == "__main__":
    unittest.main()
