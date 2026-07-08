import argparse
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd


DATA_CANDIDATES = [
    Path("performance/historical_training_data.csv"),
    Path("data/historical_training_data_v3_features.csv"),
    Path("data/historical_training_data.csv"),
]

REPORTS_DIR = Path("reports")
RESULTS_FILE = REPORTS_DIR / "v7_intelligent_strategy_results.csv"
SUMMARY_FILE = REPORTS_DIR / "v7_intelligent_strategy_summary.json"
MONTHLY_FILE = REPORTS_DIR / "v7_intelligent_strategy_monthly_holdout.csv"


RETURN_COLUMNS = {
    1: ["future_1d_return", "future_return_1d", "return_1d"],
    3: ["future_3d_return", "future_return_3d", "return_3d"],
    5: ["future_5d_return", "future_return_5d", "return_5d"],
    7: ["future_7d_return", "future_return_7d", "return_7d"],
    10: ["future_10d_return", "future_return_10d", "return_10d"],
}


BLOCKED_KEYWORDS = [
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
    "expected",
    "avg_return",
    "hold_period",
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


def get_return_col(df, hold_days):
    return find_column(df, RETURN_COLUMNS[hold_days])


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


def add_features(df):
    df = df.copy()

    base_cols = [
        "five_day_change",
        "twenty_day_change",
        "relative_strength",
        "volume_ratio",
        "open_to_close_change",
        "pre_score",
        "market_regime_score",
    ]

    for col in base_cols:
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

    rank_features = [
        "five_day_change",
        "twenty_day_change",
        "relative_strength",
        "volume_ratio",
        "pre_score",
        "market_regime_score",
        "momentum_acceleration",
        "momentum_rs_combo",
        "volume_momentum_pressure",
        "volume_rs_pressure",
        "score_volume_combo",
        "intraday_strength",
    ]

    for feature in rank_features:
        if feature in df.columns:
            df[f"{feature}_rank_daily"] = df.groupby("date")[feature].rank(pct=True)

    if "sector" in df.columns:
        for feature in [
            "five_day_change",
            "twenty_day_change",
            "relative_strength",
            "volume_ratio",
            "pre_score",
            "momentum_rs_combo",
            "volume_momentum_pressure",
            "volume_rs_pressure",
        ]:
            if feature in df.columns:
                df[f"{feature}_sector_rank"] = df.groupby(["date", "sector"])[
                    feature
                ].rank(pct=True)

    safe_features = []

    for col in df.columns:
        name = col.lower()

        if col in ["date", "ticker", "sector", "regime"]:
            continue

        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        if df[col].notna().sum() < 1000:
            continue

        if any(word in name for word in BLOCKED_KEYWORDS):
            continue

        safe_features.append(col)

    print(f"Safe V7 features: {len(safe_features)}")
    print(safe_features)

    return df, safe_features


def build_folds(df):
    max_date = df["date"].max()
    holdout_start = max_date - pd.DateOffset(months=6)

    trainable = df[df["date"] < holdout_start].copy()
    holdout = df[df["date"] >= holdout_start].copy()

    folds = []
    fold_start = trainable["date"].min() + pd.DateOffset(years=2)

    while fold_start < trainable["date"].max():
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


def safe_series(df, col):
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)

    return pd.to_numeric(df[col], errors="coerce")


def normalize_weights(weights):
    total = sum(max(value, 0.001) for value in weights.values())

    return {
        feature: max(value, 0.001) / total
        for feature, value in weights.items()
    }


def apply_filter(df, rule):
    values = safe_series(df, rule["feature"])

    if rule["mode"] == "gte":
        return df[values >= rule["threshold"]]

    if rule["mode"] == "lte":
        return df[values <= rule["threshold"]]

    return df


def strategy_score(df, scoring_features):
    score = pd.Series(0.0, index=df.index)

    for feature, weight in scoring_features.items():
        if feature not in df.columns:
            continue

        values = safe_series(df, feature)
        ranked = values.replace([np.inf, -np.inf], np.nan).rank(pct=True).fillna(0)
        score += ranked * weight

    return score


def apply_risk_controls(returns, stop_loss, take_profit):
    adjusted = returns.copy()

    if stop_loss is not None:
        adjusted = adjusted.clip(lower=-abs(stop_loss))

    if take_profit is not None:
        adjusted = adjusted.clip(upper=abs(take_profit))

    return adjusted


def select_picks(df, strategy, target_col):
    test = df.copy()

    for rule in strategy["filters"]:
        if rule["feature"] not in test.columns:
            return pd.DataFrame()

        test = apply_filter(test, rule)

        if test.empty:
            return pd.DataFrame()

    test = test.copy()
    test["strategy_score"] = strategy_score(test, strategy["scoring_features"])

    picks = (
        test.sort_values(["date", "strategy_score"], ascending=[True, False])
        .groupby("date")
        .head(strategy["top_n"])
        .copy()
    )

    picks["raw_return"] = pd.to_numeric(picks[target_col], errors="coerce")
    picks = picks.dropna(subset=["raw_return"])

    picks["return"] = apply_risk_controls(
        picks["raw_return"],
        strategy["stop_loss"],
        strategy["take_profit"],
    )

    return picks


def evaluate_period(df, strategy, target_col):
    picks = select_picks(df, strategy, target_col)

    if picks.empty:
        return None

    daily = picks.groupby("date")["return"].mean()

    if len(daily) < 10:
        return None

    baseline = pd.to_numeric(df[target_col], errors="coerce").dropna().mean()

    if pd.isna(baseline):
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
    max_drawdown = ((equity / peak) - 1).min() * 100

    return {
        "avg_return": float(avg_return),
        "median_return": float(median_return),
        "baseline": float(baseline),
        "alpha": float(avg_return - baseline),
        "win_rate": float(win_rate),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_drawdown),
        "worst_day": float(daily.min()),
        "best_day": float(daily.max()),
        "trade_count": int(len(picks)),
        "active_days": int(len(daily)),
    }


def test_strategy(df, strategy, folds):
    target_col = get_return_col(df, strategy["hold_days"])

    if target_col is None:
        return None

    fold_metrics = []

    for train_start, train_end, test_start, test_end in folds:
        test = df[(df["date"] >= test_start) & (df["date"] < test_end)]

        if test.empty:
            continue

        metrics = evaluate_period(test, strategy, target_col)

        if metrics is not None:
            fold_metrics.append(metrics)

    if len(fold_metrics) < 6:
        return None

    fold_df = pd.DataFrame(fold_metrics)

    total_trades = fold_df["trade_count"].sum()

    if total_trades < 100:
        return None

    avg_alpha = fold_df["alpha"].mean()
    median_alpha = fold_df["alpha"].median()
    positive_alpha_rate = (fold_df["alpha"] > 0).mean() * 100
    avg_return = fold_df["avg_return"].mean()
    avg_baseline = fold_df["baseline"].mean()
    avg_win_rate = fold_df["win_rate"].mean()
    avg_sharpe = fold_df["sharpe"].mean()
    avg_sortino = fold_df["sortino"].mean()
    worst_drawdown = fold_df["max_drawdown"].min()
    worst_day = fold_df["worst_day"].min()

    complexity_penalty = (
        len(strategy["filters"]) * 0.35
        + len(strategy["scoring_features"]) * 0.25
    )

    risk_penalty = 0

    if worst_drawdown < -35:
        risk_penalty += abs(worst_drawdown + 35) * 0.45

    if worst_day < -10:
        risk_penalty += abs(worst_day + 10) * 0.80

    edge_score = (
        avg_alpha * 3.0
        + median_alpha * 2.0
        + positive_alpha_rate * 0.07
        + avg_win_rate * 0.025
        + avg_sharpe * 2.0
        + avg_sortino * 0.85
        + min(total_trades / 1000, 3.0)
        + worst_drawdown * 0.08
        - complexity_penalty
        - risk_penalty
    )

    return {
        "strategy_type": strategy["strategy_type"],
        "hold_days": strategy["hold_days"],
        "top_n": strategy["top_n"],
        "stop_loss": strategy["stop_loss"],
        "take_profit": strategy["take_profit"],
        "filters": json.dumps(strategy["filters"]),
        "scoring_features": json.dumps(strategy["scoring_features"]),
        "feature_count": len(strategy["scoring_features"]),
        "filter_count": len(strategy["filters"]),
        "folds": int(len(fold_df)),
        "avg_oos_return": round(avg_return, 4),
        "avg_baseline_return": round(avg_baseline, 4),
        "avg_alpha": round(avg_alpha, 4),
        "median_alpha": round(median_alpha, 4),
        "positive_alpha_rate": round(positive_alpha_rate, 2),
        "avg_win_rate": round(avg_win_rate, 2),
        "avg_sharpe": round(avg_sharpe, 4),
        "avg_sortino": round(avg_sortino, 4),
        "worst_drawdown": round(worst_drawdown, 4),
        "worst_day": round(worst_day, 4),
        "total_trades": int(total_trades),
        "edge_score": round(edge_score, 4),
    }


def random_choice_existing(features, candidates, minimum=1):
    usable = [feature for feature in candidates if feature in features]

    if len(usable) < minimum:
        return []

    return usable


def random_strategy(features):
    strategy_type = random.choice(
        [
            "momentum_breakout",
            "relative_strength_leader",
            "volume_confirmed_momentum",
            "sector_relative_leader",
            "pullback_to_strength",
        ]
    )

    hold_days = random.choices(
        [3, 5, 7, 10],
        weights=[0.15, 0.30, 0.20, 0.35],
    )[0]

    top_n = random.choices(
        [3, 5, 7, 10],
        weights=[0.20, 0.35, 0.25, 0.20],
    )[0]

    stop_loss = random.choices(
        [None, 12, 10, 8, 6],
        weights=[0.15, 0.15, 0.25, 0.25, 0.20],
    )[0]

    take_profit = random.choices(
        [None, 15, 20, 25],
        weights=[0.35, 0.20, 0.25, 0.20],
    )[0]

    filters = []
    scoring_features = {}

    if strategy_type == "momentum_breakout":
        if "five_day_change" in features:
            filters.append({
                "feature": "five_day_change",
                "mode": "gte",
                "threshold": random.choice([3, 5, 8, 10, 12]),
            })

        if "relative_strength" in features:
            filters.append({
                "feature": "relative_strength",
                "mode": "gte",
                "threshold": random.choice([3, 5, 8, 10, 12]),
            })

        if "volume_ratio" in features:
            filters.append({
                "feature": "volume_ratio",
                "mode": "gte",
                "threshold": random.choice([1.0, 1.2, 1.5, 2.0]),
            })

        scoring_pool = random_choice_existing(
            features,
            [
                "relative_strength_rank_daily",
                "five_day_change_rank_daily",
                "twenty_day_change_rank_daily",
                "volume_ratio_rank_daily",
                "pre_score_rank_daily",
            ],
            minimum=2,
        )

    elif strategy_type == "relative_strength_leader":
        if "relative_strength_rank_daily" in features:
            filters.append({
                "feature": "relative_strength_rank_daily",
                "mode": "gte",
                "threshold": random.choice([0.6, 0.7, 0.8, 0.9]),
            })

        if "five_day_change" in features:
            filters.append({
                "feature": "five_day_change",
                "mode": "gte",
                "threshold": random.choice([0, 2, 5, 8]),
            })

        scoring_pool = random_choice_existing(
            features,
            [
                "relative_strength_rank_daily",
                "relative_strength_sector_rank",
                "momentum_rs_combo_rank_daily",
                "five_day_change_rank_daily",
                "pre_score_rank_daily",
            ],
            minimum=2,
        )

    elif strategy_type == "volume_confirmed_momentum":
        if "volume_ratio" in features:
            filters.append({
                "feature": "volume_ratio",
                "mode": "gte",
                "threshold": random.choice([1.2, 1.5, 2.0]),
            })

        if "volume_momentum_pressure_rank_daily" in features:
            filters.append({
                "feature": "volume_momentum_pressure_rank_daily",
                "mode": "gte",
                "threshold": random.choice([0.6, 0.7, 0.8]),
            })

        scoring_pool = random_choice_existing(
            features,
            [
                "volume_momentum_pressure_rank_daily",
                "volume_rs_pressure_rank_daily",
                "volume_ratio_rank_daily",
                "five_day_change_rank_daily",
                "relative_strength_rank_daily",
            ],
            minimum=2,
        )

    elif strategy_type == "sector_relative_leader":
        if "relative_strength_sector_rank" in features:
            filters.append({
                "feature": "relative_strength_sector_rank",
                "mode": "gte",
                "threshold": random.choice([0.6, 0.7, 0.8, 0.9]),
            })

        if "five_day_change_sector_rank" in features:
            filters.append({
                "feature": "five_day_change_sector_rank",
                "mode": "gte",
                "threshold": random.choice([0.6, 0.7, 0.8]),
            })

        scoring_pool = random_choice_existing(
            features,
            [
                "relative_strength_sector_rank",
                "five_day_change_sector_rank",
                "volume_ratio_sector_rank",
                "pre_score_sector_rank",
                "relative_strength_rank_daily",
            ],
            minimum=2,
        )

    else:
        if "relative_strength" in features:
            filters.append({
                "feature": "relative_strength",
                "mode": "gte",
                "threshold": random.choice([5, 8, 10, 12]),
            })

        if "five_day_change" in features:
            filters.append({
                "feature": "five_day_change",
                "mode": "lte",
                "threshold": random.choice([0, 2, 5]),
            })

        if "volume_ratio" in features:
            filters.append({
                "feature": "volume_ratio",
                "mode": "gte",
                "threshold": random.choice([0.8, 1.0, 1.2]),
            })

        scoring_pool = random_choice_existing(
            features,
            [
                "relative_strength_rank_daily",
                "pre_score_rank_daily",
                "volume_ratio_rank_daily",
                "momentum_rs_combo_rank_daily",
            ],
            minimum=2,
        )

    if len(scoring_pool) < 2:
        fallback = [
            feature
            for feature in [
                "relative_strength_rank_daily",
                "five_day_change_rank_daily",
                "volume_ratio_rank_daily",
                "pre_score_rank_daily",
                "relative_strength",
                "five_day_change",
                "volume_ratio",
                "pre_score",
            ]
            if feature in features
        ]

        scoring_pool = fallback[:4]

    selected_count = min(len(scoring_pool), random.choice([2, 3, 4, 5]))
    selected = random.sample(scoring_pool, selected_count)

    raw_weights = np.random.dirichlet(np.ones(len(selected)))

    scoring_features = {
        feature: float(weight)
        for feature, weight in zip(selected, raw_weights)
    }

    return {
        "strategy_type": strategy_type,
        "hold_days": hold_days,
        "top_n": top_n,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "filters": filters,
        "scoring_features": normalize_weights(scoring_features),
    }


def mutate(strategy, features):
    child = json.loads(json.dumps(strategy))

    if random.random() < 0.15:
        child["hold_days"] = random.choice([3, 5, 7, 10])

    if random.random() < 0.15:
        child["top_n"] = random.choice([3, 5, 7, 10])

    if random.random() < 0.20:
        child["stop_loss"] = random.choice([None, 12, 10, 8, 6])

    if random.random() < 0.15:
        child["take_profit"] = random.choice([None, 15, 20, 25])

    for rule in child["filters"]:
        if random.random() < 0.25:
            if "rank" in rule["feature"]:
                rule["threshold"] = random.choice([0.55, 0.6, 0.7, 0.8, 0.9])
            elif rule["feature"] == "volume_ratio":
                rule["threshold"] = random.choice([0.9, 1.0, 1.2, 1.5, 2.0])
            else:
                rule["threshold"] = random.choice([-5, 0, 2, 5, 8, 10, 12, 15])

    for feature in list(child["scoring_features"].keys()):
        if random.random() < 0.30:
            child["scoring_features"][feature] *= random.uniform(0.5, 1.6)

    if random.random() < 0.20 and len(child["scoring_features"]) > 2:
        remove = random.choice(list(child["scoring_features"].keys()))
        del child["scoring_features"][remove]

    child["scoring_features"] = normalize_weights(child["scoring_features"])

    return child


def run_v7(strategies, generations, population, elite, seed):
    random.seed(seed)
    np.random.seed(seed)

    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    df, features = add_features(df)
    folds, holdout, holdout_start = build_folds(df)

    print(f"Walk-forward folds: {len(folds)}")
    print(f"Untouched holdout starts: {holdout_start.date()}")
    print(f"Initial random strategies: {strategies:,}")
    print(f"Evolution generations: {generations}")
    print(f"Population: {population}")
    print(f"Elite: {elite}\n")

    all_results = []
    candidate_pool = []

    print("Stage 1: intelligent random search")

    for i in range(1, strategies + 1):
        strategy = random_strategy(features)
        result = test_strategy(df, strategy, folds)

        if result is not None:
            all_results.append(result)
            candidate_pool.append((result["edge_score"], strategy, result))

        if i % 1000 == 0:
            print(f"Tested {i:,}/{strategies:,} | Valid: {len(all_results):,}")

            if all_results:
                pd.DataFrame(all_results).sort_values(
                    "edge_score",
                    ascending=False,
                ).to_csv(RESULTS_FILE, index=False)

    if not candidate_pool:
        print("No valid strategies found.")
        return

    candidate_pool.sort(key=lambda item: item[0], reverse=True)
    parents = [item[1] for item in candidate_pool[:population]]

    print("\nStage 2: evolving top strategies")

    for generation in range(1, generations + 1):
        evolved = []

        for parent in parents:
            evolved.append(parent)

        while len(evolved) < population:
            parent = random.choice(parents[:elite])
            evolved.append(mutate(parent, features))

        scored = []

        for strategy in evolved:
            result = test_strategy(df, strategy, folds)

            if result is not None:
                all_results.append(result)
                scored.append((result["edge_score"], strategy, result))

        if not scored:
            continue

        scored.sort(key=lambda item: item[0], reverse=True)
        parents = [item[1] for item in scored[:population]]

        best = scored[0][2]

        print(
            f"Generation {generation}/{generations} | "
            f"Edge: {best['edge_score']:.4f} | "
            f"Alpha: {best['avg_alpha']:.4f}% | "
            f"Drawdown: {best['worst_drawdown']:.2f}% | "
            f"Win: {best['avg_win_rate']:.2f}%"
        )

        pd.DataFrame(all_results).sort_values(
            "edge_score",
            ascending=False,
        ).to_csv(RESULTS_FILE, index=False)

    results_df = pd.DataFrame(all_results).sort_values(
        "edge_score",
        ascending=False,
    )

    results_df.to_csv(RESULTS_FILE, index=False)

    best_row = results_df.iloc[0].to_dict()

    best_strategy = {
        "strategy_type": best_row["strategy_type"],
        "hold_days": int(best_row["hold_days"]),
        "top_n": int(best_row["top_n"]),
        "stop_loss": None if pd.isna(best_row["stop_loss"]) else best_row["stop_loss"],
        "take_profit": None if pd.isna(best_row["take_profit"]) else best_row["take_profit"],
        "filters": json.loads(best_row["filters"]),
        "scoring_features": json.loads(best_row["scoring_features"]),
    }

    target_col = get_return_col(df, best_strategy["hold_days"])
    holdout_metrics = evaluate_period(holdout, best_strategy, target_col)
    holdout_picks = select_picks(holdout, best_strategy, target_col)

    monthly = None

    if not holdout_picks.empty:
        monthly = (
            holdout_picks.assign(month=holdout_picks["date"].dt.to_period("M").astype(str))
            .groupby("month")["return"]
            .agg(["mean", "median", "count"])
            .reset_index()
            .rename(columns={
                "mean": "avg_return",
                "median": "median_return",
                "count": "trades",
            })
        )

        monthly.to_csv(MONTHLY_FILE, index=False)

    summary = {
        "random_strategies": strategies,
        "generations": generations,
        "population": population,
        "elite": elite,
        "valid_tests": int(len(results_df)),
        "holdout_start": str(holdout_start.date()),
        "best_walk_forward_strategy": best_row,
        "untouched_holdout_result": holdout_metrics,
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))

    print("\nDONE")
    print(f"Results saved: {RESULTS_FILE}")
    print(f"Summary saved: {SUMMARY_FILE}")
    print(f"Monthly holdout saved: {MONTHLY_FILE}")

    print("\nTOP 10 V7 STRATEGIES")
    print(
        results_df[
            [
                "edge_score",
                "strategy_type",
                "hold_days",
                "top_n",
                "stop_loss",
                "take_profit",
                "avg_oos_return",
                "avg_baseline_return",
                "avg_alpha",
                "positive_alpha_rate",
                "avg_win_rate",
                "avg_sharpe",
                "worst_drawdown",
                "worst_day",
                "total_trades",
                "feature_count",
                "filter_count",
            ]
        ].head(10).to_string(index=False)
    )

    print("\nUNTOUCHED HOLDOUT RESULT")
    print(holdout_metrics)

    if monthly is not None:
        print("\nMONTHLY HOLDOUT")
        print(monthly.to_string(index=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", type=int, default=15000)
    parser.add_argument("--generations", type=int, default=10)
    parser.add_argument("--population", type=int, default=500)
    parser.add_argument("--elite", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    run_v7(
        strategies=args.strategies,
        generations=args.generations,
        population=args.population,
        elite=args.elite,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()