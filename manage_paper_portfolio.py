import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from market_data_service import MarketDataService
from paper_trading_engine import (
    DATA_SOURCE,
    DEFAULT_CONFIG,
    RESEARCH_METADATA,
    STARTING_CAPITAL,
    STRATEGY_METADATA,
    PaperTradingStore,
    atomic_write_json,
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
    load_governance,
    mode_capabilities,
    position_with_governance,
)


TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")
AUDIT_FILE_NAME = "user_actions.json"


class PortfolioCommandError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def load_json(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise PortfolioCommandError("invalid_json", f"{path} did not contain a JSON object.")
    return payload


def load_audit_log(state_dir: Path) -> Dict[str, Any]:
    path = state_dir / AUDIT_FILE_NAME
    if not path.exists():
        return {"schema_version": "1.0", "actions": []}
    return load_json(path)


def save_audit_log(state_dir: Path, audit_log: Dict[str, Any]) -> None:
    audit_log.setdefault("schema_version", "1.0")
    audit_log.setdefault("actions", [])
    atomic_write_json(state_dir / AUDIT_FILE_NAME, audit_log)


def append_user_action(
    state_dir: Path,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> None:
    if dry_run:
        return
    audit_log = load_audit_log(state_dir)
    audit_log.setdefault("actions", []).append(action)
    save_audit_log(state_dir, audit_log)


def existing_success_for_request(state_dir: Path, request_id: str) -> Optional[Dict[str, Any]]:
    audit_log = load_audit_log(state_dir)
    for action in audit_log.get("actions", []):
        if action.get("action_id") == request_id and action.get("result") == "success":
            return action
    return None


def validate_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not TICKER_RE.fullmatch(normalized):
        raise PortfolioCommandError("invalid_ticker", "Ticker must be 1-12 safe symbol characters.")
    return normalized


def validate_request_id(request_id: str) -> str:
    normalized = request_id.strip()
    if not REQUEST_ID_RE.fullmatch(normalized):
        raise PortfolioCommandError("invalid_request_id", "Request ID is missing or invalid.")
    return normalized


def find_pick(daily_picks: Dict[str, Any], ticker: str, source_pick_id: str) -> Dict[str, Any]:
    for pick in daily_picks.get("picks", []):
        if pick.get("pick_id") == source_pick_id and str(pick.get("ticker", "")).upper() == ticker:
            return pick
    raise PortfolioCommandError("pick_not_found", "The requested candidate was not found in daily_picks.json.")


def research_rating_for_ticker(web_snapshot_path: Path, ticker: str) -> str:
    try:
        snapshot = load_json(web_snapshot_path)
    except Exception:
        return "Unavailable"
    for candidate in snapshot.get("ranked_candidates", []):
        if str(candidate.get("ticker", "")).upper() == ticker:
            return str(candidate.get("action", "Unavailable")).upper()
    return "Unavailable"


def paper_eligibility(pick: Dict[str, Any]) -> Dict[str, Any]:
    scanner_action = str(pick.get("action", "")).upper()
    decision = str(pick.get("paper_trade_decision", "unknown"))
    eligible = (
        scanner_action == "BUY"
        and bool(pick.get("paper_trade_candidate"))
        and decision == "eligible_scanner_export"
    )
    return {
        "eligible": eligible,
        "status": "Eligible" if eligible else "Not eligible",
        "decision": decision,
        "reason": pick.get("paper_trade_decision_reason", "No paper eligibility reason provided."),
    }


def build_audit_action(
    request_id: str,
    timestamp: str,
    ticker: str,
    source_pick_id: str,
    requested_amount: float,
    result: str,
    reason: Optional[str] = None,
    position: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "action_id": request_id,
        "timestamp": timestamp,
        "type": "add_user_directed_position",
        "ticker": ticker,
        "source_pick_id": source_pick_id,
        "requested_dollar_amount": round_money(requested_amount),
        "result": result,
        "origin": "user_directed",
        "strategy": STRATEGY_METADATA,
        "research_metadata": RESEARCH_METADATA,
    }
    if reason:
        payload["failure_reason"] = reason
    if position:
        payload.update(
            {
                "position_id": position["position_id"],
                "executed_dollar_amount": position["notional_cost"],
                "quantity": position["quantity"],
                "entry_price": position["entry_price"],
            }
        )
    return payload


def add_user_directed_position(
    ticker: str,
    amount: float,
    source_pick_id: str,
    note: str = "",
    request_id: str = "",
    acknowledge_override: bool = False,
    dry_run: bool = False,
    state_dir: Path = Path("data/paper_trading/state"),
    output_dir: Path = Path("data/paper_trading"),
    daily_picks_path: Path = Path("data/paper_trading/daily_picks.json"),
    web_snapshot_path: Path = Path("data/web_snapshot.json"),
    generated_at: Optional[str] = None,
    market_data_service: Optional[MarketDataService] = None,
) -> Dict[str, Any]:
    generated_at = generated_at or now_iso()
    ticker = validate_ticker(ticker)
    request_id = validate_request_id(request_id)
    requested_amount = safe_float(amount)
    if requested_amount <= 0:
        raise PortfolioCommandError("invalid_amount", "Amount must be greater than zero.")

    previous_success = existing_success_for_request(state_dir, request_id)
    if previous_success:
        return {
            "ok": True,
            "idempotent": True,
            "message": "Request was already processed successfully.",
            "action": previous_success,
        }

    governance = load_governance(state_dir)
    governance_mode = governance["mode"]
    if governance_mode == "ai_managed":
        reason = "Manual position creation is unavailable while AI Managed mode is active."
        append_user_action(
            state_dir,
            {
                **build_audit_action(request_id, generated_at, ticker, source_pick_id, requested_amount, "failed", reason),
                "type": "mode_restricted_action_blocked",
                "previous_mode": governance_mode,
                "new_mode": governance_mode,
            },
            dry_run=dry_run,
        )
        raise PortfolioCommandError("mode_restricted", reason)

    daily_picks = load_json(daily_picks_path)
    pick = find_pick(daily_picks, ticker, source_pick_id)
    eligibility = paper_eligibility(pick)
    scanner_action = str(pick.get("action", "")).upper()
    research_rating = research_rating_for_ticker(web_snapshot_path, ticker)

    if not eligibility["eligible"] and not acknowledge_override:
        reason = "Non-auto-eligible candidates require explicit user acknowledgement."
        append_user_action(
            state_dir,
            build_audit_action(request_id, generated_at, ticker, source_pick_id, requested_amount, "failed", reason),
            dry_run=dry_run,
        )
        raise PortfolioCommandError("override_required", reason)

    store = PaperTradingStore(state_dir)
    state = store.load()
    if dry_run:
        state = deepcopy(state)

    account = state["account"]
    open_positions = state["open_positions"].setdefault("positions", [])
    closed_trades = state["closed_trades"].setdefault("trades", [])
    equity_history = state["equity_history"]

    if any(str(position.get("ticker", "")).upper() == ticker for position in open_positions):
        reason = "This ticker already has an open simulated position."
        append_user_action(
            state_dir,
            build_audit_action(request_id, generated_at, ticker, source_pick_id, requested_amount, "failed", reason),
            dry_run=dry_run,
        )
        raise PortfolioCommandError("duplicate_open_ticker", reason)

    market_data = market_data_service or MarketDataService()
    quote = market_data.get_quote(ticker)
    if safe_float(quote.get("price")) <= 0 or quote.get("price_status") not in {"fresh", "delayed"}:
        reason = "Fresh market price was unavailable; no simulated position was created."
        append_user_action(
            state_dir,
            build_audit_action(request_id, generated_at, ticker, source_pick_id, requested_amount, "failed", reason),
            dry_run=dry_run,
        )
        raise PortfolioCommandError("price_unavailable", reason)

    active_config = DEFAULT_CONFIG.copy()
    cash = safe_float(account.get("cash", STARTING_CAPITAL))
    minimum_cash = STARTING_CAPITAL * (safe_float(active_config["minimum_cash_reserve_pct"]) / 100)
    spendable_cash = max(cash - minimum_cash, 0)
    max_position_notional = STARTING_CAPITAL * (safe_float(active_config["max_position_pct"]) / 100)
    target_notional = min(requested_amount, spendable_cash, max_position_notional)
    quantity = int(target_notional // safe_float(quote["price"]))

    if quantity <= 0:
        reason = "Requested amount cannot buy one whole share while preserving the cash reserve."
        append_user_action(
            state_dir,
            build_audit_action(request_id, generated_at, ticker, source_pick_id, requested_amount, "failed", reason),
            dry_run=dry_run,
        )
        raise PortfolioCommandError("insufficient_cash", reason)

    position = build_open_position(
        pick,
        quote,
        quantity,
        generated_at,
        daily_picks.get("market_regime", {}).get("label", "Current"),
        active_config,
    )
    position_id = f"user_{ticker}_{generated_at[:10]}_{request_id[:12]}"
    cost_basis = round_money(quantity * safe_float(quote["price"]))
    position.update(
        {
            "trade_id": position_id,
            "position_id": position_id,
            "origin": "user_directed",
            "entry_action": scanner_action,
            "scanner_action": scanner_action,
            "research_rating": research_rating,
            "automatic_paper_eligibility": eligibility["status"],
            "automatic_paper_eligibility_reason": eligibility["reason"],
            "paper_execution": "Open",
            "user_selected_allocation_pct": round((cost_basis / STARTING_CAPITAL) * 100, 4),
            "requested_dollar_amount": round_money(requested_amount),
            "executed_dollar_amount": cost_basis,
            "user_note": note.strip()[:500],
            "created_at": generated_at,
            "thesis": "User-directed simulated position created from current research queue evidence.",
            "notes": "User-directed paper simulation only. No real order was placed.",
        }
    )
    position = position_with_governance(
        position,
        mode=governance_mode,
        origin="user_directed",
        decision_authority="user",
        lifecycle_authority="user_manual",
        user_approved=True,
    )

    open_positions.append(position)
    account["cash"] = round_money(cash - cost_basis)
    account["updated_at"] = generated_at

    portfolio = calculate_portfolio(account, open_positions, closed_trades)
    quotes = {ticker: quote}
    metadata = market_metadata(
        quotes,
        equity_history,
        generated_at[:10],
        market_data,
    )
    stale_positions = stale_position_count(open_positions)
    upsert_equity_point(
        equity_history,
        portfolio,
        generated_at[:10],
        daily_picks.get("source_file"),
        metadata["price_data_status"],
    )

    paths: Dict[str, str] = {}
    if not dry_run:
        store.save(state)
        append_user_action(
            state_dir,
            build_audit_action(
                request_id,
                generated_at,
                ticker,
                source_pick_id,
                requested_amount,
                "success",
                position=position,
            ),
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

    return {
        "ok": True,
        "dry_run": dry_run,
        "origin": "user_directed",
        "ticker": ticker,
        "source_pick_id": source_pick_id,
        "scanner_action": scanner_action,
        "research_rating": research_rating,
        "automatic_paper_eligibility": eligibility["status"],
        "position": {
            "position_id": position["position_id"],
            "quantity": position["quantity"],
            "entry_price": position["entry_price"],
            "requested_dollar_amount": position["requested_dollar_amount"],
            "executed_dollar_amount": position["executed_dollar_amount"],
            "market_state": position.get("market_state"),
            "last_price_update": position.get("last_price_update"),
            "price_source": position.get("price_source"),
            "price_status": position.get("price_status"),
        },
        "portfolio": {
            "cash": portfolio["cash"],
            "total_equity": portfolio["total_equity"],
            "open_positions_count": portfolio["open_positions_count"],
        },
        "data_source": DATA_SOURCE,
        "governance": mode_capabilities(governance_mode),
        "paths": paths,
    }


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage user-directed AI Stock Hunter paper positions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a user-directed simulated paper position.")
    add_parser.add_argument("--ticker", required=True)
    add_parser.add_argument("--amount", required=True, type=float)
    add_parser.add_argument("--source-pick-id", required=True)
    add_parser.add_argument("--note", default="")
    add_parser.add_argument("--request-id", required=True)
    add_parser.add_argument("--acknowledge-override", action="store_true")
    add_parser.add_argument("--dry-run", action="store_true")
    add_parser.add_argument("--state-dir", type=Path, default=Path("data/paper_trading/state"))
    add_parser.add_argument("--output-dir", type=Path, default=Path("data/paper_trading"))
    add_parser.add_argument("--daily-picks", type=Path, default=Path("data/paper_trading/daily_picks.json"))
    add_parser.add_argument("--web-snapshot", type=Path, default=Path("data/web_snapshot.json"))

    args = parser.parse_args(argv)

    try:
        if args.command == "add":
            result = add_user_directed_position(
                ticker=args.ticker,
                amount=args.amount,
                source_pick_id=args.source_pick_id,
                note=args.note,
                request_id=args.request_id,
                acknowledge_override=args.acknowledge_override,
                dry_run=args.dry_run,
                state_dir=args.state_dir,
                output_dir=args.output_dir,
                daily_picks_path=args.daily_picks,
                web_snapshot_path=args.web_snapshot,
            )
            emit(result)
            return 0
    except PortfolioCommandError as exc:
        emit({"ok": False, "code": exc.code, "message": exc.message})
        return 2
    except Exception as exc:
        emit({"ok": False, "code": "internal_error", "message": str(exc)})
        return 1

    emit({"ok": False, "code": "unknown_command", "message": "Unknown command."})
    return 2


if __name__ == "__main__":
    sys.exit(main())
