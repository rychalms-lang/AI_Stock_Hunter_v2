import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from market_data_service import MarketDataService
from portfolio_governance import governance_summary


SCHEMA_VERSION = "1.0"
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
PAPER_DIR = DATA_DIR / "paper_trading"
REPORTS_DIR = PROJECT_ROOT / "reports"
AUTOMATION_DIR = PROJECT_ROOT / "automation"
LOCK_DIR = AUTOMATION_DIR / "locks"
LOG_DIR = AUTOMATION_DIR / "logs"
OUTPUT_FILE = DATA_DIR / "system_status.json"


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open() as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def latest_report() -> Optional[Path]:
    reports = sorted(REPORTS_DIR.glob("*_v2.csv"))
    return reports[-1] if reports else None


def file_status(path: Path) -> str:
    payload = read_json(path)
    if not payload:
        return "Unavailable"
    return str(payload.get("generated_at") or "Not yet recorded")


def parse_marker(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        for line in path.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def latest_daily_marker() -> Optional[Path]:
    markers = sorted(LOCK_DIR.glob("daily-pipeline-*.done"))
    return markers[-1] if markers else None


def daily_pipeline_status(report: Optional[Path]) -> Dict[str, Any]:
    marker = latest_daily_marker()
    marker_data = parse_marker(marker) if marker else {}
    daily_picks = read_json(PAPER_DIR / "daily_picks.json")

    last_success = marker_data.get("completed_at")
    last_market_date = marker_data.get("market_date") or (
        str(daily_picks.get("trade_date")) if daily_picks else None
    )

    if last_success:
        status = "healthy"
    elif report:
        status = "warning"
    else:
        status = "unknown"

    return {
        "status": status,
        "last_success_at": last_success or "Not yet recorded",
        "last_market_date": last_market_date or "Unavailable",
        "source_report": str(report) if report else "Unavailable",
    }


def parse_refresh_status() -> Dict[str, Any]:
    log_path = LOG_DIR / "paper-refresh.log"
    default = {
        "status": "unknown",
        "last_success_at": "Not yet recorded",
        "positions_updated": 0,
        "positions_stale": 0,
        "positions_closed": 0,
    }

    try:
        lines = log_path.read_text().splitlines()
    except OSError:
        return default

    for line in reversed(lines):
        start = line.find("{")
        if start == -1:
            continue
        try:
            payload = json.loads(line[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        price_status = str(payload.get("price_data_status", ""))
        stale = int(payload.get("positions_stale") or 0)
        status = "healthy"
        if stale > 0 or "stale" in price_status or "waiting" in price_status:
            status = "stale"

        return {
            "status": status,
            "last_success_at": payload.get("timestamp") or "Not yet recorded",
            "positions_updated": int(payload.get("positions_updated") or 0),
            "positions_stale": stale,
            "positions_closed": int(payload.get("positions_closed") or 0),
        }

    return default


def automation_status() -> Dict[str, Any]:
    user_agent_dir = Path.home() / "Library" / "LaunchAgents"
    daily = user_agent_dir / "com.aistockhunter.daily-pipeline.plist"
    refresh = user_agent_dir / "com.aistockhunter.paper-refresh.plist"

    return {
        "daily_pipeline_enabled": daily.exists(),
        "paper_refresh_enabled": refresh.exists(),
        "daily_pipeline_label": "com.aistockhunter.daily-pipeline",
        "paper_refresh_label": "com.aistockhunter.paper-refresh",
    }


def event_from_line(line: str) -> Optional[Dict[str, str]]:
    stripped = line.strip()
    if not stripped:
        return None

    timestamp = None
    message = stripped
    if stripped.startswith("[") and "]" in stripped:
        timestamp, message = stripped[1:].split("]", 1)
        message = message.strip()

    level = "info"
    lower = message.lower()
    if "error" in lower or '"status": "error"' in lower:
        level = "error"
    elif "stale" in lower or "skipped" in lower or "waiting" in lower:
        level = "warning"

    return {
        "timestamp": timestamp or "Not yet recorded",
        "level": level,
        "message": message[:240],
    }


def latest_events(limit: int = 8) -> List[Dict[str, str]]:
    lines: List[str] = []
    for path in [
        LOG_DIR / "daily-pipeline.log",
        LOG_DIR / "daily-pipeline-error.log",
        LOG_DIR / "paper-refresh.log",
        LOG_DIR / "paper-refresh-error.log",
    ]:
        try:
            lines.extend(path.read_text().splitlines()[-10:])
        except OSError:
            continue

    events = [event for line in lines if (event := event_from_line(line))]
    return events[-limit:]


def build_status() -> Dict[str, Any]:
    report = latest_report()
    daily_picks = read_json(PAPER_DIR / "daily_picks.json") or {}
    open_positions = read_json(PAPER_DIR / "open_positions.json") or {}
    portfolio = read_json(PAPER_DIR / "portfolio_summary.json") or {}
    web_snapshot = read_json(DATA_DIR / "web_snapshot.json") or {}

    try:
        market_state = MarketDataService().get_market_state()
    except Exception:
        market_state = "Unavailable"

    picks = daily_picks.get("picks") if isinstance(daily_picks.get("picks"), list) else []
    positions = (
        open_positions.get("positions")
        if isinstance(open_positions.get("positions"), list)
        else []
    )
    summary = portfolio.get("summary") if isinstance(portfolio.get("summary"), dict) else {}
    stale_positions = portfolio.get("stale_positions", summary.get("stale_positions", 0))
    governance = governance_summary(PAPER_DIR / "state")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "market_state": market_state,
        "daily_pipeline": daily_pipeline_status(report),
        "paper_refresh": parse_refresh_status(),
        "data_freshness": {
            "daily_picks": file_status(PAPER_DIR / "daily_picks.json"),
            "portfolio": file_status(PAPER_DIR / "portfolio_summary.json"),
            "web_snapshot": file_status(DATA_DIR / "web_snapshot.json"),
        },
        "strategy": {
            "name": "V8",
            "version": "8.0",
            "status": "Champion",
        },
        "automation": automation_status(),
        "scanner": {
            "candidate_count": len(picks),
            "last_export_timestamp": web_snapshot.get("generated_at", "Unavailable"),
            "source_file": web_snapshot.get("source_file", "Unavailable"),
        },
        "paper_portfolio": {
            "open_positions": len(positions),
            "stale_positions": int(stale_positions or 0),
            "price_status": portfolio.get("price_data_status", "Unavailable"),
            "last_market_update": portfolio.get("last_market_update", "Not yet recorded"),
        },
        "portfolio_governance": {
            "current_mode": governance["current_mode"],
            "label": governance["label"],
            "decision_authority": governance["decision_authority"],
            "automatic_entries_enabled": governance["automatic_entries_enabled"],
            "automatic_exits_enabled": governance["automatic_exits_enabled"],
            "manual_entries_enabled": governance["manual_entries_enabled"],
            "approval_required": governance["approval_required"],
            "pending_proposal_count": governance["pending_proposal_count"],
            "last_mode_change": governance["last_mode_change"],
            "governance_status": governance["governance_status"],
            "legacy_position_handling": governance["legacy_position_handling"],
        },
        "events": latest_events(),
    }


def export_system_status() -> Dict[str, Any]:
    payload = build_status()
    DATA_DIR.mkdir(exist_ok=True)
    with OUTPUT_FILE.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return payload


if __name__ == "__main__":
    result = export_system_status()
    print(f"System status written to {OUTPUT_FILE}")
    print(json.dumps({
        "market_state": result["market_state"],
        "daily_pipeline": result["daily_pipeline"]["status"],
        "paper_refresh": result["paper_refresh"]["status"],
    }, sort_keys=True))
