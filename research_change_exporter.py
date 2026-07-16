import csv
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "1.0"
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "research_changes.json"
CONFIDENCE_THRESHOLD = 5.0
EXPECTED_RETURN_THRESHOLD = 1.0


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def parse_hold_days(value: Any) -> Optional[int]:
    text = str(value or "")
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return None
    return int(digits)


def report_date(path: Path) -> str:
    return path.name.replace("_v2.csv", "")


def read_report(path: Path) -> List[Dict[str, str]]:
    try:
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        raise ValueError(f"Unable to read report: {path}") from exc

    if rows and "ticker" not in rows[0]:
        raise ValueError(f"Malformed report missing ticker column: {path}")

    return rows


def candidate(row: Dict[str, str], rank: int) -> Dict[str, Any]:
    return {
        "ticker": (row.get("ticker") or "Unavailable").upper(),
        "rank": rank,
        "sector": row.get("sector") or "Unavailable",
        "action": row.get("action") or "Unavailable",
        "confidence": safe_float(row.get("confidence_score") or row.get("confidence")),
        "score": safe_float(row.get("score")),
        "expected_return_pct": safe_float(row.get("expected_return")),
        "best_hold_period_days": parse_hold_days(row.get("best_hold_period")),
        "historical_matches": int(float(row.get("historical_matches") or 0)),
        "risk": row.get("risk") or "Unavailable",
    }


def load_candidates(path: Path) -> List[Dict[str, Any]]:
    return [candidate(row, index + 1) for index, row in enumerate(read_report(path))]


def report_files(reports_dir: Path) -> List[Path]:
    return sorted(reports_dir.glob("*_v2.csv"))


def report_files_through(reports_dir: Path, current_report: Optional[Path]) -> List[Path]:
    files = report_files(reports_dir)
    if not current_report:
        return files

    current_name = current_report.name
    filtered = [path for path in files if path.name <= current_name]
    if not any(path.name == current_name for path in filtered):
        filtered.append(current_report)
    return sorted(filtered)


def empty_payload(files: List[Path]) -> Dict[str, Any]:
    current = files[-1] if files else None
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "status": "insufficient_history",
        "current_date": report_date(current) if current else None,
        "previous_date": None,
        "current_source": str(current) if current else None,
        "previous_source": None,
        "summary": {
            "new_candidates": 0,
            "removed_candidates": 0,
            "rank_changes": 0,
            "action_changes": 0,
            "confidence_changes": 0,
            "expected_return_changes": 0,
            "sector_changes": 0,
        },
        "new_candidates": [],
        "removed_candidates": [],
        "rank_changes": [],
        "action_changes": [],
        "confidence_changes": [],
        "expected_return_changes": [],
        "sector_changes": [],
        "top_opportunity_change": {
            "previous": None,
            "current": None,
        },
    }


def candidate_maps(
    previous: List[Dict[str, Any]],
    current: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    return (
        {item["ticker"]: item for item in previous},
        {item["ticker"]: item for item in current},
    )


def sort_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: (item.get("rank") or 9999, item["ticker"]))


def compare_reports(previous_path: Path, current_path: Path) -> Dict[str, Any]:
    previous = load_candidates(previous_path)
    current = load_candidates(current_path)
    previous_by_ticker, current_by_ticker = candidate_maps(previous, current)
    previous_tickers = set(previous_by_ticker)
    current_tickers = set(current_by_ticker)
    common_tickers = sorted(previous_tickers & current_tickers)

    new_candidates = sort_candidates([
        current_by_ticker[ticker] for ticker in current_tickers - previous_tickers
    ])
    removed_candidates = sort_candidates([
        previous_by_ticker[ticker] for ticker in previous_tickers - current_tickers
    ])

    rank_changes = []
    action_changes = []
    confidence_changes = []
    expected_return_changes = []
    sector_changes = []

    for ticker in common_tickers:
        prev = previous_by_ticker[ticker]
        curr = current_by_ticker[ticker]

        if prev["rank"] != curr["rank"]:
            rank_changes.append({
                "ticker": ticker,
                "previous_rank": prev["rank"],
                "current_rank": curr["rank"],
                "movement": prev["rank"] - curr["rank"],
            })

        if prev["action"] != curr["action"]:
            action_changes.append({
                "ticker": ticker,
                "previous_action": prev["action"],
                "current_action": curr["action"],
            })

        if prev["confidence"] is not None and curr["confidence"] is not None:
            delta = round(curr["confidence"] - prev["confidence"], 2)
            if abs(delta) >= CONFIDENCE_THRESHOLD:
                confidence_changes.append({
                    "ticker": ticker,
                    "previous_confidence": prev["confidence"],
                    "current_confidence": curr["confidence"],
                    "change_points": delta,
                })

        if prev["expected_return_pct"] is not None and curr["expected_return_pct"] is not None:
            delta = round(curr["expected_return_pct"] - prev["expected_return_pct"], 2)
            if abs(delta) >= EXPECTED_RETURN_THRESHOLD:
                expected_return_changes.append({
                    "ticker": ticker,
                    "previous_expected_return_pct": prev["expected_return_pct"],
                    "current_expected_return_pct": curr["expected_return_pct"],
                    "change_points": delta,
                })

        if prev["sector"] != curr["sector"]:
            sector_changes.append({
                "ticker": ticker,
                "previous_sector": prev["sector"],
                "current_sector": curr["sector"],
            })

    rank_changes.sort(key=lambda item: (abs(item["movement"]) * -1, item["ticker"]))
    action_changes.sort(key=lambda item: item["ticker"])
    confidence_changes.sort(key=lambda item: (abs(item["change_points"]) * -1, item["ticker"]))
    expected_return_changes.sort(key=lambda item: (abs(item["change_points"]) * -1, item["ticker"]))
    sector_changes.sort(key=lambda item: item["ticker"])

    previous_top = previous[0] if previous else None
    current_top = current[0] if current else None
    top_change = {
        "previous": previous_top,
        "current": current_top,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "status": "ready",
        "current_date": report_date(current_path),
        "previous_date": report_date(previous_path),
        "current_source": str(current_path),
        "previous_source": str(previous_path),
        "summary": {
            "new_candidates": len(new_candidates),
            "removed_candidates": len(removed_candidates),
            "rank_changes": len(rank_changes),
            "action_changes": len(action_changes),
            "confidence_changes": len(confidence_changes),
            "expected_return_changes": len(expected_return_changes),
            "sector_changes": len(sector_changes),
        },
        "new_candidates": new_candidates,
        "removed_candidates": removed_candidates,
        "rank_changes": rank_changes,
        "action_changes": action_changes,
        "confidence_changes": confidence_changes,
        "expected_return_changes": expected_return_changes,
        "sector_changes": sector_changes,
        "top_opportunity_change": top_change,
    }


def build_research_changes(
    reports_dir: Path = REPORTS_DIR,
    current_report: Optional[Path] = None,
    package_id: Optional[str] = None,
) -> Dict[str, Any]:
    files = report_files_through(reports_dir, current_report)
    if len(files) < 2:
        payload = empty_payload(files)
    else:
        payload = compare_reports(files[-2], files[-1])
    if package_id:
        payload["package_id"] = package_id
    return payload


def export_research_changes(
    reports_dir: Path = REPORTS_DIR,
    output_file: Path = OUTPUT_FILE,
    current_report: Optional[Path] = None,
    package_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload = build_research_changes(reports_dir, current_report=current_report, package_id=package_id)
    output_file.parent.mkdir(exist_ok=True)
    with output_file.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build research change diagnostics. Live publication is handled by web_exporter.py.")
    parser.add_argument("--debug-output", type=Path, help="Write standalone debug output outside the live package path.")
    args = parser.parse_args()
    if not args.debug_output:
        print("Refusing standalone live export. Run web_exporter.py to publish an atomic research package, or pass --debug-output PATH.")
        raise SystemExit(2)
    result = export_research_changes(output_file=args.debug_output)
    print(f"Research changes debug output written to {args.debug_output}")
    print(json.dumps({
        "status": result["status"],
        "current_date": result["current_date"],
        "previous_date": result["previous_date"],
    }, sort_keys=True))
