import os
import math
import pandas as pd

from settings import PERFORMANCE_DIR

TRAINING_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"
OUTPUT_SUMMARY = f"{PERFORMANCE_DIR}/ai_backtest_strategy_summary.csv"
OUTPUT_TRADES = f"{PERFORMANCE_DIR}/ai_backtest_best_trades.csv"
OUTPUT_EQUITY = f"{PERFORMANCE_DIR}/ai_backtest_best_equity.csv"

INITIAL_CAPITAL = 2000
TRADE_SIZE = 500
START_DATE = "2021-01-01"

TOP_N_OPTIONS = [1, 2, 3, 5]
HOLD_OPTIONS = [1, 3, 5, 7, 10]
RISK_ON_ONLY_OPTIONS = [False, True]
EXCLUDE_EXTREME_OPTIONS = [False, True]

EXTREME_20D_LIMIT = 50


def score_setup(row, exclude_extreme=False):
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

    if row["twenty_day_change"] > EXTREME_20D_LIMIT:
        score -= 5

    if row["open_to_close_change"] < -1:
        score -= 5

    return round(score, 2)


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


def run_single_backtest(base_df, top_n, hold_days, risk_on_only, exclude_extreme):
    df = base_df.copy()

    return_col = f"future_{hold_days}d_return"

    if return_col not in df.columns:
        return None, None, None

    if risk_on_only:
        df = df[df["market_regime"] == "Risk-On"].copy()

    if exclude_extreme:
        df = df[df["twenty_day_change"] <= EXTREME_20D_LIMIT].copy()

    if df.empty:
        return None, None, None

    df["ai_score"] = df.apply(
        lambda row: score_setup(row, exclude_extreme),
        axis=1
    )

    scored = df.sort_values(["date", "ai_score"], ascending=[True, False])

    daily_picks = (
        scored
        .groupby("date")
        .head(top_n)
        .reset_index(drop=True)
    )

    cash = INITIAL_CAPITAL
    open_trades = []
    closed_trades = []
    equity_curve = []

    all_dates = sorted(scored["date"].unique())

    for current_date in all_dates:
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

        todays_picks = daily_picks[daily_picks["date"] == current_date]

        for _, pick in todays_picks.iterrows():
            if cash < TRADE_SIZE:
                continue

            future_return = pick[return_col]

            if pd.isna(future_return):
                continue

            exit_index = all_dates.index(current_date) + hold_days

            if exit_index >= len(all_dates):
                continue

            exit_date = all_dates[exit_index]

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
                "ai_score": pick["ai_score"],
                "market_regime": pick["market_regime"],
                "hold_days": hold_days,
                "top_n": top_n,
                "risk_on_only": risk_on_only,
                "exclude_extreme": exclude_extreme
            })

    for trade in open_trades:
        cash += trade["exit_value"]
        closed_trades.append(trade)

    if not closed_trades:
        return None, None, None

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
    avg_winner = winners["return_pct"].mean() if len(winners) else 0
    avg_loser = losers["return_pct"].mean() if len(losers) else 0

    gross_profit = winners["profit"].sum()
    gross_loss = abs(losers["profit"].sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else math.inf
    max_drawdown = calculate_max_drawdown(equity["total_equity"].tolist())

    summary = {
        "top_n": top_n,
        "hold_days": hold_days,
        "risk_on_only": risk_on_only,
        "exclude_extreme": exclude_extreme,
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
        "return_to_drawdown": round(
            total_return / abs(max_drawdown), 2
        ) if max_drawdown != 0 else 0
    }

    return summary, trades, equity


def main():
    if not os.path.exists(TRAINING_FILE):
        print("No historical_training_data.csv found. Run historical_trainer.py first.")
        return

    df = pd.read_csv(TRAINING_FILE)
    df["date"] = pd.to_datetime(df["date"])

    df = df[df["date"] >= START_DATE].copy()
    df = df[df["five_day_change"] > 0].copy()

    all_summaries = []
    best_result = None
    best_trades = None
    best_equity = None

    print("Running strategy optimizer...")

    for top_n in TOP_N_OPTIONS:
        for hold_days in HOLD_OPTIONS:
            for risk_on_only in RISK_ON_ONLY_OPTIONS:
                for exclude_extreme in EXCLUDE_EXTREME_OPTIONS:
                    summary, trades, equity = run_single_backtest(
                        df,
                        top_n,
                        hold_days,
                        risk_on_only,
                        exclude_extreme
                    )

                    if summary is None:
                        continue

                    all_summaries.append(summary)

                    print(
                        f"Tested Top {top_n}, Hold {hold_days}, "
                        f"RiskOn={risk_on_only}, ExtremeFilter={exclude_extreme} "
                        f"→ Return {summary['total_return_pct']}%, "
                        f"DD {summary['max_drawdown_pct']}%"
                    )

                    # Prefer high return with controlled drawdown.
                    if best_result is None:
                        best_result = summary
                        best_trades = trades
                        best_equity = equity
                    else:
                        current_score = (
                            summary["cagr_pct"]
                            + summary["profit_factor"] * 10
                            - abs(summary["max_drawdown_pct"]) * 0.75
                        )

                        best_score = (
                            best_result["cagr_pct"]
                            + best_result["profit_factor"] * 10
                            - abs(best_result["max_drawdown_pct"]) * 0.75
                        )

                        if current_score > best_score:
                            best_result = summary
                            best_trades = trades
                            best_equity = equity

    if not all_summaries:
        print("No strategies completed.")
        return

    summary_df = pd.DataFrame(all_summaries)
    summary_df = summary_df.sort_values(
        ["return_to_drawdown", "cagr_pct"],
        ascending=[False, False]
    )

    os.makedirs(PERFORMANCE_DIR, exist_ok=True)

    summary_df.to_csv(OUTPUT_SUMMARY, index=False)

    if best_trades is not None:
        best_trades.to_csv(OUTPUT_TRADES, index=False)

    if best_equity is not None:
        best_equity.to_csv(OUTPUT_EQUITY, index=False)

    print()
    print("AI STOCK HUNTER STRATEGY OPTIMIZER")
    print("----------------------------------")
    print("Top 10 Strategies by Return/Drawdown:")
    print(summary_df.head(10).to_string(index=False))

    print()
    print("Best Balanced Strategy:")
    for key, value in best_result.items():
        print(f"{key}: {value}")

    print()
    print(f"Summary saved to: {OUTPUT_SUMMARY}")
    print(f"Best trades saved to: {OUTPUT_TRADES}")
    print(f"Best equity curve saved to: {OUTPUT_EQUITY}")


if __name__ == "__main__":
    main()