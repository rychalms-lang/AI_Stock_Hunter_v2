import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DATA_CANDIDATES = [
    Path("performance/historical_training_data.csv"),
    Path("data/historical_training_data_v3_features.csv"),
    Path("data/historical_training_data.csv"),
]

REPORTS_DIR = Path("reports")
RESULTS_FILE = REPORTS_DIR / "v8_portfolio_optimizer_results.csv"
SUMMARY_FILE = REPORTS_DIR / "v8_portfolio_optimizer_summary.json"
EQUITY_FILE = REPORTS_DIR / "v8_portfolio_optimizer_holdout_equity.csv"
MONTHLY_FILE = REPORTS_DIR / "v8_portfolio_optimizer_monthly.csv"
TRADES_FILE = REPORTS_DIR / "v8_portfolio_optimizer_holdout_trades.csv"


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


BASE_V7_FILTERS = [
    {"feature": "relative_strength_rank_daily", "mode": "gte", "threshold": 0.90},
    {"feature": "five_day_change", "mode": "gte", "threshold": 5.0},
]


BASE_V7_SCORE = {
    "momentum_rs_combo_rank_daily": 0.09715610227706029,
    "pre_score_rank_daily": 0.6803264922366499,
    "five_day_change_rank_daily": 0.14646390512185126,
    "relative_strength_rank_daily": 0.07605350036443861,
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


def get_return_col(df, hold_days):
    return find_column(df, RETURN_COLUMNS[hold_days])


def normalize_weights(weights):
    total = sum(max(float(v), 0.001) for v in weights.values())
    return {k: max(float(v), 0.001) / total for k, v in weights.items()}


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
        df["momentum_rs_combo"] = df["five_day_change"] + df["relative_strength"]

    if "volume_ratio" in df.columns and "five_day_change" in df.columns:
        df["volume_momentum_pressure"] = df["volume_ratio"] * df["five_day_change"]

    if "volume_ratio" in df.columns and "relative_strength" in df.columns:
        df["volume_rs_pressure"] = df["volume_ratio"] * df["relative_strength"]

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
                df[f"{feature}_sector_rank"] = df.groupby(["date", "sector"])[feature].rank(pct=True)

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

    print(f"Safe V8 features: {len(safe_features)}")
    print(safe_features)

    for required in ["relative_strength_rank_daily", "five_day_change", "pre_score_rank_daily"]:
        if required not in df.columns:
            raise RuntimeError(f"Missing required V7/V8 feature: {required}")

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
        score += ranked * float(weight)

    return score


def apply_stop_and_target(returns, stop_loss=None, take_profit=None):
    adjusted = returns.copy()

    if stop_loss is not None:
        adjusted = adjusted.clip(lower=-abs(float(stop_loss)))

    if take_profit is not None:
        adjusted = adjusted.clip(upper=abs(float(take_profit)))

    return adjusted


def select_candidates(df, strategy, target_col):
    test = df.copy()

    for rule in strategy["filters"]:
        if rule["feature"] not in test.columns:
            return pd.DataFrame()
        test = apply_filter(test, rule)
        if test.empty:
            return pd.DataFrame()

    test = test.copy()
    test["strategy_score"] = strategy_score(test, strategy["scoring_features"])
    test["raw_return"] = pd.to_numeric(test[target_col], errors="coerce")
    test = test.dropna(subset=["raw_return"])
    test["return"] = apply_stop_and_target(
        test["raw_return"],
        strategy["stop_loss"],
        strategy["take_profit"],
    )

    if "sector" not in test.columns:
        test["sector"] = "Unknown"

    return test


def daily_portfolio_from_candidates(candidates, strategy):
    if candidates.empty:
        return pd.DataFrame()

    max_positions = int(strategy["max_positions"])
    sector_cap = int(strategy["sector_cap"])
    sizing_method = strategy["sizing_method"]
    max_position_weight = float(strategy["max_position_weight"])
    gross_exposure = float(strategy["gross_exposure"])

    rows = []

    for date, group in candidates.groupby("date"):
        group = group.sort_values("strategy_score", ascending=False).copy()

        selected = []
        sector_counts = {}

        for _, row in group.iterrows():
            sector = str(row.get("sector", "Unknown"))

            if sector_counts.get(sector, 0) >= sector_cap:
                continue

            selected.append(row)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

            if len(selected) >= max_positions:
                break

        if not selected:
            continue

        selected_df = pd.DataFrame(selected)

        if sizing_method == "score_weighted":
            base = selected_df["strategy_score"].clip(lower=0.001)
            weights = base / base.sum()

        elif sizing_method == "rank_weighted":
            ranks = np.arange(len(selected_df), 0, -1)
            weights = pd.Series(ranks / ranks.sum(), index=selected_df.index)

        elif sizing_method == "vol_adjusted":
            if "intraday_abs_move" in selected_df.columns:
                risk = pd.to_numeric(selected_df["intraday_abs_move"], errors="coerce").abs().fillna(3.0)
                inv_risk = 1 / risk.clip(lower=1.0)
                weights = inv_risk / inv_risk.sum()
            else:
                weights = pd.Series(1 / len(selected_df), index=selected_df.index)

        else:
            weights = pd.Series(1 / len(selected_df), index=selected_df.index)

        weights = weights.clip(upper=max_position_weight)

        if weights.sum() <= 0:
            weights = pd.Series(1 / len(selected_df), index=selected_df.index)

        weights = weights / weights.sum()
        weights = weights * gross_exposure

        selected_df["weight"] = weights.values
        selected_df["weighted_return"] = selected_df["return"] * selected_df["weight"]
        selected_df["position_count"] = len(selected_df)

        rows.append(selected_df)

    if not rows:
        return pd.DataFrame()

    return pd.concat(rows, ignore_index=True)


def evaluate_portfolio(df, strategy, target_col, return_trades=False):
    candidates = select_candidates(df, strategy, target_col)

    if candidates.empty:
        return (None, None, None) if return_trades else None

    trades = daily_portfolio_from_candidates(candidates, strategy)

    if trades.empty:
        return (None, None, None) if return_trades else None

    daily = trades.groupby("date")["weighted_return"].sum()

    if len(daily) < 10:
        return (None, trades, None) if return_trades else None

    baseline = pd.to_numeric(df[target_col], errors="coerce").dropna().mean()

    if pd.isna(baseline):
        return (None, trades, None) if return_trades else None

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

    metrics = {
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
        "trade_count": int(len(trades)),
        "active_days": int(len(daily)),
        "avg_positions": float(trades.groupby("date")["ticker"].count().mean()),
    }

    if return_trades:
        equity_df = pd.DataFrame({
            "date": daily.index,
            "daily_return": daily.values,
        })
        equity_df["equity"] = (1 + equity_df["daily_return"] / 100).cumprod()
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = ((equity_df["equity"] / equity_df["peak"]) - 1) * 100
        return metrics, trades, equity_df

    return metrics


def test_strategy(df, strategy, folds):
    target_col = get_return_col(df, strategy["hold_days"])

    if target_col is None:
        return None

    fold_metrics = []

    for train_start, train_end, test_start, test_end in folds:
        test = df[(df["date"] >= test_start) & (df["date"] < test_end)]

        if test.empty:
            continue

        metrics = evaluate_portfolio(test, strategy, target_col)

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
    avg_positions = fold_df["avg_positions"].mean()

    risk_penalty = 0.0

    if worst_drawdown < -25:
        risk_penalty += abs(worst_drawdown + 25) * 0.60

    if worst_day < -6:
        risk_penalty += abs(worst_day + 6) * 1.00

    complexity_penalty = (
        len(strategy["filters"]) * 0.30
        + len(strategy["scoring_features"]) * 0.20
    )

    edge_score = (
        avg_alpha * 3.0
        + median_alpha * 2.0
        + positive_alpha_rate * 0.07
        + avg_win_rate * 0.025
        + avg_sharpe * 2.0
        + avg_sortino * 0.85
        + min(total_trades / 1500, 3.0)
        + worst_drawdown * 0.08
        - risk_penalty
        - complexity_penalty
    )

    return {
        "strategy_type": strategy["strategy_type"],
        "hold_days": strategy["hold_days"],
        "max_positions": strategy["max_positions"],
        "sector_cap": strategy["sector_cap"],
        "sizing_method": strategy["sizing_method"],
        "gross_exposure": strategy["gross_exposure"],
        "max_position_weight": strategy["max_position_weight"],
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
        "avg_positions": round(avg_positions, 2),
        "total_trades": int(total_trades),
        "edge_score": round(edge_score, 4),
    }


def build_base_strategy():
    return {
        "strategy_type": "v7_relative_strength_leader_portfolio",
        "hold_days": 10,
        "filters": list(BASE_V7_FILTERS),
        "scoring_features": normalize_weights(BASE_V7_SCORE),
        "stop_loss": 6.0,
        "take_profit": None,
    }


def generate_portfolio_variants():
    base = build_base_strategy()
    variants = []

    max_positions_options = [3, 5, 7, 10]
    sector_cap_options = [1, 2, 3]
    sizing_methods = ["equal_weight", "score_weighted", "rank_weighted", "vol_adjusted"]
    gross_exposure_options = [0.50, 0.75, 1.00]
    max_position_weight_options = [0.20, 0.25, 0.33, 0.50]
    stop_losses = [4, 5, 6, 8, 10]
    take_profits = [None, 12, 15, 20, 25]

    for max_positions in max_positions_options:
        for sector_cap in sector_cap_options:
            for sizing_method in sizing_methods:
                for gross_exposure in gross_exposure_options:
                    for max_position_weight in max_position_weight_options:
                        for stop_loss in stop_losses:
                            for take_profit in take_profits:
                                strategy = dict(base)
                                strategy["max_positions"] = max_positions
                                strategy["sector_cap"] = sector_cap
                                strategy["sizing_method"] = sizing_method
                                strategy["gross_exposure"] = gross_exposure
                                strategy["max_position_weight"] = max_position_weight
                                strategy["stop_loss"] = stop_loss
                                strategy["take_profit"] = take_profit

                                variants.append(strategy)

    return variants


def evaluate_holdout(df, strategy, holdout):
    target_col = get_return_col(df, strategy["hold_days"])

    if target_col is None:
        return None, None, None

    metrics, trades, equity = evaluate_portfolio(
        holdout,
        strategy,
        target_col,
        return_trades=True,
    )

    monthly = None

    if trades is not None and not trades.empty:
        daily = trades.groupby("date")["weighted_return"].sum().reset_index()
        monthly = (
            daily.assign(month=daily["date"].dt.to_period("M").astype(str))
            .groupby("month")["weighted_return"]
            .agg(["mean", "median", "count"])
            .reset_index()
            .rename(columns={
                "mean": "avg_daily_return",
                "median": "median_daily_return",
                "count": "active_days",
            })
        )

    return metrics, trades, equity, monthly


def run_v8(limit=None):
    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    df, features = add_features(df)
    folds, holdout, holdout_start = build_folds(df)

    strategies = generate_portfolio_variants()

    if limit:
        strategies = strategies[:limit]

    print(f"Walk-forward folds: {len(folds)}")
    print(f"Untouched holdout starts: {holdout_start.date()}")
    print(f"Portfolio variants generated: {len(strategies):,}")
    print("Starting V8 portfolio optimization...\n")

    results = []

    for index, strategy in enumerate(strategies, start=1):
        result = test_strategy(df, strategy, folds)

        if result is not None:
            results.append(result)

        if index % 500 == 0:
            print(f"Tested {index:,}/{len(strategies):,} | Valid: {len(results):,}")

            if results:
                pd.DataFrame(results).sort_values(
                    "edge_score",
                    ascending=False,
                ).to_csv(RESULTS_FILE, index=False)

    if not results:
        print("No valid strategies found.")
        return

    results_df = pd.DataFrame(results).sort_values("edge_score", ascending=False)
    results_df.to_csv(RESULTS_FILE, index=False)

    best_row = results_df.iloc[0].to_dict()

    best_strategy = build_base_strategy()
    best_strategy.update({
        "max_positions": int(best_row["max_positions"]),
        "sector_cap": int(best_row["sector_cap"]),
        "sizing_method": best_row["sizing_method"],
        "gross_exposure": float(best_row["gross_exposure"]),
        "max_position_weight": float(best_row["max_position_weight"]),
        "stop_loss": None if pd.isna(best_row["stop_loss"]) else float(best_row["stop_loss"]),
        "take_profit": None if pd.isna(best_row["take_profit"]) else float(best_row["take_profit"]),
    })

    holdout_metrics, trades, equity, monthly = evaluate_holdout(df, best_strategy, holdout)

    if trades is not None:
        trades.to_csv(TRADES_FILE, index=False)

    if equity is not None:
        equity.to_csv(EQUITY_FILE, index=False)

    if monthly is not None:
        monthly.to_csv(MONTHLY_FILE, index=False)

    summary = {
        "portfolio_variants": len(strategies),
        "valid_strategies": int(len(results_df)),
        "holdout_start": str(holdout_start.date()),
        "best_walk_forward_portfolio": best_row,
        "best_strategy": best_strategy,
        "untouched_holdout_result": holdout_metrics,
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))

    print("\nDONE")
    print(f"Results saved: {RESULTS_FILE}")
    print(f"Summary saved: {SUMMARY_FILE}")
    print(f"Equity saved: {EQUITY_FILE}")
    print(f"Monthly saved: {MONTHLY_FILE}")
    print(f"Trades saved: {TRADES_FILE}")

    print("\nTOP 10 V8 PORTFOLIOS")
    print(
        results_df[
            [
                "edge_score",
                "hold_days",
                "max_positions",
                "sector_cap",
                "sizing_method",
                "gross_exposure",
                "max_position_weight",
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
                "avg_positions",
                "total_trades",
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
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_v8(limit=args.limit)


if __name__ == "__main__":
    main()
