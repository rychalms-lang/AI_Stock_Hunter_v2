from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


PLACEHOLDER_REASONS = [
    "AI analysis module not connected yet in v2",
    "AI analysis module not connected yet in v2.",
    "not connected yet",
]


@dataclass
class AIRecommendation:
    ticker: str
    sector: str
    score: float
    confidence: float
    expected_return: float
    best_hold_period_days: int
    historical_matches: int
    risk: str
    action: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_hold_period(value: Any) -> int:
    if value is None:
        return 0

    text = str(value).strip().lower()

    if text in ["", "n/a", "nan", "none"]:
        return 0

    digits = "".join(char for char in text if char.isdigit())

    if not digits:
        return 0

    return int(digits)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        text = str(value).strip()

        if text == "" or text.lower() in ["nan", "none", "n/a"]:
            return default

        return float(text)

    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(safe_float(value, default))
    except Exception:
        return default


def is_valid_reason(reason: Optional[str]) -> bool:
    if not reason:
        return False

    text = str(reason).strip()

    if not text:
        return False

    lowered = text.lower()

    for placeholder in PLACEHOLDER_REASONS:
        if placeholder.lower() in lowered:
            return False

    return True


def determine_action(
    score: float,
    confidence: float,
    expected_return: float,
    historical_matches: int,
    risk: str,
) -> str:
    if expected_return < 0:
        return "AVOID"

    if historical_matches < 25:
        return "WATCH"

    if score >= 45 and confidence >= 80 and expected_return >= 2 and risk != "High":
        return "BUY"

    if score >= 35 and confidence >= 65 and expected_return >= 1:
        return "WATCH"

    return "HOLD"


def build_reason(
    ticker: str,
    sector: str,
    action: str,
    confidence: float,
    expected_return: float,
    historical_matches: int,
    best_hold_period_days: int,
    risk: str,
    score: float,
    fallback_reason: Optional[str] = None,
) -> str:
    if is_valid_reason(fallback_reason):
        return str(fallback_reason).strip()

    hold_text = (
        f"{best_hold_period_days}-day"
        if best_hold_period_days > 0
        else "forward"
    )

    evidence = []

    if expected_return >= 4:
        evidence.append(f"a strong expected {hold_text} return of {expected_return:.2f}%")
    elif expected_return >= 1:
        evidence.append(f"a positive expected {hold_text} return of {expected_return:.2f}%")
    elif expected_return < 0:
        evidence.append(f"a weak expected {hold_text} return of {expected_return:.2f}%")

    if historical_matches >= 100:
        evidence.append(f"{historical_matches} historical matches")
    elif historical_matches >= 25:
        evidence.append(f"{historical_matches} comparable historical setups")
    else:
        evidence.append("limited historical confirmation")

    if confidence >= 90:
        evidence.append(f"very high confidence at {confidence:.0f}%")
    elif confidence >= 75:
        evidence.append(f"solid confidence at {confidence:.0f}%")
    else:
        evidence.append(f"moderate confidence at {confidence:.0f}%")

    if risk == "High":
        evidence.append("elevated risk")
    elif risk == "Low":
        evidence.append("controlled risk")

    evidence_text = ", ".join(evidence)

    if action == "BUY":
        return (
            f"{ticker} is the strongest current opportunity in {sector}. "
            f"The setup is supported by {evidence_text}. "
            f"This is a candidate for active review before the next session."
        )

    if action == "WATCH":
        return (
            f"{ticker} is worth watching in {sector}. "
            f"The setup has {evidence_text}, but it is not strong enough for an "
            f"automatic buy yet."
        )

    if action == "AVOID":
        return (
            f"{ticker} should be avoided for now. "
            f"Although it passed the scanner, the setup shows {evidence_text}, "
            f"which does not justify new capital."
        )

    return (
        f"{ticker} is acceptable but not high conviction. "
        f"The setup has {evidence_text}, so the best action is to hold or wait "
        f"for stronger confirmation."
    )


def recommendation_from_row(row: Any) -> AIRecommendation:
    ticker = str(row.get("ticker", "UNKNOWN")).upper()
    sector = str(row.get("sector", "Other / Uncategorized"))

    score = safe_float(row.get("score", row.get("pre_score", 0)))
    confidence = safe_float(row.get("confidence_score", row.get("confidence", 0)))
    expected_return = safe_float(row.get("best_avg_return", row.get("expected_return", 0)))

    best_hold_period_days = parse_hold_period(
        row.get("best_hold_period", row.get("best_hold_period_days", 0))
    )

    historical_matches = safe_int(row.get("historical_matches", 0))
    risk = str(row.get("risk", "Medium"))

    action = determine_action(
        score=score,
        confidence=confidence,
        expected_return=expected_return,
        historical_matches=historical_matches,
        risk=risk,
    )

    reason = build_reason(
        ticker=ticker,
        sector=sector,
        action=action,
        confidence=confidence,
        expected_return=expected_return,
        historical_matches=historical_matches,
        best_hold_period_days=best_hold_period_days,
        risk=risk,
        score=score,
        fallback_reason=row.get("analysis_brief", row.get("reason", "")),
    )

    return AIRecommendation(
        ticker=ticker,
        sector=sector,
        score=round(score, 2),
        confidence=round(confidence, 1),
        expected_return=round(expected_return, 2),
        best_hold_period_days=best_hold_period_days,
        historical_matches=historical_matches,
        risk=risk,
        action=action,
        reason=reason,
    )


def build_recommendations_from_dataframe(df) -> List[AIRecommendation]:
    recommendations = []

    for _, row in df.iterrows():
        recommendations.append(recommendation_from_row(row))

    recommendations.sort(
        key=lambda item: (
            item.action == "BUY",
            item.expected_return,
            item.confidence,
            item.score,
        ),
        reverse=True,
    )

    return recommendations