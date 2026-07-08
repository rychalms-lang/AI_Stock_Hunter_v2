import os
from datetime import datetime

import numpy as np
import pandas as pd


INPUT_PATH = "data/historical_training_data_v3_features.csv"
OUTPUT_DIR = "performance/sector_relative_strategy_test"

RETURN_TARGETS = [
    "future_1d_return",
    "future_3d_return",
    "future_5d_return",
    "future_7d_return",
    "future_10d_return",
]

WIN_TARGETS = [
    "future_1d_win",
    "future_3d_win",
    "future_5d_win",
    "future_7d_win",
    "future_10d_win",
]

RANKERS = [
    ("stock_vs_sector_5d_rank_pct", "Stock vs Sector 5D"),
    ("stock_vs_sector_20d_rank_pct", "Stock vs Sector 20D"),
    ("return_5d_rank_pct", "5D Momentum"),
    ("return_20d_rank_pct", "20D Momentum"),
    ("relative_strength_rank_pct", "Relative Strength"),
    ("pre_score", "Current Pre Score"),
    ("volume_ratio_rank_pct", "Volume Ratio"),
    ("momentum_per_vol_20d_rank_pct", "Momentum Per Vol"),
]

TOP_N_VALUES = [3, 5, 10, 20, 50]


def load_data():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Missing {INPUT_PATH}. Run feature_engineering_v3.py first."
        )

    df = pd.read_csv(INPUT_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df


def test_period_only(df, test_pct=0.15):
    dates = sorted(df["date"].dropna().unique())
    test_start_idx = int(len(dates) * (1 - test_pct))
    test_start_date = dates[test_start_idx]

    return df[df["date"] >= test_start_date].copy(), test_start_date


def evaluate_ranker(df, rank_col, label, return_col, win_col, top_n):
    temp = df.dropna(subset=[rank_col, return_col, win_col]).copy()

    if len(temp) == 0:
        return None

    temp["daily_rank"] = temp.groupby("date")[rank_col].rank(
        ascending=False,
        method="first",
    )

    selected = temp[temp["daily_rank"] <= top_n].copy()

    if len(selected) == 0:
        return None

    daily_returns = selected.groupby("date")[return_col].mean()

    cumulative_return = (1 + daily_returns / 100).prod() - 1

    return {
        "strategy": label,
        "rank_column": rank_col,
        "holding_period": return_col.replace("future_", "").replace("_return", ""),
        "top_n": top_n,
        "total_picks": int(len(selected)),
        "trading_days": int(daily_returns.count()),
        "average_trade_return": float(selected[return_col].mean()),
        "median_trade_return": float(selected[return_col].median()),
        "win_rate": float(selected[win_col].mean()),
        "average_daily_portfolio_return": float(daily_returns.mean()),
        "median_daily_portfolio_return": float(daily_returns.median()),
        "daily_return_std": float(daily_returns.std()),
        "best_daily_return": float(daily_returns.max()),
        "worst_daily_return": float(daily_returns.min()),
        "cumulative_return": float(cumulative_return * 100),
    }


def run_tests(df):
    results = []

    for return_col, win_col in zip(RETURN_TARGETS, WIN_TARGETS):
        for rank_col, label in RANKERS:
            if rank_col not in df.columns:
                continue

            for top_n in TOP_N_VALUES:
                row = evaluate_ranker(
                    df=df,
                    rank_col=rank_col,
                    label=label,
                    return_col=return_col,
                    win_col=win_col,
                    top_n=top_n,
                )

                if row is not None:
                    results.append(row)

    return pd.DataFrame(results)


def save_results(results_df, test_start_date):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(
        OUTPUT_DIR,
        f"sector_relative_strategy_test_{timestamp}.csv",
    )

    txt_path = os.path.join(
        OUTPUT_DIR,
        f"sector_relative_strategy_test_summary_{timestamp}.txt",
    )

    results_df.to_csv(csv_path, index=False)

    sorted_results = results_df.sort_values(
        ["average_daily_portfolio_return", "win_rate"],
        ascending=False,
    )

    with open(txt_path, "w") as f:
        f.write("AI STOCK HUNTER V3 - SECTOR RELATIVE STRATEGY TEST\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Input: {INPUT_PATH}\n")
        f.write(f"Test period starts: {pd.to_datetime(test_start_date).date()}\n\n")

        f.write("TOP RESULTS BY AVERAGE DAILY PORTFOLIO RETURN\n")
        f.write("-" * 80 + "\n")
        f.write(sorted_results.head(30).to_string(index=False))
        f.write("\n\n")

        f.write("BEST RESULT\n")
        f.write("-" * 80 + "\n")
        best = sorted_results.iloc[0]
        f.write(f"Strategy: {best['strategy']}\n")
        f.write(f"Holding period: {best['holding_period']}\n")
        f.write(f"Top N: {int(best['top_n'])}\n")
        f.write(f"Average trade return: {best['average_trade_return']:.4f}%\n")
        f.write(f"Average daily portfolio return: {best['average_daily_portfolio_return']:.4f}%\n")
        f.write(f"Win rate: {best['win_rate']:.4f}\n")
        f.write(f"Cumulative return: {best['cumulative_return']:.4f}%\n")
        f.write(f"Worst daily return: {best['worst_daily_return']:.4f}%\n\n")

        f.write("DECISION RULE\n")
        f.write("-" * 80 + "\n")
        f.write(
            "Sector-relative momentum should only enter the live scanner if it beats "
            "pre_score and raw momentum across realistic test-period return metrics.\n"
        )

    return csv_path, txt_path


def main():
    print("AI STOCK HUNTER V3 - SECTOR RELATIVE STRATEGY TEST")
    print("=" * 80)

    df = load_data()
    test_df, test_start_date = test_period_only(df)

    print(f"Full rows:       {len(df):,}")
    print(f"Test rows:       {len(test_df):,}")
    print(f"Test start date: {pd.to_datetime(test_start_date).date()}")

    results_df = run_tests(test_df)

    results_df = results_df.sort_values(
        ["average_daily_portfolio_return", "win_rate"],
        ascending=False,
    ).reset_index(drop=True)

    print("\nTOP 30 RESULTS")
    print("=" * 80)
    print(results_df.head(30).to_string(index=False))

    csv_path, txt_path = save_results(results_df, test_start_date)

    best = results_df.iloc[0]

    print("\nBest result:")
    print(f"{best['strategy']} | {best['holding_period']} | Top {int(best['top_n'])}")
    print(f"Average trade return: {best['average_trade_return']:.4f}%")
    print(f"Average daily portfolio return: {best['average_daily_portfolio_return']:.4f}%")
    print(f"Win rate: {best['win_rate']:.4f}")
    print(f"Cumulative return: {best['cumulative_return']:.4f}%")

    print("\nSaved:")
    print(f"CSV:     {csv_path}")
    print(f"Summary: {txt_path}")


if __name__ == "__main__":
    main()