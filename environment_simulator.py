from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple

from trading_environment import (
    SCHEMA_VERSION,
    builtin_presets,
    deep_merge,
    environment_from_overrides,
    validate_environment,
)


DISCLAIMER = (
    "Trading Environment Simulator is research software only. It replays historical "
    "strategy trade streams under configurable paper rules. It does not modify V8 or "
    "V9, place trades, connect to brokers, or provide investment advice."
)

DEFAULT_TRADE_STREAM = Path("reports/balanced_v8_vs_v9_trades.csv")
DEFAULT_OUTPUT_DIR = Path("data/strategy_lab")
STRATEGY_ALIASES = {
    "V8": "V8_CHAMPION",
    "V8_CHAMPION": "V8_CHAMPION",
    "V9": "V9_DEFENSIVE",
    "V9_DEFENSIVE": "V9_DEFENSIVE",
}


@dataclass(frozen=True)
class TradeCandidate:
    strategy: str
    entry_date: date
    exit_date: date
    ticker: str
    sector: str
    entry_value: float
    exit_value: float
    return_pct: float
    raw_return_pct: float
    weight: float
    source_row: int


@dataclass
class OpenPosition:
    trade: TradeCandidate
    entry_notional: float
    exit_notional: float
    fees_paid: float


@dataclass
class SimulationState:
    cash: float
    starting_capital: float
    open_positions: List[OpenPosition] = field(default_factory=list)
    closed_trades: List[Dict[str, Any]] = field(default_factory=list)
    missed_opportunities: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    peak_equity: float = 0.0
    previous_equity: float = 0.0
    current_day_entries: int = 0
    current_day_trades: int = 0


def parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def load_trade_stream(path: Path, strategy: str) -> List[TradeCandidate]:
    if not path.exists():
        raise FileNotFoundError(f"Trade stream not found: {path}")
    canonical = STRATEGY_ALIASES.get(strategy, strategy)
    candidates: List[TradeCandidate] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "strategy",
            "entry_date",
            "exit_date",
            "ticker",
            "sector",
            "entry_value",
            "exit_value",
            "return_pct",
            "raw_return_pct",
            "weight",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Trade stream is missing columns: {sorted(missing)}")
        for index, row in enumerate(reader, start=2):
            if row.get("strategy") != canonical:
                continue
            candidates.append(
                TradeCandidate(
                    strategy=row["strategy"],
                    entry_date=parse_date(row["entry_date"]),
                    exit_date=parse_date(row["exit_date"]),
                    ticker=row["ticker"],
                    sector=row.get("sector") or "Unknown",
                    entry_value=float(row.get("entry_value") or 0),
                    exit_value=float(row.get("exit_value") or 0),
                    return_pct=float(row.get("return_pct") or 0),
                    raw_return_pct=float(row.get("raw_return_pct") or 0),
                    weight=float(row.get("weight") or 1),
                    source_row=index,
                )
            )
    candidates.sort(key=lambda trade: (trade.entry_date, trade.exit_date, trade.ticker))
    return candidates


def resolve_preset(environment_id: str) -> Dict[str, Any]:
    for preset in builtin_presets():
        if preset["environment_id"] == environment_id:
            return preset
    raise ValueError(f"Unknown environment preset: {environment_id}")


def trade_source_metadata(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def _round(value: float, digits: int = 2) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(value, digits)


def _date_range(candidates: Iterable[TradeCandidate]) -> List[date]:
    dates = sorted({d for trade in candidates for d in (trade.entry_date, trade.exit_date)})
    return dates


def _contains_weekend(start: date, end: date) -> bool:
    days = (end - start).days
    return any(date.fromordinal(start.toordinal() + offset).weekday() >= 5 for offset in range(days + 1))


def _fee(notional: float, account: Dict[str, Any]) -> float:
    fixed = float(account.get("fixed_transaction_fee") or 0)
    pct = float(account.get("percentage_transaction_fee_pct") or 0) / 100
    return fixed + (notional * pct)


def _position_size(cash: float, equity: float, account: Dict[str, Any], overrides: Dict[str, Any]) -> float:
    reserve = float(account.get("minimum_cash_reserve_pct") or 0) / 100
    max_allocation = float(account.get("maximum_position_allocation_pct") or 0) / 100
    fixed_size = overrides.get("fixed_dollar_sizing")
    target = float(fixed_size) if fixed_size else equity * max_allocation
    available = max(0.0, cash - (equity * reserve))
    return max(0.0, min(target, available))


def _open_notional(open_positions: List[OpenPosition]) -> float:
    return sum(position.entry_notional for position in open_positions)


def _current_equity(state: SimulationState) -> float:
    return state.cash + _open_notional(state.open_positions)


def _record_violation(state: SimulationState, day: date, rule: str, message: str, severity: str = "warning") -> None:
    state.violations.append(
        {"date": day.isoformat(), "rule": rule, "severity": severity, "message": message}
    )
    state.timeline.append(
        {"date": day.isoformat(), "type": "rule_violation", "label": rule, "detail": message}
    )


def _miss(state: SimulationState, trade: TradeCandidate, reason: str, detail: str) -> None:
    state.missed_opportunities.append(
        {
            "date": trade.entry_date.isoformat(),
            "ticker": trade.ticker,
            "sector": trade.sector,
            "reason": reason,
            "detail": detail,
            "return_pct": trade.return_pct,
            "source_row": trade.source_row,
        }
    )


def run_environment_simulation(
    environment: Dict[str, Any] | None = None,
    *,
    preset_id: str | None = None,
    strategy: str = "V8",
    trade_stream_path: Path | str = DEFAULT_TRADE_STREAM,
) -> Dict[str, Any]:
    trade_stream = Path(trade_stream_path)
    if preset_id:
        base_environment = resolve_preset(preset_id)
        environment_config = environment_from_overrides(base_environment)
        if environment:
            environment_config = deep_merge(environment_config, environment)
    else:
        environment_config = environment_from_overrides(environment)

    errors, warnings = validate_environment(environment_config)
    if errors:
        raise ValueError("; ".join(errors))

    candidates = load_trade_stream(trade_stream, strategy)
    account = environment_config["account_rules"]
    risk = environment_config["risk_limits"]
    restrictions = environment_config["trading_restrictions"]
    consistency = environment_config["consistency_rules"]
    targets = environment_config["targets"]
    overrides = environment_config["execution_overrides"]
    starting_capital = float(account["starting_capital"])
    state = SimulationState(cash=starting_capital, starting_capital=starting_capital)
    state.peak_equity = starting_capital
    state.previous_equity = starting_capital
    dates = _date_range(candidates)

    by_entry: Dict[date, List[TradeCandidate]] = {}
    for trade in candidates:
        by_entry.setdefault(trade.entry_date, []).append(trade)

    for day in dates:
        state.current_day_entries = 0
        state.current_day_trades = 0

        exiting = [position for position in state.open_positions if position.trade.exit_date <= day]
        for position in exiting:
            state.open_positions.remove(position)
            trade = position.trade
            exit_fee = _fee(position.exit_notional, account)
            proceeds = max(0.0, position.exit_notional - exit_fee)
            state.cash += proceeds
            pnl = proceeds - position.entry_notional - position.fees_paid
            state.closed_trades.append(
                {
                    "ticker": trade.ticker,
                    "sector": trade.sector,
                    "entry_date": trade.entry_date.isoformat(),
                    "exit_date": day.isoformat(),
                    "return_pct": _round((pnl / position.entry_notional) * 100 if position.entry_notional else 0),
                    "raw_return_pct": trade.raw_return_pct,
                    "entry_notional": _round(position.entry_notional),
                    "exit_notional": _round(proceeds),
                    "pnl": _round(pnl),
                    "source_row": trade.source_row,
                }
            )
            state.timeline.append(
                {
                    "date": day.isoformat(),
                    "type": "exit",
                    "ticker": trade.ticker,
                    "pnl": _round(pnl),
                    "return_pct": _round((pnl / position.entry_notional) * 100 if position.entry_notional else 0),
                }
            )

        equity_before_entries = _current_equity(state)
        for trade in by_entry.get(day, []):
            if restrictions.get("long_only") is False:
                _miss(state, trade, "unsupported_direction", "Only long replay streams are available.")
                continue
            if trade.ticker in set(restrictions.get("restricted_tickers") or []):
                _miss(state, trade, "restricted_ticker", "Ticker is restricted in this environment.")
                continue
            if not restrictions.get("overnight_holding_allowed", True) and trade.exit_date > trade.entry_date:
                _miss(state, trade, "overnight_not_allowed", "Trade requires an overnight hold.")
                continue
            if not restrictions.get("weekend_holding_allowed", True) and _contains_weekend(trade.entry_date, trade.exit_date):
                _miss(state, trade, "weekend_not_allowed", "Trade would be held across a weekend.")
                continue
            if state.current_day_entries >= int(restrictions.get("maximum_new_positions_per_day") or 999999):
                _miss(state, trade, "daily_entry_limit", "Daily new-position limit reached.")
                continue
            if state.current_day_trades >= int(restrictions.get("maximum_trades_per_day") or 999999):
                _miss(state, trade, "daily_trade_limit", "Daily trade limit reached.")
                continue
            if len(state.open_positions) >= int(account.get("maximum_open_positions") or 999999):
                _miss(state, trade, "max_open_positions", "Maximum open positions reached.")
                continue
            if any(position.trade.ticker == trade.ticker for position in state.open_positions):
                _miss(state, trade, "duplicate_ticker", "Ticker already open in this simulated account.")
                continue

            equity = _current_equity(state)
            max_invested = equity * (float(account.get("maximum_invested_pct") or 100) / 100)
            if _open_notional(state.open_positions) >= max_invested:
                _miss(state, trade, "maximum_invested", "Maximum invested percentage reached.")
                continue

            sector_limit = equity * (float(risk.get("maximum_sector_exposure_pct") or 100) / 100)
            current_sector = sum(
                pos.entry_notional for pos in state.open_positions if pos.trade.sector == trade.sector
            )
            notional = _position_size(state.cash, equity, account, overrides)
            notional = min(notional, max(0.0, max_invested - _open_notional(state.open_positions)))
            notional = min(notional, max(0.0, sector_limit - current_sector))
            if notional <= 0:
                _miss(state, trade, "insufficient_buying_power", "No buying power remained after reserves and caps.")
                continue

            slippage = float(account.get("slippage_pct") or 0)
            adjusted_return_pct = trade.return_pct - (slippage * 2)
            stop_loss = overrides.get("stop_loss_override_pct")
            take_profit = overrides.get("take_profit_override_pct")
            if stop_loss is not None:
                adjusted_return_pct = max(adjusted_return_pct, -abs(float(stop_loss)))
            if take_profit is not None:
                adjusted_return_pct = min(adjusted_return_pct, abs(float(take_profit)))

            entry_fee = _fee(notional, account)
            if notional + entry_fee > state.cash:
                notional = max(0.0, state.cash - entry_fee)
            if notional <= 0:
                _miss(state, trade, "insufficient_cash", "Cash reserve prevented the entry.")
                continue

            state.cash -= notional + entry_fee
            exit_notional = notional * (1 + adjusted_return_pct / 100)
            state.open_positions.append(OpenPosition(trade=trade, entry_notional=notional, exit_notional=exit_notional, fees_paid=entry_fee))
            state.current_day_entries += 1
            state.current_day_trades += 1
            state.timeline.append(
                {
                    "date": day.isoformat(),
                    "type": "entry",
                    "ticker": trade.ticker,
                    "sector": trade.sector,
                    "notional": _round(notional),
                    "planned_exit_date": trade.exit_date.isoformat(),
                    "source_row": trade.source_row,
                }
            )

        equity = _current_equity(state)
        state.peak_equity = max(state.peak_equity, equity)
        daily_loss_pct = ((equity - state.previous_equity) / state.previous_equity * 100) if state.previous_equity else 0
        drawdown_pct = ((state.peak_equity - equity) / state.peak_equity * 100) if state.peak_equity else 0
        if daily_loss_pct < -abs(float(risk.get("daily_loss_limit_pct") or 100)):
            _record_violation(state, day, "daily_loss_limit", "Daily loss limit breached.", "failure")
        if drawdown_pct > float(risk.get("overall_max_drawdown_pct") or 100):
            _record_violation(state, day, "overall_drawdown", "Overall maximum drawdown breached.", "failure")
        trailing_amount = float(risk.get("trailing_drawdown_amount") or 0)
        if trailing_amount and state.peak_equity - equity > trailing_amount:
            _record_violation(state, day, "trailing_drawdown", "Trailing drawdown amount breached.", "failure")
        state.equity_curve.append(
            {
                "date": day.isoformat(),
                "equity": _round(equity),
                "cash": _round(state.cash),
                "open_positions": len(state.open_positions),
                "drawdown_pct": _round(drawdown_pct),
            }
        )
        state.previous_equity = equity

    final_equity = _current_equity(state)
    wins = [trade for trade in state.closed_trades if trade["pnl"] > 0]
    losses = [trade for trade in state.closed_trades if trade["pnl"] < 0]
    gross_profit = sum(trade["pnl"] for trade in wins)
    gross_loss = abs(sum(trade["pnl"] for trade in losses))
    daily_returns = []
    previous = starting_capital
    for point in state.equity_curve:
        daily_returns.append(((point["equity"] - previous) / previous) * 100 if previous else 0)
        previous = point["equity"]
    best_day_profit = max(daily_returns) if daily_returns else 0
    total_profit = final_equity - starting_capital
    largest_trade_profit = max((trade["pnl"] for trade in state.closed_trades), default=0)
    max_drawdown = max((point["drawdown_pct"] for point in state.equity_curve), default=0)
    consistency_violations = []
    if total_profit > 0 and largest_trade_profit / total_profit * 100 > float(consistency.get("maximum_profit_from_one_trade_pct") or 100):
        consistency_violations.append("maximum_profit_from_one_trade")
    if total_profit > 0 and best_day_profit / max(total_profit / starting_capital * 100, 0.0001) * 100 > float(consistency.get("maximum_profit_from_one_day_pct") or 100):
        consistency_violations.append("maximum_profit_from_one_day")

    rule_results = [
        {"rule": "profit_target", "status": "passed" if total_profit >= float(targets.get("profit_target_dollars") or 0) else "not_met"},
        {"rule": "overall_drawdown", "status": "failed" if any(v["rule"] == "overall_drawdown" for v in state.violations) else "passed"},
        {"rule": "daily_loss_limit", "status": "failed" if any(v["rule"] == "daily_loss_limit" for v in state.violations) else "passed"},
        {"rule": "trailing_drawdown", "status": "failed" if any(v["rule"] == "trailing_drawdown" for v in state.violations) else "passed"},
        {"rule": "consistency", "status": "failed" if consistency_violations else "passed"},
        {"rule": "minimum_trading_days", "status": "passed" if len(state.equity_curve) >= int(consistency.get("minimum_trading_days") or 0) else "not_met"},
    ]
    pass_fail = "failed" if any(rule["status"] == "failed" for rule in rule_results) else "passed"
    if any(rule["status"] == "not_met" for rule in rule_results):
        pass_fail = "in_progress"

    metrics = {
        "starting_capital": _round(starting_capital),
        "ending_equity": _round(final_equity),
        "total_return_pct": _round((final_equity - starting_capital) / starting_capital * 100 if starting_capital else 0),
        "net_profit": _round(total_profit),
        "max_drawdown_pct": _round(max_drawdown),
        "trades_taken": len(state.closed_trades),
        "opportunities_seen": len(candidates),
        "missed_opportunities": len(state.missed_opportunities),
        "win_rate_pct": _round(len(wins) / len(state.closed_trades) * 100 if state.closed_trades else 0),
        "profit_factor": _round(gross_profit / gross_loss if gross_loss else (999.0 if gross_profit else 0.0)),
        "average_trade_return_pct": _round(sum(t["return_pct"] for t in state.closed_trades) / len(state.closed_trades) if state.closed_trades else 0),
        "median_trade_return_pct": _round(median([t["return_pct"] for t in state.closed_trades]) if state.closed_trades else 0),
        "days_simulated": len(state.equity_curve),
        "target_progress_pct": _round(total_profit / float(targets.get("profit_target_dollars") or 1) * 100),
    }
    assumptions = [
        "Simulation consumes deterministic historical trade streams and does not call strategy logic.",
        "Open-position mark-to-market is event-based because the selected stream has entry and exit values, not daily price paths.",
        "Intraday drawdown, liquidity, and exact whole-share behavior are not inferred when source data lacks those fields.",
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "simulation_id": simulation_id(environment_config, strategy, trade_stream),
        "mode": "historical_replay",
        "disclaimer": DISCLAIMER,
        "strategy": {
            "name": "V8" if STRATEGY_ALIASES.get(strategy, strategy) == "V8_CHAMPION" else "V9",
            "source_label": STRATEGY_ALIASES.get(strategy, strategy),
            "status": "Champion" if STRATEGY_ALIASES.get(strategy, strategy) == "V8_CHAMPION" else "Experimental",
        },
        "environment": environment_config,
        "trade_stream": trade_source_metadata(trade_stream),
        "validation": {"errors": errors, "warnings": warnings},
        "accounting": {
            "cash": _round(state.cash),
            "open_notional": _round(_open_notional(state.open_positions)),
            "closed_trade_count": len(state.closed_trades),
            "open_position_count": len(state.open_positions),
        },
        "metrics": metrics,
        "rule_results": rule_results,
        "pass_fail": pass_fail,
        "equity_curve": state.equity_curve,
        "timeline": state.timeline[:500],
        "closed_trades": state.closed_trades[:500],
        "missed_opportunities": state.missed_opportunities[:500],
        "violations": state.violations,
        "assumptions": assumptions,
    }
    return payload


def simulation_id(environment: Dict[str, Any], strategy: str, trade_stream: Path) -> str:
    material = {
        "environment": environment,
        "strategy": strategy,
        "trade_stream": trade_source_metadata(trade_stream) if trade_stream.exists() else {"path": str(trade_stream)},
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"sim_{digest[:16]}"


def save_simulation_result(result: Dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{result['simulation_id']}.json"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    latest_path = output_dir / "latest_result.json"
    latest_tmp = latest_path.with_suffix(".tmp")
    latest_tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_tmp.replace(latest_path)
    return path


def run_comparison(
    preset_ids: List[str],
    *,
    strategy: str = "V8",
    trade_stream_path: Path | str = DEFAULT_TRADE_STREAM,
) -> Dict[str, Any]:
    results = [run_environment_simulation(preset_id=preset_id, strategy=strategy, trade_stream_path=trade_stream_path) for preset_id in preset_ids]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "mode": "environment_comparison",
        "results": [
            {
                "environment_id": result["environment"]["environment_id"],
                "name": result["environment"]["name"],
                "pass_fail": result["pass_fail"],
                "metrics": result["metrics"],
            }
            for result in results
        ],
    }


def run_sensitivity(
    base_environment: Dict[str, Any],
    parameter_path: str,
    values: List[float],
    *,
    strategy: str = "V8",
    trade_stream_path: Path | str = DEFAULT_TRADE_STREAM,
) -> Dict[str, Any]:
    output = []
    keys = parameter_path.split(".")
    for value in values:
        candidate = environment_from_overrides(base_environment)
        cursor = candidate
        for key in keys[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[keys[-1]] = value
        result = run_environment_simulation(environment=candidate, strategy=strategy, trade_stream_path=trade_stream_path)
        output.append({"value": value, "metrics": result["metrics"], "pass_fail": result["pass_fail"]})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "mode": "sensitivity_analysis",
        "parameter": parameter_path,
        "results": output,
    }
