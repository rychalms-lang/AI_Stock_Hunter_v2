import os
import smtplib
import sys
import argparse
import pandas as pd
from datetime import datetime
from email.message import EmailMessage
from dotenv import dotenv_values

from settings import AI_CANDIDATE_LIMIT, REPORTS_DIR, PERFORMANCE_DIR
from scanner import scan_market_with_health
from market_regime import get_market_regime
from sector_strength import rank_sectors
from sector_strength import SECTOR_ETFS
from sector_map import get_sector
from confidence import calculate_confidence
from portfolio import build_portfolio
from reporter import create_text_report, create_html_report
from pattern_learning import analyze_pattern
from scanner_status import (
    MIN_DATA_COVERAGE_PCT,
    MANUAL_TEST_REPORTS_DIR,
    iso_now,
    latest_valid_report,
    reconcile_status,
    scanner_failure_reason,
    write_failure_artifact,
    write_status,
)


config = dotenv_values(".env")

EMAIL_ADDRESS = config.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = config.get("EMAIL_PASSWORD")

REPORT_COLUMNS = [
    "ticker",
    "latest_open",
    "latest_close",
    "open_to_close_change",
    "five_day_change",
    "twenty_day_change",
    "relative_strength",
    "avg_volume",
    "volume_ratio",
    "pre_score",
    "expected_return",
    "win_probability",
    "confidence",
    "risk",
    "action",
    "reason",
    "sector",
    "sector_rank",
    "sentiment_score",
    "sentiment_label",
    "analysis_brief",
    "confidence_score",
    "confidence_reasons",
    "risk_flags",
    "historical_matches",
    "best_hold_period",
    "best_avg_return",
    "historical_summary",
    "pattern_1d_avg_return",
    "pattern_3d_avg_return",
    "pattern_5d_avg_return",
    "pattern_7d_avg_return",
    "pattern_10d_avg_return",
    "pattern_1d_win_rate",
    "pattern_3d_win_rate",
    "pattern_5d_win_rate",
    "pattern_7d_win_rate",
    "pattern_10d_win_rate",
    "score",
]


def market_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def is_trading_weekday() -> bool:
    return datetime.now().isoweekday() <= 5


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run AI Stock Hunter scanner pipeline.")
    parser.add_argument(
        "--manual-test",
        action="store_true",
        help="Write scanner outputs under reports/manual-tests/ and do not promote them to production status.",
    )
    parser.add_argument(
        "--allow-non-trading-day-production",
        action="store_true",
        help="Allow a non-trading-day run to write official production reports.",
    )
    return parser.parse_args([] if argv is None else argv)


def classify_run(args) -> str:
    if args.manual_test:
        return "manual_test"
    if not is_trading_weekday() and not args.allow_non_trading_day_production:
        return "manual_test"
    return "production"


def market_regime_data_status(market):
    index_keys = ["spy", "qqq", "iwm"]
    for key in index_keys:
        data = market.get(key, {})
        if data.get("trend") == "Unknown" or data.get("price", 0) == 0:
            return "failed"
    return "ok"


def sector_data_status(sectors):
    if not SECTOR_ETFS:
        return "failed"
    coverage_pct = (len(sectors) / len(SECTOR_ETFS)) * 100
    return "ok" if coverage_pct >= MIN_DATA_COVERAGE_PCT else "failed"


def build_status_payload(
    *,
    attempt_at,
    attempt_status,
    failure_reason,
    health,
    sectors,
    candidates_found,
    report_path=None,
    preserve_last_success=True,
    run_type="production",
):
    latest_valid = latest_valid_report()
    payload = {
        "last_attempt_at": attempt_at,
        "last_attempt_market_date": market_date(),
        "last_attempt_status": attempt_status,
        "last_attempt_type": run_type if attempt_status != "failed_data_unavailable" else "failed",
        "last_failure_reason": failure_reason,
        "latest_valid_report": str(report_path or latest_valid) if (report_path or latest_valid) else None,
        "tickers_requested": int(health.get("tickers_requested") or 0),
        "tickers_succeeded": int(health.get("tickers_succeeded") or 0),
        "tickers_failed": int(health.get("tickers_failed") or 0),
        "data_coverage_pct": float(health.get("data_coverage_pct") or 0),
        "benchmark_data_status": health.get("benchmark_data_status", "failed"),
        "sector_data_status": sector_data_status(sectors),
        "candidates_found": int(candidates_found or 0),
        "production_pipeline_completed": False,
        "exporter_completed": False,
    }

    if attempt_status == "success" and run_type == "production":
        payload.update({
            "last_success_at": attempt_at,
            "last_success_market_date": market_date(),
            "last_failure_reason": None,
            "latest_valid_report": str(report_path or latest_valid) if (report_path or latest_valid) else None,
        })
    elif attempt_status == "success" and run_type == "manual_test":
        payload.update({
            "latest_manual_test_at": attempt_at,
            "latest_manual_test_market_date": market_date(),
            "latest_manual_test_report": str(report_path) if report_path else None,
        })
        payload["latest_valid_report"] = str(latest_valid) if latest_valid else None
    elif preserve_last_success:
        payload["latest_valid_report"] = str(latest_valid) if latest_valid else None

    return payload


def get_sector_rank(stock_sector, sector_rankings):
    sector_keywords = {
        "Semiconductors": "Semiconductors",
        "Healthcare": "Healthcare",
        "Industrials": "Industrials",
        "Financials": "Financials",
        "Energy": "Energy",
        "Utilities": "Utilities",
        "Materials": "Materials",
        "REITs": "Real Estate",
        "Consumer Defensive": "Consumer Staples",
        "Consumer Cyclical": "Consumer Discretionary",
        "Mega Cap Tech": "Technology",
        "Cloud Software": "Technology",
        "Software": "Technology",
        "Cybersecurity": "Technology",
        "AI / Data": "Technology",
        "AI / Healthcare": "Healthcare",
        "Gaming / Metaverse": "Technology",
        "EV / Consumer Tech": "Consumer Discretionary",
        "Canada / Banks": "Financials",
        "Canada / Energy": "Energy",
        "Canada / Mining": "Materials",
        "Canada / Materials": "Materials",
        "Canada / Uranium": "Materials",
        "Canada / Consumer Defensive": "Consumer Staples",
        "Canada / Industrials": "Industrials",
        "Canada / Tech": "Technology",
        "Canada / Utilities": "Utilities",
        "Canada / Pipelines": "Energy",
    }

    broad_sector = sector_keywords.get(stock_sector)

    if not broad_sector:
        return None

    for i, sector in enumerate(sector_rankings, start=1):
        if sector["sector"] == broad_sector:
            return i

    return None


def apply_historical_confidence_adjustment(confidence_data, pattern_data):
    historical_adjustment = 0
    historical_notes = []

    best_avg_return = pattern_data.get("best_avg_return", 0)
    historical_matches = pattern_data.get("historical_matches", 0)

    win_rates = [
        pattern_data.get("1d_win_rate", 0),
        pattern_data.get("3d_win_rate", 0),
        pattern_data.get("5d_win_rate", 0),
        pattern_data.get("7d_win_rate", 0),
        pattern_data.get("10d_win_rate", 0),
    ]

    best_win_rate = max(win_rates) if win_rates else 0

    if historical_matches < 30:
        historical_adjustment -= 10
        historical_notes.append("Low historical sample size")

    if best_avg_return >= 3:
        historical_adjustment += 15
        historical_notes.append("Strong historical average return")
    elif best_avg_return >= 1:
        historical_adjustment += 5
        historical_notes.append("Positive historical average return")
    elif best_avg_return < 0.5:
        historical_adjustment -= 15
        historical_notes.append("Weak historical average return")

    if best_win_rate >= 65:
        historical_adjustment += 10
        historical_notes.append("Strong historical win rate")
    elif best_win_rate >= 58:
        historical_adjustment += 5
        historical_notes.append("Positive historical win rate")
    elif best_win_rate < 50:
        historical_adjustment -= 10
        historical_notes.append("Weak historical win rate")

    confidence_data["confidence_score"] = max(
        0,
        min(100, confidence_data["confidence_score"] + historical_adjustment)
    )

    confidence_data["confidence_reasons"].extend([
        note for note in historical_notes
        if "Strong" in note or "Positive" in note
    ])

    confidence_data["risk_flags"].extend([
        note for note in historical_notes
        if "Weak" in note or "Low" in note
    ])

    return confidence_data


def add_final_scoring(scanned_stocks, market, sectors):
    enriched = []

    for stock in scanned_stocks[:AI_CANDIDATE_LIMIT]:
        sector = get_sector(stock["ticker"])
        sector_rank = get_sector_rank(sector, sectors)

        sentiment_score = 50
        sentiment_label = "Neutral"
        analysis_brief = "AI analysis module not connected yet in v2."

        pattern_data = analyze_pattern({
            **stock,
            "sector": sector,
            "market_regime": market["regime"]
        })

        confidence_data = calculate_confidence(
            stock,
            sentiment_score=sentiment_score,
            market_regime=market,
            sector_rank=sector_rank
        )

        confidence_data = apply_historical_confidence_adjustment(
            confidence_data,
            pattern_data
        )

        final_score = (
            stock["five_day_change"] * 0.35
            + stock["volume_ratio"] * 15
            + stock["relative_strength"] * 0.35
            + sentiment_score * 0.15
            + confidence_data["confidence_score"] * 0.10
            + pattern_data.get("best_avg_return", 0) * 0.75
        )

        enriched.append({
            **stock,
            "sector": sector,
            "sector_rank": sector_rank,
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "analysis_brief": analysis_brief,
            "confidence_score": confidence_data["confidence_score"],
            "confidence_reasons": confidence_data["confidence_reasons"],
            "risk_flags": confidence_data["risk_flags"],
            "historical_matches": pattern_data.get("historical_matches", 0),
            "best_hold_period": pattern_data.get("best_hold_period", "Unknown"),
            "best_avg_return": pattern_data.get("best_avg_return", 0),
            "historical_summary": pattern_data.get("summary", ""),
            "pattern_1d_avg_return": pattern_data.get("1d_avg_return", 0),
            "pattern_3d_avg_return": pattern_data.get("3d_avg_return", 0),
            "pattern_5d_avg_return": pattern_data.get("5d_avg_return", 0),
            "pattern_7d_avg_return": pattern_data.get("7d_avg_return", 0),
            "pattern_10d_avg_return": pattern_data.get("10d_avg_return", 0),
            "pattern_1d_win_rate": pattern_data.get("1d_win_rate", 0),
            "pattern_3d_win_rate": pattern_data.get("3d_win_rate", 0),
            "pattern_5d_win_rate": pattern_data.get("5d_win_rate", 0),
            "pattern_7d_win_rate": pattern_data.get("7d_win_rate", 0),
            "pattern_10d_win_rate": pattern_data.get("10d_win_rate", 0),
            "score": round(final_score, 2)
        })

    return sorted(enriched, key=lambda x: x["score"], reverse=True)


def save_outputs(ranked_stocks, market, sectors, portfolio, run_type="production"):
    today = market_date()
    reports_dir = MANUAL_TEST_REPORTS_DIR if run_type == "manual_test" else REPORTS_DIR

    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(PERFORMANCE_DIR, exist_ok=True)

    text_report = create_text_report(market, sectors, ranked_stocks, portfolio)
    html_report = create_html_report(market, sectors, ranked_stocks, portfolio)

    txt_path = f"{reports_dir}/{today}_v2.txt"
    html_path = f"{reports_dir}/{today}_v2.html"
    csv_path = f"{reports_dir}/{today}_v2.csv"
    history_path = f"{PERFORMANCE_DIR}/picks_history_v2.csv"

    with open(txt_path, "w") as f:
        f.write(text_report)

    with open(html_path, "w") as f:
        f.write(html_report)

    df = pd.DataFrame(ranked_stocks, columns=REPORT_COLUMNS)
    df.to_csv(csv_path, index=False)

    if run_type == "production":
        history_df = df.copy()
        history_df.insert(0, "date", today)

        if os.path.exists(history_path):
            existing = pd.read_csv(history_path)
            history_df = pd.concat([existing, history_df], ignore_index=True)

        history_df.to_csv(history_path, index=False)

    return text_report, html_report, txt_path, html_path, csv_path, history_path


def send_email(text_report, html_report):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Email not sent: missing EMAIL_ADDRESS or EMAIL_PASSWORD.")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    msg = EmailMessage()
    msg["Subject"] = f"AI Stock Hunter v2 Market Brief - {today}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS

    msg.set_content(text_report)
    msg.add_alternative(html_report, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print("HTML email sent successfully.")

    except Exception as e:
        print(f"Email failed: {e}")


def main(argv=None):
    args = parse_args(argv)
    run_type = classify_run(args)
    print("Starting AI Stock Hunter v2...")
    print(f"Run classification: {run_type}")
    attempt_at = iso_now()

    market = get_market_regime()
    print(f"Market Regime: {market['regime']} ({market['market_score']}/100)")

    sectors = rank_sectors()
    print("Top Sectors:")
    for sector in sectors[:5]:
        print(f"- {sector['sector']}: {sector['sector_score']}")

    scan_result = scan_market_with_health()
    scanned_stocks = scan_result["results"]
    health = scan_result["health"]
    health["benchmark_data_status"] = (
        "ok"
        if health.get("benchmark_data_status") == "ok" and market_regime_data_status(market) == "ok"
        else "failed"
    )
    failure_reason = scanner_failure_reason(
        coverage_pct=float(health.get("data_coverage_pct") or 0),
        benchmark_data_status=health["benchmark_data_status"],
        sector_data_status=sector_data_status(sectors),
    )

    print(
        "Data coverage: "
        f"{health['tickers_succeeded']}/{health['tickers_requested']} "
        f"({health['data_coverage_pct']}%)"
    )

    if failure_reason:
        status_payload = build_status_payload(
            attempt_at=attempt_at,
            attempt_status="failed_data_unavailable",
            failure_reason=failure_reason,
            health=health,
            sectors=sectors,
            candidates_found=0,
            run_type="failed",
        )
        failure_artifact = write_failure_artifact({
            **status_payload,
            "failed_tickers": health.get("failed_tickers", []),
            "benchmark_failure_reason": health.get("benchmark_failure_reason"),
        })
        status_payload["failure_artifact"] = str(failure_artifact)
        status_payload["latest_failed_attempt_at"] = attempt_at
        status_payload["latest_failed_attempt_market_date"] = market_date()
        status_payload["latest_failed_artifact"] = str(failure_artifact)
        write_status(status_payload)
        print(f"Scanner failed: {failure_reason}")
        print(f"Failure artifact written: {failure_artifact}")
        return 2

    print(f"Stocks passed scanner: {len(scanned_stocks)}")

    ranked_stocks = add_final_scoring(scanned_stocks, market, sectors)

    portfolio = build_portfolio(ranked_stocks)

    text_report, html_report, txt_path, html_path, csv_path, history_path = save_outputs(
        ranked_stocks,
        market,
        sectors,
        portfolio,
        run_type=run_type,
    )
    write_status(build_status_payload(
        attempt_at=attempt_at,
        attempt_status="success",
        failure_reason=None,
        health=health,
        sectors=sectors,
        candidates_found=len(ranked_stocks),
        report_path=csv_path,
        preserve_last_success=False,
        run_type=run_type,
    ))
    reconcile_status()

    print(f"Text report saved: {txt_path}")
    print(f"HTML report saved: {html_path}")
    print(f"CSV saved: {csv_path}")
    print(f"History saved: {history_path}")

    print("\nTOP PICKS\n")
    for stock in ranked_stocks:
        print(
            f"{stock['ticker']} | "
            f"{stock['sector']} | "
            f"Score: {stock['score']} | "
            f"Confidence: {stock['confidence_score']}% | "
            f"Matches: {stock['historical_matches']} | "
            f"Best Hold: {stock['best_hold_period']} | "
            f"Best Avg Return: {stock['best_avg_return']}%"
        )

    send_email(text_report, html_report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
