import json
import math
import os
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1.0"
STARTING_CAPITAL = 25000.0
DEFAULT_MODE = "ai_assisted"
VALID_MODES = {"ai_managed", "ai_assisted", "user_managed"}
GOVERNANCE_FILE = "portfolio_governance.json"
PROPOSALS_FILE = "pending_proposals.json"
AUDIT_FILE = "user_actions.json"
STRATEGY_METADATA = {"name": "V8", "version": "8.0", "status": "Champion"}
RESEARCH_METADATA = {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "paper_trading_update",
}
DEFAULT_CONFIG = {
    "minimum_cash_reserve_pct": 10.0,
    "max_positions": 5,
    "max_position_pct": 20.0,
    "stop_loss_pct": -5.0,
    "take_profit_pct": 10.0,
}

MODE_LABELS = {
    "ai_managed": "AI Managed",
    "ai_assisted": "AI Assisted",
    "user_managed": "User Managed",
}


class GovernanceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "n/a", "null"}:
            return default
        result = float(text)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(safe_float(value, default)))
    except Exception:
        return default


def round_money(value: Any) -> float:
    return round(safe_float(value), 2)


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(temp_path, path)


def default_governance(generated_at: Optional[str] = None) -> Dict[str, Any]:
    timestamp = generated_at or now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": DEFAULT_MODE,
        "updated_at": timestamp,
        "updated_by": "system_default",
        "effective_from": timestamp,
        "previous_mode": None,
        "mode_version": 1,
        "pending_transition": None,
    }


def mode_capabilities(mode: str) -> Dict[str, Any]:
    if mode == "ai_managed":
        return {
            "current_mode": mode,
            "label": MODE_LABELS[mode],
            "decision_authority": "v8",
            "entries": "V8 eligible scanner BUY entries may open automatically.",
            "exits": "V8 paper lifecycle rules manage eligible strategy-directed exits.",
            "automatic_entries_enabled": True,
            "automatic_exits_enabled": True,
            "manual_entries_enabled": False,
            "approval_required": False,
            "governance_status": "ai_managed_active",
            "legacy_position_handling": (
                "Existing user-directed positions remain user-directed and keep manual lifecycle authority."
            ),
        }
    if mode == "user_managed":
        return {
            "current_mode": mode,
            "label": MODE_LABELS[mode],
            "decision_authority": "user",
            "entries": "User controls simulated entries. V8 provides research only.",
            "exits": "New user-managed positions use manual lifecycle authority.",
            "automatic_entries_enabled": False,
            "automatic_exits_enabled": False,
            "manual_entries_enabled": True,
            "approval_required": False,
            "governance_status": "user_managed_active",
            "legacy_position_handling": (
                "Existing strategy-directed positions remain labeled Strategy Directed and keep their original lifecycle rules."
            ),
        }
    return {
        "current_mode": "ai_assisted",
        "label": MODE_LABELS["ai_assisted"],
        "decision_authority": "user_approved_v8",
        "entries": "V8 creates proposals. User approval is required before simulated entry.",
        "exits": "Exit proposals are tracked as governance work; automatic assisted exits are disabled in this sprint.",
        "automatic_entries_enabled": False,
        "automatic_exits_enabled": False,
        "manual_entries_enabled": True,
        "approval_required": True,
        "governance_status": "ai_assisted_active",
        "legacy_position_handling": (
            "Existing positions keep their original origin and lifecycle metadata."
        ),
    }


def read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return deepcopy(default)
    try:
        with path.open() as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        raise GovernanceError("corrupt_state", f"Corrupt governance state file: {path}") from exc
    if not isinstance(payload, dict):
        raise GovernanceError("invalid_state", f"Invalid governance state shape: {path}")
    return payload


def load_governance(state_dir: Path = Path("data/paper_trading/state")) -> Dict[str, Any]:
    payload = read_json(state_dir / GOVERNANCE_FILE, default_governance())
    mode = payload.get("mode")
    if mode not in VALID_MODES:
        payload["mode"] = DEFAULT_MODE
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("updated_at", None)
    payload.setdefault("updated_by", "system_default")
    payload.setdefault("effective_from", payload.get("updated_at"))
    payload.setdefault("previous_mode", None)
    payload.setdefault("mode_version", 1)
    payload.setdefault("pending_transition", None)
    return payload


def save_governance(state_dir: Path, payload: Dict[str, Any]) -> None:
    atomic_write_json(state_dir / GOVERNANCE_FILE, payload)


def load_proposals(state_dir: Path = Path("data/paper_trading/state")) -> Dict[str, Any]:
    payload = read_json(
        state_dir / PROPOSALS_FILE,
        {"schema_version": SCHEMA_VERSION, "proposals": []},
    )
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("proposals", [])
    if not isinstance(payload["proposals"], list):
        payload["proposals"] = []
    return payload


def save_proposals(state_dir: Path, payload: Dict[str, Any]) -> None:
    atomic_write_json(state_dir / PROPOSALS_FILE, payload)


def load_audit(state_dir: Path) -> Dict[str, Any]:
    payload = read_json(state_dir / AUDIT_FILE, {"schema_version": SCHEMA_VERSION, "actions": []})
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("actions", [])
    return payload


def append_audit(state_dir: Path, event: Dict[str, Any], dry_run: bool = False) -> None:
    if dry_run:
        return
    audit = load_audit(state_dir)
    audit["actions"].append(event)
    atomic_write_json(state_dir / AUDIT_FILE, audit)


def audit_event(
    request_id: str,
    event_type: str,
    result: str,
    previous_mode: Optional[str] = None,
    new_mode: Optional[str] = None,
    proposal_id: Optional[str] = None,
    ticker: Optional[str] = None,
    failure_reason: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "action_id": request_id,
        "request_id": request_id,
        "timestamp": timestamp or now_iso(),
        "type": event_type,
        "actor": "user",
        "result": result,
        "previous_mode": previous_mode,
        "new_mode": new_mode,
        "proposal_id": proposal_id,
        "ticker": ticker,
        "strategy": STRATEGY_METADATA,
        "research_metadata": RESEARCH_METADATA,
    }
    if failure_reason:
        payload["failure_reason"] = failure_reason
    return payload


def request_already_succeeded(state_dir: Path, request_id: str, event_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    audit = load_audit(state_dir)
    for event in audit.get("actions", []):
        if event.get("request_id") == request_id and event.get("result") == "success":
            if event_type is None or event.get("type") == event_type:
                return event
    return None


def set_mode(
    mode: str,
    request_id: str,
    state_dir: Path = Path("data/paper_trading/state"),
    generated_at: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if mode not in VALID_MODES:
        raise GovernanceError("invalid_mode", "Portfolio governance mode is invalid.")
    timestamp = generated_at or now_iso()
    previous_success = request_already_succeeded(state_dir, request_id, "mode_change_completed")
    if previous_success:
        return {"ok": True, "idempotent": True, "event": previous_success}

    current = load_governance(state_dir)
    previous_mode = current["mode"]
    updated = {
        **current,
        "mode": mode,
        "updated_at": timestamp,
        "updated_by": "user",
        "effective_from": timestamp,
        "previous_mode": previous_mode,
        "mode_version": safe_int(current.get("mode_version"), 1) + (0 if previous_mode == mode else 1),
        "pending_transition": None,
    }
    event = audit_event(
        request_id=request_id,
        event_type="mode_change_completed",
        result="success",
        previous_mode=previous_mode,
        new_mode=mode,
        timestamp=timestamp,
    )
    if not dry_run:
        save_governance(state_dir, updated)
        append_audit(state_dir, event)
    return {"ok": True, "governance": updated, "capabilities": mode_capabilities(mode)}


def governance_summary(state_dir: Path = Path("data/paper_trading/state")) -> Dict[str, Any]:
    governance = load_governance(state_dir)
    proposals = load_proposals(state_dir)
    pending_count = len([
        proposal
        for proposal in proposals.get("proposals", [])
        if proposal.get("status") == "pending"
    ])
    capabilities = mode_capabilities(governance["mode"])
    return {
        **governance,
        **capabilities,
        "pending_proposal_count": pending_count,
        "last_mode_change": governance.get("updated_at"),
    }


def stable_proposal_id(pick_id: str, action_type: str) -> str:
    return f"proposal_{action_type}_{pick_id}"


def find_proposal(proposals: Dict[str, Any], proposal_id: str) -> Optional[Dict[str, Any]]:
    for proposal in proposals.get("proposals", []):
        if proposal.get("proposal_id") == proposal_id:
            return proposal
    return None


def create_open_position_proposal(
    state_dir: Path,
    pick: Dict[str, Any],
    quote: Dict[str, Any],
    generated_at: str,
    proposed_amount: float,
    proposed_quantity: int,
    scanner_action: str,
    research_rating: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    proposals = load_proposals(state_dir)
    proposal_id = stable_proposal_id(str(pick["pick_id"]), "open_position")
    existing = find_proposal(proposals, proposal_id)
    if existing and existing.get("status") in {"pending", "approved", "executed"}:
        return existing

    price = safe_float(quote.get("price"))
    stop_loss = round_money(price * (1 + safe_float(DEFAULT_CONFIG["stop_loss_pct"]) / 100)) if price else None
    take_profit = round_money(price * (1 + safe_float(DEFAULT_CONFIG["take_profit_pct"]) / 100)) if price else None
    expires_at = (datetime.fromisoformat(generated_at[:19]) + timedelta(days=1)).isoformat(timespec="seconds")
    proposal = {
        "proposal_id": proposal_id,
        "created_at": generated_at,
        "expires_at": expires_at,
        "action_type": "open_position",
        "ticker": pick.get("ticker"),
        "source_pick_id": pick.get("pick_id"),
        "scanner_action": scanner_action,
        "research_rating": research_rating,
        "proposed_amount": round_money(proposed_amount),
        "proposed_quantity": proposed_quantity,
        "estimated_price": round_money(price),
        "quote_status": quote.get("price_status", "unavailable"),
        "price_source": quote.get("price_source"),
        "last_price_update": quote.get("last_price_update"),
        "rationale": pick.get("ai_explanation", {}).get("summary", "V8 scanner evidence generated this proposal."),
        "confidence": safe_float(pick.get("confidence")),
        "expected_return": safe_float(pick.get("expected_return_pct")),
        "risk": pick.get("risk", "Medium"),
        "hold_period": safe_int(pick.get("best_hold_period_days")),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "status": "pending",
        "user_decision": None,
        "decided_at": None,
        "strategy": pick.get("strategy", STRATEGY_METADATA),
        "research_metadata": pick.get("research_metadata", RESEARCH_METADATA),
    }
    proposals["proposals"].append(proposal)
    if not dry_run:
        save_proposals(state_dir, proposals)
        append_audit(
            state_dir,
            audit_event(
                request_id=proposal_id,
                event_type="proposal_created",
                result="success",
                new_mode="ai_assisted",
                proposal_id=proposal_id,
                ticker=str(pick.get("ticker", "")),
                timestamp=generated_at,
            ),
        )
    return proposal


def expire_old_proposals(state_dir: Path, generated_at: Optional[str] = None) -> int:
    timestamp = generated_at or now_iso()
    proposals = load_proposals(state_dir)
    changed = 0
    for proposal in proposals.get("proposals", []):
        if proposal.get("status") != "pending":
            continue
        expires_at = proposal.get("expires_at")
        if expires_at and expires_at < timestamp:
            proposal["status"] = "expired"
            proposal["user_decision"] = "expired"
            proposal["decided_at"] = timestamp
            changed += 1
    if changed:
        save_proposals(state_dir, proposals)
    return changed


def position_with_governance(
    position: Dict[str, Any],
    mode: str,
    origin: str,
    decision_authority: str,
    lifecycle_authority: str,
    user_approved: bool,
    proposal_id: Optional[str] = None,
) -> Dict[str, Any]:
    position.setdefault("origin", origin)
    position["governance_mode_at_entry"] = mode
    position["decision_authority"] = decision_authority
    position["strategy_name"] = STRATEGY_METADATA["name"]
    position["strategy_version"] = STRATEGY_METADATA["version"]
    position["user_approved"] = user_approved
    position["proposal_id"] = proposal_id
    position.setdefault("created_at", position.get("opened_at"))
    position["lifecycle_authority"] = lifecycle_authority
    return position


def auto_exit_allowed(position: Dict[str, Any], mode: str) -> bool:
    lifecycle = position.get("lifecycle_authority")
    origin = position.get("origin")
    if lifecycle == "user_manual" or origin == "user_directed":
        return False
    if mode == "ai_assisted":
        return False
    if mode == "user_managed":
        return origin in {"strategy_directed", None} and lifecycle in {"v8_rules", None}
    return True
