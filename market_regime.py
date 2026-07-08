import yfinance as yf


def get_trend_score(ticker):
    hist = yf.Ticker(ticker).history(period="6mo")

    if len(hist) < 50:
        return {
            "ticker": ticker,
            "trend": "Unknown",
            "score": 0,
            "price": 0,
            "ma20": 0,
            "ma50": 0,
            "return_20d": 0
        }

    price = hist["Close"].iloc[-1]
    ma20 = hist["Close"].tail(20).mean()
    ma50 = hist["Close"].tail(50).mean()
    price_20d = hist["Close"].iloc[-20]

    return_20d = ((price / price_20d) - 1) * 100

    score = 0

    if price > ma20:
        score += 25

    if price > ma50:
        score += 25

    if ma20 > ma50:
        score += 25

    if return_20d > 0:
        score += 25

    if score >= 75:
        trend = "Bullish"
    elif score >= 50:
        trend = "Mixed"
    else:
        trend = "Bearish"

    return {
        "ticker": ticker,
        "trend": trend,
        "score": score,
        "price": round(price, 2),
        "ma20": round(ma20, 2),
        "ma50": round(ma50, 2),
        "return_20d": round(return_20d, 2)
    }


def get_market_regime():
    spy = get_trend_score("SPY")
    qqq = get_trend_score("QQQ")
    iwm = get_trend_score("IWM")

    average_score = round(
        (spy["score"] + qqq["score"] + iwm["score"]) / 3,
        2
    )

    if average_score >= 75:
        regime = "Risk-On"
        description = "Major indexes are broadly trending higher."
    elif average_score >= 50:
        regime = "Mixed"
        description = "Market conditions are positive but uneven."
    else:
        regime = "Risk-Off"
        description = "Major indexes are weak or below key trend levels."

    return {
        "regime": regime,
        "market_score": average_score,
        "description": description,
        "spy": spy,
        "qqq": qqq,
        "iwm": iwm
    }