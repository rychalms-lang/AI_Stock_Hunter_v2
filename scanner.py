import yfinance as yf
import pandas as pd

from settings import (
    TICKERS_FILE,
    MIN_AVG_VOLUME,
    MARKET_BENCHMARK
)


def load_tickers():
    with open(TICKERS_FILE, "r") as f:
        return list(dict.fromkeys([
            line.strip().upper()
            for line in f
            if line.strip()
        ]))


def safe_pct_change(current, previous):
    if previous == 0:
        return 0
    return ((current / previous) - 1) * 100


def get_spy_return():
    spy = yf.Ticker(MARKET_BENCHMARK).history(period="3mo")

    if len(spy) < 20:
        return 0

    return safe_pct_change(spy["Close"].iloc[-1], spy["Close"].iloc[-20])


def calculate_risk_label(volume_ratio, twenty_day_change, open_to_close_change):
    if volume_ratio >= 2.5 or abs(open_to_close_change) >= 6:
        return "High"

    if volume_ratio >= 1.5 or abs(twenty_day_change) >= 15:
        return "Medium"

    return "Low"


def estimate_expected_return(five_day_change, twenty_day_change, relative_strength, volume_ratio):
    """
    Temporary rule-based expected return estimate.

    This is NOT final ML.
    This gives the website and portfolio engine a structured field while we
    continue improving the real model through backtesting.
    """

    estimate = (
        five_day_change * 0.18
        + twenty_day_change * 0.08
        + relative_strength * 0.12
        + min(volume_ratio, 3) * 0.65
    )

    return max(min(estimate, 8), -4)


def estimate_win_probability(pre_score, relative_strength, volume_ratio):
    """
    Temporary probability estimate.

    This is intentionally conservative until a validated model replaces it.
    """

    probability = 50

    probability += min(pre_score, 100) * 0.18
    probability += max(min(relative_strength, 20), -20) * 0.6
    probability += max(min(volume_ratio - 1, 2), -1) * 4

    return max(min(probability, 82), 35)


def calculate_confidence(win_probability, risk_label, avg_volume):
    confidence = win_probability

    if risk_label == "High":
        confidence -= 8
    elif risk_label == "Medium":
        confidence -= 3

    if avg_volume >= 5_000_000:
        confidence += 3
    elif avg_volume < 1_000_000:
        confidence -= 3

    return max(min(confidence, 95), 20)


def determine_action(expected_return, win_probability, risk_label):
    if expected_return >= 4 and win_probability >= 68 and risk_label != "High":
        return "BUY"

    if expected_return >= 2 and win_probability >= 60:
        return "WATCH"

    if expected_return < 0:
        return "AVOID"

    return "HOLD"


def build_reason(ticker, five_day_change, relative_strength, volume_ratio, expected_return, action):
    reasons = []

    if five_day_change > 5:
        reasons.append("strong short-term momentum")

    if relative_strength > 5:
        reasons.append("outperformance versus the market")

    if volume_ratio > 1.5:
        reasons.append("above-average trading volume")

    if expected_return > 3:
        reasons.append("positive forward return estimate")

    if not reasons:
        reasons.append("acceptable but not exceptional setup quality")

    return (
        f"{ticker} is rated {action} because it shows "
        + ", ".join(reasons)
        + "."
    )


def scan_market():
    stocks = load_tickers()
    spy_return = get_spy_return()

    results = []

    for ticker in stocks:
        try:
            hist = yf.Ticker(ticker).history(period="3mo")

            if len(hist) < 20:
                continue

            latest_open = hist["Open"].iloc[-1]
            latest_close = hist["Close"].iloc[-1]
            current = latest_close

            five_day = hist["Close"].iloc[-5]
            twenty_day = hist["Close"].iloc[-20]

            five_day_change = safe_pct_change(current, five_day)
            twenty_day_change = safe_pct_change(current, twenty_day)
            relative_strength = twenty_day_change - spy_return

            open_to_close_change = safe_pct_change(latest_close, latest_open)

            avg_volume = hist["Volume"].tail(20).mean()
            today_volume = hist["Volume"].iloc[-1]

            if avg_volume < MIN_AVG_VOLUME:
                continue

            volume_ratio = today_volume / avg_volume if avg_volume else 0

            if five_day_change <= 0:
                continue

            pre_score = (
                five_day_change * 0.5
                + volume_ratio * 20
                + relative_strength * 0.5
            )

            risk_label = calculate_risk_label(
                volume_ratio,
                twenty_day_change,
                open_to_close_change
            )

            expected_return = estimate_expected_return(
                five_day_change,
                twenty_day_change,
                relative_strength,
                volume_ratio
            )

            win_probability = estimate_win_probability(
                pre_score,
                relative_strength,
                volume_ratio
            )

            confidence = calculate_confidence(
                win_probability,
                risk_label,
                avg_volume
            )

            action = determine_action(
                expected_return,
                win_probability,
                risk_label
            )

            reason = build_reason(
                ticker,
                five_day_change,
                relative_strength,
                volume_ratio,
                expected_return,
                action
            )

            results.append({
                "ticker": ticker,

                # Original scanner fields
                "latest_open": round(latest_open, 2),
                "latest_close": round(latest_close, 2),
                "open_to_close_change": round(open_to_close_change, 2),
                "five_day_change": round(five_day_change, 2),
                "twenty_day_change": round(twenty_day_change, 2),
                "relative_strength": round(relative_strength, 2),
                "avg_volume": round(avg_volume, 0),
                "volume_ratio": round(volume_ratio, 2),
                "pre_score": round(pre_score, 2),

                # New AI-style fields
                "expected_return": round(expected_return, 2),
                "win_probability": round(win_probability, 1),
                "confidence": round(confidence, 1),
                "risk": risk_label,
                "action": action,
                "reason": reason
            })

        except Exception as e:
            print(f"Error scanning {ticker}: {e}")

    return sorted(
        results,
        key=lambda x: (
            x["action"] == "BUY",
            x["expected_return"],
            x["confidence"],
            x["pre_score"]
        ),
        reverse=True
    )