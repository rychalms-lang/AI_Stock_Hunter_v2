import json
from pathlib import Path
from datetime import datetime

import pandas as pd

from ai_engine import build_recommendations_from_dataframe


REPORTS_DIR = Path("reports")
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "web_snapshot.json"


def latest_report():
    files = sorted(REPORTS_DIR.glob("*_v2.csv"))

    if not files:
        raise FileNotFoundError("No report CSV found in reports/.")

    return files[-1]


def load_report():
    report_file = latest_report()
    df = pd.read_csv(report_file)

    if df.empty:
        raise ValueError(f"{report_file} is empty.")

    return report_file, df


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
    report_file, df = load_report()
    recommendations = build_recommendations_from_dataframe(df)

    if not recommendations:
        raise ValueError("No recommendations were generated.")

    snapshot = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": str(report_file),
        "market_regime": {
            "label": "Risk-On",
            "score": 100.0,
        },
        "top_opportunity": recommendations[0].to_dict(),
        "portfolio_summary": build_portfolio_summary(recommendations),
        "today_actions": build_today_actions(recommendations),
        "ranked_candidates": [
            item.to_dict()
            for item in recommendations[:25]
        ],
    }

    DATA_DIR.mkdir(exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(snapshot, f, indent=2)

    print(f"Web snapshot written to {OUTPUT_FILE}")
    print(
        f"Top opportunity: {snapshot['top_opportunity']['ticker']} | "
        f"Action: {snapshot['top_opportunity']['action']} | "
        f"Expected Return: {snapshot['top_opportunity']['expected_return']}% | "
        f"Matches: {snapshot['top_opportunity']['historical_matches']}"
    )


if __name__ == "__main__":
    export_snapshot()