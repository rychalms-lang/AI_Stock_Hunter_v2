import csv
from pathlib import Path
from datetime import datetime

from ai_engine import recommendation_from_row
from paper_trading_exporter import build_daily_picks_file, export_paper_trading_snapshot
from research_archive_exporter import export_research_archive
from research_change_exporter import build_research_changes
from research_package import package_id_for_report, publish_research_package, write_json
from scanner_status import latest_valid_report, report_validation, write_status


REPORTS_DIR = Path("reports")
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "web_snapshot.json"
PUBLIC_SNAPSHOT_FILE = Path("ai-stock-hunter-web/public/web_snapshot.json")


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


def build_snapshot_payload(report_file: Path, rows, package_id: str):
    recommendations = [
        recommendation_from_row(row)
        for row in rows
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "package_id": package_id,
        "source_file": str(report_file),
        "source_market_date": report_file.name.replace("_v2.csv", ""),
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


def build_research_package_outputs(report_file: Path, package_id: str, package_dir: Path):
    validation = report_validation(report_file)
    if not validation["valid"]:
        raise ValueError(f"{report_file} is invalid: {validation['reason']}")

    with report_file.open(newline="") as f:
        rows = list(csv.DictReader(f))

    data_dir = package_dir / "data"
    paper_dir = data_dir / "paper_trading"
    snapshot_path = data_dir / "web_snapshot.json"
    changes_path = data_dir / "research_changes.json"
    archive_path = data_dir / "research_archive.json"
    daily_picks_path = paper_dir / "daily_picks.json"

    snapshot = build_snapshot_payload(report_file, rows, package_id)
    write_json(snapshot_path, snapshot)

    generated_at = datetime.now().isoformat(timespec="seconds")
    daily_picks = build_daily_picks_file(rows, report_file, generated_at, package_id=package_id)
    write_json(daily_picks_path, daily_picks)

    changes = build_research_changes(REPORTS_DIR, current_report=report_file, package_id=package_id)
    write_json(changes_path, changes)

    export_research_archive(output_file=archive_path, current_report=report_file, package_id=package_id, reports_dir=REPORTS_DIR)

    return {
        "artifacts": [snapshot_path, daily_picks_path, changes_path, archive_path],
        "publish": [
            (snapshot_path, OUTPUT_FILE),
            (snapshot_path, PUBLIC_SNAPSHOT_FILE),
            (changes_path, DATA_DIR / "research_changes.json"),
            (archive_path, DATA_DIR / "research_archive.json"),
            (daily_picks_path, DATA_DIR / "paper_trading" / "daily_picks.json"),
        ],
        "metadata": {
            "paper_result": {"daily_picks": str(daily_picks_path)},
            "top_ticker": snapshot["top_opportunity"]["ticker"] if snapshot.get("top_opportunity") else None,
            "top_action": snapshot["top_opportunity"]["action"] if snapshot.get("top_opportunity") else None,
            "top_expected_return": snapshot["top_opportunity"]["expected_return"] if snapshot.get("top_opportunity") else None,
            "top_matches": snapshot["top_opportunity"]["historical_matches"] if snapshot.get("top_opportunity") else None,
            "candidate_count": len(snapshot.get("ranked_candidates") or []),
        },
    }


def export_snapshot():
    report_file = latest_report()
    package_id = package_id_for_report(report_file)
    result = publish_research_package(build_research_package_outputs, data_dir=DATA_DIR, reports_dir=REPORTS_DIR)

    if not result["ok"]:
        write_status({
            "exporter_completed": False,
            "production_pipeline_completed": False,
            "latest_valid_report": str(report_file),
            "latest_research_package_id": package_id,
            "research_package_status": "failed",
            "research_package_failure": result.get("diagnostics_file"),
        })
        raise RuntimeError(f"Research package validation failed: {result.get('diagnostics_file')}")

    paper_result = export_paper_trading_snapshot(
        report_file,
        output_dir=DATA_DIR / "paper_trading",
        state_dir=DATA_DIR / "paper_trading" / "state",
        package_id=package_id,
        run_engine=True,
    )

    print(f"Web snapshot written to {OUTPUT_FILE}")
    if result.get("top_ticker"):
        print(
            f"Top opportunity: {result['top_ticker']} | "
            f"Action: {result['top_action']} | "
            f"Expected Return: {result['top_expected_return']}% | "
            f"Matches: {result['top_matches']}"
        )
    else:
        print("No qualifying candidates in the latest valid scanner report.")

    print(
        "Paper trading JSON written: "
        f"{paper_result['daily_picks']} and {paper_result['portfolio_summary']}"
    )
    print(
        "Research changes written: "
        f"package_id={package_id} current={result['market_date']}"
    )
    write_status({
        "exporter_completed": True,
        "production_pipeline_completed": True,
        "latest_valid_report": str(report_file),
        "latest_research_package_id": package_id,
        "research_package_status": "published",
        "research_package_failure": None,
    })


if __name__ == "__main__":
    export_snapshot()
