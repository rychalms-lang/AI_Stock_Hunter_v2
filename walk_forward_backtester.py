import os
import math
import pandas as pd

from settings import PERFORMANCE_DIR

TRAINING_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"
OUTPUT_TRADES = f"{PERFORMANCE_DIR}/walk_forward_trades.csv"
OUTPUT_EQUITY = f"{PERFORMANCE_DIR}/walk_forward_equity.csv"

INITIAL_CAPITAL = 2000
TRADE_SIZE = 500

START_DATE = "2022-01-01"
MIN_TRAINING_ROWS = 5000

TOP_N = 5
HOLD_DAYS = 7
RISK_ON_ONLY = True
EXCLUDE_EXTREME = True
EXTREME_20D_LIMIT = 50


def calculate_max_drawdown(equity_values):
    peak = equity_values[0]
    max_drawdown = 0

    for value in equity_values:
        if value > peak:
            peak = value

        drawdown = (value - peak) / peak

        if drawdown < max_drawdown:
            max_drawdown = drawdown

    return round(max_drawdown * 100, 2)


def score_setup(row, training_data):
    score = 0

    score += row["five_day_change"] * 0.35
    score += row["volume_ratio"] * 15
    score += row["relative_strength"] * 0.35

    if row["market_regime"] == "Risk-On":
        score += 7
    elif row["market_regime"] == "Mixed":
        score += 2
    elif row["market_regime"] == "Risk-Off":
        score -= 8

    if row["open_to_close_change"] < -1:
        score -= 5

    if row["twenty_day_change"] > EXTREME_20D_LIMIT:
        score -= 5

    similar = training_data[
        (training_data["sector"] == row["sector"])
        & (training_data["market_regime"] == row["market_regime"])
        & (training_data["five_day_change"].between(row["five_day_change"] - 5, row["five_day_change"] + 5))
        & (training_data["twenty_day_change"].between(row["twenty_day_change"] - 10, row["twenty_day_change"] + 10))
        & (training_data["relative_strength"].between(row["relative_strength"] - 10, row["relative_strength"] + 10))
    ]

    return_col = f"future_{HOLD_DAYS}d_return"
    win_col = f"future_{HOLD_DAYS}d_win"

    if len(similar) >= 30:
        avg_return = similar[return_col].mean()
        win_rate = similar[win_col].mean() * 100

        if avg_return >= 3:
            score += 12
        elif avg_return >= 1:
            score += 5
        elif avg_return < 0.5:
            score -= 10

        if win_rate >= 60:
            score += 8
        elif win_rate < 50:
            score -= 8

        historical_matches = len(similar)
        historical_avg_return = round(avg_return, 2)
        historical_win_rate = round(win_rate, 2)
    else:
        score -= 5
        historical_matches = len(similar)
        historical_avg_return = 0
        historical_win_rate = 0

    return round(score, 2), historical_matches, historical_avg_return, historical_win_rate


def main():
    if not os.path.exists(TRAINING_FILE):
        print("No historical training file found.")
        return

    df = pd.read_csv(TRAINING_FILE)
    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values("date")
    df = df[df["five_day_change"] > 0].copy()

    if RISK_ON_ONLY:
        df = df[df["market_regime"] == "Risk-On"].copy()

    if EXCLUDE_EXTREME:
        df = df[df["twenty_day_change"] <= EXTREME_20D_LIMIT].copy()

    return_col = f"future_{HOLD_DAYS}d_return"

    cash = INITIAL_CAPITAL
    open_trades = []
    closed_trades = []
    equity_curve = []

    all_dates = sorted(df[df["date"] >= START_DATE]["date"].unique())

    print("Running walk-forward backtest...")
    print(f"Strategy: Top {TOP_N}, Hold {HOLD_DAYS}, RiskOn={RISK_ON_ONLY}, ExtremeFilter={EXCLUDE_EXTREME}")

    for current_date in all_dates:
        training_data = df[df["date"] < current_date].copy()
        today_data = df[df["date"] == current_date].copy()

        if len(training_data) < MIN_TRAINING_ROWS or today_data.empty:
            continue

        still_open = []

        for trade in open_trades:
            if current_date >= trade["exit_date"]:
                cash += trade["exit_value"]
                closed_trades.append(trade)
            else:
                still_open.append(trade)

        open_trades = still_open

        open_value = sum(trade["entry_value"] for trade in open_trades)
        total_equity = cash + open_value

        equity_curve.append({
            "date": current_date,
            "cash": round(cash, 2),
            "open_positions_value": round(open_value, 2),
            "total_equity": round(total_equity, 2)
        })

        scored_rows = []

        for _, row in today_data.iterrows():
            score, matches, hist_return, hist_win = score_setup(row, training_data)

            scored_rows.append({
                **row.to_dict(),
                "walk_forward_score": score,
                "historical_matches": matches,
                "historical_avg_return": hist_return,
                "historical_win_rate": hist_win
            })

        scored_today = pd.DataFrame(scored_rows)
        scored_today = scored_today.sort_values("walk_forward_score", ascending=False)

        picks = scored_today.head(TOP_N)

        future_dates = all_dates
        current_index = future_dates.index(current_date)
        exit_index = current_index + HOLD_DAYS

        if exit_index >= len(future_dates):
            continue

        exit_date = future_dates[exit_index]

        for _, pick in picks.iterrows():
            if cash < TRADE_SIZE:
                continue

            future_return = pick[return_col]

            if pd.isna(future_return):
                continue

            entry_value = TRADE_SIZE
            exit_value = entry_value * (1 + future_return / 100)

            cash -= entry_value

            open_trades.append({
                "entry_date": current_date,
                "exit_date": exit_date,
                "ticker": pick["ticker"],
                "sector": pick["sector"],
                "entry_value": round(entry_value, 2),
                "exit_value": round(exit_value, 2),
                "profit": round(exit_value - entry_value, 2),
                "return_pct": round(future_return, 2),
                "walk_forward_score": pick["walk_forward_score"],
                "historical_matches": pick["historical_matches"],
                "historical_avg_return": pick["historical_avg_return"],
                "historical_win_rate": pick["historical_win_rate"],
                "market_regime": pick["market_regime"]
            })

    for trade in open_trades:
        cash += trade["exit_value"]
        closed_trades.append(trade)

    if not closed_trades:
        print("No trades completed.")
        return

    trades = pd.DataFrame(closed_trades)
    equity = pd.DataFrame(equity_curve)

    trades.to_csv(OUTPUT_TRADES, index=False)
    equity.to_csv(OUTPUT_EQUITY, index=False)

    final_value = cash
    total_return = ((final_value / INITIAL_CAPITAL) - 1) * 100

    start = pd.to_datetime(START_DATE)
    end = pd.to_datetime(equity["date"].max())
    years = max((end - start).days / 365.25, 0.01)

    cagr = ((final_value / INITIAL_CAPITAL) ** (1 / years) - 1) * 100

    winners = trades[trades["profit"] > 0]
    losers = trades[trades["profit"] < 0]

    win_rate = len(winners) / len(trades) * 100
    avg_winner = winners["return_pct"].mean() if len(winners) else 0
    avg_loser = losers["return_pct"].mean() if len(losers) else 0

    gross_profit = winners["profit"].sum()
    gross_loss = abs(losers["profit"].sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else math.inf
    max_drawdown = calculate_max_drawdown(equity["total_equity"].tolist())

    print()
    print("WALK-FORWARD BACKTEST")
    print("---------------------")
    print(f"Start date: {START_DATE}")
    print(f"Initial capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Final value: ${final_value:,.2f}")
    print(f"Total return: {total_return:.2f}%")
    print(f"CAGR: {cagr:.2f}%")
    print(f"Trades completed: {len(trades)}")
    print(f"Win rate: {win_rate:.2f}%")
    print(f"Average winner: {avg_winner:.2f}%")
    print(f"Average loser: {avg_loser:.2f}%")
    print(f"Profit factor: {profit_factor:.2f}")
    print(f"Max drawdown: {max_drawdown:.2f}%")
    print()
    print(f"Trades saved to: {OUTPUT_TRADES}")
    print(f"Equity curve saved to: {OUTPUT_EQUITY}")


if __name__ == "__main__":
    main()