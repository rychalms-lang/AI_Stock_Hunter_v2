import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from paper_trading_engine import process_paper_trading
from portfolio import build_portfolio
from scanner_status import latest_valid_report as find_latest_valid_report
from scanner_status import report_validation


REPORTS_DIR = Path("reports")
DATA_DIR = Path("data")
PAPER_TRADING_DIR = DATA_DIR / "paper_trading"

SCHEMA_VERSION = "1.0"
STARTING_CAPITAL = 25000.0
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
    "generated_from": "daily_scanner",
}

DATA_SOURCE = {
    "type": "scanner_export",
    "generated_by": "paper_trading_exporter",
    "generator_version": "1.0",
}


def latest_report() -> Path:
    report = find_latest_valid_report(REPORTS_DIR)

    if not report:
        raise FileNotFoundError("No valid report CSV found in reports/.")

    return report


def trade_date_from_report(report_file: Path) -> str:
    return report_file.name.replace("_v2.csv", "")


def read_report_rows(report_file: Path) -> List[Dict[str, str]]:
    validation = report_validation(report_file)
    if not validation["valid"]:
        raise ValueError(f"{report_file} is invalid: {validation['reason']}")

    with report_file.open(newline="") as f:
        return list(csv.DictReader(f))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        text = str(value).strip()

        if text == "" or text.lower() in ["nan", "none", "n/a"]:
            return default

        return float(text)

    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(safe_float(value, default)))
    except Exception:
        return default


def parse_list_field(value: Any) -> List[str]:
    if value is None:
        return []

    text = str(value).strip()

    if not text or text.lower() in ["nan", "none", "[]"]:
        return []

    try:
        parsed = json.loads(text.replace("'", '"'))
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except Exception:
        pass

    return [
        item.strip()
        for item in text.strip("[]").split(",")
        if item.strip()
    ]


def parse_hold_period(value: Any) -> int:
    text = str(value or "").strip()
    digits = "".join(char for char in text if char.isdigit())
    return int(digits) if digits else 0


def display_action(action: str) -> str:
    if action == "BUY":
        return "REVIEW"

    return action or "WATCH"


def pick_id(trade_date: str, ticker: str) -> str:
    return f"{trade_date}_{ticker.upper()}"


def evidence_explanation(row: Dict[str, str]) -> Dict[str, Any]:
    ticker = row.get("ticker", "UNKNOWN").upper()
    confidence = safe_float(row.get("confidence_score", row.get("confidence")))
    relative_strength = safe_float(row.get("relative_strength"))
    best_avg_return = safe_float(row.get("best_avg_return", row.get("expected_return")))
    historical_matches = safe_int(row.get("historical_matches"))
    risk = row.get("risk", "Medium")

    strengths = []
    risks = []

    if confidence >= 80:
        strengths.append(f"Confidence is high at {confidence:.0f}%.")
    elif confidence >= 65:
        strengths.append(f"Confidence is constructive at {confidence:.0f}%.")
    else:
        risks.append(f"Confidence is modest at {confidence:.0f}%.")

    if relative_strength > 0:
        strengths.append(f"Relative strength is positive at {relative_strength:.2f}%.")
    else:
        risks.append(f"Relative strength is weak at {relative_strength:.2f}%.")

    if best_avg_return > 0:
        strengths.append(f"Historical average return evidence is positive at {best_avg_return:.2f}%.")
    else:
        risks.append(f"Historical average return evidence is weak at {best_avg_return:.2f}%.")

    if historical_matches >= 100:
        strengths.append(f"{historical_matches} similar historical setups were found.")
    elif historical_matches >= 25:
        strengths.append(f"{historical_matches} comparable historical setups were found.")
    else:
        risks.append(f"Historical sample size is limited at {historical_matches} matches.")

    if risk == "High":
        risks.append("Risk label is High.")
    elif risk == "Medium":
        risks.append("Risk label is Medium.")

    if not strengths:
        strengths.append("The setup passed the daily scanner filters.")

    return {
        "summary": (
            f"{ticker} is included from the daily scanner because the current "
            "setup has measurable scanner, confidence, and historical evidence."
        ),
        "strengths": strengths,
        "risks": risks,
        "similar_historical_cases": [
            {
                "label": "Comparable scanner setups",
                "count": historical_matches,
                "average_return_pct": round(best_avg_return, 2),
                "win_rate_pct": round(
                    max(
                        safe_float(row.get("pattern_1d_win_rate")),
                        safe_float(row.get("pattern_3d_win_rate")),
                        safe_float(row.get("pattern_5d_win_rate")),
                        safe_float(row.get("pattern_7d_win_rate")),
                        safe_float(row.get("pattern_10d_win_rate")),
                    ),
                    2,
                ),
            }
        ],
    }


def build_daily_pick(row: Dict[str, str], trade_date: str, rank: int) -> Dict[str, Any]:
    ticker = row.get("ticker", "UNKNOWN").upper()
    action = display_action(row.get("action", "WATCH"))
    confidence = safe_float(row.get("confidence_score", row.get("confidence")))

    return {
        "pick_id": pick_id(trade_date, ticker),
        "trade_date": trade_date,
        "ticker": ticker,
        "company_name": None,
        "sector": row.get("sector", "Other / Uncategorized"),
        "sector_rank": safe_int(row.get("sector_rank")),
        "rank": rank,
        "action": action,
        "score": round(safe_float(row.get("score", row.get("pre_score"))), 2),
        "confidence": round(confidence, 1),
        "risk": row.get("risk", "Medium"),
        "expected_return_pct": round(
            safe_float(row.get("best_avg_return", row.get("expected_return"))),
            2,
        ),
        "win_probability_pct": round(safe_float(row.get("win_probability")), 1),
        "best_hold_period_days": parse_hold_period(row.get("best_hold_period")),
        "historical_matches": safe_int(row.get("historical_matches")),
        "historical_best_avg_return_pct": round(safe_float(row.get("best_avg_return")), 2),
        "latest_open": round(safe_float(row.get("latest_open")), 2),
        "latest_close": round(safe_float(row.get("latest_close")), 2),
        "five_day_change_pct": round(safe_float(row.get("five_day_change")), 2),
        "twenty_day_change_pct": round(safe_float(row.get("twenty_day_change")), 2),
        "relative_strength_pct": round(safe_float(row.get("relative_strength")), 2),
        "volume_ratio": round(safe_float(row.get("volume_ratio")), 2),
        "paper_trade_candidate": action in ["REVIEW", "WATCH"],
        "paper_trade_decision": (
            "eligible_scanner_export"
            if action == "REVIEW"
            else "watch_scanner_export"
        ),
        "paper_trade_decision_reason": (
            "Generated from the latest daily scanner CSV. No real order was placed."
        ),
        "strategy": STRATEGY_METADATA,
        "research_metadata": RESEARCH_METADATA,
        "ai_explanation": evidence_explanation(row),
        "confidence_reasons": parse_list_field(row.get("confidence_reasons")),
        "risk_flags": parse_list_field(row.get("risk_flags")),
    }


def build_daily_picks_file(
    rows: List[Dict[str, str]],
    report_file: Path,
    generated_at: str,
) -> Dict[str, Any]:
    trade_date = trade_date_from_report(report_file)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_file": str(report_file),
        "trade_date": trade_date,
        "mock_data": False,
        "data_source": DATA_SOURCE,
        "strategy": STRATEGY_METADATA,
        "research_metadata": RESEARCH_METADATA,
        "market_regime": {
            "label": "Current",
            "score": 0.0,
            "description": "Daily scanner export. Full market regime is generated by the main scanner run.",
        },
        "picks": [
            build_daily_pick(row, trade_date, rank)
            for rank, row in enumerate(rows, start=1)
        ],
        "disclaimer": DISCLAIMER,
    }


def rows_for_portfolio(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    stocks = []

    for row in rows:
        stocks.append({
            "ticker": row.get("ticker", "UNKNOWN").upper(),
            "sector": row.get("sector", "Other / Uncategorized"),
            "confidence_score": safe_float(row.get("confidence_score", row.get("confidence")), 50),
            "score": safe_float(row.get("score", row.get("pre_score"))),
            "risk": row.get("risk", "Medium"),
        })

    return stocks


def group_exposure(
    positions: List[Dict[str, Any]],
    key: str,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for position in positions:
        label = position.get(key, "Unknown")
        allocation = safe_float(position.get("allocation_pct"))

        if label not in grouped:
            grouped[label] = {
                key: label,
                "value": 0.0,
                "portfolio_pct": 0.0,
                "position_count": 0,
            }

        grouped[label]["portfolio_pct"] += allocation
        grouped[label]["position_count"] += 1

    for item in grouped.values():
        item["portfolio_pct"] = round(item["portfolio_pct"], 2)
        item["value"] = round((STARTING_CAPITAL * item["portfolio_pct"]) / 100, 2)

    return list(grouped.values())


def build_portfolio_summary_file(
    rows: List[Dict[str, str]],
    report_file: Path,
    generated_at: str,
) -> Dict[str, Any]:
    trade_date = trade_date_from_report(report_file)
    portfolio = build_portfolio(rows_for_portfolio(rows))
    positions = portfolio.get("positions", [])

    cash_pct = safe_float(portfolio.get("cash_allocation"), 100)
    invested_pct = round(100 - cash_pct, 2)
    cash = round((STARTING_CAPITAL * cash_pct) / 100, 2)
    invested_value = round((STARTING_CAPITAL * invested_pct) / 100, 2)

    risk_lookup = {
        row.get("ticker", "UNKNOWN").upper(): row.get("risk", "Medium")
        for row in rows
    }

    positions_with_risk = [
        {
            **position,
            "risk": risk_lookup.get(position.get("ticker", "UNKNOWN"), "Medium"),
        }
        for position in positions
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_file": str(report_file),
        "trade_date": trade_date,
        "as_of_date": trade_date,
        "mock_data": False,
        "data_source": DATA_SOURCE,
        "strategy": STRATEGY_METADATA,
        "research_metadata": RESEARCH_METADATA,
        "account": {
            "account_id": "paper_default",
            "mode": "paper_only",
            "starting_capital": STARTING_CAPITAL,
            "currency": "USD",
        },
        "summary": {
            "cash": cash,
            "invested_value": invested_value,
            "total_equity": STARTING_CAPITAL,
            "open_positions_count": len(positions),
            "closed_trades_count": 0,
            "cash_pct": round(cash_pct, 2),
            "invested_pct": invested_pct,
            "total_return_pct": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "day_pnl": 0.0,
            "day_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "largest_position_pct": round(
                max(
                    [safe_float(position.get("allocation_pct")) for position in positions]
                    or [0.0]
                ),
                2,
            ),
            "sector_exposure": group_exposure(positions, "sector"),
            "risk_exposure": group_exposure(positions_with_risk, "risk"),
            "positions": positions_with_risk,
            "notes": (
                "Allocations are generated from portfolio.py. P/L and position "
                "lifecycle fields remain zero until the paper trading ledger is implemented."
            ),
        },
        "disclaimer": DISCLAIMER,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def export_paper_trading_snapshot(report_file: Optional[Path] = None) -> Dict[str, Any]:
    report = report_file or latest_report()
    rows = read_report_rows(report)

    generated_at = datetime.now().isoformat(timespec="seconds")

    daily_picks = build_daily_picks_file(rows, report, generated_at)

    write_json(PAPER_TRADING_DIR / "daily_picks.json", daily_picks)
    engine_result = process_paper_trading(
        daily_picks=daily_picks,
        raw_rows=rows,
        output_dir=PAPER_TRADING_DIR,
        state_dir=PAPER_TRADING_DIR / "state",
        generated_at=generated_at,
    )

    return {
        "daily_picks": str(PAPER_TRADING_DIR / "daily_picks.json"),
        "open_positions": str(PAPER_TRADING_DIR / "open_positions.json"),
        "closed_trades": str(PAPER_TRADING_DIR / "closed_trades.json"),
        "portfolio_summary": str(PAPER_TRADING_DIR / "portfolio_summary.json"),
        "equity_curve": str(PAPER_TRADING_DIR / "equity_curve.json"),
        "performance_statistics": str(PAPER_TRADING_DIR / "performance_statistics.json"),
        "source_file": str(report),
        "trade_date": trade_date_from_report(report),
        "engine": engine_result,
    }


if __name__ == "__main__":
    result = export_paper_trading_snapshot()
    print(
        "Paper trading JSON written: "
        f"{result['daily_picks']} and {result['portfolio_summary']}"
    )
