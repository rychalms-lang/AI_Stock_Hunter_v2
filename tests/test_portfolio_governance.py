import json
import tempfile
import unittest
from pathlib import Path

from manage_paper_portfolio import PortfolioCommandError, add_user_directed_position
from manage_portfolio_governance import (
    GovernanceError,
    approve_open_position_proposal,
    reject_proposal,
)
from paper_trading_engine import process_paper_trading
from portfolio_governance import (
    governance_summary,
    load_governance,
    load_proposals,
    set_mode,
)
from system_status_exporter import build_status
from tests.test_paper_trading_engine import FakeMarketDataService, daily_picks, pick, quote, raw_rows_from


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(payload, f)


def write_web_snapshot(path: Path, ticker="TEST", action="BUY"):
    write_json(path, {
        "generated_at": "2026-07-01T10:00:00",
        "source_file": "reports/test_v2.csv",
        "market_regime": {"label": "Risk-On", "score": 80},
        "top_opportunity": {},
        "portfolio_summary": {},
        "today_actions": [],
        "ranked_candidates": [{
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
        }],
    })


class PortfolioGovernanceTest(unittest.TestCase):
    def test_missing_governance_defaults_to_ai_assisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state = load_governance(Path(temp_dir))
            self.assertEqual(state["mode"], "ai_assisted")
            self.assertFalse(governance_summary(Path(temp_dir))["automatic_entries_enabled"])

    def test_valid_mode_transition_and_idempotent_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            first = set_mode("user_managed", "transition-0001", state_dir, generated_at="2026-07-01T10:00:00")
            second = set_mode("ai_managed", "transition-0001", state_dir, generated_at="2026-07-01T10:01:00")
            self.assertEqual(first["governance"]["mode"], "user_managed")
            self.assertTrue(second["idempotent"])
            self.assertEqual(load_governance(state_dir)["mode"], "user_managed")

    def test_invalid_mode_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(GovernanceError):
                set_mode("real_trading", "transition-0002", Path(temp_dir))

    def test_ai_assisted_creates_proposal_instead_of_trade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = pick("ASSIST", "BUY", 100)
            payload = daily_picks([item])
            result = process_paper_trading(
                daily_picks=payload,
                raw_rows=raw_rows_from([item]),
                output_dir=root / "out",
                state_dir=root / "state",
                generated_at=payload["generated_at"],
                market_data_service=FakeMarketDataService({"ASSIST": quote("ASSIST", 100)}),
            )
            proposals = load_proposals(root / "state")["proposals"]
            self.assertEqual(result["open_positions"], 0)
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0]["status"], "pending")

    def test_user_managed_blocks_automatic_v8_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            set_mode("user_managed", "transition-0003", root / "state")
            item = pick("USERMODE", "BUY", 100)
            result = process_paper_trading(
                daily_picks=daily_picks([item]),
                raw_rows=raw_rows_from([item]),
                output_dir=root / "out",
                state_dir=root / "state",
                market_data_service=FakeMarketDataService({"USERMODE": quote("USERMODE", 100)}),
            )
            self.assertEqual(result["open_positions"], 0)
            with open(root / "state" / "processed_picks.json") as f:
                processed = json.load(f)["picks"][item["pick_id"]]
            self.assertEqual(processed["status"], "skipped_governance_user_managed")

    def test_ai_managed_blocks_user_directed_add(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            set_mode("ai_managed", "transition-0004", root / "state")
            item = pick("BLOCK", "BUY", 100)
            daily_path = root / "daily_picks.json"
            snapshot_path = root / "web_snapshot.json"
            write_json(daily_path, daily_picks([item]))
            write_web_snapshot(snapshot_path, "BLOCK")
            with self.assertRaises(PortfolioCommandError) as context:
                add_user_directed_position(
                    ticker="BLOCK",
                    amount=1000,
                    source_pick_id=item["pick_id"],
                    request_id="manual-block-0001",
                    state_dir=root / "state",
                    output_dir=root / "out",
                    daily_picks_path=daily_path,
                    web_snapshot_path=snapshot_path,
                    market_data_service=FakeMarketDataService({"BLOCK": quote("BLOCK", 100)}),
                )
            self.assertEqual(context.exception.code, "mode_restricted")

    def test_proposal_approval_executes_once_and_rejection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = pick("APPROVE", "BUY", 100)
            payload = daily_picks([item])
            daily_path = root / "daily_picks.json"
            write_json(daily_path, payload)
            process_paper_trading(
                daily_picks=payload,
                raw_rows=raw_rows_from([item]),
                output_dir=root / "out",
                state_dir=root / "state",
                generated_at=payload["generated_at"],
                market_data_service=FakeMarketDataService({"APPROVE": quote("APPROVE", 100)}),
            )
            proposal = load_proposals(root / "state")["proposals"][0]
            first = approve_open_position_proposal(
                proposal["proposal_id"],
                "approve-0001",
                root / "state",
                root / "out",
                daily_path,
                generated_at="2026-07-01T10:05:00",
                market_data_service=FakeMarketDataService({"APPROVE": quote("APPROVE", 100, timestamp="2026-07-01T10:05:00-04:00")}),
            )
            second = approve_open_position_proposal(
                proposal["proposal_id"],
                "approve-0001",
                root / "state",
                root / "out",
                daily_path,
                generated_at="2026-07-01T10:06:00",
                market_data_service=FakeMarketDataService({"APPROVE": quote("APPROVE", 100, timestamp="2026-07-01T10:06:00-04:00")}),
            )
            self.assertTrue(first["ok"])
            self.assertTrue(second["idempotent"])
            with open(root / "state" / "open_positions_ledger.json") as f:
                self.assertEqual(len(json.load(f)["positions"]), 1)

            item2 = pick("REJECT", "BUY", 50)
            payload2 = daily_picks([item2])
            process_paper_trading(
                daily_picks=payload2,
                raw_rows=raw_rows_from([item2]),
                output_dir=root / "out",
                state_dir=root / "state2",
                generated_at=payload2["generated_at"],
                market_data_service=FakeMarketDataService({"REJECT": quote("REJECT", 50)}),
            )
            proposal2 = load_proposals(root / "state2")["proposals"][0]
            rejected = reject_proposal(proposal2["proposal_id"], "reject-0001", root / "state2")
            self.assertEqual(rejected["proposal"]["status"], "rejected")

    def test_stale_quote_blocks_proposal_execution_and_existing_position_survives_mode_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = pick("STALEP", "BUY", 100)
            payload = daily_picks([item])
            daily_path = root / "daily_picks.json"
            write_json(daily_path, payload)
            process_paper_trading(
                daily_picks=payload,
                raw_rows=raw_rows_from([item]),
                output_dir=root / "out",
                state_dir=root / "state",
                generated_at=payload["generated_at"],
                market_data_service=FakeMarketDataService({"STALEP": quote("STALEP", 100)}),
            )
            proposal = load_proposals(root / "state")["proposals"][0]
            with self.assertRaises(GovernanceError):
                approve_open_position_proposal(
                    proposal["proposal_id"],
                    "approve-stale-0001",
                    root / "state",
                    root / "out",
                    daily_path,
                    generated_at="2026-07-01T10:05:00",
                    market_data_service=FakeMarketDataService({"STALEP": quote("STALEP", 100, status="stale")}),
                )
            set_mode("user_managed", "transition-0005", root / "state")
            self.assertEqual(load_proposals(root / "state")["proposals"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
