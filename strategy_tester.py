import os
import pandas as pd
import yfinance as yf

HISTORY_FILE = "performance/picks_history.csv"
OUTPUT_FILE = "performance/strategy_test_results.csv"

INITIAL_CAPITAL = 2500
TRADE_SIZE = 500

STRATEGIES = [
    {"name": "Score >= 70 / Hold 7 Days", "type": "score_filter", "min_score": 70, "hold_days": 7, "sentiment_min": None},
    {"name": "Top 1 Per Day / Hold 5 Days", "type": "top_n", "top_n": 1, "hold_days": 5, "sentiment_min": None},
    {"name": "Top 3 Per Day / Hold 3 Days", "type": "top_n", "top_n": 3, "hold_days": 3, "sentiment_min": None},
    {"name": "Top 3 Per Day / Hold 7 Days", "type": "top_n", "top_n": 3, "hold_days": 7, "sentiment_min": None},
    {"name": "Top 5 Per Day / Hold 5 Days", "type": "top_n", "top_n": 5, "hold_days": 5, "sentiment_min": None},
    {"name": "Score >= 70 + Bullish AI / Hold 7 Days", "type": "score_filter", "min_score": 70, "hold_days": 7, "sentiment_min": 70},
    {"name": "Top 3 + Bullish AI / Hold 5 Days", "type": "top_n", "top_n": 3, "hold_days": 5, "sentiment_min": 70},
]


def load_history():
    if not os.path.exists(HISTORY_FILE):
        print("No picks_history.csv found.")
        exit()

    df = pd.read_csv(HISTORY_FILE)
    df = df.dropna(subset=["date", "ticker", "score"])
    df["date"] = pd.to_datetime(df["date"])
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["sentiment_score"] = pd.to_numeric(df.get("sentiment_score", 50), errors="coerce").fillna(50)
    df = df.dropna(subset=["score"])

    df = df.sort_values(["date", "ticker", "score"], ascending=[True, True, False])
    df = df.drop_duplicates(subset=["date", "ticker"], keep="first")

    return df


def select_picks(history, strategy):
    df = history.copy()

    if strategy.get("sentiment_min") is not None:
        df = df[df["sentiment_score"] >= strategy["sentiment_min"]]

    if strategy["type"] == "score_filter":
        df = df[df["score"] >= strategy["min_score"]]

    elif strategy["type"] == "top_n":
        df = (
            df.sort_values(["date", "score"], ascending=[True, False])
            .groupby("date")
            .head(strategy["top_n"])
        )

    return df.sort_values("date")


def get_trade_result(ticker, pick_date, hold_days):
    data = yf.Ticker(ticker).history(
        start=pick_date.strftime("%Y-%m-%d"),
        period=f"{hold_days + 10}d"
    )

    if len(data) <= hold_days:
        return None

    entry_price = data["Open"].iloc[1]
    exit_price = data["Close"].iloc[hold_days]

    if entry_price <= 0:
        return None

    shares = TRADE_SIZE / entry_price
    final_value = shares * exit_price
    profit = final_value - TRADE_SIZE
    return_pct = (profit / TRADE_SIZE) * 100

    return {
        "entry_price": round(entry_price, 2),
        "exit_price": round(exit_price, 2),
        "profit": round(profit, 2),
        "return_pct": round(return_pct, 2)
    }


def calculate_max_drawdown(equity_curve):
    peak = equity_curve[0]
    max_drawdown = 0

    for value in equity_curve:
        if value > peak:
            peak = value

        drawdown = ((value - peak) / peak) * 100

        if drawdown < max_drawdown:
            max_drawdown = drawdown

    return round(max_drawdown, 2)


def run_strategy(history, strategy):
    picks = select_picks(history, strategy)

    cash = INITIAL_CAPITAL
    equity_curve = [cash]
    trades = []

    for _, row in picks.iterrows():
        if cash < TRADE_SIZE:
            break

        ticker = row["ticker"]
        pick_date = row["date"]
        score = row["score"]
        sentiment = row.get("sentiment_score", 50)

        result = get_trade_result(ticker, pick_date, strategy["hold_days"])

        if result is None:
            continue

        cash -= TRADE_SIZE
        cash += TRADE_SIZE + result["profit"]
        equity_curve.append(cash)

        trades.append({
            "strategy": strategy["name"],
            "pick_date": pick_date.strftime("%Y-%m-%d"),
            "ticker": ticker,
            "score": round(score, 2),
            "sentiment_score": round(sentiment, 2),
            "entry_price": result["entry_price"],
            "exit_price": result["exit_price"],
            "profit": result["profit"],
            "return_pct": result["return_pct"],
            "ending_cash": round(cash, 2)
        })

    if not trades:
        return None, pd.DataFrame()

    trades_df = pd.DataFrame(trades)

    winners = trades_df[trades_df["profit"] > 0]
    losers = trades_df[trades_df["profit"] < 0]

    gross_profit = winners["profit"].sum()
    gross_loss = abs(losers["profit"].sum())

    avg_winner = winners["return_pct"].mean() if len(winners) > 0 else 0
    avg_loser = losers["return_pct"].mean() if len(losers) > 0 else 0

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    win_rate = (trades_df["profit"] > 0).mean()
    loss_rate = 1 - win_rate

    expectancy = (win_rate * avg_winner) + (loss_rate * avg_loser)

    final_value = cash
    total_return = ((final_value / INITIAL_CAPITAL) - 1) * 100
    max_drawdown = calculate_max_drawdown(equity_curve)

    best_trade = trades_df.loc[trades_df["return_pct"].idxmax()]
    worst_trade = trades_df.loc[trades_df["return_pct"].idxmin()]

    summary = {
        "strategy": strategy["name"],
        "initial_capital": INITIAL_CAPITAL,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "trades": len(trades_df),
        "win_rate_pct": round(win_rate * 100, 2),
        "avg_trade_return_pct": round(trades_df["return_pct"].mean(), 2),
        "avg_winner_pct": round(avg_winner, 2),
        "avg_loser_pct": round(avg_loser, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "expectancy_pct_per_trade": round(expectancy, 2),
        "max_drawdown_pct": max_drawdown,
        "best_trade": f"{best_trade['ticker']} {best_trade['return_pct']}%",
        "worst_trade": f"{worst_trade['ticker']} {worst_trade['return_pct']}%"
    }

    return summary, trades_df


def main():
    history = load_history()

    all_summaries = []
    all_trades = []

    for strategy in STRATEGIES:
        summary, trades = run_strategy(history, strategy)

        if summary is None:
            continue

        all_summaries.append(summary)
        all_trades.append(trades)

    if not all_summaries:
        print("No completed strategy trades yet.")
        return

    summary_df = pd.DataFrame(all_summaries)
    summary_df = summary_df.sort_values("total_return_pct", ascending=False)

    trades_df = pd.concat(all_trades, ignore_index=True)

    os.makedirs("performance", exist_ok=True)
    summary_df.to_csv(OUTPUT_FILE, index=False)
    trades_df.to_csv("performance/strategy_test_trades.csv", index=False)

    print("\nSTRATEGY TEST RESULTS")
    print("---------------------")
    print(summary_df.to_string(index=False))

    print()
    print(f"Saved summary to: {OUTPUT_FILE}")
    print("Saved trades to: performance/strategy_test_trades.csv")


if __name__ == "__main__":
    main()