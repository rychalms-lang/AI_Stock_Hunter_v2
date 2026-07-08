import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd


DATA_CANDIDATES = [
    Path("performance/historical_training_data.csv"),
    Path("data/historical_training_data_v3_features.csv"),
    Path("data/historical_training_data.csv"),
    Path("historical_training_data.csv"),
]

REPORTS_DIR = Path("reports")
RESULTS_FILE = REPORTS_DIR / "strategy_discovery_results.csv"
SUMMARY_FILE = REPORTS_DIR / "strategy_discovery_summary.json"


DATE_COLUMNS = ["date", "Date", "scan_date", "entry_date"]
TICKER_COLUMNS = ["ticker", "Ticker", "symbol", "Symbol"]

RETURN_COLUMNS = {
    1: ["future_1d_return", "future_return_1d", "return_1d"],
    3: ["future_3d_return", "future_return_3d", "return_3d"],
    5: ["future_5d_return", "future_return_5d", "return_5d"],
    7: ["future_7d_return", "future_return_7d", "return_7d"],
    10: ["future_10d_return", "future_return_10d", "return_10d"],
}


FEATURE_CANDIDATES = [
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


def find_data_file():
    for path in DATA_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError("Could not find historical training data.")


def find_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def find_return_column(df, hold_days):
    return find_column(df, RETURN_COLUMNS[hold_days])


def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def load_data():
    path = find_data_file()
    print(f"Loading data: {path}")

    df = pd.read_csv(path)

    date_col = find_column(df, DATE_COLUMNS)
    ticker_col = find_column(df, TICKER_COLUMNS)

    if date_col is None:
        raise ValueError(f"No date column found. Columns: {df.columns.tolist()}")

    if ticker_col is None:
        raise ValueError(f"No ticker column found. Columns: {df.columns.tolist()}")

    df["date"] = pd.to_datetime(df[date_col])
    df["ticker"] = df[ticker_col].astype(str).str.upper()

    cutoff = df["date"].max() - pd.DateOffset(years=5)
    df = df[df["date"] >= cutoff].copy()

    for col in FEATURE_CANDIDATES:
        if col in df.columns:
            df[col] = safe_numeric(df[col])

    for hold_days, candidates in RETURN_COLUMNS.items():
        col = find_column(df, candidates)
        if col:
            df[col] = safe_numeric(df[col])

    print(f"Rows loaded: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    return df


def available_features(df):
    usable = []

    for col in FEATURE_CANDIDATES:
        if col in df.columns and df[col].notna().sum() > 100:
            usable.append(col)

    if not usable:
        raise ValueError("No usable numeric feature columns found.")

    print(f"Usable features: {usable}")
    return usable


def random_strategy(features):
    hold_days = random.choice([1, 3, 5, 7, 10])
    top_n = random.choice([3, 5, 7, 10, 15, 20])

    selected_features = random.sample(
        features,
        k=random.randint(2, min(6, len(features)))
    )

    raw_weights = np.random.dirichlet(np.ones(len(selected_features)))
    weights = {
        feature: float(weight)
        for feature, weight in zip(selected_features, raw_weights)
    }

    filters = {}

    possible_filters = [
        "five_day_change",
        "twenty_day_change",
        "relative_strength",
        "volume_ratio",
        "open_to_close_change",
        "score",
        "confidence_score",
        "pre_score",
    ]

    for feature in possible_filters:
        if feature not in features:
            continue

        if random.random() < 0.45:
            continue

        if feature == "volume_ratio":
            filters[feature] = random.choice([0.7, 0.9, 1.0, 1.2, 1.5, 2.0])
        elif feature == "open_to_close_change":
            filters[feature] = random.choice([-8, -5, -3, 0, 2])
        elif feature in ["score", "confidence_score"]:
            filters[feature] = random.choice([40, 50, 60, 70, 80])
        else:
            filters[feature] = random.choice([-10, -5, 0, 2, 5, 8, 12])

    return {
        "hold_days": hold_days,
        "top_n": top_n,
        "weights": weights,
        "filters": filters,
    }


def apply_filters(df, filters):
    test = df.copy()

    for feature, threshold in filters.items():
        if feature not in test.columns:
            continue

        values = test[feature].fillna(-999)

        if feature == "open_to_close_change":
            test = test[values >= threshold]
        else:
            test = test[values >= threshold]

    return test


def score_rows(df, weights):
    score = pd.Series(0.0, index=df.index)

    for feature, weight in weights.items():
        if feature not in df.columns:
            continue

        values = df[feature].replace([np.inf, -np.inf], np.nan)
        ranked = values.rank(pct=True).fillna(0)

        score += ranked * weight

    return score


def select_picks(df, strategy, return_col):
    filtered = apply_filters(df, strategy["filters"])

    if filtered.empty:
        return pd.DataFrame()

    filtered = filtered.copy()
    filtered["strategy_score"] = score_rows(filtered, strategy["weights"])

    picks = (
        filtered.sort_values(["date", "strategy_score"], ascending=[True, False])
        .groupby("date")
        .head(strategy["top_n"])
        .copy()
    )

    picks["return"] = safe_numeric(picks[return_col])
    picks = picks.dropna(subset=["return"])

    return picks


def evaluate_picks(picks):
    if picks.empty:
        return None

    daily = picks.groupby("date")["return"].mean()

    if len(daily) < 10:
        return None

    avg_return = daily.mean()
    median_return = daily.median()
    win_rate = (daily > 0).mean() * 100
    std = daily.std()

    sharpe = 0 if std == 0 or pd.isna(std) else avg_return / std
    downside = daily[daily < 0].std()
    sortino = 0 if downside == 0 or pd.isna(downside) else avg_return / downside

    equity = (1 + daily / 100).cumprod()
    peak = equity.cummax()
    drawdown = ((equity / peak) - 1) * 100
    max_drawdown = drawdown.min()

    return {
        "avg_return": float(avg_return),
        "median_return": float(median_return),
        "win_rate": float(win_rate),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_drawdown),
        "trade_count": int(len(picks)),
        "active_days": int(len(daily)),
    }


def strategy_quality(metrics, baseline_return):
    alpha = metrics["avg_return"] - baseline_return

    return (
        alpha * 2.5
        + metrics["sharpe"] * 1.5
        + metrics["sortino"] * 0.75
        + metrics["win_rate"] * 0.025
        + min(metrics["active_days"], 60) * 0.01
        + metrics["max_drawdown"] * 0.03
    )


def build_folds(df):
    start = df["date"].min() + pd.DateOffset(years=2)
    end = df["date"].max()

    folds = []
    fold_start = start

    while fold_start < end:
        train_start = fold_start - pd.DateOffset(years=2)
        train_end = fold_start
        test_start = fold_start
        test_end = fold_start + pd.DateOffset(months=3)

        folds.append((train_start, train_end, test_start, test_end))
        fold_start = test_end

    return folds


def test_strategy(df, strategy, folds):
    hold_days = strategy["hold_days"]
    return_col = find_return_column(df, hold_days)

    if return_col is None:
        return None

    fold_results = []

    for train_start, train_end, test_start, test_end in folds:
        train = df[(df["date"] >= train_start) & (df["date"] < train_end)]
        test = df[(df["date"] >= test_start) & (df["date"] < test_end)]

        if train.empty or test.empty:
            continue

        train_picks = select_picks(train, strategy, return_col)
        train_metrics = evaluate_picks(train_picks)

        if train_metrics is None:
            continue

        test_picks = select_picks(test, strategy, return_col)
        test_metrics = evaluate_picks(test_picks)

        if test_metrics is None:
            continue

        baseline = safe_numeric(test[return_col]).dropna().mean()

        if pd.isna(baseline):
            continue

        fold_results.append({
            "fold_start": str(test_start.date()),
            "fold_end": str(test_end.date()),
            "train_avg_return": train_metrics["avg_return"],
            "test_avg_return": test_metrics["avg_return"],
            "baseline_return": float(baseline),
            "alpha": test_metrics["avg_return"] - float(baseline),
            "test_win_rate": test_metrics["win_rate"],
            "test_sharpe": test_metrics["sharpe"],
            "test_sortino": test_metrics["sortino"],
            "test_max_drawdown": test_metrics["max_drawdown"],
            "test_trades": test_metrics["trade_count"],
            "test_active_days": test_metrics["active_days"],
        })

    if len(fold_results) < 3:
        return None

    folds_df = pd.DataFrame(fold_results)

    avg_alpha = folds_df["alpha"].mean()
    median_alpha = folds_df["alpha"].median()
    avg_return = folds_df["test_avg_return"].mean()
    avg_baseline = folds_df["baseline_return"].mean()
    avg_win_rate = folds_df["test_win_rate"].mean()
    avg_sharpe = folds_df["test_sharpe"].mean()
    avg_sortino = folds_df["test_sortino"].mean()
    worst_drawdown = folds_df["test_max_drawdown"].min()
    positive_alpha_rate = (folds_df["alpha"] > 0).mean() * 100
    total_trades = folds_df["test_trades"].sum()

    quality = (
        avg_alpha * 3.0
        + median_alpha * 2.0
        + avg_sharpe * 1.5
        + avg_sortino * 0.75
        + positive_alpha_rate * 0.04
        + avg_win_rate * 0.02
        + worst_drawdown * 0.04
    )

    return {
        "hold_days": strategy["hold_days"],
        "top_n": strategy["top_n"],
        "features": json.dumps(strategy["weights"]),
        "filters": json.dumps(strategy["filters"]),
        "folds": len(fold_results),
        "avg_oos_return": round(avg_return, 4),
        "avg_baseline_return": round(avg_baseline, 4),
        "avg_alpha": round(avg_alpha, 4),
        "median_alpha": round(median_alpha, 4),
        "positive_alpha_rate": round(positive_alpha_rate, 2),
        "avg_win_rate": round(avg_win_rate, 2),
        "avg_sharpe": round(avg_sharpe, 4),
        "avg_sortino": round(avg_sortino, 4),
        "worst_drawdown": round(worst_drawdown, 4),
        "total_trades": int(total_trades),
        "quality_score": round(quality, 4),
    }


def run_discovery(strategy_count, seed, checkpoint_every):
    random.seed(seed)
    np.random.seed(seed)

    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    features = available_features(df)
    folds = build_folds(df)

    print(f"Walk-forward folds: {len(folds)}")
    print(f"Strategies to test: {strategy_count:,}")
    print("Starting strategy discovery...\n")

    results = []
    start_time = time.time()

    for i in range(1, strategy_count + 1):
        strategy = random_strategy(features)
        result = test_strategy(df, strategy, folds)

        if result is not None:
            results.append(result)

        if i % checkpoint_every == 0:
            elapsed = time.time() - start_time
            print(
                f"Tested {i:,}/{strategy_count:,} strategies | "
                f"Valid: {len(results):,} | "
                f"Elapsed: {elapsed / 60:.1f} min"
            )

            if results:
                pd.DataFrame(results).sort_values(
                    "quality_score",
                    ascending=False
                ).to_csv(RESULTS_FILE, index=False)

    results_df = pd.DataFrame(results)

    if results_df.empty:
        print("No valid strategies found.")
        return

    results_df = results_df.sort_values("quality_score", ascending=False)
    results_df.to_csv(RESULTS_FILE, index=False)

    top = results_df.head(25)

    summary = {
        "strategy_count_requested": strategy_count,
        "valid_strategies": int(len(results_df)),
        "best_quality_score": float(results_df.iloc[0]["quality_score"]),
        "best_avg_alpha": float(results_df.iloc[0]["avg_alpha"]),
        "best_positive_alpha_rate": float(results_df.iloc[0]["positive_alpha_rate"]),
        "best_avg_oos_return": float(results_df.iloc[0]["avg_oos_return"]),
        "best_avg_baseline_return": float(results_df.iloc[0]["avg_baseline_return"]),
        "best_strategy": results_df.iloc[0].to_dict(),
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))

    print("\nDONE")
    print(f"Results saved: {RESULTS_FILE}")
    print(f"Summary saved: {SUMMARY_FILE}")

    print("\nTOP 10 STRATEGIES")
    print(
        top[
            [
                "quality_score",
                "hold_days",
                "top_n",
                "avg_oos_return",
                "avg_baseline_return",
                "avg_alpha",
                "positive_alpha_rate",
                "avg_win_rate",
                "avg_sharpe",
                "worst_drawdown",
                "total_trades",
            ]
        ].head(10).to_string(index=False)
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--strategies",
        type=int,
        default=50000,
        help="Number of random strategies to test."
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed."
    )

    parser.add_argument(
        "--checkpoint",
        type=int,
        default=500,
        help="Save progress every N strategies."
    )

    args = parser.parse_args()

    run_discovery(
        strategy_count=args.strategies,
        seed=args.seed,
        checkpoint_every=args.checkpoint,
    )


if __name__ == "__main__":
    main()