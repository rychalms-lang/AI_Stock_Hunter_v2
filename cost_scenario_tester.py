import os
import math
import pandas as pd

from settings import PERFORMANCE_DIR

TRAINING_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"
OUTPUT_FILE = f"{PERFORMANCE_DIR}/cost_scenario_results.csv"

INITIAL_CAPITAL = 2000
TRADE_SIZE = 500
START_DATE = "2022-01-01"

TOP_N = 5
HOLD_DAYS = 7
RISK_ON_ONLY = True
EXCLUDE_EXTREME = True
EXTREME_20D_LIMIT = 50
MIN_TRAINING_ROWS = 5000

SCENARIOS = [
    {
        "name": "Current CAD Account: US FX Cost",
        "universe": "all",
        "us_round_trip_cost": 0.02,
        "canada_round_trip_cost": 0.00,
        "slippage": 0.0025,
    },
    {
        "name": "USD Account: No US FX Cost",
        "universe": "all",
        "us_round_trip_cost": 0.00,
        "canada_round_trip_cost": 0.00,
        "slippage": 0.0025,
    },
    {
        "name": "Canadian Stocks Only",
        "universe": "canada_only",
        "us_round_trip_cost": 0.00,
        "canada_round_trip_cost": 0.00,
        "slippage": 0.0025,
    },
    {
        "name": "US Stocks Only: No FX Cost",
        "universe": "us_only",
        "us_round_trip_cost": 0.00,
        "canada_round_trip_cost": 0.00,
        "slippage": 0.0025,
    },
]


def is_canadian_ticker(ticker):
    return str(ticker).endswith(".TO")


def calculate_max_drawdown(equity_values):
    peak = equity_values[0]
    max_drawdown = 0

    for value in equity_values:
        peak = max(peak, value)
        drawdown = (value - peak) / peak
        max_drawdown = min(max_drawdown, drawdown)

    return round(max_drawdown * 100, 2)


def apply_universe_filter(df, universe):
    if universe == "canada_only":
        return df[df["ticker"].astype(str).str.endswith(".TO")].copy()

    if universe == "us_only":
        return df[~df["ticker"].astype(str).str.endswith(".TO")].copy()

    return df.copy()


def trade_cost_for_ticker(ticker, scenario):
    if is_canadian_ticker(ticker):
        return scenario["canada_round_trip_cost"] + scenario["slippage"]

    return scenario["us_round_trip_cost"] + scenario["slippage"]


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
    else:
        score -= 5

    return round(score, 2)


def run_scenario(base_df, scenario):
    df = apply_universe_filter(base_df, scenario["universe"])

    if df.empty:
        return None

    cash = INITIAL_CAPITAL
    open_trades = []
    closed_trades = []
    equity_curve = []

    all_dates = sorted(df[df["date"] >= START_DATE]["date"].unique())
    return_col = f"future_{HOLD_DAYS}d_return"

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

        total_equity = cash + sum(t["entry_value"] for t in open_trades)

        equity_curve.append({
            "date": current_date,
            "total_equity": round(total_equity, 2)
        })

        scored_rows = []

        for _, row in today_data.iterrows():
            scored_rows.append({
                **row.to_dict(),
                "score": score_setup(row, training_data)
            })

        scored_today = pd.DataFrame(scored_rows)
        scored_today = scored_today.sort_values("score", ascending=False)

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

            cost = trade_cost_for_ticker(pick["ticker"], scenario)
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
        "scenario": scenario["name"],
        "universe": scenario["universe"],
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
        df = df[df["twenty_day_change"] <= EXTREME_20D_LIMIT].copy()

    results = []

    for scenario in SCENARIOS:
        print(f"Testing: {scenario['name']}")
        result = run_scenario(df, scenario)

        if result:
            results.append(result)

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("final_value", ascending=False)

    results_df.to_csv(OUTPUT_FILE, index=False)

    print()
    print("COST SCENARIO RESULTS")
    print("---------------------")
    print(results_df.to_string(index=False))
    print()
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()