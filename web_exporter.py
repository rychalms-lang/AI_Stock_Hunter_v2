import json
import csv
from pathlib import Path
from datetime import datetime

from ai_engine import recommendation_from_row
from paper_trading_exporter import export_paper_trading_snapshot
from scanner_status import latest_valid_report, report_validation, write_status


REPORTS_DIR = Path("reports")
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "web_snapshot.json"


def latest_report():
    report = latest_valid_report(REPORTS_DIR)

    if not report:
        raise FileNotFoundError("No valid report CSV found in reports/.")

    return report


def load_report():
    report_file = latest_report()
    validation = report_validation(report_file)
    if not validation["valid"]:
        raise ValueError(f"{report_file} is invalid: {validation['reason']}")

    with report_file.open(newline="") as f:
        rows = list(csv.DictReader(f))

    return report_file, rows


def build_portfolio_summary(recommendations):
    top = recommendations[:10]

    buy_count = sum(1 for item in top if item.action == "BUY")
    watch_count = sum(1 for item in top if item.action == "WATCH")
    avoid_count = sum(1 for item in top if item.action == "AVOID")

    avg_expected_return = sum(item.expected_return for item in top) / max(len(top), 1)
    avg_confidence = sum(item.confidence for item in top) / max(len(top), 1)

    if buy_count >= 3 and avg_confidence >= 75:
        status = "Excellent"
        health_label = "Healthy"
    elif buy_count >= 1 or watch_count >= 3:
        status = "Selective"
        health_label = "Cautious"
    else:
        status = "Defensive"
        health_label = "Risk Controlled"

    return {
        "status": status,
        "health_label": health_label,
        "total_value": 25000,
        "total_return": 16.4,
        "cash_percent": 12,
        "positions": 8,
        "expected_10_day_return": round(avg_expected_return, 2),
        "ai_confidence": round(avg_confidence, 1),
        "summary": (
            f"{buy_count} buy candidates, {watch_count} watch candidates, "
            f"and {avoid_count} avoid candidates were identified."
        ),
    }


def build_today_actions(recommendations):
    actions = []

    for item in recommendations[:10]:
        if item.action == "BUY":
            actions.append({
                "ticker": item.ticker,
                "action": "Review buy",
                "badge": "BUY",
                "tone": "green",
                "confidence": item.confidence,
                "reason": item.reason,
            })

        elif item.action == "WATCH":
            actions.append({
                "ticker": item.ticker,
                "action": "Watch setup",
                "badge": "WATCH",
                "tone": "amber",
                "confidence": item.confidence,
                "reason": item.reason,
            })

        elif item.action == "AVOID":
            actions.append({
                "ticker": item.ticker,
                "action": "Avoid",
                "badge": "AVOID",
                "tone": "red",
                "confidence": item.confidence,
                "reason": item.reason,
            })

        if len(actions) >= 3:
            break

    return actions


def export_snapshot():
    report_file, rows = load_report()
    recommendations = [
        recommendation_from_row(row)
        for row in rows
    ]

    recommendations.sort(
        key=lambda item: (
            item.action == "BUY",
            item.expected_return,
            item.confidence,
            item.score,
        ),
        reverse=True,
    )

    snapshot = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": str(report_file),
        "market_regime": {
            "label": "Risk-On",
            "score": 100.0,
        },
        "top_opportunity": recommendations[0].to_dict() if recommendations else None,
        "portfolio_summary": build_portfolio_summary(recommendations),
        "today_actions": build_today_actions(recommendations),
        "ranked_candidates": [
            item.to_dict()
            for item in recommendations[:25]
        ],
    }

    DATA_DIR.mkdir(exist_ok=True)

    paper_result = export_paper_trading_snapshot(report_file)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(snapshot, f, indent=2)

    print(f"Web snapshot written to {OUTPUT_FILE}")
    if recommendations:
        print(
            f"Top opportunity: {snapshot['top_opportunity']['ticker']} | "
            f"Action: {snapshot['top_opportunity']['action']} | "
            f"Expected Return: {snapshot['top_opportunity']['expected_return']}% | "
            f"Matches: {snapshot['top_opportunity']['historical_matches']}"
        )
    else:
        print("No qualifying candidates in the latest valid scanner report.")

    print(
        "Paper trading JSON written: "
        f"{paper_result['daily_picks']} and {paper_result['portfolio_summary']}"
    )
    write_status({
        "exporter_completed": True,
        "production_pipeline_completed": True,
        "latest_valid_report": str(report_file),
    })


if __name__ == "__main__":
    export_snapshot()
