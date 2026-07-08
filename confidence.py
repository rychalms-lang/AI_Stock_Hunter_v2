def calculate_confidence(stock, sentiment_score=50, market_regime=None, sector_rank=None):
    confidence = 50
    reasons = []
    risks = []

    # Momentum confirmation
    if stock["five_day_change"] > 5:
        confidence += 10
        reasons.append("Strong 5-day momentum")

    if stock["twenty_day_change"] > 10:
        confidence += 10
        reasons.append("Strong 20-day trend")

    if stock["relative_strength"] > 10:
        confidence += 10
        reasons.append("Strong relative strength vs SPY")

    # Volume confirmation
    if stock["volume_ratio"] > 1.2:
        confidence += 10
        reasons.append("Above-average volume confirmation")

    # Intraday confirmation
    if stock["open_to_close_change"] > 1:
        confidence += 10
        reasons.append("Positive open-to-close action")

    # AI sentiment confirmation
    if sentiment_score >= 70:
        confidence += 10
        reasons.append("Bullish AI news analysis")

    # Market regime adjustment
    if market_regime:
        if market_regime.get("regime") == "Risk-On":
            confidence += 5
            reasons.append("Supportive risk-on market environment")
        elif market_regime.get("regime") == "Risk-Off":
            confidence -= 10
            risks.append("Risk-off market environment")

    # Sector strength adjustment
    if sector_rank is not None:
        if sector_rank <= 3:
            confidence += 10
            reasons.append("Stock belongs to a leading sector")
        elif sector_rank >= 10:
            confidence -= 5
            risks.append("Stock belongs to a weak sector")

    # Risk flags
    if stock["twenty_day_change"] > 40:
        confidence -= 10
        risks.append("Very extended 20-day move")

    if stock["open_to_close_change"] < -1:
        confidence -= 10
        risks.append("Weak intraday close")

    if sentiment_score <= 40:
        confidence -= 15
        risks.append("Bearish AI news analysis")

    if stock["volume_ratio"] > 4:
        confidence -= 5
        risks.append("Extreme volume spike may indicate exhaustion")

    confidence = max(0, min(100, confidence))

    if not reasons:
        reasons.append("No major confirmation signals")

    if not risks:
        risks.append("No major risk flags detected")

    return {
        "confidence_score": confidence,
        "confidence_reasons": reasons,
        "risk_flags": risks
    }