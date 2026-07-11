import csv
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


def build_archive() -> Dict[str, Any]:
    items = [
        item
        for path in sorted(REPORTS_DIR.glob("*_v2.csv"), reverse=True)
        if (item := archive_item(path))
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "items": items,
    }


def export_research_archive() -> Dict[str, Any]:
    payload = build_archive()
    DATA_DIR.mkdir(exist_ok=True)
    with OUTPUT_FILE.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return payload


if __name__ == "__main__":
    result = export_research_archive()
    print(f"Research archive written to {OUTPUT_FILE}")
    print(json.dumps({"items": len(result["items"])}, sort_keys=True))
