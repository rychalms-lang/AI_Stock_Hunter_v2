import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from market_data_service import MarketDataService
from paper_trading_engine import (
    DEFAULT_CONFIG,
    PaperTradingStore,
    build_open_position,
    calculate_portfolio,
    export_files,
    market_metadata,
    now_iso,
    round_money,
    safe_float,
    stale_position_count,
    upsert_equity_point,
)
from portfolio_governance import (
    GovernanceError,
    append_audit,
    audit_event,
    find_proposal,
    governance_summary,
    load_governance,
    load_proposals,
    mode_capabilities,
    position_with_governance,
    request_already_succeeded,
    save_proposals,
    set_mode,
)


REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def load_json(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise GovernanceError("invalid_json", f"{path} did not contain a JSON object.")
    return payload


def validate_request_id(request_id: str) -> str:
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise GovernanceError("invalid_request_id", "Request ID is missing or invalid.")
    return request_id


def find_pick(daily_picks: Dict[str, Any], source_pick_id: str) -> Dict[str, Any]:
    for pick in daily_picks.get("picks", []):
        if pick.get("pick_id") == source_pick_id:
            return pick
    raise GovernanceError("pick_not_found", "The proposal source pick no longer exists in daily_picks.json.")


def approve_open_position_proposal(
    proposal_id: str,
    request_id: str,
    state_dir: Path = Path("data/paper_trading/state"),
    output_dir: Path = Path("data/paper_trading"),
    daily_picks_path: Path = Path("data/paper_trading/daily_picks.json"),
    generated_at: Optional[str] = None,
    market_data_service: Optional[MarketDataService] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    request_id = validate_request_id(request_id)
    generated_at = generated_at or now_iso()
    previous_success = request_already_succeeded(state_dir, request_id, "proposal_executed")
    if previous_success:
        return {"ok": True, "idempotent": True, "event": previous_success}

    governance = load_governance(state_dir)
    if governance["mode"] != "ai_assisted":
        raise GovernanceError("mode_restricted", "Proposal approval is available only in AI Assisted mode.")

    proposals = load_proposals(state_dir)
    proposal = find_proposal(proposals, proposal_id)
    if not proposal:
        raise GovernanceError("proposal_not_found", "Proposal was not found.")
    if proposal.get("status") != "pending":
        raise GovernanceError("invalid_proposal_status", "Only pending proposals can be approved.")
    if proposal.get("expires_at") and proposal["expires_at"] < generated_at:
        proposal["status"] = "expired"
        proposal["user_decision"] = "expired"
        proposal["decided_at"] = generated_at
        if not dry_run:
            save_proposals(state_dir, proposals)
            append_audit(
                state_dir,
                audit_event(request_id, "proposal_expired", "failed", proposal_id=proposal_id, ticker=proposal.get("ticker"), failure_reason="Proposal expired.", timestamp=generated_at),
            )
        raise GovernanceError("proposal_expired", "Proposal has expired.")

    daily_picks = load_json(daily_picks_path)
    pick = find_pick(daily_picks, str(proposal["source_pick_id"]))
    ticker = str(proposal["ticker"]).upper()
    store = PaperTradingStore(state_dir)
    state = store.load()
    account = state["account"]
    open_positions = state["open_positions"].setdefault("positions", [])
    closed_trades = state["closed_trades"].setdefault("trades", [])
    equity_history = state["equity_history"]

    if any(str(position.get("ticker", "")).upper() == ticker for position in open_positions):
        raise GovernanceError("duplicate_open_ticker", "This ticker already has an open simulated position.")

    market_data = market_data_service or MarketDataService()
    quote = market_data.get_quote(ticker)
    if safe_float(quote.get("price")) <= 0 or quote.get("price_status") not in {"fresh", "delayed"}:
        raise GovernanceError("price_unavailable", "Fresh market price was unavailable; proposal was not executed.")

    cash = safe_float(account.get("cash"))
    minimum_cash = 25000.0 * (safe_float(DEFAULT_CONFIG["minimum_cash_reserve_pct"]) / 100)
    spendable_cash = max(cash - minimum_cash, 0)
    max_position_notional = 25000.0 * (safe_float(DEFAULT_CONFIG["max_position_pct"]) / 100)
    target_notional = min(safe_float(proposal.get("proposed_amount")), spendable_cash, max_position_notional)
    quantity = int(target_notional // safe_float(quote["price"]))
    if quantity <= 0:
        raise GovernanceError("insufficient_cash", "Available cash is insufficient for one whole share while preserving reserve.")

    position = build_open_position(
        pick,
        quote,
        quantity,
        generated_at,
        daily_picks.get("market_regime", {}).get("label", "Current"),
        DEFAULT_CONFIG,
    )
    position = position_with_governance(
        position,
        mode="ai_assisted",
        origin="ai_proposed_user_approved",
        decision_authority="user_approved_v8",
        lifecycle_authority="v8_rules_with_user_approval",
        user_approved=True,
        proposal_id=proposal_id,
    )
    open_positions.append(position)
    account["cash"] = round_money(cash - position["cost_basis"])
    account["updated_at"] = generated_at
    proposal["status"] = "executed"
    proposal["user_decision"] = "approved"
    proposal["decided_at"] = generated_at
    proposal["executed_position_id"] = position["position_id"]

    portfolio = calculate_portfolio(account, open_positions, closed_trades)
    quotes = {ticker: quote}
    metadata = market_metadata(quotes, equity_history, generated_at[:10], market_data)
    stale_positions = stale_position_count(open_positions)
    upsert_equity_point(equity_history, portfolio, generated_at[:10], daily_picks.get("source_file"), metadata["price_data_status"])

    paths: Dict[str, str] = {}
    if not dry_run:
        store.save(state)
        save_proposals(state_dir, proposals)
        append_audit(
            state_dir,
            audit_event(request_id, "proposal_executed", "success", previous_mode="ai_assisted", new_mode="ai_assisted", proposal_id=proposal_id, ticker=ticker, timestamp=generated_at),
        )
        paths = export_files(
            output_dir,
            generated_at,
            generated_at[:10],
            daily_picks.get("source_file"),
            open_positions,
            closed_trades,
            portfolio,
            equity_history.get("points", []),
            metadata["price_data_status"],
            metadata["market_state"],
            metadata["last_market_update"],
            metadata["live_prices"],
            stale_positions,
        )

    return {"ok": True, "proposal": proposal, "position_id": position["position_id"], "paths": paths}


def reject_proposal(
    proposal_id: str,
    request_id: str,
    state_dir: Path = Path("data/paper_trading/state"),
    generated_at: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    request_id = validate_request_id(request_id)
    generated_at = generated_at or now_iso()
    previous_success = request_already_succeeded(state_dir, request_id, "proposal_rejected")
    if previous_success:
        return {"ok": True, "idempotent": True, "event": previous_success}
    proposals = load_proposals(state_dir)
    proposal = find_proposal(proposals, proposal_id)
    if not proposal:
        raise GovernanceError("proposal_not_found", "Proposal was not found.")
    if proposal.get("status") != "pending":
        raise GovernanceError("invalid_proposal_status", "Only pending proposals can be rejected.")
    proposal["status"] = "rejected"
    proposal["user_decision"] = "rejected"
    proposal["decided_at"] = generated_at
    if not dry_run:
        save_proposals(state_dir, proposals)
        append_audit(
            state_dir,
            audit_event(request_id, "proposal_rejected", "success", proposal_id=proposal_id, ticker=proposal.get("ticker"), timestamp=generated_at),
        )
    return {"ok": True, "proposal": proposal}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage AI Stock Hunter paper portfolio governance.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show = subparsers.add_parser("show")
    show.add_argument("--state-dir", type=Path, default=Path("data/paper_trading/state"))

    set_mode_parser = subparsers.add_parser("set-mode")
    set_mode_parser.add_argument("--mode", required=True)
    set_mode_parser.add_argument("--request-id", required=True)
    set_mode_parser.add_argument("--state-dir", type=Path, default=Path("data/paper_trading/state"))

    list_parser = subparsers.add_parser("list-proposals")
    list_parser.add_argument("--state-dir", type=Path, default=Path("data/paper_trading/state"))

    approve = subparsers.add_parser("approve-proposal")
    approve.add_argument("--proposal-id", required=True)
    approve.add_argument("--request-id", required=True)
    approve.add_argument("--state-dir", type=Path, default=Path("data/paper_trading/state"))
    approve.add_argument("--output-dir", type=Path, default=Path("data/paper_trading"))
    approve.add_argument("--daily-picks", type=Path, default=Path("data/paper_trading/daily_picks.json"))

    reject = subparsers.add_parser("reject-proposal")
    reject.add_argument("--proposal-id", required=True)
    reject.add_argument("--request-id", required=True)
    reject.add_argument("--state-dir", type=Path, default=Path("data/paper_trading/state"))

    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            emit({"ok": True, "governance": governance_summary(args.state_dir)})
        elif args.command == "set-mode":
            emit(set_mode(args.mode, validate_request_id(args.request_id), args.state_dir))
        elif args.command == "list-proposals":
            emit({"ok": True, **load_proposals(args.state_dir)})
        elif args.command == "approve-proposal":
            emit(approve_open_position_proposal(args.proposal_id, args.request_id, args.state_dir, args.output_dir, args.daily_picks))
        elif args.command == "reject-proposal":
            emit(reject_proposal(args.proposal_id, args.request_id, args.state_dir))
        return 0
    except GovernanceError as exc:
        emit({"ok": False, "code": exc.code, "message": exc.message})
        return 2
    except Exception as exc:
        emit({"ok": False, "code": "internal_error", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
