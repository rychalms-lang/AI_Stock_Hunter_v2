import json
import os
import shutil
import tempfile
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from scanner_status import latest_valid_report, market_date_from_report


SCHEMA_VERSION = "1.0"
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
PUBLIC_SNAPSHOT_FILE = PROJECT_ROOT / "ai-stock-hunter-web" / "public" / "web_snapshot.json"
DIAGNOSTICS_DIR = DATA_DIR / "diagnostics"


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open() as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def source_report_hash(report: Path) -> str:
    digest = hashlib.sha256()
    with report.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def package_id_for_report(report: Path) -> str:
    return f"research_{market_date_from_report(report)}_{source_report_hash(report)}"


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


def artifact_identity(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    if path.name == "web_snapshot.json":
        rank_one = rank_one_ticker(payload.get("ranked_candidates"))
        source = payload.get("source_file")
        market_date = payload.get("source_market_date") or source_market_date(source)
        count = len(payload.get("ranked_candidates") or [])
    elif path.name == "daily_picks.json":
        rank_one = rank_one_ticker(payload.get("picks"))
        source = payload.get("source_file")
        market_date = payload.get("trade_date") or source_market_date(source)
        count = len(payload.get("picks") or [])
    elif path.name == "research_changes.json":
        rank_one = rank_one_ticker([(payload.get("top_opportunity_change") or {}).get("current")])
        source = payload.get("current_source")
        market_date = payload.get("current_date") or source_market_date(source)
        count = None
    elif path.name == "research_archive.json":
        current = payload.get("current_item") if isinstance(payload.get("current_item"), dict) else None
        rank_one = (current.get("top_opportunity") or {}).get("ticker") if current else None
        source = payload.get("current_source_report") or (current or {}).get("source_report")
        market_date = payload.get("current_market_date") or (current or {}).get("date") or source_market_date(source)
        count = (current or {}).get("candidate_count")
    else:
        rank_one = None
        source = payload.get("source_file") or payload.get("source_report")
        market_date = payload.get("source_market_date") or payload.get("trade_date") or source_market_date(source)
        count = None

    return {
        "path": str(path),
        "package_id": payload.get("package_id"),
        "source_report": str(source) if source else None,
        "source_report_name": source_identity(source),
        "market_date": market_date,
        "rank_one_ticker": str(rank_one).upper() if rank_one else None,
        "candidate_count": count,
    }


def validate_package_artifacts(
    artifacts: Iterable[Path],
    *,
    expected_package_id: str,
    expected_source_report: Path,
) -> Dict[str, Any]:
    expected_source = source_identity(expected_source_report)
    expected_date = market_date_from_report(expected_source_report)
    identities = []
    mismatches = []
    rank_one_values = []
    candidate_counts = []

    for path in artifacts:
        payload = read_json(path)
        if not payload:
            mismatches.append(f"missing_or_invalid:{path.name}")
            identities.append({"path": str(path), "error": "missing_or_invalid"})
            continue
        identity = artifact_identity(path, payload)
        identities.append(identity)
        if identity["package_id"] != expected_package_id:
            mismatches.append(f"package_id_mismatch:{path.name}:{identity['package_id']}!={expected_package_id}")
        if identity["source_report_name"] and identity["source_report_name"] != expected_source:
            mismatches.append(f"source_report_mismatch:{path.name}:{identity['source_report_name']}!={expected_source}")
        if identity["market_date"] and identity["market_date"] != expected_date:
            mismatches.append(f"market_date_mismatch:{path.name}:{identity['market_date']}!={expected_date}")
        if identity["rank_one_ticker"]:
            rank_one_values.append((path.name, identity["rank_one_ticker"]))
        if isinstance(identity["candidate_count"], int):
            candidate_counts.append((path.name, identity["candidate_count"]))

    if rank_one_values:
        expected_rank_one = rank_one_values[0][1]
        for name, ticker in rank_one_values[1:]:
            if ticker != expected_rank_one:
                mismatches.append(f"rank_one_mismatch:{name}:{ticker}!={expected_rank_one}")

    if candidate_counts:
        expected_count = candidate_counts[0][1]
        for name, count in candidate_counts[1:]:
            if count != expected_count:
                mismatches.append(f"candidate_count_mismatch:{name}:{count}!={expected_count}")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if not mismatches else "mismatch",
        "package_id": expected_package_id,
        "expected_source_report": str(expected_source_report),
        "expected_market_date": expected_date,
        "expected_rank_one_ticker": rank_one_values[0][1] if rank_one_values else None,
        "expected_candidate_count": candidate_counts[0][1] if candidate_counts else None,
        "mismatches": mismatches,
        "artifacts": identities,
    }


def diagnostics_payload(validation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "status": "failed",
        "customer_safe_summary": "Research package generation failed because public research files did not agree on one official production report.",
        "technical_diagnostics": validation,
    }


def write_package_failure(validation: Dict[str, Any], diagnostics_dir: Path = DIAGNOSTICS_DIR) -> Path:
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    path = diagnostics_dir / f"research_package_failure_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    write_json(path, diagnostics_payload(validation))
    return path


def atomic_publish_json_files(mapping) -> None:
    items = mapping.items() if isinstance(mapping, dict) else mapping
    for source, destination in items:
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copyfile(source, tmp)
        os.replace(tmp, destination)


def publish_research_package(build_fn, *, data_dir: Path = DATA_DIR, reports_dir: Path = REPORTS_DIR) -> Dict[str, Any]:
    official_report = latest_valid_report(reports_dir)
    if not official_report:
        raise FileNotFoundError("No official production report is available.")

    package_id = package_id_for_report(official_report)
    with tempfile.TemporaryDirectory(prefix="research-package-") as tmp:
        package_dir = Path(tmp)
        outputs = build_fn(official_report, package_id, package_dir)
        validation = validate_package_artifacts(
            outputs["artifacts"],
            expected_package_id=package_id,
            expected_source_report=official_report,
        )
        if validation["status"] != "ready":
            failure_path = write_package_failure(validation, data_dir / "diagnostics")
            return {
                "ok": False,
                "status": "failed",
                "package_id": package_id,
                "diagnostics_file": str(failure_path),
                "validation": validation,
            }

        atomic_publish_json_files(outputs["publish"])
        return {
            "ok": True,
            "status": "published",
            "package_id": package_id,
            "source_report": str(official_report),
            "market_date": market_date_from_report(official_report),
            "validation": validation,
            **outputs.get("metadata", {}),
        }


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
    expected_package_id = package_id_for_report(official_report) if official_report else None
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
    snapshot_package = snapshot.get("package_id")
    changes_package = changes.get("package_id")
    daily_package = daily_picks.get("package_id")

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

    for label, actual in [
        ("web_snapshot_package_id", snapshot_package),
        ("daily_picks_package_id", daily_package),
        ("research_changes_package_id", changes_package),
    ]:
        if expected_package_id and actual and actual != expected_package_id:
            mismatches.append(f"{label}_mismatch:{actual}!={expected_package_id}")

    if expected_package_id:
        if snapshot and not snapshot_package:
            mismatches.append("web_snapshot_package_id_missing")
        if daily_picks and not daily_package:
            mismatches.append("daily_picks_package_id_missing")
        if changes and not changes_package:
            mismatches.append("research_changes_package_id_missing")

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
        "expected_package_id": expected_package_id,
        "package_id": snapshot_package,
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
        "file_package_ids": {
            "web_snapshot": snapshot_package,
            "daily_picks": daily_package,
            "research_changes": changes_package,
        },
        "technical_diagnostics": {
            "expected_package_id": expected_package_id,
            "actual_package_id_per_file": {
                "web_snapshot": snapshot_package,
                "daily_picks": daily_package,
                "research_changes": changes_package,
            },
            "expected_source_report": str(official_report) if official_report else None,
            "actual_source_report_per_file": {
                "web_snapshot": snapshot.get("source_file"),
                "daily_picks": daily_picks.get("source_file"),
                "research_changes": changes.get("current_source"),
            },
            "expected_market_date": expected_market_date,
            "actual_market_date_per_file": {
                "web_snapshot": snapshot_date,
                "daily_picks": daily_date,
                "research_changes": changes_date,
            },
            "rank_one_per_file": {
                "web_snapshot": snapshot_rank_one,
                "daily_picks": daily_rank_one,
                "research_changes": changes_top,
            },
        },
    }
