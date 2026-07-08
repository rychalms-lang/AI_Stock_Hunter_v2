import os
import itertools
from datetime import datetime

import numpy as np
import pandas as pd


INPUT_PATH = "data/historical_training_data_v3_features.csv"
OUTPUT_DIR = "performance/walk_forward_weight_optimizer"

RETURN_COL = "future_10d_return"
WIN_COL = "future_10d_win"

TRAIN_MONTHS = 24
TEST_MONTHS = 6

TOP_N_VALUES = [3, 5, 10]

FACTOR_COLUMNS = [
    "stock_vs_sector_20d_rank_pct",
    "relative_strength_rank_pct",
    "return_20d_rank_pct",
    "momentum_per_vol_20d_rank_pct",
    "volume_ratio_rank_pct",
    "market_regime_rank_pct",
]

BASELINE_RANKERS = [
    ("pre_score", "Current Pre Score"),
    ("stock_vs_sector_20d_rank_pct", "Stock vs Sector 20D"),
    ("return_20d_rank_pct", "20D Momentum"),
    ("relative_strength_rank_pct", "Relative Strength"),
    ("momentum_v4_quality_fixed", "Momentum V4 Quality Fixed"),
]


def load_data():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Missing {INPUT_PATH}. Run feature_engineering_v3.py first."
        )

    df = pd.read_csv(INPUT_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "ticker"]).reset_index(drop=True)

    return df


def add_required_scores(df):
    df = df.copy()

    if "market_regime_score" not in df.columns:
        raise ValueError("Missing market_regime_score column.")

    df["market_regime_rank_pct"] = df.groupby("date")["market_regime_score"].rank(
        pct=True
    )

    missing = [col for col in FACTOR_COLUMNS if col not in df.columns]

    if missing:
        raise ValueError(f"Missing required factor columns: {missing}")

    df["momentum_v4_quality_fixed"] = (
        0.30 * df["stock_vs_sector_20d_rank_pct"]
        + 0.20 * df["momentum_per_vol_20d_rank_pct"]
        + 0.15 * df["relative_strength_rank_pct"]
        + 0.15 * df["return_20d_rank_pct"]
        + 0.10 * df["volume_ratio_rank_pct"]
        + 0.10 * df["market_regime_rank_pct"]
    )

    return df


def generate_weight_grid():
    """
    Generates reasonable factor weight combinations.

    We intentionally keep this grid limited so the test remains fast
    and avoids over-optimizing.
    """

    values = [0.00, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

    weight_sets = []

    for weights in itertools.product(values, repeat=len(FACTOR_COLUMNS)):
        total = sum(weights)

        if total == 0:
            continue

        if abs(total - 1.0) > 0.001:
            continue

        weight_dict = dict(zip(FACTOR_COLUMNS, weights))

        # Keep the search realistic.
        # Sector-relative strength should matter, but not become the entire model.
        if weight_dict["stock_vs_sector_20d_rank_pct"] < 0.20:
            continue

        if weight_dict["stock_vs_sector_20d_rank_pct"] > 0.55:
            continue

        # Avoid useless models where too many factors are zero.
        non_zero_factors = sum(1 for w in weights if w > 0)

        if non_zero_factors < 3:
            continue

        weight_sets.append(weight_dict)

    return weight_sets


def add_weighted_score(df, weights, score_col):
    df = df.copy()
    df[score_col] = 0.0

    for col, weight in weights.items():
        df[score_col] += weight * df[col]

    return df


def evaluate_ranker(df, rank_col, top_n):
    temp = df.dropna(subset=[rank_col, RETURN_COL, WIN_COL]).copy()

    if len(temp) == 0:
        return None

    temp["daily_rank"] = temp.groupby("date")[rank_col].rank(
        ascending=False,
        method="first",
    )

    selected = temp[temp["daily_rank"] <= top_n].copy()

    if len(selected) == 0:
        return None

    daily_returns = selected.groupby("date")[RETURN_COL].mean()
    cumulative_return = (1 + daily_returns / 100).prod() - 1

    return {
        "top_n": top_n,
        "total_picks": int(len(selected)),
        "trading_days": int(daily_returns.count()),
        "average_trade_return": float(selected[RETURN_COL].mean()),
        "median_trade_return": float(selected[RETURN_COL].median()),
        "win_rate": float(selected[WIN_COL].mean()),
        "average_daily_portfolio_return": float(daily_returns.mean()),
        "median_daily_portfolio_return": float(daily_returns.median()),
        "daily_return_std": float(daily_returns.std()),
        "worst_daily_return": float(daily_returns.min()),
        "best_daily_return": float(daily_returns.max()),
        "cumulative_return": float(cumulative_return * 100),
    }


def optimization_objective(metric):
    """
    Objective function for choosing weights on the training window.

    We reward high average daily return and win rate, while penalizing
    extreme daily volatility.
    """

    if metric is None:
        return -999999

    avg_return = metric["average_daily_portfolio_return"]
    win_rate = metric["win_rate"]
    volatility = metric["daily_return_std"]

    if pd.isna(volatility) or volatility == 0:
        volatility = 999

    score = (
        avg_return
        + 2.0 * (win_rate - 0.50)
        - 0.05 * volatility
    )

    return score


def optimize_weights(train_df, weight_grid, top_n):
    best_score = -999999
    best_weights = None
    best_metric = None

    for weights in weight_grid:
        scored_df = add_weighted_score(train_df, weights, "optimized_score")
        metric = evaluate_ranker(scored_df, "optimized_score", top_n)

        score = optimization_objective(metric)

        if score > best_score:
            best_score = score
            best_weights = weights
            best_metric = metric

    return best_weights, best_metric, best_score


def evaluate_baselines(test_df, top_n):
    rows = []

    for rank_col, label in BASELINE_RANKERS:
        if rank_col not in test_df.columns:
            continue

        metric = evaluate_ranker(test_df, rank_col, top_n)

        if metric is None:
            continue

        row = {
            "strategy": label,
            "rank_column": rank_col,
        }

        row.update(metric)
        rows.append(row)

    return rows


def create_walk_forward_windows(df):
    min_date = df["date"].min()
    max_date = df["date"].max()

    windows = []

    train_start = min_date

    while True:
        train_end = train_start + pd.DateOffset(months=TRAIN_MONTHS)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=TEST_MONTHS)

        if test_end > max_date:
            break

        windows.append({
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
        })

        train_start = train_start + pd.DateOffset(months=TEST_MONTHS)

    return windows


def run_walk_forward(df):
    weight_grid = generate_weight_grid()

    print(f"Weight combinations tested per optimization: {len(weight_grid):,}")

    if len(weight_grid) == 0:
        raise ValueError("Weight grid is empty. Check generate_weight_grid().")

    windows = create_walk_forward_windows(df)

    print(f"Walk-forward windows: {len(windows):,}")

    all_results = []
    all_weight_rows = []

    for window_id, window in enumerate(windows, start=1):
        train_df = df[
            (df["date"] >= window["train_start"])
            & (df["date"] < window["train_end"])
        ].copy()

        test_df = df[
            (df["date"] >= window["test_start"])
            & (df["date"] < window["test_end"])
        ].copy()

        if len(train_df) == 0 or len(test_df) == 0:
            continue

        print("\n" + "=" * 90)
        print(f"WINDOW {window_id}")
        print("=" * 90)
        print(f"Train: {window['train_start'].date()} to {window['train_end'].date()}")
        print(f"Test:  {window['test_start'].date()} to {window['test_end'].date()}")
        print(f"Train rows: {len(train_df):,}")
        print(f"Test rows:  {len(test_df):,}")

        for top_n in TOP_N_VALUES:
            print(f"\nOptimizing Top {top_n}...")

            best_weights, train_metric, train_score = optimize_weights(
                train_df=train_df,
                weight_grid=weight_grid,
                top_n=top_n,
            )

            scored_test_df = add_weighted_score(
                test_df,
                best_weights,
                "optimized_score",
            )

            test_metric = evaluate_ranker(
                scored_test_df,
                "optimized_score",
                top_n,
            )

            optimized_row = {
                "window_id": window_id,
                "strategy": "Optimized V4 Weights",
                "rank_column": "optimized_score",
                "top_n": top_n,
                "train_start": window["train_start"].date(),
                "train_end": window["train_end"].date(),
                "test_start": window["test_start"].date(),
                "test_end": window["test_end"].date(),
                "train_objective_score": train_score,
            }

            optimized_row.update(test_metric)
            all_results.append(optimized_row)

            weight_row = {
                "window_id": window_id,
                "top_n": top_n,
                "train_start": window["train_start"].date(),
                "train_end": window["train_end"].date(),
                "test_start": window["test_start"].date(),
                "test_end": window["test_end"].date(),
                "train_objective_score": train_score,
            }

            for factor, weight in best_weights.items():
                weight_row[factor] = weight

            all_weight_rows.append(weight_row)

            print("Best weights:")
            for factor, weight in best_weights.items():
                print(f"  {factor}: {weight:.2f}")

            print(
                f"Optimized test avg daily return: "
                f"{test_metric['average_daily_portfolio_return']:.4f}%"
            )
            print(f"Optimized test win rate: {test_metric['win_rate']:.4f}")

            baseline_rows = evaluate_baselines(test_df, top_n)

            for row in baseline_rows:
                row["window_id"] = window_id
                row["train_start"] = window["train_start"].date()
                row["train_end"] = window["train_end"].date()
                row["test_start"] = window["test_start"].date()
                row["test_end"] = window["test_end"].date()
                row["train_objective_score"] = np.nan
                all_results.append(row)

    results_df = pd.DataFrame(all_results)
    weights_df = pd.DataFrame(all_weight_rows)

    return results_df, weights_df


def summarize_results(results_df):
    summary = (
        results_df
        .groupby(["strategy", "top_n"])
        .agg(
            windows=("window_id", "count"),
            avg_daily_return=("average_daily_portfolio_return", "mean"),
            median_daily_return=("average_daily_portfolio_return", "median"),
            avg_win_rate=("win_rate", "mean"),
            avg_daily_std=("daily_return_std", "mean"),
            avg_worst_day=("worst_daily_return", "mean"),
            avg_cumulative_return=("cumulative_return", "mean"),
        )
        .reset_index()
        .sort_values(
            ["avg_daily_return", "avg_win_rate"],
            ascending=False,
        )
    )

    return summary


def save_outputs(results_df, weights_df, summary_df):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results_path = os.path.join(
        OUTPUT_DIR,
        f"walk_forward_weight_optimizer_results_{timestamp}.csv",
    )

    weights_path = os.path.join(
        OUTPUT_DIR,
        f"walk_forward_weight_optimizer_weights_{timestamp}.csv",
    )

    summary_path = os.path.join(
        OUTPUT_DIR,
        f"walk_forward_weight_optimizer_summary_{timestamp}.csv",
    )

    txt_path = os.path.join(
        OUTPUT_DIR,
        f"walk_forward_weight_optimizer_report_{timestamp}.txt",
    )

    results_df.to_csv(results_path, index=False)
    weights_df.to_csv(weights_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    with open(txt_path, "w") as f:
        f.write("AI STOCK HUNTER V3 - WALK-FORWARD WEIGHT OPTIMIZER\n")
        f.write("=" * 100 + "\n\n")

        f.write(f"Input: {INPUT_PATH}\n")
        f.write(f"Return target: {RETURN_COL}\n")
        f.write(f"Win target: {WIN_COL}\n")
        f.write(f"Train months: {TRAIN_MONTHS}\n")
        f.write(f"Test months: {TEST_MONTHS}\n")
        f.write(f"Top N values: {TOP_N_VALUES}\n\n")

        f.write("SUMMARY RESULTS\n")
        f.write("-" * 100 + "\n")
        f.write(summary_df.to_string(index=False))
        f.write("\n\n")

        f.write("DECISION RULE\n")
        f.write("-" * 100 + "\n")
        f.write(
            "Optimized V4 can only move toward live deployment if it beats "
            "Current Pre Score and Stock vs Sector 20D across multiple "
            "walk-forward windows, not just one test period.\n"
        )

    return results_path, weights_path, summary_path, txt_path


def main():
    print("AI STOCK HUNTER V3 - WALK-FORWARD WEIGHT OPTIMIZER")
    print("=" * 100)

    df = load_data()
    df = add_required_scores(df)

    df = df.dropna(subset=[RETURN_COL, WIN_COL]).copy()

    print(f"Rows loaded: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Return target: {RETURN_COL}")
    print(f"Top N values: {TOP_N_VALUES}")

    results_df, weights_df = run_walk_forward(df)
    summary_df = summarize_results(results_df)

    print("\n" + "=" * 100)
    print("WALK-FORWARD SUMMARY")
    print("=" * 100)
    print(summary_df.to_string(index=False))

    results_path, weights_path, summary_path, txt_path = save_outputs(
        results_df,
        weights_df,
        summary_df,
    )

    print("\nSaved:")
    print(f"Results: {results_path}")
    print(f"Weights: {weights_path}")
    print(f"Summary: {summary_path}")
    print(f"Report:  {txt_path}")

    print("\nResearch rule:")
    print("If optimized V4 does not beat the baselines across windows,")
    print("we do not put it into the live scanner.")


if __name__ == "__main__":
    main()