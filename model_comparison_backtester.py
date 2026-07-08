import os
import math
import pandas as pd

from settings import PERFORMANCE_DIR

TRAINING_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"
OUTPUT_FILE = f"{PERFORMANCE_DIR}/model_comparison_results.csv"

INITIAL_CAPITAL = 2000
TRADE_SIZE = 500
START_DATE = "2022-01-01"

TOP_N = 5
HOLD_DAYS = 7
RISK_ON_ONLY = True
EXCLUDE_EXTREME = False
MIN_TRAINING_ROWS = 5000

US_ROUND_TRIP_COST = 0.0025
CANADA_ROUND_TRIP_COST = 0.0025


def is_canadian_ticker(ticker):
    return str(ticker).endswith(".TO")


def trade_cost_for_ticker(ticker):
    if is_canadian_ticker(ticker):
        return CANADA_ROUND_TRIP_COST

    return US_ROUND_TRIP_COST


def calculate_max_drawdown(equity_values):
    peak = equity_values[0]
    max_drawdown = 0

    for value in equity_values:
        peak = max(peak, value)
        drawdown = (value - peak) / peak
        max_drawdown = min(max_drawdown, drawdown)

    return round(max_drawdown * 100, 2)


def momentum_score(row, training_data):
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

    if row["twenty_day_change"] > 50:
        score -= 5

    if row["open_to_close_change"] < -1:
        score -= 5

    return round(score, 2)


def early_breakout_score(row, training_data):
    score = 0

    five_day = row["five_day_change"]
    twenty_day = row["twenty_day_change"]
    relative_strength = row["relative_strength"]
    volume_ratio = row["volume_ratio"]
    open_to_close = row["open_to_close_change"]

    if 2 <= five_day <= 10:
        score += 15

    if 3 <= twenty_day <= 25:
        score += 20

    if twenty_day > 40:
        score -= 20

    if twenty_day > 75:
        score -= 35

    if abs(twenty_day) > 1:
        acceleration = five_day / abs(twenty_day)
    else:
        acceleration = five_day

    if 0.35 <= acceleration <= 1.25:
        score += 15

    if acceleration < 0.15 and twenty_day > 20:
        score -= 10

    if 3 <= relative_strength <= 25:
        score += 15

    if relative_strength > 50:
        score -= 10

    if 1.15 <= volume_ratio <= 3:
        score += 15

    if volume_ratio > 4:
        score -= 10

    if 0.5 <= open_to_close <= 5:
        score += 10

    if open_to_close > 8:
        score -= 8

    if open_to_close < -1:
        score -= 15

    if row["market_regime"] == "Risk-On":
        score += 7

    return round(score, 2)


def historical_edge_score(row, training_data):
    score = 0

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
            score += 20
        elif avg_return >= 1:
            score += 10
        elif avg_return < 0.5:
            score -= 15

        if win_rate >= 60:
            score += 15
        elif win_rate >= 55:
            score += 7
        elif win_rate < 50:
            score -= 10
    else:
        score -= 10

    return round(score, 2)


def combined_model_score(row, training_data, model_name):
    m = momentum_score(row, training_data)
    e = early_breakout_score(row, training_data)
    h = historical_edge_score(row, training_data)

    if model_name == "Momentum":
        return m

    if model_name == "Early Breakout":
        return e

    if model_name == "Hybrid 50/50":
        return round((m * 0.5) + (e * 0.5), 2)

    if model_name == "Hybrid + Historical":
        return round((m * 0.35) + (e * 0.35) + (h * 0.30), 2)

    return m


def run_model(base_df, model_name):
    cash = INITIAL_CAPITAL
    open_trades = []
    closed_trades = []
    equity_curve = []

    all_dates = sorted(base_df[base_df["date"] >= START_DATE]["date"].unique())
    return_col = f"future_{HOLD_DAYS}d_return"

    for current_date in all_dates:
        training_data = base_df[base_df["date"] < current_date].copy()
        today_data = base_df[base_df["date"] == current_date].copy()

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

        total_equity = cash + sum(t["entry_value"] for t in open_trades)

        equity_curve.append({
            "date": current_date,
            "total_equity": round(total_equity, 2)
        })

        scored_rows = []

        for _, row in today_data.iterrows():
            score = combined_model_score(row, training_data, model_name)

            scored_rows.append({
                **row.to_dict(),
                "model_score": score
            })

        scored_today = pd.DataFrame(scored_rows)
        scored_today = scored_today.sort_values("model_score", ascending=False)

        picks = scored_today.head(TOP_N)

        current_index = all_dates.index(current_date)
        entry_index = current_index + 1
        exit_index = entry_index + HOLD_DAYS

        if exit_index >= len(all_dates):
            continue

        entry_date = all_dates[entry_index]
        exit_date = all_dates[exit_index]

        for _, pick in picks.iterrows():
            if cash < TRADE_SIZE:
                continue

            gross_return = pick[return_col]

            if pd.isna(gross_return):
                continue

            cost = trade_cost_for_ticker(pick["ticker"])
            net_return = gross_return - cost * 100

            entry_value = TRADE_SIZE
            exit_value = entry_value * (1 + net_return / 100)

            cash -= entry_value

            open_trades.append({
                "ticker": pick["ticker"],
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_value": round(entry_value, 2),
                "exit_value": round(exit_value, 2),
                "profit": round(exit_value - entry_value, 2),
                "net_return_pct": round(net_return, 2),
                "model_score": pick["model_score"],
            })

    for trade in open_trades:
        cash += trade["exit_value"]
        closed_trades.append(trade)

    if not closed_trades or not equity_curve:
        return None

    trades = pd.DataFrame(closed_trades)
    equity = pd.DataFrame(equity_curve)

    final_value = cash
    total_return = ((final_value / INITIAL_CAPITAL) - 1) * 100

    start = pd.to_datetime(START_DATE)
    end = pd.to_datetime(equity["date"].max())
    years = max((end - start).days / 365.25, 0.01)

    cagr = ((final_value / INITIAL_CAPITAL) ** (1 / years) - 1) * 100

    winners = trades[trades["profit"] > 0]
    losers = trades[trades["profit"] < 0]

    win_rate = len(winners) / len(trades) * 100
    avg_winner = winners["net_return_pct"].mean() if len(winners) else 0
    avg_loser = losers["net_return_pct"].mean() if len(losers) else 0

    gross_profit = winners["profit"].sum()
    gross_loss = abs(losers["profit"].sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else math.inf
    max_drawdown = calculate_max_drawdown(equity["total_equity"].tolist())

    return {
        "model": model_name,
        "initial_capital": INITIAL_CAPITAL,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "trades": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "avg_winner_pct": round(avg_winner, 2),
        "avg_loser_pct": round(avg_loser, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown_pct": max_drawdown,
    }


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
        df = df[df["twenty_day_change"] <= 50].copy()

    models = [
        "Momentum",
        "Early Breakout",
        "Hybrid 50/50",
        "Hybrid + Historical",
    ]

    results = []

    for model in models:
        print(f"Testing model: {model}")
        result = run_model(df, model)

        if result:
            results.append(result)

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("final_value", ascending=False)

    results_df.to_csv(OUTPUT_FILE, index=False)

    print()
    print("MODEL COMPARISON RESULTS")
    print("------------------------")
    print(results_df.to_string(index=False))
    print()
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()