from __future__ import annotations

import hashlib
import html
import json
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional, Protocol
from zoneinfo import ZoneInfo

from dotenv import dotenv_values


DISCLAIMER = (
    "Paper trading simulation only. No real trades are placed. "
    "This is research and decision support, not investment advice."
)
NOTIFICATION_FILE = "trade_notifications.json"
AUDIT_FILE = "user_actions.json"


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None:
        ...


@dataclass
class SmtpEmailSender:
    email_address: str
    email_password: str
    host: str = "smtp.gmail.com"
    port: int = 465

    def send(self, message: EmailMessage) -> None:
        with smtplib.SMTP_SSL(self.host, self.port) as smtp:
            smtp.login(self.email_address, self.email_password)
            smtp.send_message(message)


class FakeEmailSender:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("Fake sender failure")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_env() -> Dict[str, Optional[str]]:
    values = {**dotenv_values(".env"), **os.environ}
    return {
        "email_address": values.get("EMAIL_ADDRESS"),
        "email_password": values.get("EMAIL_PASSWORD"),
        "enabled": values.get("TRADE_EMAIL_NOTIFICATIONS_ENABLED", "false"),
        "recipient": values.get("TRADE_EMAIL_RECIPIENT") or values.get("EMAIL_ADDRESS"),
        "from_name": values.get("TRADE_EMAIL_FROM_NAME", "AI Stock Hunter"),
        "max_retries": values.get("TRADE_EMAIL_MAX_RETRIES", "3"),
    }


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else default.copy()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default.copy()


def notification_id(event_id: str) -> str:
    digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:20]
    return f"trade_email_{digest}"


def event_id(event: Dict[str, Any]) -> str:
    if event.get("event_id"):
        return str(event["event_id"])
    return "|".join([
        str(event.get("event_type", "trade_event")),
        str(event.get("position_id") or event.get("trade_id")),
        str(event.get("ticker")),
        str(event.get("created_at")),
    ])


def money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "Unavailable"


def pct(value: Any) -> str:
    try:
        number = float(value)
        sign = "+" if number > 0 else ""
        return f"{sign}{number:.2f}%"
    except Exception:
        return "Unavailable"


STATUS_LABELS = {
    "ai_assisted": "AI Assisted",
    "ai_managed": "AI Managed",
    "avoid": "Avoid",
    "buy": "Buy",
    "closed": "Closed",
    "current": "Current quote",
    "delayed": "Delayed quote",
    "eligible": "Eligible",
    "hold": "Hold",
    "open": "Open",
    "opened": "Opened",
    "paper_engine": "Paper Engine",
    "position_closed": "Simulated position closed",
    "position_opened": "Simulated position opened",
    "scanner_automatic": "Added by V8",
    "stale": "Stale quote",
    "strategy_directed": "Added by V8",
    "take_profit": "Take-profit reached",
    "stop_loss": "Stop-loss reached",
    "time_exit": "Planned hold completed",
    "user": "User",
    "user_approved_v8": "Approved V8 suggestion",
    "user_directed": "Added by User",
    "user_managed": "User Managed",
    "v8": "V8",
    "watch": "Watch",
}


def clean(value: Any) -> str:
    if value is None or value == "":
        return "Unavailable"
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    text = str(value).strip()
    normalized = text.lower()
    if normalized in STATUS_LABELS:
        return STATUS_LABELS[normalized]
    text = text.replace("_", " ").replace("-", " ").strip()
    return " ".join(word.upper() if word.upper() in {"AI", "V8", "V9"} else word.capitalize() for word in text.split())


def format_datetime(value: Any) -> str:
    if value is None or value == "":
        return "Unavailable"
    text = str(value).strip()
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            parsed = datetime.strptime(text, "%Y-%m-%d")
            return parsed.strftime("%b %-d, %Y")
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
        eastern = parsed.astimezone(ZoneInfo("America/New_York"))
        return eastern.strftime("%b %-d, %Y at %-I:%M %p ET")
    except Exception:
        return clean(value)


def format_days(value: Any) -> str:
    if value is None or value == "":
        return "Unavailable"
    try:
        number = int(float(value))
        unit = "day" if number == 1 else "days"
        return f"{number} {unit}"
    except Exception:
        return clean(value)


def signed_money(value: Any) -> str:
    try:
        number = float(value)
        sign = "+" if number > 0 else ""
        return f"{sign}${number:,.2f}" if number >= 0 else f"-${abs(number):,.2f}"
    except Exception:
        return "Unavailable"


def performance_color(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "#111111"
    if number > 0:
        return "#16794c"
    if number < 0:
        return "#b42318"
    return "#111111"


def masked_recipient(value: Optional[str]) -> str:
    if not value or "@" not in value:
        return "not configured"
    name, domain = value.split("@", 1)
    return f"{name[:2]}***@{domain}"


def build_subject(event: Dict[str, Any], test: bool = False) -> str:
    prefix = "TEST — " if test else ""
    ticker = event.get("ticker", "Unknown")
    if event.get("event_type") == "position_closed":
        return f"{prefix}AI Stock Hunter — {ticker} Closed at {pct(event.get('realized_return_pct'))}"
    if str(event.get("decision_authority") or event.get("origin") or "").lower() == "user_approved_v8":
        return f"{prefix}AI Stock Hunter — Approved Simulated Position Opened: {ticker}"
    return f"{prefix}AI Stock Hunter — Simulated Position Opened: {ticker}"


def added_by(event: Dict[str, Any]) -> str:
    authority = str(event.get("decision_authority") or event.get("origin") or "")
    if authority == "v8":
        return "V8"
    if authority == "user_approved_v8":
        return "Approved V8 suggestion"
    if authority == "user":
        return "Added by User"
    return clean(authority or "Paper engine")


def explanation(event: Dict[str, Any]) -> str:
    value = event.get("explanation")
    if isinstance(value, dict):
        return str(value.get("summary") or "Evidence was preserved from the source paper-trading record.")
    return str(value or "Evidence was preserved from the source paper-trading record.")


def entry_lines(event: Dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("Ticker", clean(event.get("ticker"))),
        ("Sector", clean(event.get("sector"))),
        ("Action", "Simulated position opened"),
        ("Added by", added_by(event)),
        ("Trading mode", clean(event.get("governance_mode"))),
        ("Quantity", clean(event.get("quantity"))),
        ("Entry price", money(event.get("entry_price"))),
        ("Position value", money(event.get("invested_amount"))),
        ("Portfolio weight", pct(event.get("portfolio_weight_pct"))),
        ("Cash remaining", money(event.get("cash_after"))),
        ("AI Research Rating", clean(event.get("research_rating"))),
        ("Strategy Signal", clean(event.get("strategy_signal"))),
        ("Confidence", pct(event.get("confidence"))),
        ("Expected return", pct(event.get("expected_return"))),
        ("Suggested hold", format_days(event.get("planned_hold_days"))),
        ("Historical comparisons", clean(event.get("historical_matches"))),
        ("Risk", clean(event.get("risk"))),
        ("Stop-loss", money(event.get("stop_loss"))),
        ("Take-profit", money(event.get("take_profit"))),
        ("Why opened", explanation(event)),
        ("Risk flags", clean(", ".join(event.get("risk_flags") or []) if isinstance(event.get("risk_flags"), list) else event.get("risk_flags"))),
        ("Source research date", format_datetime(event.get("source_research_date"))),
        ("Quote time", format_datetime(event.get("quote_timestamp"))),
        ("Price status", clean(event.get("price_status"))),
    ]


def exit_lines(event: Dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("Ticker", clean(event.get("ticker"))),
        ("Action", "Simulated position closed"),
        ("Exit reason", clean(event.get("exit_reason"))),
        ("Exit authority", added_by(event)),
        ("Quantity", clean(event.get("quantity"))),
        ("Entry price", money(event.get("entry_price"))),
        ("Exit price", money(event.get("exit_price"))),
        ("Realized P/L", signed_money(event.get("realized_pnl"))),
        ("Realized return", pct(event.get("realized_return_pct"))),
        ("Hold duration", format_days(event.get("actual_hold_days"))),
        ("Planned hold", format_days(event.get("planned_hold_days"))),
        ("Original confidence", pct(event.get("confidence"))),
        ("Original expected return", pct(event.get("expected_return"))),
        ("Original risk", clean(event.get("risk"))),
        ("Cash after exit", money(event.get("cash_after"))),
        ("Portfolio equity after exit", money(event.get("total_equity_after"))),
        ("Why closed", explanation(event)),
        ("Exit style", "Automatic" if event.get("decision_authority") != "user" else "User-directed"),
    ]


def value_for(event: Dict[str, Any], key: str) -> str:
    values = dict(exit_lines(event) if event.get("event_type") == "position_closed" else entry_lines(event))
    return values.get(key, "Unavailable")


def section_text(title: str, pairs: list[tuple[str, str]]) -> list[str]:
    lines = [title.upper(), "-" * len(title)]
    width = max([len(label) for label, _ in pairs] or [0])
    lines.extend(f"{label.ljust(width)}  {value}" for label, value in pairs)
    return lines


def build_text_body(event: Dict[str, Any], test: bool = False) -> str:
    closed = event.get("event_type") == "position_closed"
    title = "Simulated Position Closed" if closed else "Simulated Position Opened"
    if test:
        title = f"TEST - {title}"
    lines = ["AI STOCK HUNTER", title, "=" * 48, ""]
    if closed:
        lines += section_text("Trade Result", [
            ("Ticker", clean(event.get("ticker"))),
            ("Outcome", signed_money(event.get("realized_pnl"))),
            ("Return", pct(event.get("realized_return_pct"))),
            ("Exit reason", clean(event.get("exit_reason"))),
        ])
        lines += [""] + section_text("Execution Details", [
            ("Quantity", clean(event.get("quantity"))),
            ("Entry price", money(event.get("entry_price"))),
            ("Exit price", money(event.get("exit_price"))),
            ("Hold duration", format_days(event.get("actual_hold_days"))),
            ("Planned hold", format_days(event.get("planned_hold_days"))),
            ("Cash", money(event.get("cash_after"))),
            ("Total equity", money(event.get("total_equity_after"))),
        ])
        lines += [""] + section_text("Original Research Context", [
            ("AI Research Rating", clean(event.get("research_rating"))),
            ("Strategy Signal", clean(event.get("strategy_signal"))),
            ("Confidence", pct(event.get("confidence"))),
            ("Expected return", pct(event.get("expected_return"))),
            ("Risk", clean(event.get("risk"))),
        ])
        lines += ["", "WHY THE POSITION CLOSED", "-----------------------", explanation(event)]
    else:
        lines += section_text("Position Summary", [
            ("Ticker", clean(event.get("ticker"))),
            ("Sector", clean(event.get("sector"))),
            ("Action", "Simulated position opened"),
            ("Added by", added_by(event)),
            ("Entry", money(event.get("entry_price"))),
            ("Position value", money(event.get("invested_amount"))),
            ("Portfolio weight", pct(event.get("portfolio_weight_pct"))),
        ])
        lines += [""] + section_text("Research Summary", [
            ("AI Research Rating", clean(event.get("research_rating"))),
            ("Strategy Signal", clean(event.get("strategy_signal"))),
            ("Confidence", pct(event.get("confidence"))),
            ("Expected return", pct(event.get("expected_return"))),
            ("Suggested hold", format_days(event.get("planned_hold_days"))),
            ("Historical comparisons", clean(event.get("historical_matches"))),
            ("Risk", clean(event.get("risk"))),
        ])
        lines += [""] + section_text("Risk Controls", [
            ("Stop-loss", money(event.get("stop_loss"))),
            ("Take-profit", money(event.get("take_profit"))),
            ("Cash remaining", money(event.get("cash_after"))),
            ("Open positions after entry", clean(event.get("open_positions_after"))),
        ])
        lines += ["", "WHY THIS POSITION WAS OPENED", "----------------------------", explanation(event)]
    lines += [""] + section_text("Source Details", [
        ("Research date", format_datetime(event.get("source_research_date"))),
        ("Quote time", format_datetime(event.get("quote_timestamp"))),
        ("Quote status", clean(event.get("price_status"))),
        ("Trading mode", clean(event.get("governance_mode"))),
        ("Source pick ID", clean(event.get("source_pick_id"))),
    ])
    lines.extend(["", DISCLAIMER])
    return "\n".join(lines)


def html_row(label: str, value: str, *, color: str = "#111111") -> str:
    return (
        "<tr>"
        f"<td style=\"padding:10px 0;border-bottom:1px solid #eeeeea;color:#6b6b65;font-size:13px;line-height:18px;\">{html.escape(label)}</td>"
        f"<td align=\"right\" style=\"padding:10px 0;border-bottom:1px solid #eeeeea;color:{color};font-size:14px;line-height:18px;font-weight:600;\">{html.escape(value)}</td>"
        "</tr>"
    )


def metric_table(metrics: list[tuple[str, str, str]]) -> str:
    cells = []
    for label, value, color in metrics:
        cells.append(
            "<td width=\"33.33%\" valign=\"top\" style=\"padding:0 18px 18px 0;\">"
            f"<div style=\"font-size:11px;line-height:15px;letter-spacing:.08em;text-transform:uppercase;color:#8a8a84;margin-bottom:6px;\">{html.escape(label)}</div>"
            f"<div style=\"font-size:20px;line-height:26px;font-weight:650;color:{color};\">{html.escape(value)}</div>"
            "</td>"
        )
    rows = ""
    for index in range(0, len(cells), 3):
        rows += f"<tr>{''.join(cells[index:index + 3])}</tr>"
    return f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">{rows}</table>"


def details_table(pairs: list[tuple[str, str]], *, color_labels: Optional[Dict[str, str]] = None) -> str:
    color_labels = color_labels or {}
    rows = "".join(html_row(label, value, color=color_labels.get(label, "#111111")) for label, value in pairs)
    return f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">{rows}</table>"


def html_section(title: str, body: str) -> str:
    return (
        "<tr><td style=\"padding:30px 0 0 0;\">"
        f"<div style=\"font-size:12px;line-height:16px;letter-spacing:.1em;text-transform:uppercase;color:#8a8a84;margin-bottom:12px;\">{html.escape(title)}</div>"
        f"{body}"
        "</td></tr>"
    )


def build_html_body(event: Dict[str, Any], test: bool = False) -> str:
    closed = event.get("event_type") == "position_closed"
    ticker = clean(event.get("ticker"))
    title = "Simulated Position Closed" if closed else "Simulated Position Opened"
    subtitle = "Professional paper-trading report"
    action_time = format_datetime(event.get("created_at"))
    source_date = format_datetime(event.get("source_research_date"))
    mode = clean(event.get("governance_mode"))
    test_badge = "<div style=\"display:inline-block;margin-bottom:16px;padding:5px 9px;border:1px solid #e0b4a4;color:#9a3412;font-size:12px;line-height:16px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;\">TEST - no email was sent unless explicitly requested</div>" if test else ""

    if closed:
        return_color = performance_color(event.get("realized_return_pct"))
        sections = "".join([
            html_section("Trade Result", metric_table([
                ("Outcome", signed_money(event.get("realized_pnl")), performance_color(event.get("realized_pnl"))),
                ("Return", pct(event.get("realized_return_pct")), return_color),
                ("Exit reason", clean(event.get("exit_reason")), "#111111"),
            ])),
            html_section("Execution", details_table([
                ("Quantity", clean(event.get("quantity"))),
                ("Entry price", money(event.get("entry_price"))),
                ("Exit price", money(event.get("exit_price"))),
                ("Hold duration", format_days(event.get("actual_hold_days"))),
                ("Planned hold", format_days(event.get("planned_hold_days"))),
                ("Realized P/L", signed_money(event.get("realized_pnl"))),
                ("Realized return", pct(event.get("realized_return_pct"))),
            ], color_labels={"Realized P/L": performance_color(event.get("realized_pnl")), "Realized return": return_color})),
            html_section("Why the position closed", f"<p style=\"margin:0;color:#292926;font-size:15px;line-height:24px;\">{html.escape(explanation(event))}</p>"),
            html_section("Original Research Context", details_table([
                ("AI Research Rating", clean(event.get("research_rating"))),
                ("Strategy Signal", clean(event.get("strategy_signal"))),
                ("Confidence", pct(event.get("confidence"))),
                ("Expected return", pct(event.get("expected_return"))),
                ("Risk", clean(event.get("risk"))),
                ("Original source date", source_date),
            ])),
            html_section("Portfolio After Exit", details_table([
                ("Cash", money(event.get("cash_after"))),
                ("Total equity", money(event.get("total_equity_after"))),
                ("Open positions remaining", clean(event.get("open_positions_after"))),
            ])),
        ])
    else:
        sections = "".join([
            html_section("Position Summary", metric_table([
                ("Entry", money(event.get("entry_price")), "#111111"),
                ("Position value", money(event.get("invested_amount")), "#111111"),
                ("Portfolio weight", pct(event.get("portfolio_weight_pct")), "#111111"),
            ])),
            html_section("Research Summary", details_table([
                ("AI Research Rating", clean(event.get("research_rating"))),
                ("Strategy Signal", clean(event.get("strategy_signal"))),
                ("Confidence", pct(event.get("confidence"))),
                ("Expected return", pct(event.get("expected_return"))),
                ("Suggested hold", format_days(event.get("planned_hold_days"))),
                ("Historical comparisons", clean(event.get("historical_matches"))),
                ("Risk", clean(event.get("risk"))),
            ], color_labels={"Expected return": performance_color(event.get("expected_return"))})),
            html_section("Why this position was opened", f"<p style=\"margin:0;color:#292926;font-size:15px;line-height:24px;\">{html.escape(explanation(event))}</p>"),
            html_section("Risk Controls", details_table([
                ("Stop-loss", money(event.get("stop_loss"))),
                ("Take-profit", money(event.get("take_profit"))),
                ("Planned hold period", format_days(event.get("planned_hold_days"))),
                ("Cash remaining", money(event.get("cash_after"))),
                ("Open positions after entry", clean(event.get("open_positions_after"))),
            ])),
        ])

    source_details = html_section("Source Details", details_table([
        ("Ticker", ticker),
        ("Sector", clean(event.get("sector"))),
        ("Action time", action_time),
        ("Trading mode", mode),
        ("Source research date", source_date),
        ("Quote time", format_datetime(event.get("quote_timestamp"))),
        ("Quote status", clean(event.get("price_status"))),
        ("Source pick ID", clean(event.get("source_pick_id"))),
    ]))

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(build_subject(event, test))}</title>
  </head>
  <body style="margin:0;padding:0;background:#f8f8f6;color:#111111;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#f8f8f6;">
      <tr>
        <td align="center" style="padding:28px 14px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;max-width:640px;background:#ffffff;border:1px solid #e8e8e3;">
            <tr><td style="height:3px;background:#9bd23c;font-size:0;line-height:0;">&nbsp;</td></tr>
            <tr>
              <td style="padding:34px 34px 18px 34px;">
                {test_badge}
                <div style="font-size:11px;line-height:15px;letter-spacing:.18em;text-transform:uppercase;color:#6f6f68;font-weight:700;">AI STOCK HUNTER</div>
                <h1 style="margin:12px 0 6px 0;color:#050505;font-size:34px;line-height:39px;font-weight:700;">{html.escape(title)}</h1>
                <p style="margin:0;color:#666660;font-size:15px;line-height:23px;">{html.escape(subtitle)}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:0 34px 10px 34px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="padding:16px 0;border-top:1px solid #eeeeea;border-bottom:1px solid #eeeeea;color:#050505;font-size:26px;line-height:30px;font-weight:700;">{html.escape(ticker)}</td>
                    <td align="right" style="padding:16px 0;border-top:1px solid #eeeeea;border-bottom:1px solid #eeeeea;color:#666660;font-size:13px;line-height:19px;">{html.escape(clean(event.get('sector')))}<br>{html.escape(action_time)}</td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr><td style="padding:0 34px 36px 34px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{sections}{source_details}</table></td></tr>
            <tr>
              <td style="padding:22px 34px 32px 34px;background:#fbfbfa;border-top:1px solid #eeeeea;color:#6b6b65;font-size:12px;line-height:19px;">
                {html.escape(DISCLAIMER)}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def append_audit(state_dir: Path, action: Dict[str, Any]) -> None:
    audit = read_json(state_dir / AUDIT_FILE, {"schema_version": "1.0", "actions": []})
    audit.setdefault("schema_version", "1.0")
    audit.setdefault("actions", []).append(action)
    atomic_write_json(state_dir / AUDIT_FILE, audit)


def audit_notification(state_dir: Path, event: Dict[str, Any], record: Dict[str, Any], action_type: str, result: str, recipient: Optional[str], failure_reason: Optional[str] = None) -> None:
    append_audit(state_dir, {
        "action_id": record["notification_id"],
        "request_id": record["notification_id"],
        "timestamp": now_iso(),
        "type": action_type,
        "actor": "system",
        "result": result,
        "event_id": record["event_id"],
        "notification_id": record["notification_id"],
        "event_type": record["event_type"],
        "ticker": record["ticker"],
        "retry_count": record["attempt_count"],
        "recipient": masked_recipient(recipient),
        "failure_reason": failure_reason,
    })


def notification_status(state_dir: Path) -> Dict[str, Any]:
    state = read_json(state_dir / NOTIFICATION_FILE, {"schema_version": "1.0", "notifications": {}})
    records = list((state.get("notifications") or {}).values())
    return {
        "enabled": str(read_env()["enabled"]).lower() == "true",
        "recipient_configured": bool(read_env()["recipient"]),
        "last_successful_email": max([r.get("sent_at") for r in records if r.get("sent_at")] or [None]),
        "last_failed_email": max([r.get("last_attempt_at") for r in records if r.get("status") in {"failed", "retry_pending"} and r.get("last_attempt_at")] or [None]),
        "pending_retries": len([r for r in records if r.get("status") == "retry_pending"]),
        "total_sent": len([r for r in records if r.get("status") == "sent"]),
        "total_failed": len([r for r in records if r.get("status") == "failed"]),
        "last_failure_reason": next((r.get("failure_reason") for r in reversed(records) if r.get("failure_reason")), None),
    }


def notify_trade_event(
    event: Dict[str, Any],
    *,
    state_dir: Path = Path("data/paper_trading/state"),
    sender: Optional[EmailSender] = None,
    dry_run: bool = False,
    test: bool = False,
) -> Dict[str, Any]:
    env = read_env()
    max_retries = int(env["max_retries"] or 3)
    eid = event_id(event)
    nid = notification_id(eid)
    state = read_json(state_dir / NOTIFICATION_FILE, {"schema_version": "1.0", "notifications": {}})
    notifications = state.setdefault("notifications", {})
    record = notifications.get(nid) or {
        "notification_id": nid,
        "event_id": eid,
        "event_type": event.get("event_type"),
        "position_id": event.get("position_id"),
        "ticker": event.get("ticker"),
        "status": "pending",
        "first_attempt_at": None,
        "last_attempt_at": None,
        "sent_at": None,
        "attempt_count": 0,
        "failure_reason": None,
    }

    if record.get("status") == "sent":
        notifications[nid] = record
        atomic_write_json(state_dir / NOTIFICATION_FILE, state)
        return {"ok": True, "status": "skipped", "reason": "already_sent", "notification": record}

    if dry_run:
        return {"ok": True, "status": "rendered", "subject": build_subject(event, test), "text": build_text_body(event, test), "html": build_html_body(event, test)}

    if str(env["enabled"]).lower() != "true":
        record.update({"status": "disabled", "last_attempt_at": now_iso(), "failure_reason": "Trade email notifications are disabled."})
        notifications[nid] = record
        atomic_write_json(state_dir / NOTIFICATION_FILE, state)
        audit_notification(state_dir, event, record, "notification_created", "disabled", env["recipient"], record["failure_reason"])
        return {"ok": True, "status": "disabled", "notification": record}

    if not env["email_address"] or not env["email_password"] or not env["recipient"]:
        record.update({"status": "failed", "last_attempt_at": now_iso(), "failure_reason": "Email configuration is incomplete."})
        notifications[nid] = record
        atomic_write_json(state_dir / NOTIFICATION_FILE, state)
        audit_notification(state_dir, event, record, "notification_failed", "failed", env["recipient"], record["failure_reason"])
        return {"ok": False, "status": "failed", "notification": record}

    if record["attempt_count"] >= max_retries:
        record["status"] = "failed"
        notifications[nid] = record
        atomic_write_json(state_dir / NOTIFICATION_FILE, state)
        audit_notification(state_dir, event, record, "notification_abandoned", "failed", env["recipient"], "Maximum retries reached.")
        return {"ok": False, "status": "failed", "notification": record}

    record["attempt_count"] += 1
    record["first_attempt_at"] = record["first_attempt_at"] or now_iso()
    record["last_attempt_at"] = now_iso()
    notifications[nid] = record
    atomic_write_json(state_dir / NOTIFICATION_FILE, state)
    audit_notification(state_dir, event, record, "notification_created", "pending", env["recipient"])

    message = EmailMessage()
    message["Subject"] = build_subject(event, test)
    message["From"] = f"{env['from_name']} <{env['email_address']}>"
    message["To"] = str(env["recipient"])
    message.set_content(build_text_body(event, test))
    message.add_alternative(build_html_body(event, test), subtype="html")

    try:
        (sender or SmtpEmailSender(str(env["email_address"]), str(env["email_password"]))).send(message)
        record.update({"status": "sent", "sent_at": now_iso(), "failure_reason": None})
        notifications[nid] = record
        atomic_write_json(state_dir / NOTIFICATION_FILE, state)
        audit_notification(state_dir, event, record, "notification_sent", "success", env["recipient"])
        return {"ok": True, "status": "sent", "notification": record}
    except Exception as exc:
        record["failure_reason"] = str(exc)[:240]
        record["status"] = "retry_pending" if record["attempt_count"] < max_retries else "failed"
        notifications[nid] = record
        atomic_write_json(state_dir / NOTIFICATION_FILE, state)
        audit_notification(
            state_dir,
            event,
            record,
            "notification_retry_scheduled" if record["status"] == "retry_pending" else "notification_failed",
            "failed",
            env["recipient"],
            record["failure_reason"],
        )
        return {"ok": False, "status": record["status"], "notification": record}


def sample_event(event_type: str = "position_opened") -> Dict[str, Any]:
    base = {
        "event_type": "position_opened" if event_type in {"opened", "position_opened"} else "position_closed",
        "created_at": now_iso(),
        "position_id": "test_position_001",
        "ticker": "HIMS",
        "sector": "Consumer Health",
        "origin": "test",
        "governance_mode": "ai_managed",
        "decision_authority": "v8",
        "strategy_name": "V8",
        "strategy_version": "8.0",
        "source_pick_id": "test_pick_001",
        "strategy_signal": "BUY",
        "research_rating": "BUY",
        "confidence": 75,
        "expected_return": 5.79,
        "historical_matches": 61,
        "risk": "Medium",
        "quantity": 10,
        "entry_price": 100,
        "invested_amount": 1000,
        "portfolio_weight_pct": 4,
        "stop_loss": 95,
        "take_profit": 110,
        "planned_hold_days": 10,
        "quote_timestamp": "2026-07-14T10:00:00-04:00",
        "price_status": "DELAYED",
        "cash_after": 24000,
        "total_equity_after": 25000,
        "open_positions_after": 1,
        "explanation": "Synthetic test event for rendering the paper-trade email template.",
        "risk_flags": ["Test email"],
        "source_research_date": "2026-07-14",
    }
    if base["event_type"] == "position_closed":
        base.update({
            "exit_price": 106.2,
            "proceeds": 1062,
            "realized_pnl": 62,
            "realized_return_pct": 6.2,
            "actual_hold_days": 8,
            "exit_reason": "take_profit",
        })
    return base
