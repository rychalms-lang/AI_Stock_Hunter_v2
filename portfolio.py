def build_portfolio(ranked_stocks, max_positions=5):
    """
    Builds a simple suggested allocation from the ranked stock list.

    This is NOT a trade recommendation.
    It is a research allocation model for comparing ideas.
    """

    if not ranked_stocks:
        return {
            "cash_allocation": 100,
            "positions": []
        }

    candidates = ranked_stocks[:max_positions]

    total_confidence = sum(
        stock.get("confidence_score", 50)
        for stock in candidates
    )

    positions = []

    if total_confidence <= 0:
        weight = round(100 / len(candidates), 2)

        for stock in candidates:
            positions.append({
                "ticker": stock["ticker"],
                "sector": stock.get("sector", "Unknown"),
                "allocation_pct": weight,
                "confidence_score": stock.get("confidence_score", 50),
                "score": stock.get("score", stock.get("pre_score", 0))
            })

        return {
            "cash_allocation": 0,
            "positions": positions
        }

    market_risk_adjustment = 0

    average_confidence = total_confidence / len(candidates)

    if average_confidence >= 85:
        cash_allocation = 10
    elif average_confidence >= 70:
        cash_allocation = 20
    elif average_confidence >= 55:
        cash_allocation = 35
    else:
        cash_allocation = 50

    investable_allocation = 100 - cash_allocation

    for stock in candidates:
        confidence = stock.get("confidence_score", 50)

        allocation = (
            confidence / total_confidence
        ) * investable_allocation

        positions.append({
            "ticker": stock["ticker"],
            "sector": stock.get("sector", "Unknown"),
            "allocation_pct": round(allocation, 2),
            "confidence_score": confidence,
            "score": stock.get("score", stock.get("pre_score", 0))
        })

    return {
        "cash_allocation": cash_allocation,
        "positions": positions
    }