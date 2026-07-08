import os
import pandas as pd
import yfinance as yf
from datetime import datetime

from scanner import load_tickers
from sector_map import get_sector
from settings import PERFORMANCE_DIR, MARKET_BENCHMARK

OUTPUT_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"
YEARS = "5y"

HOLD_PERIODS = [1, 3, 5, 7, 10]


def calculate_market_regime(spy_hist, index):
    if index < 50:
        return "Unknown", 0

    price = spy_hist["Close"].iloc[index]
    ma20 = spy_hist["Close"].iloc[index - 20:index].mean()
    ma50 = spy_hist["Close"].iloc[index - 50:index].mean()
    price_20d = spy_hist["Close"].iloc[index - 20]

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
        regime = "Risk-On"
    elif score >= 50:
        regime = "Mixed"
    else:
        regime = "Risk-Off"

    return regime, score


def train_ticker(ticker, spy_hist):
    rows = []

    try:
        hist = yf.Ticker(ticker).history(period=YEARS)

        if len(hist) < 80:
            return rows

        hist = hist.reset_index()
        spy_hist = spy_hist.reset_index()

        min_len = min(len(hist), len(spy_hist))

        hist = hist.tail(min_len).reset_index(drop=True)
        spy = spy_hist.tail(min_len).reset_index(drop=True)

        for i in range(50, len(hist) - max(HOLD_PERIODS) - 1):
            try:
                date = hist["Date"].iloc[i]

                current_close = hist["Close"].iloc[i]
                current_open = hist["Open"].iloc[i]

                close_5d = hist["Close"].iloc[i - 5]
                close_20d = hist["Close"].iloc[i - 20]

                spy_close = spy["Close"].iloc[i]
                spy_20d = spy["Close"].iloc[i - 20]

                five_day_change = ((current_close / close_5d) - 1) * 100
                twenty_day_change = ((current_close / close_20d) - 1) * 100

                spy_20d_return = ((spy_close / spy_20d) - 1) * 100
                relative_strength = twenty_day_change - spy_20d_return

                open_to_close_change = ((current_close / current_open) - 1) * 100

                avg_volume = hist["Volume"].iloc[i - 20:i].mean()
                today_volume = hist["Volume"].iloc[i]

                if avg_volume <= 0:
                    continue

                volume_ratio = today_volume / avg_volume

                pre_score = (
                    five_day_change * 0.5
                    + volume_ratio * 20
                    + relative_strength * 0.5
                )

                regime, regime_score = calculate_market_regime(spy, i)

                row = {
                    "date": date.strftime("%Y-%m-%d"),
                    "ticker": ticker,
                    "sector": get_sector(ticker),
                    "open": round(current_open, 2),
                    "close": round(current_close, 2),
                    "five_day_change": round(five_day_change, 2),
                    "twenty_day_change": round(twenty_day_change, 2),
                    "relative_strength": round(relative_strength, 2),
                    "open_to_close_change": round(open_to_close_change, 2),
                    "avg_volume": round(avg_volume, 0),
                    "volume_ratio": round(volume_ratio, 2),
                    "pre_score": round(pre_score, 2),
                    "market_regime": regime,
                    "market_regime_score": regime_score,
                }

                for hold in HOLD_PERIODS:
                    future_close = hist["Close"].iloc[i + hold]
                    future_return = ((future_close / current_close) - 1) * 100

                    row[f"future_{hold}d_return"] = round(future_return, 2)
                    row[f"future_{hold}d_win"] = future_return > 0

                rows.append(row)

            except Exception:
                continue

    except Exception as e:
        print(f"Error training {ticker}: {e}")

    return rows


def main():
    os.makedirs(PERFORMANCE_DIR, exist_ok=True)

    tickers = load_tickers()

    print(f"Training on {len(tickers)} tickers...")
    print("Downloading SPY benchmark...")

    spy_hist = yf.Ticker(MARKET_BENCHMARK).history(period=YEARS)

    if len(spy_hist) < 100:
        print("Not enough SPY data.")
        return

    all_rows = []

    for index, ticker in enumerate(tickers, start=1):
        print(f"[{index}/{len(tickers)}] Training {ticker}...")

        rows = train_ticker(ticker, spy_hist)
        all_rows.extend(rows)

        print(f"  Added {len(rows)} rows")

    if not all_rows:
        print("No training data created.")
        return

    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_FILE, index=False)

    print()
    print("HISTORICAL TRAINING COMPLETE")
    print("----------------------------")
    print(f"Rows created: {len(df)}")
    print(f"Saved to: {OUTPUT_FILE}")

    print()
    print("Sample:")
    print(df.head())


if __name__ == "__main__":
    main()