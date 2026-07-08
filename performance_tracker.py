import os
import pandas as pd
import yfinance as yf

HISTORY_FILE = "performance/picks_history.csv"
OUTPUT_FILE = "performance/performance_summary.csv"

if not os.path.exists(HISTORY_FILE):
    print("No picks_history.csv found yet.")
    exit()

history = pd.read_csv(HISTORY_FILE)

if history.empty:
    print("No history data found.")
    exit()

results = []

for _, row in history.iterrows():
    try:
        date = row["date"]
        ticker = row["ticker"]
        score = row["score"]

        stock = yf.Ticker(ticker)
        hist = stock.history(start=date, period="15d")

        spy = yf.Ticker("SPY")
        spy_hist = spy.history(start=date, period="15d")

        if len(hist) < 6 or len(spy_hist) < 6:
            continue

        entry_price = hist["Close"].iloc[0]
        one_day_price = hist["Close"].iloc[1]
        five_day_price = hist["Close"].iloc[5]

        spy_entry = spy_hist["Close"].iloc[0]
        spy_one_day = spy_hist["Close"].iloc[1]
        spy_five_day = spy_hist["Close"].iloc[5]

        one_day_return = ((one_day_price / entry_price) - 1) * 100
        five_day_return = ((five_day_price / entry_price) - 1) * 100

        spy_one_day_return = ((spy_one_day / spy_entry) - 1) * 100
        spy_five_day_return = ((spy_five_day / spy_entry) - 1) * 100

        results.append({
            "date": date,
            "ticker": ticker,
            "score": score,
            "one_day_return": round(one_day_return, 2),
            "five_day_return": round(five_day_return, 2),
            "spy_one_day_return": round(spy_one_day_return, 2),
            "spy_five_day_return": round(spy_five_day_return, 2),
            "beat_spy_1d": one_day_return > spy_one_day_return,
            "beat_spy_5d": five_day_return > spy_five_day_return
        })

    except Exception as e:
        print(f"Error tracking {row.get('ticker', 'UNKNOWN')}: {e}")

df = pd.DataFrame(results)

if df.empty:
    print("Not enough future price data yet. Try again after a few market days.")
    exit()

df.to_csv(OUTPUT_FILE, index=False)

print(f"Performance summary saved to: {OUTPUT_FILE}")
print()

print("SUMMARY")
print("-------")

print(f"Tracked picks: {len(df)}")
print(f"Average 1-day return: {df['one_day_return'].mean():.2f}%")
print(f"Average 5-day return: {df['five_day_return'].mean():.2f}%")
print(f"Average SPY 1-day return: {df['spy_one_day_return'].mean():.2f}%")
print(f"Average SPY 5-day return: {df['spy_five_day_return'].mean():.2f}%")
print(f"Beat SPY 1-day rate: {df['beat_spy_1d'].mean() * 100:.2f}%")
print(f"Beat SPY 5-day rate: {df['beat_spy_5d'].mean() * 100:.2f}%")

print()
print("TOP 10 FIVE-DAY RETURNS")
print(df.sort_values("five_day_return", ascending=False).head(10))