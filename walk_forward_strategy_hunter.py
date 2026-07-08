import itertools
from pathlib import Path

import numpy as np
import pandas as pd


DATA_CANDIDATES = [
    Path("data/historical_training_data.csv"),
    Path("historical_training_data.csv"),
    Path("performance/picks_history_v2.csv"),
]

OUTPUT_DIR = Path("reports")
OUTPUT_FILE = OUTPUT_DIR / "walk_forward_strategy_hunter_results.csv"


DATE_COLUMNS = ["date", "Date", "scan_date", "entry_date"]
TICKER_COLUMNS = ["ticker", "Ticker", "symbol", "Symbol"]

RETURN_COLUMNS = {
    1: ["future_1d_return", "future_return_1d", "pattern_1d_avg_return", "return_1d"],
    3: ["future_3d_return", "future_return_3d", "pattern_3d_avg_return", "return_3d"],
    5: ["future_5d_return", "future_return_5d", "pattern_5d_avg_return", "return_5d"],
    7: ["future_7d_return", "future_return_7d", "pattern_7d_avg_return", "return_7d"],
    10: ["future_10d_return", "future_return_10d", "pattern_10d_avg_return", "return_10d"],
}


def find_data_file():
    for path in DATA_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find historical data. Expected one of: "
        + ", ".join(str(p) for p in DATA_CANDIDATES)
    )


def find_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def find_return_column(df, hold_days):
    return find_column(df, RETURN_COLUMNS[hold_days])


def clean_data(df):
    date_col = find_column(df, DATE_COLUMNS)
    ticker_col = find_column(df, TICKER_COLUMNS)

    if date_col is None:
        raise ValueError(f"No date column found. Columns: {df.columns.tolist()}")

    if ticker_col is None:
        raise ValueError(f"No ticker column found. Columns: {df.columns.tolist()}")

    df = df.copy()
    df["date"] = pd.to_datetime(df[date_col])
    df["ticker"] = df[ticker_col].astype(str).str.upper()

    cutoff = df["date"].max() - pd.DateOffset(years=5)
    df = df[df["date"] >= cutoff].copy()

    numeric_cols = [
        "five_day_change",
        "twenty_day_change",
        "relative_strength",
        "volume_ratio",
        "open_to_close_change",
        "pre_score",
        "score",
        "confidence",
        "confidence_score",
        "sector_rank",
        "sentiment_score",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def safe_col(df, col, default=0):
    if col in df.columns:
        return df[col].fillna(default)
    return pd.Series(default, index=df.index)


def build_strategy_grid():
    hold_periods = [1, 3, 5, 7, 10]
    top_ns = [3, 5, 10, 15]
    min_five_day = [0, 2, 5, 8]
    min_relative_strength = [-5, 0, 3, 5]
    min_volume_ratio = [0.8, 1.0, 1.2, 1.5]
    max_open_to_close_abs = [999, 8, 5]

    weight_sets = [
        {"momentum": 0.50, "relative": 0.30, "volume": 0.20, "confidence": 0.00},
        {"momentum": 0.35, "relative": 0.35, "volume": 0.20, "confidence": 0.10},
        {"momentum": 0.25, "relative": 0.45, "volume": 0.20, "confidence": 0.10},
        {"momentum": 0.40, "relative": 0.20, "volume": 0.30, "confidence": 0.10},
        {"momentum": 0.25, "relative": 0.25, "volume": 0.20, "confidence": 0.30},
    ]

    strategies = []

    for hold, top_n, min_5d, min_rs, min_vol, max_oc, weights in itertools.product(
        hold_periods,
        top_ns,
        min_five_day,
        min_relative_strength,
        min_volume_ratio,
        max_open_to_close_abs,
        weight_sets,
    ):
        strategies.append({
            "hold_days": hold,
            "top_n": top_n,
            "min_five_day_change": min_5d,
            "min_relative_strength": min_rs,
            "min_volume_ratio": min_vol,
            "max_open_to_close_abs": max_oc,
            "weights": weights,
        })

    return strategies


def score_rows(df, strategy):
    weights = strategy["weights"]

    five_day = safe_col(df, "five_day_change")
    twenty_day = safe_col(df, "twenty_day_change")
    relative = safe_col(df, "relative_strength")
    volume = safe_col(df, "volume_ratio")
    confidence = safe_col(df, "confidence_score", safe_col(df, "confidence", 0))

    score = (
        five_day.rank(pct=True) * weights["momentum"]
        + relative.rank(pct=True) * weights["relative"]
        + volume.rank(pct=True) * weights["volume"]
        + confidence.rank(pct=True) * weights["confidence"]
    )

    if "score" in df.columns:
        score = score + safe_col(df, "score").rank(pct=True) * 0.15

    if "pre_score" in df.columns:
        score = score + safe_col(df, "pre_score").rank(pct=True) * 0.10

    return score


def apply_strategy(df, strategy, return_col):
    test = df.copy()

    test = test[
        (safe_col(test, "five_day_change") >= strategy["min_five_day_change"])
        & (safe_col(test, "relative_strength") >= strategy["min_relative_strength"])
        & (safe_col(test, "volume_ratio") >= strategy["min_volume_ratio"])
        & (safe_col(test, "open_to_close_change").abs() <= strategy["max_open_to_close_abs"])
    ].copy()

    if test.empty:
        return pd.DataFrame()

    test["strategy_score"] = score_rows(test, strategy)

    picks = (
        test.sort_values(["date", "strategy_score"], ascending=[True, False])
        .groupby("date")
        .head(strategy["top_n"])
        .copy()
    )

    picks["return"] = pd.to_numeric(picks[return_col], errors="coerce")
    picks = picks.dropna(subset=["return"])

    return picks


def evaluate_picks(picks):
    if picks.empty:
        return {
            "avg_return": -999,
            "median_return": -999,
            "win_rate": 0,
            "trade_count": 0,
            "active_days": 0,
            "daily_sharpe": -999,
        }

    daily = picks.groupby("date")["return"].mean()

    avg = daily.mean()
    std = daily.std()

    sharpe = 0 if std == 0 or pd.isna(std) else avg / std

    return {
        "avg_return": round(avg, 4),
        "median_return": round(daily.median(), 4),
        "win_rate": round((daily > 0).mean() * 100, 2),
        "trade_count": int(len(picks)),
        "active_days": int(daily.shape[0]),
        "daily_sharpe": round(sharpe, 4),
    }


def score_strategy_result(metrics):
    if metrics["trade_count"] < 50 or metrics["active_days"] < 20:
        return -999

    return (
        metrics["avg_return"] * 2.0
        + metrics["win_rate"] * 0.03
        + metrics["daily_sharpe"] * 1.5
    )


def walk_forward_test(df, strategies):
    results = []

    start = df["date"].min()
    end = df["date"].max()

    fold_start = start + pd.DateOffset(years=2)

    while fold_start < end:
        train_start = fold_start - pd.DateOffset(years=2)
        train_end = fold_start
        test_start = fold_start
        test_end = fold_start + pd.DateOffset(months=3)

        train_df = df[(df["date"] >= train_start) & (df["date"] < train_end)]
        test_df = df[(df["date"] >= test_start) & (df["date"] < test_end)]

        if train_df.empty or test_df.empty:
            fold_start = test_end
            continue

        best_train = None

        for strategy in strategies:
            return_col = find_return_column(train_df, strategy["hold_days"])

            if return_col is None:
                continue

            train_picks = apply_strategy(train_df, strategy, return_col)
            train_metrics = evaluate_picks(train_picks)
            train_score = score_strategy_result(train_metrics)

            if best_train is None or train_score > best_train["train_score"]:
                best_train = {
                    "strategy": strategy,
                    "return_col": return_col,
                    "train_metrics": train_metrics,
                    "train_score": train_score,
                }

        if best_train is None:
            fold_start = test_end
            continue

        strategy = best_train["strategy"]
        return_col = find_return_column(test_df, strategy["hold_days"])

        if return_col is None:
            fold_start = test_end
            continue

        test_picks = apply_strategy(test_df, strategy, return_col)
        test_metrics = evaluate_picks(test_picks)

        baseline = pd.to_numeric(test_df[return_col], errors="coerce").mean()
        alpha = test_metrics["avg_return"] - baseline

        results.append({
            "fold_start": test_start.date(),
            "fold_end": test_end.date(),
            "hold_days": strategy["hold_days"],
            "top_n": strategy["top_n"],
            "min_five_day_change": strategy["min_five_day_change"],
            "min_relative_strength": strategy["min_relative_strength"],
            "min_volume_ratio": strategy["min_volume_ratio"],
            "max_open_to_close_abs": strategy["max_open_to_close_abs"],
            "weights": str(strategy["weights"]),
            "train_avg_return": best_train["train_metrics"]["avg_return"],
            "train_win_rate": best_train["train_metrics"]["win_rate"],
            "train_trades": best_train["train_metrics"]["trade_count"],
            "test_avg_return": test_metrics["avg_return"],
            "test_median_return": test_metrics["median_return"],
            "test_win_rate": test_metrics["win_rate"],
            "test_trades": test_metrics["trade_count"],
            "test_active_days": test_metrics["active_days"],
            "test_daily_sharpe": test_metrics["daily_sharpe"],
            "baseline_avg_return": round(baseline, 4),
            "alpha_vs_baseline": round(alpha, 4),
        })

        fold_start = test_end

    return pd.DataFrame(results)


def summarize(results):
    if results.empty:
        print("No walk-forward results generated.")
        return

    print("\nWALK-FORWARD SUMMARY")
    print("--------------------")
    print(f"Folds tested: {len(results)}")
    print(f"Average OOS return: {results['test_avg_return'].mean():.3f}%")
    print(f"Average baseline return: {results['baseline_avg_return'].mean():.3f}%")
    print(f"Average alpha: {results['alpha_vs_baseline'].mean():.3f}%")
    print(f"Average win rate: {results['test_win_rate'].mean():.2f}%")
    print(f"Total OOS trades: {results['test_trades'].sum()}")

    print("\nBEST OOS FOLDS")
    print(results.sort_values("alpha_vs_baseline", ascending=False).head(10)[[
        "fold_start",
        "fold_end",
        "hold_days",
        "top_n",
        "test_avg_return",
        "baseline_avg_return",
        "alpha_vs_baseline",
        "test_win_rate",
        "test_trades",
    ]].to_string(index=False))

    print("\nMOST COMMON WINNING STRATEGIES")
    winners = results[results["alpha_vs_baseline"] > 0]

    if winners.empty:
        print("No positive-alpha folds.")
        return

    grouped = (
        winners.groupby(["hold_days", "top_n", "min_five_day_change", "min_relative_strength", "min_volume_ratio"])
        .agg(
            folds=("alpha_vs_baseline", "count"),
            avg_alpha=("alpha_vs_baseline", "mean"),
            avg_return=("test_avg_return", "mean"),
            avg_win_rate=("test_win_rate", "mean"),
            total_trades=("test_trades", "sum"),
        )
        .reset_index()
        .sort_values(["avg_alpha", "folds"], ascending=False)
    )

    print(grouped.head(15).to_string(index=False))


def main():
    data_file = find_data_file()
    print(f"Loading data: {data_file}")

    df = pd.read_csv(data_file)
    df = clean_data(df)

    print(f"Rows loaded from last 5 years: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    strategies = build_strategy_grid()
    print(f"Strategies generated: {len(strategies):,}")

    results = walk_forward_test(df, strategies)

    OUTPUT_DIR.mkdir(exist_ok=True)
    results.to_csv(OUTPUT_FILE, index=False)

    print(f"\nResults saved: {OUTPUT_FILE}")

    summarize(results)


if __name__ == "__main__":
    main()