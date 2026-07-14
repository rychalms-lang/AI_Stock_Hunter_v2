import json
import tempfile
import unittest
from pathlib import Path

from market_data_service import MarketDataProvider, MarketDataService, MarketQuote
from refresh_market_snapshot import build_market_snapshot, collect_tickers, overall_quote_status


def fake_quote(ticker: str, status: str = "DELAYED", price: float | None = 100.0) -> MarketQuote:
    return MarketQuote(
        ticker=ticker,
        current_price=price,
        previous_close=99.0 if price else None,
        price_change=1.0 if price else None,
        price_change_pct=1.01 if price else None,
        bid=None,
        ask=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        quote_timestamp="2026-07-10T10:00:00-04:00",
        provider_timestamp="2026-07-10T09:59:00-04:00",
        market_state="OPEN",
        source="fake",
        delay_seconds=60 if status == "DELAYED" else None,
        price_age_seconds=60,
        price_status=status,
        error="bad ticker" if status == "UNAVAILABLE" else None,
    )


class FakeProvider(MarketDataProvider):
    name = "fake"

    def __init__(self, quotes, state="OPEN"):
        self.quotes = quotes
        self.state = state
        self.calls = {}

    def get_market_state(self, now=None):
        return self.state

    def get_quote(self, ticker):
        normalized = ticker.upper()
        self.calls[normalized] = self.calls.get(normalized, 0) + 1
        return self.quotes.get(normalized, fake_quote(normalized, "UNAVAILABLE", None))


class MarketSnapshotTest(unittest.TestCase):
    def test_service_reuses_cache_once_per_ticker(self):
        provider = FakeProvider({"HIMS": fake_quote("HIMS")})
        service = MarketDataService(provider)
        service.get_quote("hims")
        service.get_quote("HIMS")
        self.assertEqual(provider.calls["HIMS"], 1)

    def test_overall_quote_status(self):
        self.assertEqual(overall_quote_status({"A": {"price_status": "LIVE"}}, "OPEN"), "LIVE")
        self.assertEqual(overall_quote_status({"A": {"price_status": "DELAYED"}}, "OPEN"), "DELAYED")
        self.assertEqual(overall_quote_status({"A": {"price_status": "STALE"}}, "OPEN"), "STALE")
        self.assertEqual(overall_quote_status({"A": {"price_status": "UNAVAILABLE"}}, "OPEN"), "UNAVAILABLE")
        self.assertEqual(
            overall_quote_status({"A": {"price_status": "MARKET_CLOSED"}}, "CLOSED"),
            "MARKET_CLOSED",
        )

    def test_collect_tickers_from_all_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper_dir = root / "paper"
            state_dir = paper_dir / "state"
            state_dir.mkdir(parents=True)
            (paper_dir / "open_positions.json").write_text(json.dumps({
                "positions": [{"ticker": "OPEN"}],
            }))
            (paper_dir / "daily_picks.json").write_text(json.dumps({
                "picks": [{"ticker": "PICK"}],
            }))
            (state_dir / "pending_proposals.json").write_text(json.dumps({
                "proposals": [{"ticker": "PROP", "status": "pending"}],
            }))
            tickers = collect_tickers(paper_dir, state_dir, include_benchmarks=False)
            self.assertEqual(tickers, {"OPEN", "PICK", "PROP"})

    def test_build_snapshot_records_partial_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper_dir = root / "paper"
            state_dir = paper_dir / "state"
            state_dir.mkdir(parents=True)
            (paper_dir / "daily_picks.json").write_text(json.dumps({
                "picks": [{"ticker": "GOOD"}, {"ticker": "BAD"}],
            }))

            service = MarketDataService(FakeProvider({
                "GOOD": fake_quote("GOOD", "DELAYED", 100),
                "BAD": fake_quote("BAD", "UNAVAILABLE", None),
            }))
            payload = build_market_snapshot(
                market_data_service=service,
                paper_dir=paper_dir,
                state_dir=state_dir,
                include_benchmarks=False,
                generated_at="2026-07-10T10:00:00-04:00",
            )
            self.assertEqual(payload["provider"], "fake")
            self.assertEqual(payload["quote_status"], "STALE")
            self.assertEqual(payload["tickers_requested"], ["BAD", "GOOD"])
            self.assertEqual(len(payload["errors"]), 1)
            self.assertEqual(service.provider.calls["GOOD"], 1)
            self.assertEqual(service.provider.calls["BAD"], 1)

    def test_snapshot_records_five_minute_batch_metadata(self):
        service = MarketDataService(FakeProvider({"GOOD": fake_quote("GOOD", "DELAYED", 100)}))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper_dir = root / "paper"
            state_dir = paper_dir / "state"
            state_dir.mkdir(parents=True)
            (paper_dir / "daily_picks.json").write_text(json.dumps({"picks": [{"ticker": "GOOD"}]}))
            payload = build_market_snapshot(
                market_data_service=service,
                paper_dir=paper_dir,
                state_dir=state_dir,
                include_benchmarks=False,
                generated_at="2026-07-10T10:05:00-04:00",
            )
        self.assertEqual(payload["refresh_cadence_seconds"], 300)
        self.assertEqual(payload["valuation_generated_at"], "2026-07-10T10:05:00-04:00")
        self.assertTrue(payload["valuation_batch_id"].startswith("valuation_"))
        self.assertEqual(payload["tickers_stale"], 0)


if __name__ == "__main__":
    unittest.main()
