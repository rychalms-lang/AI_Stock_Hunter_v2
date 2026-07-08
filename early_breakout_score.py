def calculate_early_breakout_score(row):
    score = 0
    reasons = []
    risks = []

    five_day = row.get("five_day_change", 0)
    twenty_day = row.get("twenty_day_change", 0)
    relative_strength = row.get("relative_strength", 0)
    volume_ratio = row.get("volume_ratio", 1)
    open_to_close = row.get("open_to_close_change", 0)

    # 1. Early trend, not already exploded
    if 2 <= five_day <= 10:
        score += 15
        reasons.append("Healthy 5-day momentum")

    if 3 <= twenty_day <= 25:
        score += 20
        reasons.append("20-day move is strong but not overextended")

    if twenty_day > 40:
        score -= 20
        risks.append("Stock may already be extended")

    if twenty_day > 75:
        score -= 35
        risks.append("Very extended 20-day move")

    # 2. Acceleration: recent strength becoming meaningful
    if abs(twenty_day) > 1:
        acceleration = five_day / abs(twenty_day)
    else:
        acceleration = five_day

    if 0.35 <= acceleration <= 1.25:
        score += 15
        reasons.append("Momentum acceleration looks constructive")

    if acceleration < 0.15 and twenty_day > 20:
        score -= 10
        risks.append("Recent momentum is weak compared with prior move")

    # 3. Relative strength improving
    if 3 <= relative_strength <= 25:
        score += 15
        reasons.append("Positive relative strength without extreme extension")

    if relative_strength > 50:
        score -= 10
        risks.append("Relative strength may be overheated")

    # 4. Volume confirmation
    if 1.15 <= volume_ratio <= 3:
        score += 15
        reasons.append("Volume confirmation without extreme spike")

    if volume_ratio > 4:
        score -= 10
        risks.append("Extreme volume spike may indicate exhaustion")

    # 5. Intraday confirmation
    if 0.5 <= open_to_close <= 5:
        score += 10
        reasons.append("Positive open-to-close action")

    if open_to_close > 8:
        score -= 8
        risks.append("Large intraday move may be chasey")

    if open_to_close < -1:
        score -= 15
        risks.append("Weak intraday close")

    # Normalize
    score = max(0, min(100, round(score, 2)))

    if not reasons:
        reasons.append("No strong early-breakout confirmations")

    if not risks:
        risks.append("No major early-breakout risks detected")

    return {
        "early_breakout_score": score,
        "early_breakout_reasons": reasons,
        "early_breakout_risks": risks,
        "acceleration_ratio": round(acceleration, 2)
    }