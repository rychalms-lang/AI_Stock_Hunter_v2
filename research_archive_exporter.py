import csv
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1.0"
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "research_archive.json"


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def parse_hold_days(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip().lower()
    digits = "".join(char for char in text if char.isdigit())
    return safe_int(digits)


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def candidate_from_row(row: Dict[str, str], index: int) -> Dict[str, Any]:
    confidence = safe_float(row.get("confidence_score") or row.get("confidence"))
    expected_return = safe_float(row.get("expected_return"))

    return {
        "rank": index + 1,
        "ticker": row.get("ticker") or "Unavailable",
        "sector": row.get("sector") or "Unavailable",
        "action": row.get("action") or "Unavailable",
        "confidence": confidence,
        "score": safe_float(row.get("score")),
        "expected_return_pct": expected_return,
        "best_hold_period_days": parse_hold_days(row.get("best_hold_period")),
        "historical_matches": safe_int(row.get("historical_matches")),
        "risk": row.get("risk") or "Unavailable",
        "reason": row.get("reason") or "",
        "source_fields": {
            "latest_open": safe_float(row.get("latest_open")),
            "latest_close": safe_float(row.get("latest_close")),
            "five_day_change_pct": safe_float(row.get("five_day_change")),
            "twenty_day_change_pct": safe_float(row.get("twenty_day_change")),
            "relative_strength_pct": safe_float(row.get("relative_strength")),
            "volume_ratio": safe_float(row.get("volume_ratio")),
            "best_avg_return_pct": safe_float(row.get("best_avg_return")),
        },
    }


def archive_item(path: Path) -> Optional[Dict[str, Any]]:
    try:
        rows = read_rows(path)
    except OSError:
        return None

    if not rows:
        return None

    top = rows[0]
    report_date = path.name.replace("_v2.csv", "")
    candidates = [candidate_from_row(row, index) for index, row in enumerate(rows)]

    return {
        "date": report_date,
        "market_regime": top.get("market_regime") or "Unavailable",
        "candidate_count": len(rows),
        "top_opportunity": {
            "ticker": top.get("ticker") or "Unavailable",
            "sector": top.get("sector") or "Unavailable",
            "action": top.get("action") or "Unavailable",
            "confidence": safe_float(top.get("confidence_score") or top.get("confidence")),
            "expected_return_pct": safe_float(top.get("expected_return")),
            "score": safe_float(top.get("score")),
        },
        "candidates": candidates,
        "strategy": {
            "name": "V8",
            "version": "8.0",
            "status": "Champion",
        },
        "source_metadata": {
            "schema": "scanner_report_v2_csv",
            "future_outcomes_exposed": False,
        },
        "source_report": str(path),
    }


def report_files_through(current_report: Optional[Path] = None, reports_dir: Optional[Path] = None) -> List[Path]:
    reports_dir = reports_dir or REPORTS_DIR
    files = sorted(reports_dir.glob("*_v2.csv"), reverse=True)
    if not current_report:
        return files
    current_name = current_report.name
    return [path for path in files if path.name <= current_name]


def build_archive(
    current_report: Optional[Path] = None,
    package_id: Optional[str] = None,
    reports_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    reports_dir = reports_dir or REPORTS_DIR
    items = [
        item
        for path in report_files_through(current_report, reports_dir=reports_dir)
        if (item := archive_item(path))
    ]
    current_item = next((item for item in items if current_report and Path(item.get("source_report", "")).name == current_report.name), items[0] if items else None)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "package_id": package_id,
        "current_market_date": current_item.get("date") if current_item else None,
        "current_source_report": str(current_report) if current_report else (current_item.get("source_report") if current_item else None),
        "current_item": current_item,
        "items": items,
    }
    return payload


def export_research_archive(
    output_file: Path = OUTPUT_FILE,
    current_report: Optional[Path] = None,
    package_id: Optional[str] = None,
    reports_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    reports_dir = reports_dir or REPORTS_DIR
    payload = build_archive(current_report=current_report, package_id=package_id, reports_dir=reports_dir)
    DATA_DIR.mkdir(exist_ok=True)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build research archive diagnostics. Live publication is handled by web_exporter.py.")
    parser.add_argument("--debug-output", type=Path, help="Write standalone debug output outside the live package path.")
    args = parser.parse_args()
    if not args.debug_output:
        print("Refusing standalone live export. Run web_exporter.py to publish an atomic research package, or pass --debug-output PATH.")
        raise SystemExit(2)
    result = export_research_archive(output_file=args.debug_output)
    print(f"Research archive debug output written to {args.debug_output}")
    print(json.dumps({"items": len(result["items"])}, sort_keys=True))
