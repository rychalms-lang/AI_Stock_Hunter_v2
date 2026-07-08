import os
import pandas as pd
import yfinance as yf

HISTORY_FILE = "performance/picks_history.csv"
OUTPUT_FILE = "performance/backtest_results.csv"

INITIAL_CAPITAL = 2500
TRADE_SIZE = 500
MIN_SCORE = 70
HOLD_DAYS = 7

if not os.path.exists(HISTORY_FILE):
    print("No picks_history.csv found.")
    exit()

history = pd.read_csv(HISTORY_FILE)

history = history.dropna(subset=["date", "ticker", "score"])
history["date"] = pd.to_datetime(history["date"])
history["score"] = pd.to_numeric(history["score"], errors="coerce")
history = history.dropna(subset=["score"])

# Remove repeated reruns from the same day/ticker.
history = history.sort_values(["date", "ticker", "score"], ascending=[True, True, False])
history = history.drop_duplicates(subset=["date", "ticker"], keep="first")

picks = history[history["score"] >= MIN_SCORE].copy()
picks = picks.sort_values("date")

cash = INITIAL_CAPITAL
open_trades = []
closed_trades = []

for _, row in picks.iterrows():
    pick_date = row["date"]
    ticker = row["ticker"]
    score = row["score"]

    try:
        data = yf.Ticker(ticker).history(
            start=pick_date.strftime("%Y-%m-%d"),
            period="20d"
        )

        if len(data) <= HOLD_DAYS:
            continue

        entry_price = data["Open"].iloc[1]
        exit_price = data["Close"].iloc[HOLD_DAYS]

        if cash < TRADE_SIZE:
            continue

        shares = TRADE_SIZE / entry_price
        final_value = shares * exit_price
        profit = final_value - TRADE_SIZE
        return_pct = (profit / TRADE_SIZE) * 100

        cash -= TRADE_SIZE
        cash += final_value

        closed_trades.append({
            "pick_date": pick_date.strftime("%Y-%m-%d"),
            "ticker": ticker,
            "score": round(score, 2),
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "profit": round(profit, 2),
            "return_pct": round(return_pct, 2),
            "ending_cash": round(cash, 2)
        })

    except Exception as e:
        print(f"Error backtesting {ticker} from {pick_date.date()}: {e}")

if not closed_trades:
    print("No completed trades yet. You may need more than 7 trading days of data.")
    exit()

results = pd.DataFrame(closed_trades)
results.to_csv(OUTPUT_FILE, index=False)

final_value = cash
total_return = ((final_value / INITIAL_CAPITAL) - 1) * 100
win_rate = (results["profit"] > 0).mean() * 100

print("BACKTEST RESULTS")
print("----------------")
print(f"Strategy: Buy score >= {MIN_SCORE}, hold {HOLD_DAYS} trading days")
print(f"Initial capital: ${INITIAL_CAPITAL:.2f}")
print(f"Final value: ${final_value:.2f}")
print(f"Total return: {total_return:.2f}%")
print(f"Trades completed: {len(results)}")
print(f"Win rate: {win_rate:.2f}%")
print(f"Average trade return: {results['return_pct'].mean():.2f}%")
print(f"Best trade: {results.loc[results['return_pct'].idxmax(), 'ticker']} {results['return_pct'].max():.2f}%")
print(f"Worst trade: {results.loc[results['return_pct'].idxmin(), 'ticker']} {results['return_pct'].min():.2f}%")
print()
print(f"Saved to: {OUTPUT_FILE}")
print()
print(results.tail(20))