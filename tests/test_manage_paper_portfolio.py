import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from manage_paper_portfolio import PortfolioCommandError, add_user_directed_position
from tests.test_paper_trading_engine import FakeMarketDataService, daily_picks, pick, quote


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(payload, f)


def web_snapshot_for(ticker="TEST", action="BUY"):
    return {
        "generated_at": "2026-07-01T10:00:00",
        "source_file": "reports/test_v2.csv",
        "market_regime": {"label": "Risk-On", "score": 80},
        "top_opportunity": {
            "ticker": ticker,
            "sector": "Software",
            "score": 80,
            "confidence": 90,
            "expected_return": 4,
            "best_hold_period_days": 5,
            "historical_matches": 120,
            "risk": "Low",
            "action": action,
            "reason": "Test.",
        },
        "portfolio_summary": {},
        "today_actions": [],
        "ranked_candidates": [
            {
                "ticker": ticker,
                "sector": "Software",
                "score": 80,
                "confidence": 90,
                "expected_return": 4,
                "best_hold_period_days": 5,
                "historical_matches": 120,
                "risk": "Low",
                "action": action,
                "reason": "Test.",
            }
        ],
    }


class ManagePaperPortfolioTest(unittest.TestCase):
    def setup_files(self, temp_dir, item):
        root = Path(temp_dir)
        daily_path = root / "daily_picks.json"
        snapshot_path = root / "web_snapshot.json"
        write_json(daily_path, daily_picks([item]))
        write_json(snapshot_path, web_snapshot_for(item["ticker"], "BUY"))
        return root, daily_path, snapshot_path

    def run_add(self, temp_dir, item, **kwargs):
        root, daily_path, snapshot_path = self.setup_files(temp_dir, item)
        market_data = kwargs.pop(
            "market_data_service",
            FakeMarketDataService({item["ticker"]: quote(item["ticker"], item["latest_close"])}),
        )
        return add_user_directed_position(
            ticker=item["ticker"],
            amount=kwargs.pop("amount", 1000),
            source_pick_id=item["pick_id"],
            note=kwargs.pop("note", "Test note"),
            request_id=kwargs.pop("request_id", "test-request-0001"),
            acknowledge_override=kwargs.pop("acknowledge_override", False),
            dry_run=kwargs.pop("dry_run", False),
            state_dir=root / "state",
            output_dir=root / "out",
            daily_picks_path=daily_path,
            web_snapshot_path=snapshot_path,
            generated_at=kwargs.pop("generated_at", "2026-07-01T10:00:00"),
            market_data_service=market_data,
        )

    def test_adds_user_directed_position_and_exports_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("MANUAL", "BUY", 100)
            result = self.run_add(temp_dir, item)

            self.assertTrue(result["ok"])
            self.assertEqual(result["origin"], "user_directed")
            self.assertEqual(result["position"]["quantity"], 10)

            open_positions_path = Path(temp_dir) / "out" / "open_positions.json"
            with open_positions_path.open() as f:
                exported = json.load(f)
            position = exported["positions"][0]
            self.assertEqual(position["origin"], "user_directed")
            self.assertEqual(position["scanner_action"], "BUY")
            self.assertEqual(position["research_rating"], "BUY")
            self.assertEqual(position["automatic_paper_eligibility"], "Eligible")

    def test_writes_audit_log_for_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("AUDIT", "BUY", 100)
            self.run_add(temp_dir, item)
            with open(Path(temp_dir) / "state" / "user_actions.json") as f:
                audit = json.load(f)

            user_actions = [
                action for action in audit["actions"]
                if action.get("type") == "add_user_directed_position"
            ]
            self.assertEqual(len(user_actions), 1)
            self.assertEqual(user_actions[0]["result"], "success")
            self.assertEqual(user_actions[0]["origin"], "user_directed")

    def test_request_id_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("IDEMP", "BUY", 100)
            first = self.run_add(temp_dir, item, request_id="idem-request-001")
            second = self.run_add(temp_dir, item, request_id="idem-request-001")

            self.assertTrue(first["ok"])
            self.assertTrue(second["idempotent"])
            with open(Path(temp_dir) / "state" / "open_positions_ledger.json") as f:
                ledger = json.load(f)
            self.assertEqual(len(ledger["positions"]), 1)

    def test_duplicate_open_ticker_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("DUPL", "BUY", 100)
            self.run_add(temp_dir, item, request_id="dupl-request-001")
            with self.assertRaises(PortfolioCommandError) as context:
                self.run_add(temp_dir, item, request_id="dupl-request-002")
            self.assertEqual(context.exception.code, "duplicate_open_ticker")

    def test_watch_requires_explicit_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("WATCHX", "WATCH", 50)
            item["paper_trade_decision"] = "skipped_not_buy"
            item["paper_trade_candidate"] = False

            with self.assertRaises(PortfolioCommandError) as context:
                self.run_add(temp_dir, item)

            self.assertEqual(context.exception.code, "override_required")

    def test_watch_can_be_user_directed_with_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("OVERRIDE", "WATCH", 50)
            item["paper_trade_decision"] = "skipped_not_buy"
            item["paper_trade_candidate"] = False
            result = self.run_add(temp_dir, item, acknowledge_override=True)

            self.assertEqual(result["scanner_action"], "WATCH")
            self.assertEqual(result["automatic_paper_eligibility"], "Not eligible")

    def test_stale_quote_rejected_without_position(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("STALE", "BUY", 100)
            stale_service = FakeMarketDataService({
                "STALE": quote("STALE", 100, status="stale")
            })

            with self.assertRaises(PortfolioCommandError) as context:
                self.run_add(temp_dir, item, market_data_service=stale_service)

            self.assertEqual(context.exception.code, "price_unavailable")
            self.assertFalse((Path(temp_dir) / "state" / "open_positions_ledger.json").exists())

    def test_unavailable_quote_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("NOQUOTE", "BUY", 100)
            service = FakeMarketDataService({"NOQUOTE": quote("NOQUOTE", None, status="unavailable")})

            with self.assertRaises(PortfolioCommandError) as context:
                self.run_add(temp_dir, item, market_data_service=service)

            self.assertEqual(context.exception.code, "price_unavailable")

    def test_invalid_ticker_blocks_command_injection_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("SAFE", "BUY", 100)
            root, daily_path, snapshot_path = self.setup_files(temp_dir, item)
            with self.assertRaises(PortfolioCommandError) as context:
                add_user_directed_position(
                    ticker="SAFE;rm -rf /",
                    amount=1000,
                    source_pick_id=item["pick_id"],
                    request_id="safe-request-001",
                    state_dir=root / "state",
                    output_dir=root / "out",
                    daily_picks_path=daily_path,
                    web_snapshot_path=snapshot_path,
                    market_data_service=FakeMarketDataService(),
                )
            self.assertEqual(context.exception.code, "invalid_ticker")

    def test_whole_share_sizing_preserves_cash_reserve(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("RESERVE", "BUY", 100)
            result = self.run_add(temp_dir, item, amount=50000)

            self.assertEqual(result["position"]["executed_dollar_amount"], 5000)
            self.assertGreaterEqual(result["portfolio"]["cash"], 20000)

    def test_amount_too_small_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("SMALL", "BUY", 100)

            with self.assertRaises(PortfolioCommandError) as context:
                self.run_add(temp_dir, item, amount=10)

            self.assertEqual(context.exception.code, "insufficient_cash")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("DRYRUN", "BUY", 100)
            result = self.run_add(temp_dir, item, dry_run=True)

            self.assertTrue(result["dry_run"])
            self.assertFalse((Path(temp_dir) / "state" / "open_positions_ledger.json").exists())
            self.assertFalse((Path(temp_dir) / "out" / "open_positions.json").exists())

    def test_cli_returns_structured_json_on_validation_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            item = pick("CLI", "BUY", 100)
            root, daily_path, snapshot_path = self.setup_files(temp_dir, item)
            result = subprocess.run(
                [
                    sys.executable,
                    "manage_paper_portfolio.py",
                    "add",
                    "--ticker",
                    "CLI",
                    "--amount",
                    "1000",
                    "--source-pick-id",
                    item["pick_id"],
                    "--request-id",
                    "bad",
                    "--dry-run",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "out"),
                    "--daily-picks",
                    str(daily_path),
                    "--web-snapshot",
                    str(snapshot_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "invalid_request_id")


if __name__ == "__main__":
    unittest.main()
