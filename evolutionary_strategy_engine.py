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
RESULTS_FILE = REPORTS_DIR / "evolutionary_strategy_results.csv"
SUMMARY_FILE = REPORTS_DIR / "evolutionary_strategy_summary.json"


DATE_COLUMNS = ["date", "Date", "scan_date", "entry_date"]
TICKER_COLUMNS = ["ticker", "Ticker", "symbol", "Symbol"]

RETURN_COLUMNS = {
    1: ["future_1d_return", "future_return_1d", "return_1d"],
    3: ["future_3d_return", "future_return_3d", "return_3d"],
    5: ["future_5d_return", "future_return_5d", "return_5d"],
    7: ["future_7d_return", "future_return_7d", "return_7d"],
    10: ["future_10d_return", "future_return_10d", "return_10d"],
}

FEATURES = [
    "five_day_change",
    "twenty_day_change",
    "relative_strength",
    "volume_ratio",
    "open_to_close_change",
    "pre_score",
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


def load_data():
    path = find_data_file()
    print(f"Loading data: {path}")

    df = pd.read_csv(path)

    date_col = find_column(df, DATE_COLUMNS)
    ticker_col = find_column(df, TICKER_COLUMNS)

    if date_col is None:
        raise ValueError("No date column found.")

    if ticker_col is None:
        raise ValueError("No ticker column found.")

    df["date"] = pd.to_datetime(df[date_col])
    df["ticker"] = df[ticker_col].astype(str).str.upper()

    cutoff = df["date"].max() - pd.DateOffset(years=5)
    df = df[df["date"] >= cutoff].copy()

    for col in FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for hold_days, cols in RETURN_COLUMNS.items():
        return_col = find_column(df, cols)
        if return_col:
            df[return_col] = pd.to_numeric(df[return_col], errors="coerce")

    usable_features = [col for col in FEATURES if col in df.columns]

    print(f"Rows loaded: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Features: {usable_features}")

    return df, usable_features


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


def random_strategy(features):
    selected = random.sample(features, k=random.randint(2, min(6, len(features))))
    raw_weights = np.random.dirichlet(np.ones(len(selected)))

    weights = {
        feature: float(weight)
        for feature, weight in zip(selected, raw_weights)
    }

    filters = {}

    if "five_day_change" in features:
        filters["five_day_change"] = random.choice([0, 2, 5, 8, 10, 12, 15])

    if "twenty_day_change" in features:
        filters["twenty_day_change"] = random.choice([-10, -5, 0, 5, 8, 10, 12, 15])

    if "relative_strength" in features:
        filters["relative_strength"] = random.choice([-10, -5, 0, 3, 5, 8, 12])

    if "volume_ratio" in features:
        filters["volume_ratio"] = random.choice([0.7, 0.9, 1.0, 1.2, 1.5, 2.0])

    if "open_to_close_change" in features and random.random() < 0.5:
        filters["open_to_close_change"] = random.choice([-8, -5, -3, 0, 2])

    if "pre_score" in features and random.random() < 0.5:
        filters["pre_score"] = random.choice([-10, -5, 0, 5, 8, 12])

    return {
        "hold_days": random.choice([1, 3, 5, 7, 10]),
        "top_n": random.choice([3, 5, 7, 10, 15, 20]),
        "weights": weights,
        "filters": filters,
    }


def normalize_weights(weights):
    total = sum(max(v, 0.001) for v in weights.values())
    return {k: max(v, 0.001) / total for k, v in weights.items()}


def mutate_strategy(strategy, features, mutation_rate=0.25):
    child = json.loads(json.dumps(strategy))

    if random.random() < mutation_rate:
        child["hold_days"] = random.choice([1, 3, 5, 7, 10])

    if random.random() < mutation_rate:
        child["top_n"] = random.choice([3, 5, 7, 10, 15, 20])

    for feature in list(child["weights"].keys()):
        if random.random() < mutation_rate:
            child["weights"][feature] *= random.uniform(0.5, 1.7)

    if random.random() < mutation_rate and len(child["weights"]) < len(features):
        available = [f for f in features if f not in child["weights"]]
        if available:
            child["weights"][random.choice(available)] = random.uniform(0.05, 0.5)

    if random.random() < mutation_rate and len(child["weights"]) > 2:
        remove_feature = random.choice(list(child["weights"].keys()))
        del child["weights"][remove_feature]

    child["weights"] = normalize_weights(child["weights"])

    for feature in list(child["filters"].keys()):
        if random.random() < mutation_rate:
            if feature == "volume_ratio":
                child["filters"][feature] = random.choice([0.7, 0.9, 1.0, 1.2, 1.5, 2.0])
            elif feature == "open_to_close_change":
                child["filters"][feature] = random.choice([-8, -5, -3, 0, 2])
            else:
                child["filters"][feature] = random.choice([-10, -5, 0, 2, 5, 8, 10, 12, 15])

    return child


def crossover(parent_a, parent_b, features):
    child = {
        "hold_days": random.choice([parent_a["hold_days"], parent_b["hold_days"]]),
        "top_n": random.choice([parent_a["top_n"], parent_b["top_n"]]),
        "weights": {},
        "filters": {},
    }

    all_weight_features = set(parent_a["weights"]) | set(parent_b["weights"])

    for feature in all_weight_features:
        if feature not in features:
            continue

        if random.random() < 0.5 and feature in parent_a["weights"]:
            child["weights"][feature] = parent_a["weights"][feature]
        elif feature in parent_b["weights"]:
            child["weights"][feature] = parent_b["weights"][feature]

    if len(child["weights"]) < 2:
        return random_strategy(features)

    child["weights"] = normalize_weights(child["weights"])

    all_filter_features = set(parent_a["filters"]) | set(parent_b["filters"])

    for feature in all_filter_features:
        if random.random() < 0.5 and feature in parent_a["filters"]:
            child["filters"][feature] = parent_a["filters"][feature]
        elif feature in parent_b["filters"]:
            child["filters"][feature] = parent_b["filters"][feature]

    return child


def apply_filters(df, filters):
    filtered = df

    for feature, threshold in filters.items():
        if feature not in filtered.columns:
            continue

        values = filtered[feature].fillna(-999)
        filtered = filtered[values >= threshold]

    return filtered


def score_rows(df, weights):
    score = pd.Series(0.0, index=df.index)

    for feature, weight in weights.items():
        if feature not in df.columns:
            continue

        ranked = df[feature].replace([np.inf, -np.inf], np.nan).rank(pct=True).fillna(0)
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


def evaluate_daily_returns(daily_returns):
    if len(daily_returns) < 10:
        return None

    avg_return = daily_returns.mean()
    median_return = daily_returns.median()
    win_rate = (daily_returns > 0).mean() * 100
    std = daily_returns.std()

    sharpe = 0 if std == 0 or pd.isna(std) else avg_return / std

    downside = daily_returns[daily_returns < 0].std()
    sortino = 0 if downside == 0 or pd.isna(downside) else avg_return / downside

    equity = (1 + daily_returns / 100).cumprod()
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
        "active_days": int(len(daily_returns)),
    }


def test_strategy(df, strategy, folds):
    hold_days = strategy["hold_days"]
    return_col = find_return_column(df, hold_days)

    if return_col is None:
        return None

    fold_results = []

    for train_start, train_end, test_start, test_end in folds:
        test = df[(df["date"] >= test_start) & (df["date"] < test_end)]

        if test.empty:
            continue

        picks = select_picks(test, strategy, return_col)

        if picks.empty:
            continue

        daily = picks.groupby("date")["return"].mean()
        metrics = evaluate_daily_returns(daily)

        if metrics is None:
            continue

        baseline = pd.to_numeric(test[return_col], errors="coerce").dropna().mean()

        if pd.isna(baseline):
            continue

        fold_results.append({
            "test_start": str(test_start.date()),
            "test_end": str(test_end.date()),
            "avg_return": metrics["avg_return"],
            "median_return": metrics["median_return"],
            "win_rate": metrics["win_rate"],
            "sharpe": metrics["sharpe"],
            "sortino": metrics["sortino"],
            "max_drawdown": metrics["max_drawdown"],
            "baseline": float(baseline),
            "alpha": metrics["avg_return"] - float(baseline),
            "trades": int(len(picks)),
            "active_days": metrics["active_days"],
        })

    if len(fold_results) < 6:
        return None

    folds_df = pd.DataFrame(fold_results)

    avg_alpha = folds_df["alpha"].mean()
    median_alpha = folds_df["alpha"].median()
    positive_alpha_rate = (folds_df["alpha"] > 0).mean() * 100
    avg_return = folds_df["avg_return"].mean()
    avg_baseline = folds_df["baseline"].mean()
    avg_win_rate = folds_df["win_rate"].mean()
    avg_sharpe = folds_df["sharpe"].mean()
    avg_sortino = folds_df["sortino"].mean()
    worst_drawdown = folds_df["max_drawdown"].min()
    total_trades = folds_df["trades"].sum()

    quality = (
        avg_alpha * 3.0
        + median_alpha * 2.0
        + positive_alpha_rate * 0.04
        + avg_win_rate * 0.02
        + avg_sharpe * 1.5
        + avg_sortino * 0.75
        + worst_drawdown * 0.02
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
        "worst_drawdown": round(worst_drawdown, 4),
        "total_trades": int(total_trades),
        "quality_score": round(quality, 4),
    }


def run_evolution(generations, population_size, elite_size, seed):
    random.seed(seed)
    np.random.seed(seed)

    REPORTS_DIR.mkdir(exist_ok=True)

    df, features = load_data()
    folds = build_folds(df)

    print(f"Walk-forward folds: {len(folds)}")
    print(f"Population size: {population_size}")
    print(f"Generations: {generations}")
    print(f"Elite size: {elite_size}")
    print("Starting evolutionary strategy discovery...\n")

    population = [random_strategy(features) for _ in range(population_size)]

    all_results = []
    best_seen = None
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

        scored.sort(key=lambda x: x[0], reverse=True)
        elites = scored[:elite_size]

        if best_seen is None or elites[0][0] > best_seen[0]:
            best_seen = elites[0]

        elapsed = (time.time() - start_time) / 60

        print(
            f"Generation {generation}/{generations} | "
            f"Best Quality: {elites[0][0]:.4f} | "
            f"Best Alpha: {elites[0][2]['avg_alpha']:.4f}% | "
            f"Positive Alpha: {elites[0][2]['positive_alpha_rate']:.2f}% | "
            f"Elapsed: {elapsed:.1f} min"
        )

        pd.DataFrame(all_results).sort_values(
            "quality_score",
            ascending=False
        ).to_csv(RESULTS_FILE, index=False)

        parents = [item[1] for item in elites]

        next_population = parents.copy()

        while len(next_population) < population_size:
            if random.random() < 0.75 and len(parents) >= 2:
                parent_a, parent_b = random.sample(parents, 2)
                child = crossover(parent_a, parent_b, features)
            else:
                child = random_strategy(features)

            child = mutate_strategy(child, features)
            next_population.append(child)

        population = next_population

    results_df = pd.DataFrame(all_results).sort_values("quality_score", ascending=False)
    results_df.to_csv(RESULTS_FILE, index=False)

    best = results_df.iloc[0].to_dict()

    summary = {
        "generations": generations,
        "population_size": population_size,
        "elite_size": elite_size,
        "total_valid_tests": int(len(results_df)),
        "best_strategy": best,
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))

    print("\nDONE")
    print(f"Results saved: {RESULTS_FILE}")
    print(f"Summary saved: {SUMMARY_FILE}")

    print("\nTOP 10 EVOLVED STRATEGIES")
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
                "worst_drawdown",
                "total_trades",
            ]
        ].head(10).to_string(index=False)
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--generations", type=int, default=40)
    parser.add_argument("--population", type=int, default=500)
    parser.add_argument("--elite", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    run_evolution(
        generations=args.generations,
        population_size=args.population,
        elite_size=args.elite,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()