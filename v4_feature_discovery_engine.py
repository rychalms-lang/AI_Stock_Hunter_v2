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
]

REPORTS_DIR = Path("reports")
RESULTS_FILE = REPORTS_DIR / "v4_feature_discovery_results.csv"
SUMMARY_FILE = REPORTS_DIR / "v4_feature_discovery_summary.json"


RETURN_COLUMNS = {
    1: ["future_1d_return", "future_return_1d", "return_1d"],
    3: ["future_3d_return", "future_return_3d", "return_3d"],
    5: ["future_5d_return", "future_return_5d", "return_5d"],
    7: ["future_7d_return", "future_return_7d", "return_7d"],
    10: ["future_10d_return", "future_return_10d", "return_10d"],
}


BASE_FEATURES = [
    "five_day_change",
    "twenty_day_change",
    "relative_strength",
    "volume_ratio",
    "open_to_close_change",
    "pre_score",
]


BLOCKED_FEATURE_KEYWORDS = [
    "future",
    "return_",
    "_return",
    "target",
    "label",
    "outcome",
    "pattern_",
    "best_",
    "historical",
    "win_rate",
    "confidence",
    "expected_return",
    "avg_return",
    "hold_period",
]


LEAKAGE_CHECK_KEYWORDS = [
    "future",
    "return_",
    "_return",
    "target",
    "label",
    "outcome",
]


def find_data_file():
    for path in DATA_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError("Could not find historical training data.")


def find_column(df, names):
    for name in names:
        if name in df.columns:
            return name

    return None


def load_data():
    path = find_data_file()
    print(f"Loading data: {path}")

    df = pd.read_csv(path)

    if "date" not in df.columns:
        raise ValueError("No date column found.")

    if "ticker" not in df.columns:
        raise ValueError("No ticker column found.")

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper()

    cutoff = df["date"].max() - pd.DateOffset(years=5)
    df = df[df["date"] >= cutoff].copy()

    for col in df.columns:
        if col not in ["date", "ticker", "sector", "regime"]:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except Exception:
                pass

    print(f"Rows loaded: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    return df


def is_allowed_feature(column_name):
    name = column_name.lower()

    if column_name in ["date", "ticker", "sector", "regime"]:
        return False

    if any(keyword in name for keyword in BLOCKED_FEATURE_KEYWORDS):
        return False

    return True


def add_v4_features(df):
    df = df.copy()

    for col in BASE_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "five_day_change" in df.columns and "twenty_day_change" in df.columns:
        df["momentum_acceleration"] = (
            df["five_day_change"] - (df["twenty_day_change"] / 4)
        )

    if "five_day_change" in df.columns and "relative_strength" in df.columns:
        df["momentum_rs_combo"] = (
            df["five_day_change"] + df["relative_strength"]
        )

    if "volume_ratio" in df.columns and "five_day_change" in df.columns:
        df["volume_momentum_pressure"] = (
            df["volume_ratio"] * df["five_day_change"]
        )

    if "volume_ratio" in df.columns and "relative_strength" in df.columns:
        df["volume_rs_pressure"] = (
            df["volume_ratio"] * df["relative_strength"]
        )

    if "pre_score" in df.columns and "volume_ratio" in df.columns:
        df["score_volume_combo"] = df["pre_score"] * df["volume_ratio"]

    if "open_to_close_change" in df.columns:
        df["intraday_strength"] = df["open_to_close_change"]
        df["intraday_abs_move"] = df["open_to_close_change"].abs()

    if "five_day_change" in df.columns:
        df["five_day_rank_daily"] = df.groupby("date")["five_day_change"].rank(
            pct=True
        )

    if "twenty_day_change" in df.columns:
        df["twenty_day_rank_daily"] = df.groupby("date")[
            "twenty_day_change"
        ].rank(pct=True)

    if "relative_strength" in df.columns:
        df["relative_strength_rank_daily"] = df.groupby("date")[
            "relative_strength"
        ].rank(pct=True)

    if "volume_ratio" in df.columns:
        df["volume_rank_daily"] = df.groupby("date")["volume_ratio"].rank(
            pct=True
        )

    if "pre_score" in df.columns:
        df["pre_score_rank_daily"] = df.groupby("date")["pre_score"].rank(
            pct=True
        )

    if "sector" in df.columns and "five_day_change" in df.columns:
        df["sector_momentum_rank"] = df.groupby(["date", "sector"])[
            "five_day_change"
        ].rank(pct=True)

    if "sector" in df.columns and "relative_strength" in df.columns:
        df["sector_rs_rank"] = df.groupby(["date", "sector"])[
            "relative_strength"
        ].rank(pct=True)

    feature_cols = []

    for col in df.columns:
        if not is_allowed_feature(col):
            continue

        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        if df[col].notna().sum() <= 1000:
            continue

        feature_cols.append(col)

    print(f"\nV4 usable features: {len(feature_cols)}")
    print(feature_cols)

    return df, feature_cols


def check_for_leakage(features):
    print("\nChecking for leakage...")

    for feature in features:
        lower = feature.lower()

        if any(keyword in lower for keyword in LEAKAGE_CHECK_KEYWORDS):
            raise RuntimeError(f"DATA LEAKAGE DETECTED -> {feature}")

    print("No leakage detected.\n")


def get_return_col(df, hold_days):
    return find_column(df, RETURN_COLUMNS[hold_days])


def build_folds(df):
    max_date = df["date"].max()
    holdout_start = max_date - pd.DateOffset(months=6)

    trainable = df[df["date"] < holdout_start].copy()
    holdout = df[df["date"] >= holdout_start].copy()

    start = trainable["date"].min() + pd.DateOffset(years=2)
    end = trainable["date"].max()

    folds = []
    fold_start = start

    while fold_start < end:
        folds.append(
            (
                fold_start - pd.DateOffset(years=2),
                fold_start,
                fold_start,
                fold_start + pd.DateOffset(months=3),
            )
        )

        fold_start += pd.DateOffset(months=3)

    return folds, holdout, holdout_start


def random_strategy(features):
    selected = random.sample(features, random.randint(3, min(8, len(features))))
    raw_weights = np.random.dirichlet(np.ones(len(selected)))

    weights = {
        feature: float(weight)
        for feature, weight in zip(selected, raw_weights)
    }

    filters = {}

    filter_candidates = [
        "five_day_change",
        "twenty_day_change",
        "relative_strength",
        "volume_ratio",
        "open_to_close_change",
        "pre_score",
        "momentum_acceleration",
        "momentum_rs_combo",
        "volume_momentum_pressure",
        "volume_rs_pressure",
        "five_day_rank_daily",
        "relative_strength_rank_daily",
        "volume_rank_daily",
        "sector_momentum_rank",
        "sector_rs_rank",
    ]

    for feature in filter_candidates:
        if feature not in features:
            continue

        if random.random() > 0.45:
            continue

        if "rank" in feature:
            filters[feature] = random.choice([0.5, 0.6, 0.7, 0.8, 0.9])
        elif feature == "volume_ratio":
            filters[feature] = random.choice([0.8, 1.0, 1.2, 1.5, 2.0])
        elif feature == "open_to_close_change":
            filters[feature] = random.choice([-8, -5, -3, 0, 2])
        else:
            filters[feature] = random.choice([-10, -5, 0, 2, 5, 8, 10, 12, 15])

    return {
        "hold_days": random.choice([1, 3, 5, 7, 10]),
        "top_n": random.choice([3, 5, 7, 10, 15]),
        "weights": weights,
        "filters": filters,
    }


def normalize_weights(weights):
    total = sum(max(value, 0.001) for value in weights.values())

    return {
        feature: max(value, 0.001) / total
        for feature, value in weights.items()
    }


def mutate(strategy, features, mutation_rate=0.28):
    child = json.loads(json.dumps(strategy))

    if random.random() < mutation_rate:
        child["hold_days"] = random.choice([1, 3, 5, 7, 10])

    if random.random() < mutation_rate:
        child["top_n"] = random.choice([3, 5, 7, 10, 15])

    for feature in list(child["weights"].keys()):
        if random.random() < mutation_rate:
            child["weights"][feature] *= random.uniform(0.45, 1.8)

    if random.random() < mutation_rate and len(child["weights"]) < 8:
        choices = [
            feature
            for feature in features
            if feature not in child["weights"]
        ]

        if choices:
            child["weights"][random.choice(choices)] = random.uniform(0.05, 0.5)

    if random.random() < mutation_rate and len(child["weights"]) > 3:
        del child["weights"][random.choice(list(child["weights"].keys()))]

    child["weights"] = normalize_weights(child["weights"])

    return child


def crossover(a, b, features):
    child = {
        "hold_days": random.choice([a["hold_days"], b["hold_days"]]),
        "top_n": random.choice([a["top_n"], b["top_n"]]),
        "weights": {},
        "filters": {},
    }

    for feature in set(a["weights"]) | set(b["weights"]):
        if feature not in features:
            continue

        if feature in a["weights"] and feature in b["weights"]:
            child["weights"][feature] = random.choice(
                [a["weights"][feature], b["weights"][feature]]
            )
        elif feature in a["weights"] and random.random() < 0.5:
            child["weights"][feature] = a["weights"][feature]
        elif feature in b["weights"]:
            child["weights"][feature] = b["weights"][feature]

    if len(child["weights"]) < 3:
        return random_strategy(features)

    child["weights"] = normalize_weights(child["weights"])

    for feature in set(a["filters"]) | set(b["filters"]):
        if random.random() < 0.5 and feature in a["filters"]:
            child["filters"][feature] = a["filters"][feature]
        elif feature in b["filters"]:
            child["filters"][feature] = b["filters"][feature]

    return child


def apply_filters(df, filters):
    filtered = df

    for feature, threshold in filters.items():
        if feature not in filtered.columns:
            continue

        filtered = filtered[filtered[feature].fillna(-999) >= threshold]

    return filtered


def score_rows(df, weights):
    score = pd.Series(0.0, index=df.index)

    for feature, weight in weights.items():
        if feature not in df.columns:
            continue

        ranked = (
            df[feature]
            .replace([np.inf, -np.inf], np.nan)
            .rank(pct=True)
            .fillna(0)
        )

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

    picks["return"] = pd.to_numeric(picks[return_col], errors="coerce")
    picks = picks.dropna(subset=["return"])

    return picks


def evaluate(df, strategy, return_col):
    picks = select_picks(df, strategy, return_col)

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

    baseline = pd.to_numeric(df[return_col], errors="coerce").dropna().mean()

    if pd.isna(baseline):
        return None

    return {
        "avg_return": float(avg_return),
        "median_return": float(median_return),
        "win_rate": float(win_rate),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "baseline": float(baseline),
        "alpha": float(avg_return - baseline),
        "trade_count": int(len(picks)),
        "active_days": int(len(daily)),
    }


def test_strategy(df, strategy, folds):
    return_col = get_return_col(df, strategy["hold_days"])

    if return_col is None:
        return None

    fold_rows = []

    for train_start, train_end, test_start, test_end in folds:
        test = df[(df["date"] >= test_start) & (df["date"] < test_end)]

        if test.empty:
            continue

        metrics = evaluate(test, strategy, return_col)

        if metrics is None:
            continue

        fold_rows.append(metrics)

    if len(fold_rows) < 6:
        return None

    folds_df = pd.DataFrame(fold_rows)

    avg_alpha = folds_df["alpha"].mean()
    median_alpha = folds_df["alpha"].median()
    positive_alpha_rate = (folds_df["alpha"] > 0).mean() * 100
    avg_return = folds_df["avg_return"].mean()
    avg_baseline = folds_df["baseline"].mean()
    avg_win_rate = folds_df["win_rate"].mean()
    avg_sharpe = folds_df["sharpe"].mean()
    avg_sortino = folds_df["sortino"].mean()
    total_trades = folds_df["trade_count"].sum()

    quality_score = (
        avg_alpha * 3.0
        + median_alpha * 2.0
        + positive_alpha_rate * 0.05
        + avg_win_rate * 0.025
        + avg_sharpe * 2.0
        + avg_sortino * 1.0
        + min(total_trades / 1000, 3)
    )

    return {
        "hold_days": strategy["hold_days"],
        "top_n": strategy["top_n"],
        "features": json.dumps(strategy["weights"]),
        "filters": json.dumps(strategy["filters"]),
        "folds": int(len(folds_df)),
        "avg_oos_return": round(avg_return, 4),
        "avg_baseline_return": round(avg_baseline, 4),
        "avg_alpha": round(avg_alpha, 4),
        "median_alpha": round(median_alpha, 4),
        "positive_alpha_rate": round(positive_alpha_rate, 2),
        "avg_win_rate": round(avg_win_rate, 2),
        "avg_sharpe": round(avg_sharpe, 4),
        "avg_sortino": round(avg_sortino, 4),
        "total_trades": int(total_trades),
        "quality_score": round(quality_score, 4),
    }


def evaluate_holdout(df, strategy, holdout):
    return_col = get_return_col(df, strategy["hold_days"])

    if return_col is None:
        return None

    return evaluate(holdout, strategy, return_col)


def run_v4(generations, population_size, elite_size, seed):
    random.seed(seed)
    np.random.seed(seed)

    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    df, features = add_v4_features(df)
    check_for_leakage(features)

    folds, holdout, holdout_start = build_folds(df)

    print(f"Walk-forward folds: {len(folds)}")
    print(f"Untouched holdout starts: {holdout_start.date()}")
    print(f"Population: {population_size}")
    print(f"Generations: {generations}")
    print("Starting V4 feature discovery...\n")

    population = [random_strategy(features) for _ in range(population_size)]
    all_results = []
    start_time = time.time()

    for generation in range(1, generations + 1):
        scored = []

        for strategy in population:
            result = test_strategy(df, strategy, folds)

            if result is None:
                continue

            scored.append((result["quality_score"], strategy, result))
            all_results.append(result)

        if not scored:
            print(f"Generation {generation}: no valid strategies.")
            population = [random_strategy(features) for _ in range(population_size)]
            continue

        scored.sort(key=lambda item: item[0], reverse=True)
        elites = scored[:elite_size]

        elapsed = (time.time() - start_time) / 60

        print(
            f"Generation {generation}/{generations} | "
            f"Best Quality: {elites[0][0]:.4f} | "
            f"Alpha: {elites[0][2]['avg_alpha']:.4f}% | "
            f"Positive Alpha: {elites[0][2]['positive_alpha_rate']:.2f}% | "
            f"Elapsed: {elapsed:.1f} min"
        )

        pd.DataFrame(all_results).sort_values(
            "quality_score",
            ascending=False,
        ).to_csv(RESULTS_FILE, index=False)

        parents = [item[1] for item in elites]
        next_population = parents.copy()

        while len(next_population) < population_size:
            if random.random() < 0.75:
                parent_a, parent_b = random.sample(parents, 2)
                child = crossover(parent_a, parent_b, features)
            else:
                child = random_strategy(features)

            child = mutate(child, features)
            next_population.append(child)

        population = next_population

    results_df = pd.DataFrame(all_results).sort_values(
        "quality_score",
        ascending=False
    )

    results_df.to_csv(RESULTS_FILE, index=False)

    best_row = results_df.iloc[0].to_dict()

    best_strategy = {
        "hold_days": int(best_row["hold_days"]),
        "top_n": int(best_row["top_n"]),
        "weights": json.loads(best_row["features"]),
        "filters": json.loads(best_row["filters"]),
    }

    holdout_result = evaluate_holdout(df, best_strategy, holdout)

    summary = {
        "generations": generations,
        "population_size": population_size,
        "elite_size": elite_size,
        "total_valid_tests": int(len(results_df)),
        "holdout_start": str(holdout_start.date()),
        "best_walk_forward_strategy": best_row,
        "untouched_holdout_result": holdout_result,
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))

    print("\nDONE")
    print(f"Results saved: {RESULTS_FILE}")
    print(f"Summary saved: {SUMMARY_FILE}")

    print("\nTOP 10 V4 STRATEGIES")
    print(
        results_df[
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
                "total_trades",
            ]
        ].head(10).to_string(index=False)
    )

    print("\nUNTOUCHED HOLDOUT RESULT")
    print(holdout_result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--population", type=int, default=500)
    parser.add_argument("--elite", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    run_v4(
        generations=args.generations,
        population_size=args.population,
        elite_size=args.elite,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
