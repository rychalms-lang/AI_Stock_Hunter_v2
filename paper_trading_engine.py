import json
import math
import os
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1.0"
STARTING_CAPITAL = 25000.0
ACCOUNT_ID = "paper_default"
DISCLAIMER = (
    "Paper trading simulation only. No real trades are placed. "
    "This is research and decision support, not investment advice."
)

STRATEGY_METADATA = {
    "name": "V8",
    "version": "8.0",
    "status": "Champion",
}

RESEARCH_METADATA = {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "paper_trading_update",
}

DATA_SOURCE = {
    "type": "paper_ledger",
    "generated_by": "paper_trading_engine",
    "generator_version": "1.0",
}

ACCOUNT = {
    "account_id": ACCOUNT_ID,
    "mode": "paper_only",
    "starting_capital": STARTING_CAPITAL,
    "currency": "USD",
}

DEFAULT_CONFIG = {
    "starting_capital": STARTING_CAPITAL,
    "minimum_cash_reserve_pct": 10.0,
    "max_positions": 5,
    "max_position_pct": 20.0,
    "stop_loss_pct": -5.0,
    "take_profit_pct": 10.0,
    "fees_per_trade": 0.0,
    "slippage_pct": 0.0,
}


class PaperTradingStateError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_date(value: str) -> date:
    return datetime.fromisoformat(value[:10]).date()


def is_stale_source_date(source_market_date: str, generated_at: str) -> bool:
    return parse_date(source_market_date) < parse_date(generated_at)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "n/a", "null"}:
            return default
        result = float(text)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(safe_float(value, default)))
    except Exception:
        return default


def round_money(value: Any) -> float:
    return round(safe_float(value), 2)


def round_pct(value: Any) -> float:
    return round(safe_float(value), 2)


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(temp_path, path)


class PaperTradingStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir

    def _path(self, file_name: str) -> Path:
        return self.state_dir / file_name

    def _load(self, file_name: str, default: Dict[str, Any]) -> Dict[str, Any]:
        path = self._path(file_name)
        if not path.exists():
            return deepcopy(default)

        try:
            with path.open() as f:
                payload = json.load(f)
        except json.JSONDecodeError as exc:
            raise PaperTradingStateError(f"Corrupt paper trading state file: {path}") from exc

        if not isinstance(payload, dict):
            raise PaperTradingStateError(f"Invalid paper trading state shape: {path}")

        return payload

    def load(self) -> Dict[str, Dict[str, Any]]:
        return {
            "account": self._load(
                "account_state.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "account_id": ACCOUNT_ID,
                    "starting_capital": STARTING_CAPITAL,
                    "cash": STARTING_CAPITAL,
                    "realized_pnl": 0.0,
                    "currency": "USD",
                    "updated_at": None,
                },
            ),
            "open_positions": self._load(
                "open_positions_ledger.json",
                {"schema_version": SCHEMA_VERSION, "positions": []},
            ),
            "closed_trades": self._load(
                "closed_trades_ledger.json",
                {"schema_version": SCHEMA_VERSION, "trades": []},
            ),
            "processed_picks": self._load(
                "processed_picks.json",
                {"schema_version": SCHEMA_VERSION, "picks": {}},
            ),
            "equity_history": self._load(
                "equity_history.json",
                {"schema_version": SCHEMA_VERSION, "points": []},
            ),
        }

    def save(self, state: Dict[str, Dict[str, Any]]) -> None:
        atomic_write_json(self._path("account_state.json"), state["account"])
        atomic_write_json(self._path("open_positions_ledger.json"), state["open_positions"])
        atomic_write_json(self._path("closed_trades_ledger.json"), state["closed_trades"])
        atomic_write_json(self._path("processed_picks.json"), state["processed_picks"])
        atomic_write_json(self._path("equity_history.json"), state["equity_history"])


class ScannerPriceProvider:
    def __init__(self, daily_picks: Dict[str, Any], generated_at: str):
        self.generated_at = daily_picks.get("generated_at")
        self.source_market_date = daily_picks.get("trade_date", generated_at[:10])
        self.stale_price_data = is_stale_source_date(self.source_market_date, generated_at)
        self.prices: Dict[str, Dict[str, Any]] = {}

        for pick in daily_picks.get("picks", []):
            ticker = str(pick.get("ticker", "")).upper()
            price = safe_float(pick.get("latest_close"))
            if ticker and price > 0:
                self.prices[ticker] = {
                    "price": price,
                    "source": "scanner_csv_latest_close",
                    "timestamp": self.generated_at,
                    "source_market_date": self.source_market_date,
                    "stale_price_data": self.stale_price_data,
                    "price_data_status": "stale_price_data" if self.stale_price_data else "fresh",
                }

    def get_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self.prices.get(ticker.upper())


def pick_lookup(daily_picks: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(pick.get("pick_id")): pick
        for pick in daily_picks.get("picks", [])
        if pick.get("pick_id")
    }


def raw_action_lookup(raw_rows: List[Dict[str, str]], trade_date: str) -> Dict[str, str]:
    actions = {}
    for row in raw_rows:
        ticker = str(row.get("ticker", "")).upper()
        if ticker:
            actions[f"{trade_date}_{ticker}"] = str(row.get("action", "")).upper()
    return actions


def allocation_lookup(raw_rows: List[Dict[str, str]]) -> Dict[str, float]:
    try:
        from portfolio import build_portfolio

        portfolio_rows = [
            {
                "ticker": str(row.get("ticker", "UNKNOWN")).upper(),
                "sector": row.get("sector", "Other / Uncategorized"),
                "confidence_score": safe_float(row.get("confidence_score", row.get("confidence")), 50),
                "score": safe_float(row.get("score", row.get("pre_score"))),
                "risk": row.get("risk", "Medium"),
            }
            for row in raw_rows
        ]
        portfolio = build_portfolio(portfolio_rows)
        return {
            str(position.get("ticker", "")).upper(): safe_float(position.get("allocation_pct"))
            for position in portfolio.get("positions", [])
        }
    except Exception:
        return {}


def stable_trade_id(pick: Dict[str, Any]) -> str:
    return f"paper_{pick['pick_id']}"


def planned_exit_date(entry_date: str, hold_days: int) -> str:
    return (parse_date(entry_date) + timedelta(days=max(hold_days, 0))).isoformat()


def days_between(start_date: str, end_date: str) -> int:
    return max((parse_date(end_date) - parse_date(start_date)).days, 0)


def build_open_position(
    pick: Dict[str, Any],
    price: Dict[str, Any],
    quantity: int,
    generated_at: str,
    market_regime: str,
    config: Dict[str, float],
) -> Dict[str, Any]:
    entry_price = round_money(price["price"])
    cost_basis = round_money(quantity * entry_price)
    hold_days = max(safe_int(pick.get("best_hold_period_days"), 1), 1)
    trade_date = pick.get("trade_date", generated_at[:10])
    trade_id = stable_trade_id(pick)
    stop_price = round_money(entry_price * (1 + safe_float(config["stop_loss_pct"]) / 100))
    take_profit_price = round_money(entry_price * (1 + safe_float(config["take_profit_pct"]) / 100))

    return {
        "trade_id": trade_id,
        "position_id": trade_id,
        "source_pick_id": pick["pick_id"],
        "ticker": pick["ticker"],
        "sector": pick.get("sector", "Other / Uncategorized"),
        "status": "open",
        "opened_at": generated_at,
        "entry_date": trade_date,
        "entry_price": entry_price,
        "current_price": entry_price,
        "quantity": quantity,
        "cost_basis": cost_basis,
        "notional_cost": cost_basis,
        "market_value": cost_basis,
        "current_value": cost_basis,
        "unrealized_pnl": 0.0,
        "unrealized_return_pct": 0.0,
        "target_hold_days": hold_days,
        "planned_hold_period_days": hold_days,
        "planned_exit_date": planned_exit_date(trade_date, hold_days),
        "days_held": 0,
        "stop_loss_price": stop_price,
        "take_profit_price": take_profit_price,
        "risk_label": pick.get("risk", "Medium"),
        "entry_action": "BUY",
        "entry_score": safe_float(pick.get("score")),
        "entry_confidence": safe_float(pick.get("confidence")),
        "entry_expected_return_pct": safe_float(pick.get("expected_return_pct")),
        "entry_historical_matches": safe_int(pick.get("historical_matches")),
        "entry_risk": pick.get("risk", "Medium"),
        "entry_market_regime": market_regime,
        "entry_sector_rank": safe_int(pick.get("sector_rank")),
        "original_confidence": safe_float(pick.get("confidence")),
        "expected_return": safe_float(pick.get("expected_return_pct")),
        "historical_matches": safe_int(pick.get("historical_matches")),
        "strategy": pick.get("strategy", STRATEGY_METADATA),
        "research_metadata": pick.get("research_metadata", RESEARCH_METADATA),
        "ai_explanation": pick.get("ai_explanation", empty_explanation(pick["ticker"])),
        "thesis": "Paper position created from an eligible BUY scanner signal.",
        "exit_rule": "hold_period_or_risk_rule",
        "stop_rule": f"{config['stop_loss_pct']}%",
        "take_profit_rule": f"{config['take_profit_pct']}%",
        "price_source": price["source"],
        "price_timestamp": price.get("timestamp"),
        "source_market_date": price.get("source_market_date"),
        "stale_price_data": False,
        "price_data_status": "fresh",
        "last_updated_at": generated_at,
        "last_price_source_market_date": price.get("source_market_date"),
        "max_unrealized_gain_pct": 0.0,
        "max_unrealized_loss_pct": 0.0,
        "fees": safe_float(config["fees_per_trade"]),
        "slippage": 0.0,
        "notes": "Paper trading simulation only. No real order was placed.",
    }


def empty_explanation(ticker: str) -> Dict[str, Any]:
    return {
        "summary": f"{ticker} was processed by the paper trading engine from scanner evidence.",
        "strengths": [],
        "risks": [],
        "similar_historical_cases": [],
    }


def update_position_price(
    position: Dict[str, Any],
    price: Optional[Dict[str, Any]],
    as_of_date: str,
    generated_at: str,
) -> None:
    if not price:
        position["status"] = "open_price_unavailable"
        position["price_data_status"] = "price_unavailable"
        position["last_price_check_at"] = generated_at
        return

    source_market_date = price.get("source_market_date", as_of_date)
    previous_source_market_date = position.get("last_price_source_market_date")

    if price.get("stale_price_data"):
        position["status"] = "stale_price_data"
        position["stale_price_data"] = True
        position["price_data_status"] = "stale_price_data"
        position["source_market_date"] = source_market_date
        position["last_price_check_at"] = generated_at
        position["stale_price_reason"] = (
            "Scanner price source is older than the paper-engine run date; "
            "position price, days held, and exit rules were not updated."
        )
        return

    if previous_source_market_date and source_market_date <= previous_source_market_date:
        position["status"] = "stale_price_data"
        position["stale_price_data"] = True
        position["price_data_status"] = "unchanged_source_market_date"
        position["source_market_date"] = source_market_date
        position["last_price_check_at"] = generated_at
        position["stale_price_reason"] = (
            "Scanner source market date did not advance; position price, days held, "
            "and exit rules were not updated."
        )
        return

    position["days_held"] = days_between(position["entry_date"], as_of_date)
    position["last_updated_at"] = generated_at

    current_price = round_money(price["price"])
    market_value = round_money(position["quantity"] * current_price)
    pnl = round_money(market_value - safe_float(position.get("cost_basis", position.get("notional_cost"))))
    return_pct = round_pct((pnl / safe_float(position.get("cost_basis", position.get("notional_cost")), 1)) * 100)

    position["status"] = "open"
    position["current_price"] = current_price
    position["market_value"] = market_value
    position["current_value"] = market_value
    position["unrealized_pnl"] = pnl
    position["unrealized_return_pct"] = return_pct
    position["price_source"] = price["source"]
    position["price_timestamp"] = price.get("timestamp")
    position["source_market_date"] = source_market_date
    position["stale_price_data"] = False
    position["price_data_status"] = "fresh"
    position["last_price_source_market_date"] = source_market_date
    position.pop("stale_price_reason", None)
    position["max_unrealized_gain_pct"] = max(
        safe_float(position.get("max_unrealized_gain_pct")),
        return_pct,
    )
    position["max_unrealized_loss_pct"] = min(
        safe_float(position.get("max_unrealized_loss_pct")),
        return_pct,
    )


def exit_reason(position: Dict[str, Any]) -> Optional[str]:
    if position.get("stale_price_data") or position.get("price_data_status") in {
        "stale_price_data",
        "unchanged_source_market_date",
        "price_unavailable",
    }:
        return None

    current_price = safe_float(position.get("current_price"))
    if current_price <= 0:
        return None

    if current_price <= safe_float(position.get("stop_loss_price")):
        return "stop_loss"
    if current_price >= safe_float(position.get("take_profit_price")):
        return "take_profit"
    if safe_int(position.get("days_held")) >= safe_int(position.get("target_hold_days", position.get("planned_hold_period_days"))):
        return "planned_hold_period"
    return None


def close_position(position: Dict[str, Any], generated_at: str, reason: str) -> Dict[str, Any]:
    exit_price = round_money(position["current_price"])
    proceeds = round_money(position["quantity"] * exit_price)
    cost_basis = round_money(position.get("cost_basis", position.get("notional_cost")))
    realized_pnl = round_money(proceeds - cost_basis)
    realized_return_pct = round_pct((realized_pnl / cost_basis) * 100 if cost_basis else 0)

    return {
        "trade_id": position["trade_id"],
        "position_id": position["position_id"],
        "source_pick_id": position["source_pick_id"],
        "ticker": position["ticker"],
        "sector": position.get("sector", "Other / Uncategorized"),
        "status": "closed",
        "entry_date": position["entry_date"],
        "exit_date": generated_at[:10],
        "entry_price": position["entry_price"],
        "exit_price": exit_price,
        "quantity": position["quantity"],
        "cost_basis": cost_basis,
        "notional_cost": cost_basis,
        "proceeds": proceeds,
        "exit_value": proceeds,
        "realized_pnl": realized_pnl,
        "realized_return_pct": realized_return_pct,
        "days_held": safe_int(position.get("days_held")),
        "planned_hold_period_days": safe_int(position.get("planned_hold_period_days")),
        "actual_hold_days": safe_int(position.get("days_held")),
        "exit_reason": reason,
        "original_confidence": safe_float(position.get("original_confidence", position.get("entry_confidence"))),
        "expected_return": safe_float(position.get("expected_return", position.get("entry_expected_return_pct"))),
        "historical_matches": safe_int(position.get("historical_matches", position.get("entry_historical_matches"))),
        "entry_action": position.get("entry_action", "BUY"),
        "entry_score": safe_float(position.get("entry_score")),
        "entry_confidence": safe_float(position.get("entry_confidence")),
        "entry_expected_return_pct": safe_float(position.get("entry_expected_return_pct")),
        "entry_risk": position.get("entry_risk", position.get("risk_label", "Medium")),
        "entry_market_regime": position.get("entry_market_regime", "Current"),
        "entry_sector_rank": safe_int(position.get("entry_sector_rank")),
        "max_unrealized_gain_pct": safe_float(position.get("max_unrealized_gain_pct")),
        "max_unrealized_loss_pct": safe_float(position.get("max_unrealized_loss_pct")),
        "thesis_outcome": "closed_by_paper_engine_rule",
        "strategy": position.get("strategy", STRATEGY_METADATA),
        "research_metadata": position.get("research_metadata", RESEARCH_METADATA),
        "ai_explanation": position.get("ai_explanation", empty_explanation(position["ticker"])),
        "market_regime_at_entry": position.get("entry_market_regime", "Current"),
        "fees": safe_float(position.get("fees")),
        "slippage": safe_float(position.get("slippage")),
        "price_source": position.get("price_source"),
        "price_timestamp": position.get("price_timestamp"),
        "source_market_date": position.get("source_market_date"),
        "stale_price_data": False,
        "price_data_status": "fresh",
        "notes": "Closed by deterministic paper trading rules. No real order was placed.",
    }


def exposure_by_key(positions: List[Dict[str, Any]], total_equity: float, key: str, output_key: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for position in positions:
        label = position.get(key, "Unknown")
        value = safe_float(position.get("market_value", position.get("current_value")))
        if label not in grouped:
            grouped[label] = {output_key: label, "value": 0.0, "portfolio_pct": 0.0, "position_count": 0}
        grouped[label]["value"] += value
        grouped[label]["position_count"] += 1

    for item in grouped.values():
        item["value"] = round_money(item["value"])
        item["portfolio_pct"] = round_pct((item["value"] / total_equity) * 100 if total_equity else 0)

    return sorted(grouped.values(), key=lambda item: item["value"], reverse=True)


def calculate_portfolio(
    account: Dict[str, Any],
    open_positions: List[Dict[str, Any]],
    closed_trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    cash = round_money(account.get("cash", STARTING_CAPITAL))
    invested_value = round_money(sum(safe_float(position.get("market_value", position.get("current_value"))) for position in open_positions))
    total_equity = round_money(cash + invested_value)
    realized_pnl = round_money(sum(safe_float(trade.get("realized_pnl")) for trade in closed_trades))
    unrealized_pnl = round_money(sum(safe_float(position.get("unrealized_pnl")) for position in open_positions))
    largest_position_value = max([safe_float(position.get("market_value", position.get("current_value"))) for position in open_positions] or [0.0])

    return {
        "cash": cash,
        "invested_value": invested_value,
        "total_equity": total_equity,
        "open_positions_count": len(open_positions),
        "closed_trades_count": len(closed_trades),
        "cash_pct": round_pct((cash / total_equity) * 100 if total_equity else 0),
        "invested_pct": round_pct((invested_value / total_equity) * 100 if total_equity else 0),
        "total_return_pct": round_pct(((total_equity - STARTING_CAPITAL) / STARTING_CAPITAL) * 100),
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "day_pnl": 0.0,
        "day_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "largest_position_pct": round_pct((largest_position_value / total_equity) * 100 if total_equity else 0),
        "sector_exposure": exposure_by_key(open_positions, total_equity, "sector", "sector"),
        "risk_exposure": exposure_by_key(open_positions, total_equity, "risk_label", "risk"),
    }


def upsert_equity_point(
    equity_history: Dict[str, Any],
    portfolio: Dict[str, Any],
    as_of_date: str,
    source_file: Optional[str],
    price_data_status: str,
) -> None:
    points = equity_history.setdefault("points", [])
    previous = points[-1] if points else None
    daily_pnl = round_money(portfolio["total_equity"] - safe_float(previous.get("total_equity", STARTING_CAPITAL)) if previous else portfolio["total_equity"] - STARTING_CAPITAL)
    daily_return_pct = round_pct((daily_pnl / safe_float(previous.get("total_equity", STARTING_CAPITAL), STARTING_CAPITAL)) * 100 if previous else (daily_pnl / STARTING_CAPITAL) * 100)
    peak = max([safe_float(point.get("total_equity")) for point in points] + [portfolio["total_equity"], STARTING_CAPITAL])
    drawdown_pct = round_pct(((portfolio["total_equity"] - peak) / peak) * 100 if peak else 0)

    point = {
        "date": as_of_date,
        "timestamp": now_iso(),
        "source_file": source_file,
        "price_data_status": price_data_status,
        "stale_price_data": price_data_status != "fresh",
        "cash": portfolio["cash"],
        "invested_value": portfolio["invested_value"],
        "total_equity": portfolio["total_equity"],
        "realized_pnl": portfolio["realized_pnl"],
        "unrealized_pnl": portfolio["unrealized_pnl"],
        "daily_pnl": daily_pnl,
        "daily_return_pct": daily_return_pct,
        "cumulative_pnl": round_money(portfolio["total_equity"] - STARTING_CAPITAL),
        "cumulative_return_pct": portfolio["total_return_pct"],
        "drawdown_pct": drawdown_pct,
        "open_positions_count": portfolio["open_positions_count"],
        "closed_trades_count": portfolio["closed_trades_count"],
    }

    if points and points[-1].get("date") == as_of_date:
        points[-1] = point
    else:
        points.append(point)


def max_drawdown(points: List[Dict[str, Any]]) -> Optional[float]:
    if not points:
        return None
    peak = safe_float(points[0].get("total_equity"))
    worst = 0.0
    for point in points:
        equity = safe_float(point.get("total_equity"))
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, ((equity - peak) / peak) * 100)
    return round_pct(worst)


def performance_stats(
    closed_trades: List[Dict[str, Any]],
    open_positions: List[Dict[str, Any]],
    equity_points: List[Dict[str, Any]],
) -> Dict[str, Any]:
    returns = [safe_float(trade.get("realized_return_pct")) for trade in closed_trades]
    winners = [value for value in returns if value > 0]
    losers = [value for value in returns if value < 0]
    gains = sum(safe_float(trade.get("realized_pnl")) for trade in closed_trades if safe_float(trade.get("realized_pnl")) > 0)
    losses = abs(sum(safe_float(trade.get("realized_pnl")) for trade in closed_trades if safe_float(trade.get("realized_pnl")) < 0))
    realized = round_money(sum(safe_float(trade.get("realized_pnl")) for trade in closed_trades))
    unrealized = round_money(sum(safe_float(position.get("unrealized_pnl")) for position in open_positions))

    insufficient = len(closed_trades) == 0

    return {
        "total_trades": len(closed_trades),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate_pct": None if insufficient else round_pct((len(winners) / len(closed_trades)) * 100),
        "average_return_pct": None if insufficient else round_pct(mean(returns)),
        "median_return_pct": None if insufficient else round_pct(median(returns)),
        "best_trade_return_pct": None if insufficient else round_pct(max(returns)),
        "worst_trade_return_pct": None if insufficient else round_pct(min(returns)),
        "average_win_pct": None if not winners else round_pct(mean(winners)),
        "average_loss_pct": None if not losers else round_pct(mean(losers)),
        "profit_factor": None if losses == 0 else round_pct(gains / losses),
        "total_realized_pnl": realized,
        "total_unrealized_pnl": unrealized,
        "max_drawdown_pct": max_drawdown(equity_points),
        "average_hold_days": None if insufficient else round_pct(mean([safe_float(trade.get("actual_hold_days", trade.get("days_held"))) for trade in closed_trades])),
        "status": "insufficient data" if insufficient else "ready",
    }


def bucket_stats(closed_trades: List[Dict[str, Any]], key: str, output_key: str) -> List[Dict[str, Any]]:
    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for trade in closed_trades:
        grouped.setdefault(trade.get(key, "Unknown"), []).append(trade)

    buckets = []
    for label, trades in grouped.items():
        returns = [safe_float(trade.get("realized_return_pct")) for trade in trades]
        buckets.append({
            output_key: label,
            "total_trades": len(trades),
            "win_rate_pct": round_pct((len([value for value in returns if value > 0]) / len(trades)) * 100),
            "average_return_pct": round_pct(mean(returns)),
            "total_realized_pnl": round_money(sum(safe_float(trade.get("realized_pnl")) for trade in trades)),
        })
    return buckets


def confidence_bucket(confidence: float) -> str:
    if confidence >= 85:
        return "85+"
    if confidence >= 70:
        return "70-84"
    if confidence >= 55:
        return "55-69"
    return "Under 55"


def performance_buckets(closed_trades: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    with_confidence = [
        {**trade, "confidence_bucket": confidence_bucket(safe_float(trade.get("entry_confidence", trade.get("original_confidence"))))}
        for trade in closed_trades
    ]
    return {
        "by_hold_period": bucket_stats(closed_trades, "planned_hold_period_days", "hold_period_days"),
        "by_action": bucket_stats(closed_trades, "entry_action", "action"),
        "by_market_regime": bucket_stats(closed_trades, "entry_market_regime", "market_regime"),
        "by_confidence_bucket": bucket_stats(with_confidence, "confidence_bucket", "bucket"),
        "by_sector": bucket_stats(closed_trades, "sector", "sector"),
    }


def file_base(generated_at: str, mock_data: bool = False) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "mock_data": mock_data,
        "data_source": DATA_SOURCE,
        "strategy": STRATEGY_METADATA,
        "research_metadata": RESEARCH_METADATA,
    }


def export_files(
    output_dir: Path,
    generated_at: str,
    as_of_date: str,
    source_file: Optional[str],
    open_positions: List[Dict[str, Any]],
    closed_trades: List[Dict[str, Any]],
    portfolio: Dict[str, Any],
    equity_points: List[Dict[str, Any]],
    price_data_status: str,
    source_market_date: str,
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    portfolio_with_drawdown = {**portfolio, "max_drawdown_pct": max_drawdown(equity_points) or 0.0}

    payloads = {
        "open_positions.json": {
            **file_base(generated_at),
            "source_file": source_file,
            "as_of_date": as_of_date,
            "source_market_date": source_market_date,
            "price_data_status": price_data_status,
            "stale_price_data": price_data_status != "fresh",
            "account": ACCOUNT,
            "positions": open_positions,
            "disclaimer": DISCLAIMER,
        },
        "closed_trades.json": {
            **file_base(generated_at),
            "source_file": source_file,
            "as_of_date": as_of_date,
            "source_market_date": source_market_date,
            "price_data_status": price_data_status,
            "stale_price_data": price_data_status != "fresh",
            "trades": closed_trades,
            "disclaimer": DISCLAIMER,
        },
        "portfolio_summary.json": {
            **file_base(generated_at),
            "source_file": source_file,
            "trade_date": as_of_date,
            "as_of_date": as_of_date,
            "source_market_date": source_market_date,
            "price_data_status": price_data_status,
            "stale_price_data": price_data_status != "fresh",
            "account": ACCOUNT,
            "summary": portfolio_with_drawdown,
            "disclaimer": DISCLAIMER,
        },
        "equity_curve.json": {
            **file_base(generated_at),
            "source_file": source_file,
            "source_market_date": source_market_date,
            "price_data_status": price_data_status,
            "stale_price_data": price_data_status != "fresh",
            "account": ACCOUNT,
            "points": equity_points,
            "disclaimer": DISCLAIMER,
        },
        "performance_statistics.json": {
            **file_base(generated_at),
            "source_file": source_file,
            "as_of_date": as_of_date,
            "source_market_date": source_market_date,
            "price_data_status": price_data_status,
            "stale_price_data": price_data_status != "fresh",
            "account": ACCOUNT,
            "overall": performance_stats(closed_trades, open_positions, equity_points),
            **performance_buckets(closed_trades),
            "disclaimer": DISCLAIMER,
        },
    }

    paths = {}
    for file_name, payload in payloads.items():
        path = output_dir / file_name
        atomic_write_json(path, payload)
        paths[file_name] = str(path)
    return paths


def process_paper_trading(
    daily_picks: Dict[str, Any],
    raw_rows: List[Dict[str, str]],
    output_dir: Path = Path("data/paper_trading"),
    state_dir: Path = Path("data/paper_trading/state"),
    config: Optional[Dict[str, float]] = None,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    generated_at = generated_at or now_iso()
    active_config = {**DEFAULT_CONFIG, **(config or {})}
    store = PaperTradingStore(state_dir)
    state = store.load()

    account = state["account"]
    open_ledger = state["open_positions"]
    closed_ledger = state["closed_trades"]
    processed = state["processed_picks"].setdefault("picks", {})
    equity_history = state["equity_history"]

    as_of_date = daily_picks.get("trade_date", generated_at[:10])
    market_regime = daily_picks.get("market_regime", {}).get("label", "Current")
    prices = ScannerPriceProvider(daily_picks, generated_at)
    price_data_status = "stale_price_data" if prices.stale_price_data else "fresh"
    raw_actions = raw_action_lookup(raw_rows, as_of_date)
    allocations = allocation_lookup(raw_rows)
    source_file = daily_picks.get("source_file")

    open_positions = open_ledger.setdefault("positions", [])
    closed_trades = closed_ledger.setdefault("trades", [])

    still_open = []
    for position in open_positions:
        update_position_price(position, prices.get_price(position["ticker"]), as_of_date, generated_at)
        reason = exit_reason(position)
        if reason:
            trade = close_position(position, generated_at, reason)
            closed_trades.append(trade)
            account["cash"] = round_money(safe_float(account.get("cash")) + trade["proceeds"])
            account["realized_pnl"] = round_money(safe_float(account.get("realized_pnl")) + trade["realized_pnl"])
        else:
            still_open.append(position)
    open_positions[:] = still_open

    open_tickers = {position["ticker"] for position in open_positions}
    open_pick_ids = {position["source_pick_id"] for position in open_positions}
    closed_trade_ids = {trade["trade_id"] for trade in closed_trades}
    available_cash = safe_float(account.get("cash", STARTING_CAPITAL))
    minimum_cash = STARTING_CAPITAL * (safe_float(active_config["minimum_cash_reserve_pct"]) / 100)

    for pick in daily_picks.get("picks", []):
        pick_id = pick.get("pick_id")
        ticker = pick.get("ticker")
        if not pick_id or not ticker:
            continue
        if pick_id in processed:
            continue
        if pick_id in open_pick_ids or stable_trade_id(pick) in closed_trade_ids or ticker in open_tickers:
            processed[pick_id] = {
                "status": "skipped_duplicate",
                "ticker": ticker,
                "processed_at": generated_at,
                "reason": "Ticker or pick already exists in the paper ledger.",
            }
            continue

        raw_action = raw_actions.get(pick_id, str(pick.get("action", "")).upper())
        if raw_action != "BUY":
            processed[pick_id] = {
                "status": "skipped_not_buy",
                "ticker": ticker,
                "processed_at": generated_at,
                "action": raw_action,
                "reason": "Only scanner BUY actions open paper positions.",
            }
            continue

        if len(open_positions) >= safe_int(active_config["max_positions"]):
            processed[pick_id] = {
                "status": "skipped_max_positions",
                "ticker": ticker,
                "processed_at": generated_at,
                "reason": "Maximum open paper positions reached.",
            }
            continue

        price = prices.get_price(ticker)
        if not price:
            processed[pick_id] = {
                "status": "skipped_missing_price",
                "ticker": ticker,
                "processed_at": generated_at,
                "reason": "No valid current price was available from scanner output.",
            }
            continue

        if price.get("stale_price_data"):
            processed[pick_id] = {
                "status": "skipped_stale_price",
                "ticker": ticker,
                "processed_at": generated_at,
                "source_market_date": price.get("source_market_date"),
                "price_data_status": price.get("price_data_status"),
                "reason": "Scanner latest_close is stale relative to the paper-engine run date.",
            }
            continue

        allocation_pct = allocations.get(ticker, 100 / max(safe_int(active_config["max_positions"]), 1))
        allocation_pct = min(allocation_pct, safe_float(active_config["max_position_pct"]))
        target_notional = STARTING_CAPITAL * (allocation_pct / 100)
        spendable_cash = max(available_cash - minimum_cash, 0)
        notional = min(target_notional, spendable_cash)
        quantity = int(notional // safe_float(price["price"]))

        if quantity <= 0:
            processed[pick_id] = {
                "status": "skipped_insufficient_cash",
                "ticker": ticker,
                "processed_at": generated_at,
                "reason": "Available cash was insufficient for one whole share while preserving reserve.",
            }
            continue

        position = build_open_position(pick, price, quantity, generated_at, market_regime, active_config)
        open_positions.append(position)
        available_cash = round_money(available_cash - position["cost_basis"])
        account["cash"] = available_cash
        open_tickers.add(ticker)
        open_pick_ids.add(pick_id)
        processed[pick_id] = {
            "status": "opened",
            "ticker": ticker,
            "trade_id": position["trade_id"],
            "processed_at": generated_at,
            "price": price["price"],
            "price_source": price["source"],
        }

    account["updated_at"] = generated_at
    portfolio = calculate_portfolio(account, open_positions, closed_trades)
    upsert_equity_point(equity_history, portfolio, as_of_date, source_file, price_data_status)

    store.save(state)

    paths = export_files(
        output_dir,
        generated_at,
        as_of_date,
        source_file,
        open_positions,
        closed_trades,
        portfolio,
        equity_history.get("points", []),
        price_data_status,
        as_of_date,
    )

    return {
        "state_dir": str(state_dir),
        "output_dir": str(output_dir),
        "as_of_date": as_of_date,
        "open_positions": len(open_positions),
        "closed_trades": len(closed_trades),
        "price_data_status": price_data_status,
        "source_market_date": as_of_date,
        "paths": paths,
    }


__all__ = [
    "DEFAULT_CONFIG",
    "PaperTradingStateError",
    "PaperTradingStore",
    "ScannerPriceProvider",
    "is_stale_source_date",
    "process_paper_trading",
]
