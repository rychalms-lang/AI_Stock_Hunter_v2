import json
from pathlib import Path
from typing import Any, Dict, Optional

from scanner_status import latest_valid_report, market_date_from_report


SCHEMA_VERSION = "1.0"
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open() as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def source_identity(value: Any) -> Optional[str]:
    if not value:
        return None
    return Path(str(value)).name


def source_market_date(value: Any) -> Optional[str]:
    identity = source_identity(value)
    if not identity:
        return None
    path = Path(identity)
    if "_v2" not in path.name:
        return None
    return market_date_from_report(path)


def top_ticker_from_snapshot(snapshot: Dict[str, Any]) -> Optional[str]:
    top = snapshot.get("top_opportunity")
    if isinstance(top, dict) and top.get("ticker"):
        return str(top["ticker"]).upper()
    return None


def rank_one_ticker(items: Any) -> Optional[str]:
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if isinstance(first, dict) and first.get("ticker"):
        return str(first["ticker"]).upper()
    return None


def resolve_research_package(
    *,
    data_dir: Path = DATA_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> Dict[str, Any]:
    snapshot = read_json(data_dir / "web_snapshot.json") or {}
    changes = read_json(data_dir / "research_changes.json") or {}
    daily_picks = read_json(data_dir / "paper_trading" / "daily_picks.json") or {}
    official_report = latest_valid_report(reports_dir)

    expected_source = source_identity(official_report) if official_report else None
    expected_market_date = market_date_from_report(official_report) if official_report else None
    snapshot_source = source_identity(snapshot.get("source_file"))
    snapshot_date = source_market_date(snapshot.get("source_file"))
    changes_source = source_identity(changes.get("current_source"))
    changes_date = changes.get("current_date")
    daily_source = source_identity(daily_picks.get("source_file"))
    daily_date = daily_picks.get("trade_date") or source_market_date(daily_picks.get("source_file"))
    snapshot_top = top_ticker_from_snapshot(snapshot)
    snapshot_rank_one = rank_one_ticker(snapshot.get("ranked_candidates"))
    daily_rank_one = rank_one_ticker(daily_picks.get("picks"))
    changes_top = rank_one_ticker([
        (changes.get("top_opportunity_change") or {}).get("current")
    ])

    mismatches = []

    if not official_report:
        mismatches.append("missing_official_report")
    if not snapshot:
        mismatches.append("missing_web_snapshot")
    if not daily_picks:
        mismatches.append("missing_daily_picks")

    for label, actual in [
        ("web_snapshot_source", snapshot_source),
        ("daily_picks_source", daily_source),
    ]:
        if expected_source and actual and actual != expected_source:
            mismatches.append(f"{label}_mismatch:{actual}!={expected_source}")

    if changes and changes_source and expected_source and changes_source != expected_source:
        mismatches.append(f"research_changes_source_mismatch:{changes_source}!={expected_source}")

    for label, actual in [
        ("web_snapshot_market_date", snapshot_date),
        ("daily_picks_market_date", daily_date),
    ]:
        if expected_market_date and actual and actual != expected_market_date:
            mismatches.append(f"{label}_mismatch:{actual}!={expected_market_date}")

    if changes and changes_date and expected_market_date and changes_date != expected_market_date:
        mismatches.append(f"research_changes_current_date_mismatch:{changes_date}!={expected_market_date}")

    if snapshot_top and snapshot_rank_one and snapshot_top != snapshot_rank_one:
        mismatches.append(f"top_opportunity_rank_mismatch:{snapshot_top}!={snapshot_rank_one}")

    if snapshot_rank_one and daily_rank_one and snapshot_rank_one != daily_rank_one:
        mismatches.append(f"daily_picks_rank_mismatch:{daily_rank_one}!={snapshot_rank_one}")

    if changes_top and snapshot_rank_one and changes_top != snapshot_rank_one:
        mismatches.append(f"research_changes_top_mismatch:{changes_top}!={snapshot_rank_one}")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if not mismatches else "mismatch",
        "mismatches": mismatches,
        "official_market_date": expected_market_date,
        "official_source_report": str(official_report) if official_report else None,
        "source_report": snapshot.get("source_file"),
        "source_report_name": snapshot_source,
        "generated_at": snapshot.get("generated_at"),
        "top_opportunity_ticker": snapshot_rank_one,
        "snapshot_top_opportunity_ticker": snapshot_top,
        "daily_picks_top_ticker": daily_rank_one,
        "research_changes_top_ticker": changes_top,
        "web_snapshot_market_date": snapshot_date,
        "daily_picks_market_date": daily_date,
        "research_changes_current_date": changes_date,
    }
