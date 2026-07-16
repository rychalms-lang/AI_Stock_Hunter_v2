import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


SCHEMA_VERSION = "1.0"
DATA_DIR = Path("data")
REPORTS_DIR = Path("reports")
FAILED_REPORTS_DIR = REPORTS_DIR / "failed"
MANUAL_TEST_REPORTS_DIR = REPORTS_DIR / "manual-tests"
SCANNER_STATUS_FILE = DATA_DIR / "scanner_status.json"
MIN_DATA_COVERAGE_PCT = 60.0

REQUIRED_REPORT_COLUMNS = {
    "ticker",
    "latest_close",
    "five_day_change",
    "twenty_day_change",
    "relative_strength",
    "volume_ratio",
    "action",
    "score",
    "confidence_score",
    "historical_matches",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def market_date_from_report(path: Path) -> str:
    for suffix in ["_v2.csv", "_v2.html", "_v2.txt"]:
        if path.name.endswith(suffix):
            return path.name.replace(suffix, "")
    return path.stem


def read_status(path: Path = SCANNER_STATUS_FILE) -> Dict[str, Any]:
    try:
        with path.open() as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def write_status(
    payload: Dict[str, Any],
    path: Path = SCANNER_STATUS_FILE,
    merge: bool = True,
) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = read_status(path) if merge else {}
    merged = {
        "schema_version": SCHEMA_VERSION,
        **current,
        **payload,
    }
    with path.open("w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    return merged


def file_iso(path: Optional[Path]) -> Optional[str]:
    if not path:
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds")
    except OSError:
        return None


def report_validation(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "valid": False,
            "reason": "missing_report",
            "row_count": 0,
            "fieldnames": [],
        }

    try:
        if path.stat().st_size == 0:
            return {
                "valid": False,
                "reason": "empty_file",
                "row_count": 0,
                "fieldnames": [],
            }

        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            if not fieldnames:
                return {
                    "valid": False,
                    "reason": "missing_header",
                    "row_count": 0,
                    "fieldnames": [],
                }

            missing = sorted(REQUIRED_REPORT_COLUMNS.difference(fieldnames))
            if missing:
                return {
                    "valid": False,
                    "reason": f"missing_columns:{','.join(missing)}",
                    "row_count": 0,
                    "fieldnames": fieldnames,
                }

            row_count = sum(1 for _ in reader)
            return {
                "valid": True,
                "reason": "valid",
                "row_count": row_count,
                "fieldnames": fieldnames,
            }
    except (csv.Error, OSError, UnicodeDecodeError) as error:
        return {
            "valid": False,
            "reason": f"read_error:{error}",
            "row_count": 0,
            "fieldnames": [],
        }


def latest_valid_report(reports_dir: Path = REPORTS_DIR) -> Optional[Path]:
    for path in sorted(reports_dir.glob("*_v2.csv"), reverse=True):
        if report_validation(path)["valid"]:
            return path
    return None


def source_report_hash(report: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with report.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()[:16]
    except OSError:
        return None


def package_id_for_report(report: Optional[Path]) -> Optional[str]:
    if not report:
        return None
    digest = source_report_hash(report)
    if not digest:
        return None
    return f"research_{market_date_from_report(report)}_{digest}"


def latest_file(paths):
    items = [path for path in paths if path.exists() and path.is_file()]
    if not items:
        return None
    return sorted(items, key=lambda item: (market_date_from_report(item) if "_v2." in item.name else item.name, item.stat().st_mtime))[-1]


def latest_failed_artifact(reports_dir: Path = REPORTS_DIR) -> Optional[Path]:
    failed_dir = reports_dir / "failed"
    candidates = (
        list(failed_dir.glob("*_scanner_failure.json"))
        + list(failed_dir.glob("*_v2.csv"))
        + list(failed_dir.glob("*_v2.html"))
        + list(failed_dir.glob("*_v2.txt"))
    )
    if not candidates:
        return None

    priority = {
        ".json": 4,
        ".csv": 3,
        ".html": 2,
        ".txt": 1,
    }
    return sorted(
        candidates,
        key=lambda path: (
            market_date_from_report(path) if "_v2." in path.name else path.name,
            priority.get(path.suffix, 0),
            path.stat().st_mtime,
        ),
    )[-1]


def reconcile_status(
    reports_dir: Path = REPORTS_DIR,
    status_path: Path = SCANNER_STATUS_FILE,
) -> Dict[str, Any]:
    production_report = latest_valid_report(reports_dir)
    manual_report = latest_valid_report(reports_dir / "manual-tests")
    failed_artifact = latest_failed_artifact(reports_dir)
    production_validation = report_validation(production_report) if production_report else {}

    candidates = []
    if production_report:
        candidates.append(("production", "success", production_report))
    if manual_report:
        candidates.append(("manual_test", "success", manual_report))
    if failed_artifact:
        candidates.append(("failed", "failed_data_unavailable", failed_artifact))

    latest_attempt = None
    if candidates:
        latest_attempt = sorted(
            candidates,
            key=lambda item: (
                market_date_from_report(item[2]) if "_v2." in item[2].name else item[2].name,
                item[2].stat().st_mtime,
            ),
        )[-1]

    current = read_status(status_path)
    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "last_attempt_at": file_iso(latest_attempt[2]) if latest_attempt else current.get("last_attempt_at"),
        "last_attempt_market_date": market_date_from_report(latest_attempt[2]) if latest_attempt and "_v2." in latest_attempt[2].name else current.get("last_attempt_market_date"),
        "last_attempt_status": latest_attempt[1] if latest_attempt else current.get("last_attempt_status", "unknown"),
        "last_attempt_type": latest_attempt[0] if latest_attempt else current.get("last_attempt_type", "unknown"),
        "last_failure_reason": current.get("last_failure_reason"),
        "last_success_at": file_iso(production_report),
        "last_success_market_date": market_date_from_report(production_report) if production_report else None,
        "latest_valid_report": str(production_report) if production_report else None,
        "latest_research_package_id": package_id_for_report(production_report),
        "latest_manual_test_at": file_iso(manual_report),
        "latest_manual_test_market_date": market_date_from_report(manual_report) if manual_report else None,
        "latest_manual_test_report": str(manual_report) if manual_report else None,
        "latest_failed_attempt_at": file_iso(failed_artifact),
        "latest_failed_attempt_market_date": market_date_from_report(failed_artifact) if failed_artifact and "_v2." in failed_artifact.name else None,
        "latest_failed_artifact": str(failed_artifact) if failed_artifact else None,
        "tickers_requested": current.get("tickers_requested", 0),
        "tickers_succeeded": current.get("tickers_succeeded", 0),
        "tickers_failed": current.get("tickers_failed", 0),
        "data_coverage_pct": current.get("data_coverage_pct"),
        "benchmark_data_status": current.get("benchmark_data_status", "unknown"),
        "sector_data_status": current.get("sector_data_status", "unknown"),
        "candidates_found": int(production_validation.get("row_count") or 0),
        "production_pipeline_completed": bool(production_report),
        "exporter_completed": bool(production_report),
    }

    if failed_artifact:
        payload["last_failure_reason"] = current.get("last_failure_reason") or "failed_artifact_present"
    if latest_attempt and latest_attempt[0] != "failed":
        payload["last_failure_reason"] = current.get("last_failure_reason")

    return write_status(payload, status_path, merge=False)


def scanner_failure_reason(
    *,
    coverage_pct: float,
    benchmark_data_status: str,
    sector_data_status: str,
    min_coverage_pct: float = MIN_DATA_COVERAGE_PCT,
) -> Optional[str]:
    if benchmark_data_status != "ok":
        return "benchmark_or_regime_data_unavailable"
    if sector_data_status != "ok":
        return "sector_data_unavailable"
    if coverage_pct < min_coverage_pct:
        return "insufficient_ticker_data_coverage"
    return None


def write_failure_artifact(payload: Dict[str, Any], reports_dir: Path = REPORTS_DIR) -> Path:
    failed_dir = reports_dir / "failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = failed_dir / f"{timestamp}_scanner_failure.json"
    with path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return path


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] != "reconcile":
        print("Usage: python scanner_status.py reconcile")
        return 2

    payload = reconcile_status()
    print(json.dumps({
        "latest_valid_report": payload.get("latest_valid_report"),
        "latest_manual_test_report": payload.get("latest_manual_test_report"),
        "latest_failed_artifact": payload.get("latest_failed_artifact"),
        "last_attempt_type": payload.get("last_attempt_type"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
