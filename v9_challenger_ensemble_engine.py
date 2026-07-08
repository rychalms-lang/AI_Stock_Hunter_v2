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
RESULTS_FILE = REPORTS_DIR / "v9_challenger_ensemble_results.csv"
SUMMARY_FILE = REPORTS_DIR / "v9_challenger_ensemble_summary.json"
MONTHLY_FILE = REPORTS_DIR / "v9_challenger_ensemble_monthly.csv"

RETURN_COLUMNS = {
    10: ["future_10d_return", "future_return_10d", "return_10d"],
}

V8_CHAMPION = {
    "avg_return": 3.0502,
    "alpha": 2.0724,
    "win_rate": 76.0,
    "sharpe": 0.6963,
    "max_drawdown": -13.8081,
    "worst_day": -3.0,
}


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
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper()

    cutoff = df["date"].max() - pd.DateOffset(years=5)
    df = df[df["date"] >= cutoff].copy()

    for col in df.columns:
        if col not in ["date", "ticker", "sector", "regime"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    print(f"Rows loaded: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    return df


def add_features(df):
    df = df.copy()

    if "five_day_change" in df.columns and "twenty_day_change" in df.columns:
        df["momentum_acceleration"] = df["five_day_change"] - (
            df["twenty_day_change"] / 4
        )

    if "five_day_change" in df.columns and "relative_strength" in df.columns:
        df["momentum_rs_combo"] = df["five_day_change"] + df["relative_strength"]

    if "volume_ratio" in df.columns and "five_day_change" in df.columns:
        df["volume_momentum_pressure"] = df["volume_ratio"] * df["five_day_change"]

    if "volume_ratio" in df.columns and "relative_strength" in df.columns:
        df["volume_rs_pressure"] = df["volume_ratio"] * df["relative_strength"]

    if "pre_score" in df.columns and "volume_ratio" in df.columns:
        df["score_volume_combo"] = df["pre_score"] * df["volume_ratio"]

    rank_features = [
        "five_day_change",
        "twenty_day_change",
        "relative_strength",
        "volume_ratio",
        "pre_score",
        "momentum_acceleration",
        "momentum_rs_combo",
        "volume_momentum_pressure",
        "volume_rs_pressure",
        "score_volume_combo",
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
        ]:
            if feature in df.columns:
                df[f"{feature}_sector_rank"] = df.groupby(["date", "sector"])[
                    feature
                ].rank(pct=True)

    return df


def get_return_col(df):
    col = find_column(df, RETURN_COLUMNS[10])
    if col is None:
        raise ValueError("No 10-day return column found.")
    return col


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
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def model_scores(df):
    scores = pd.DataFrame(index=df.index)

    scores["momentum_model"] = (
        safe_series(df, "five_day_change_rank_daily") * 0.45
        + safe_series(df, "twenty_day_change_rank_daily") * 0.35
        + safe_series(df, "momentum_acceleration_rank_daily") * 0.20
    )

    scores["relative_strength_model"] = (
        safe_series(df, "relative_strength_rank_daily") * 0.60
        + safe_series(df, "momentum_rs_combo_rank_daily") * 0.25
        + safe_series(df, "relative_strength_sector_rank") * 0.15
    )

    scores["volume_breakout_model"] = (
        safe_series(df, "volume_ratio_rank_daily") * 0.40
        + safe_series(df, "volume_momentum_pressure_rank_daily") * 0.35
        + safe_series(df, "volume_rs_pressure_rank_daily") * 0.25
    )

    scores["sector_leader_model"] = (
        safe_series(df, "relative_strength_sector_rank") * 0.40
        + safe_series(df, "five_day_change_sector_rank") * 0.35
        + safe_series(df, "pre_score_sector_rank") * 0.25
    )

    scores["quality_model"] = (
        safe_series(df, "pre_score_rank_daily") * 0.65
        + safe_series(df, "score_volume_combo_rank_daily") * 0.20
        + safe_series(df, "volume_ratio_rank_daily") * 0.15
    )

    return scores.fillna(0)


def random_strategy():
    model_names = [
        "momentum_model",
        "relative_strength_model",
        "volume_breakout_model",
        "sector_leader_model",
        "quality_model",
    ]

    raw = np.random.dirichlet(np.ones(len(model_names)))

    weights = {
        model: float(weight)
        for model, weight in zip(model_names, raw)
    }

    return {
        "hold_days": 10,
        "top_n": random.choice([5, 7, 10]),
        "max_positions": random.choice([5, 7, 10]),
        "sector_cap": random.choice([2, 3]),
        "gross_exposure": random.choice([0.50, 0.65, 0.75, 0.90]),
        "max_position_weight": random.choice([0.15, 0.20, 0.25]),
        "stop_loss": random.choice([3, 4, 5, 6]),
        "take_profit": random.choice([15, 20, 25, None]),
        "min_consensus": random.choice([0.55, 0.60, 0.65, 0.70]),
        "min_rs_rank": random.choice([0.80, 0.85, 0.90]),
        "min_five_day": random.choice([0, 3, 5, 8]),
        "model_weights": weights,
    }


def mutate(strategy):
    child = json.loads(json.dumps(strategy))

    if random.random() < 0.20:
        child["max_positions"] = random.choice([5, 7, 10])

    if random.random() < 0.20:
        child["sector_cap"] = random.choice([2, 3])

    if random.random() < 0.20:
        child["gross_exposure"] = random.choice([0.50, 0.65, 0.75, 0.90])

    if random.random() < 0.20:
        child["max_position_weight"] = random.choice([0.15, 0.20, 0.25])

    if random.random() < 0.20:
        child["stop_loss"] = random.choice([3, 4, 5, 6])

    if random.random() < 0.15:
        child["take_profit"] = random.choice([15, 20, 25, None])

    if random.random() < 0.25:
        child["min_consensus"] = random.choice([0.55, 0.60, 0.65, 0.70])

    if random.random() < 0.25:
        child["min_rs_rank"] = random.choice([0.80, 0.85, 0.90])

    if random.random() < 0.25:
        child["min_five_day"] = random.choice([0, 3, 5, 8])

    for key in child["model_weights"]:
        if random.random() < 0.35:
            child["model_weights"][key] *= random.uniform(0.5, 1.7)

    total = sum(child["model_weights"].values())
    child["model_weights"] = {
        key: value / total for key, value in child["model_weights"].items()
    }

    return child


def apply_stop_take_profit(returns, stop_loss, take_profit):
    adjusted = returns.copy()

    if stop_loss is not None:
        adjusted = adjusted.clip(lower=-abs(stop_loss))

    if take_profit is not None:
        adjusted = adjusted.clip(upper=abs(take_profit))

    return adjusted


def select_picks(df, strategy, return_col):
    test = df.copy()

    test = test[
        (safe_series(test, "relative_strength_rank_daily") >= strategy["min_rs_rank"])
        & (safe_series(test, "five_day_change") >= strategy["min_five_day"])
    ].copy()

    if test.empty:
        return pd.DataFrame()

    scores = model_scores(test)

    consensus = pd.Series(0.0, index=test.index)

    for model, weight in strategy["model_weights"].items():
        if model in scores.columns:
            consensus += scores[model] * weight

    test["consensus_score"] = consensus

    test = test[test["consensus_score"] >= strategy["min_consensus"]].copy()

    if test.empty:
        return pd.DataFrame()

    selected = []

    for date, group in test.sort_values(
        ["date", "consensus_score"],
        ascending=[True, False],
    ).groupby("date"):
        sector_counts = {}
        day_picks = []

        for _, row in group.iterrows():
            sector = (
                row["sector"]
                if "sector" in row and pd.notna(row["sector"])
                else "Unknown"
            )

            if sector_counts.get(sector, 0) >= strategy["sector_cap"]:
                continue

            day_picks.append(row)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

            if len(day_picks) >= strategy["max_positions"]:
                break

        if day_picks:
            selected.append(pd.DataFrame(day_picks))

    if not selected:
        return pd.DataFrame()

    picks = pd.concat(selected, ignore_index=True)
    picks["raw_return"] = pd.to_numeric(picks[return_col], errors="coerce")
    picks = picks.dropna(subset=["raw_return"])

    picks["return"] = apply_stop_take_profit(
        picks["raw_return"],
        strategy["stop_loss"],
        strategy["take_profit"],
    )

    return picks


def portfolio_daily_returns(picks, strategy):
    if picks.empty:
        return pd.Series(dtype=float)

    daily_returns = {}

    for date, group in picks.groupby("date"):
        group = group.copy()

        score = pd.to_numeric(group["consensus_score"], errors="coerce").fillna(0)

        if score.sum() <= 0:
            weights = pd.Series(1 / len(group), index=group.index)
        else:
            weights = score / score.sum()

        weights = weights.clip(upper=strategy["max_position_weight"])
        weights = weights / weights.sum()
        weights = weights * strategy["gross_exposure"]

        daily_returns[date] = (group["return"] * weights).sum()

    return pd.Series(daily_returns).sort_index()


def evaluate_period(df, strategy, return_col):
    picks = select_picks(df, strategy, return_col)

    if picks.empty:
        return None

    daily = portfolio_daily_returns(picks, strategy)

    if len(daily) < 10:
        return None

    baseline = pd.to_numeric(df[return_col], errors="coerce").dropna().mean()

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

    return {
        "avg_return": float(avg_return),
        "median_return": float(median_return),
        "baseline": float(baseline),
        "alpha": float(avg_return - baseline),
        "win_rate": float(win_rate),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(drawdown.min()),
        "worst_day": float(daily.min()),
        "best_day": float(daily.max()),
        "trade_count": int(len(picks)),
        "active_days": int(len(daily)),
    }


def test_strategy(df, strategy, folds):
    return_col = get_return_col(df)

    fold_metrics = []

    for _, _, test_start, test_end in folds:
        test = df[(df["date"] >= test_start) & (df["date"] < test_end)]

        metrics = evaluate_period(test, strategy, return_col)

        if metrics is not None:
            fold_metrics.append(metrics)

    if len(fold_metrics) < 6:
        return None

    fold_df = pd.DataFrame(fold_metrics)

    total_trades = fold_df["trade_count"].sum()

    if total_trades < 150:
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

    risk_penalty = 0

    if worst_drawdown < -15:
        risk_penalty += abs(worst_drawdown + 15) * 1.4

    if worst_day < -4:
        risk_penalty += abs(worst_day + 4) * 2.0

    edge_score = (
        avg_alpha * 4.0
        + median_alpha * 2.5
        + positive_alpha_rate * 0.08
        + avg_win_rate * 0.04
        + avg_sharpe * 4.0
        + avg_sortino * 1.2
        + min(total_trades / 1000, 4.0)
        + worst_drawdown * 0.20
        - risk_penalty
    )

    return {
        "edge_score": round(edge_score, 4),
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
        "strategy": json.dumps(strategy),
    }


def champion_score(metrics):
    score = (
        metrics["alpha"] * 4.0
        + metrics["win_rate"] * 0.04
        + metrics["sharpe"] * 4.0
        + metrics["max_drawdown"] * 0.20
    )
    return score


def compare_to_v8(holdout_metrics):
    if holdout_metrics is None:
        return False

    return (
        holdout_metrics["alpha"] > V8_CHAMPION["alpha"]
        and holdout_metrics["win_rate"] >= V8_CHAMPION["win_rate"]
        and holdout_metrics["max_drawdown"] >= V8_CHAMPION["max_drawdown"]
        and holdout_metrics["worst_day"] >= V8_CHAMPION["worst_day"]
    )


def monthly_breakdown(picks, strategy):
    daily = portfolio_daily_returns(picks, strategy)

    if daily.empty:
        return pd.DataFrame()

    return (
        daily.reset_index()
        .rename(columns={"index": "date", 0: "daily_return"})
        .assign(month=lambda x: x["date"].dt.to_period("M").astype(str))
        .groupby("month")["daily_return"]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(
            columns={
                "mean": "avg_daily_return",
                "median": "median_daily_return",
                "count": "active_days",
            }
        )
    )


def run_v9(strategies, generations, population, elite, seed):
    random.seed(seed)
    np.random.seed(seed)

    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    df = add_features(df)
    folds, holdout, holdout_start = build_folds(df)
    return_col = get_return_col(df)

    print(f"Walk-forward folds: {len(folds)}")
    print(f"Untouched holdout starts: {holdout_start.date()}")
    print("Champion to beat: V8")
    print(V8_CHAMPION)
    print()

    results = []
    pool = []

    print("Stage 1: searching V9 ensemble challengers")

    for i in range(1, strategies + 1):
        strategy = random_strategy()
        result = test_strategy(df, strategy, folds)

        if result is not None:
            results.append(result)
            pool.append((result["edge_score"], strategy, result))

        if i % 1000 == 0:
            print(f"Tested {i:,}/{strategies:,} | Valid: {len(results):,}")

            if results:
                pd.DataFrame(results).sort_values(
                    "edge_score",
                    ascending=False,
                ).to_csv(RESULTS_FILE, index=False)

    if not pool:
        print("No valid challengers found. V8 remains champion.")
        return

    pool.sort(key=lambda item: item[0], reverse=True)
    parents = [item[1] for item in pool[:population]]

    print("\nStage 2: evolving best challengers")

    for generation in range(1, generations + 1):
        candidates = parents.copy()

        while len(candidates) < population:
            parent = random.choice(parents[:elite])
            candidates.append(mutate(parent))

        scored = []

        for strategy in candidates:
            result = test_strategy(df, strategy, folds)

            if result is not None:
                results.append(result)
                scored.append((result["edge_score"], strategy, result))

        if scored:
            scored.sort(key=lambda item: item[0], reverse=True)
            parents = [item[1] for item in scored[:population]]
            best = scored[0][2]

            print(
                f"Generation {generation}/{generations} | "
                f"Edge: {best['edge_score']} | "
                f"Alpha: {best['avg_alpha']}% | "
                f"Drawdown: {best['worst_drawdown']}% | "
                f"Win: {best['avg_win_rate']}%"
            )

        pd.DataFrame(results).sort_values(
            "edge_score",
            ascending=False,
        ).to_csv(RESULTS_FILE, index=False)

    results_df = pd.DataFrame(results).sort_values("edge_score", ascending=False)
    results_df.to_csv(RESULTS_FILE, index=False)

    best_row = results_df.iloc[0].to_dict()
    best_strategy = json.loads(best_row["strategy"])

    holdout_metrics = evaluate_period(holdout, best_strategy, return_col)
    holdout_picks = select_picks(holdout, best_strategy, return_col)
    monthly = monthly_breakdown(holdout_picks, best_strategy)
    monthly.to_csv(MONTHLY_FILE, index=False)

    v9_beats_v8 = compare_to_v8(holdout_metrics)

    summary = {
        "champion": "V8",
        "challenger": "V9 Ensemble",
        "v9_beats_v8": v9_beats_v8,
        "decision": "PROMOTE V9" if v9_beats_v8 else "REJECT V9 - KEEP V8",
        "v8_champion_holdout": V8_CHAMPION,
        "v9_best_walk_forward": best_row,
        "v9_holdout": holdout_metrics,
        "v9_strategy": best_strategy,
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))

    print("\nDONE")
    print(f"Results saved: {RESULTS_FILE}")
    print(f"Summary saved: {SUMMARY_FILE}")
    print(f"Monthly saved: {MONTHLY_FILE}")

    print("\nV9 HOLDOUT")
    print(holdout_metrics)

    print("\nV8 CHAMPION")
    print(V8_CHAMPION)

    print("\nDECISION")
    print(summary["decision"])

    print("\nMONTHLY HOLDOUT")
    print(monthly.to_string(index=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", type=int, default=20000)
    parser.add_argument("--generations", type=int, default=12)
    parser.add_argument("--population", type=int, default=600)
    parser.add_argument("--elite", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    run_v9(
        strategies=args.strategies,
        generations=args.generations,
        population=args.population,
        elite=args.elite,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()