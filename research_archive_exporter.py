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


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def archive_item(path: Path) -> Optional[Dict[str, Any]]:
    try:
        rows = read_rows(path)
    except OSError:
        return None

    if not rows:
        return None

    top = rows[0]
    report_date = path.name.replace("_v2.csv", "")

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
