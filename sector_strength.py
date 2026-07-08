import yfinance as yf


SECTOR_ETFS = {
    "Semiconductors": "SMH",
    "Technology": "XLK",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Small Caps": "IWM",
    "Nasdaq Growth": "QQQ",
    "S&P 500": "SPY",
}


def get_sector_return(etf):
    try:
        hist = yf.Ticker(etf).history(period="3mo")

        if len(hist) < 20:
            return None

        current = hist["Close"].iloc[-1]
        five_day = hist["Close"].iloc[-5]
        twenty_day = hist["Close"].iloc[-20]

        five_day_return = ((current / five_day) - 1) * 100
        twenty_day_return = ((current / twenty_day) - 1) * 100

        score = (five_day_return * 0.4) + (twenty_day_return * 0.6)

        return {
            "etf": etf,
            "five_day_return": round(five_day_return, 2),
            "twenty_day_return": round(twenty_day_return, 2),
            "sector_score": round(score, 2)
        }

    except Exception as e:
        print(f"Error getting sector ETF {etf}: {e}")
        return None


def rank_sectors():
    results = []

    for sector, etf in SECTOR_ETFS.items():
        data = get_sector_return(etf)

        if data:
            results.append({
                "sector": sector,
                **data
            })

    return sorted(
        results,
        key=lambda x: x["sector_score"],
        reverse=True
    )


def get_top_sectors(limit=5):
    return rank_sectors()[:limit]