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
SUMMARY_FILE = REPORTS_DIR / "compare_v2_vs_v8_summary.json"
MONTHLY_FILE = REPORTS_DIR / "compare_v2_vs_v8_monthly.csv"


RETURN_COLUMNS = {
    10: ["future_10d_return", "future_return_10d", "return_10d"],
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
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except Exception:
                pass

    print(f"Rows loaded: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    return df


def add_features(df):
    df = df.copy()

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
            "relative_strength",
            "volume_ratio",
            "pre_score",
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


def holdout_data(df):
    holdout_start = df["date"].max() - pd.DateOffset(months=6)
    return df[df["date"] >= holdout_start].copy(), holdout_start


def safe_series(df, col):
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def apply_stop_take_profit(returns, stop_loss=None, take_profit=None):
    adjusted = returns.copy()

    if stop_loss is not None:
        adjusted = adjusted.clip(lower=-abs(stop_loss))

    if take_profit is not None:
        adjusted = adjusted.clip(upper=abs(take_profit))

    return adjusted


def evaluate_daily_returns(daily, baseline):
    if daily.empty:
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
        "avg_return": round(float(avg_return), 4),
        "median_return": round(float(median_return), 4),
        "baseline": round(float(baseline), 4),
        "alpha": round(float(avg_return - baseline), 4),
        "win_rate": round(float(win_rate), 2),
        "sharpe": round(float(sharpe), 4),
        "sortino": round(float(sortino), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "worst_day": round(float(daily.min()), 4),
        "best_day": round(float(daily.max()), 4),
        "active_days": int(len(daily)),
    }


def v2_picks(df, return_col):
    test = df.copy()

    test = test[
        (safe_series(test, "five_day_change") > 0)
        & (safe_series(test, "volume_ratio") >= 1.0)
    ].copy()

    if "pre_score" in test.columns:
        rank_col = "pre_score"
    elif "score" in test.columns:
        rank_col = "score"
    else:
        rank_col = "five_day_change"

    picks = (
        test.sort_values(["date", rank_col], ascending=[True, False])
        .groupby("date")
        .head(5)
        .copy()
    )

    picks["return"] = pd.to_numeric(picks[return_col], errors="coerce")
    picks = picks.dropna(subset=["return"])

    return picks


def v8_picks(df, return_col):
    test = df.copy()

    test = test[
        (safe_series(test, "relative_strength_rank_daily") >= 0.90)
        & (safe_series(test, "five_day_change") >= 5)
    ].copy()

    if test.empty:
        return pd.DataFrame()

    scoring_features = {
        "momentum_rs_combo_rank_daily": 0.09715610227706029,
        "pre_score_rank_daily": 0.6803264922366499,
        "five_day_change_rank_daily": 0.14646390512185126,
        "relative_strength_rank_daily": 0.07605350036443861,
    }

    score = pd.Series(0.0, index=test.index)

    for feature, weight in scoring_features.items():
        values = safe_series(test, feature)
        score += values.rank(pct=True).fillna(0) * weight

    test["strategy_score"] = score

    selected = []

    for date, group in test.sort_values(
        ["date", "strategy_score"],
        ascending=[True, False],
    ).groupby("date"):
        sector_counts = {}
        day_picks = []

        for _, row in group.iterrows():
            sector = row["sector"] if "sector" in row and pd.notna(row["sector"]) else "Unknown"

            if sector_counts.get(sector, 0) >= 2:
                continue

            day_picks.append(row)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

            if len(day_picks) >= 7:
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
        stop_loss=4,
        take_profit=20,
    )

    return picks


def weighted_v8_daily_returns(picks):
    if picks.empty:
        return pd.Series(dtype=float)

    daily_returns = {}

    for date, group in picks.groupby("date"):
        group = group.copy()

        raw_score = pd.to_numeric(group["strategy_score"], errors="coerce").fillna(0)

        if raw_score.sum() <= 0:
            weights = pd.Series(1 / len(group), index=group.index)
        else:
            weights = raw_score / raw_score.sum()

        weights = weights.clip(upper=0.25)
        weights = weights / weights.sum()

        gross_exposure = 0.75
        daily_returns[date] = (group["return"] * weights * gross_exposure).sum()

    return pd.Series(daily_returns).sort_index()


def equal_weight_daily_returns(picks):
    if picks.empty:
        return pd.Series(dtype=float)

    return picks.groupby("date")["return"].mean()


def monthly_breakdown(v2_daily, v8_daily):
    all_dates = sorted(set(v2_daily.index) | set(v8_daily.index))
    rows = []

    for month, group_dates in pd.Series(all_dates).groupby(
        pd.Series(all_dates).dt.to_period("M").astype(str)
    ):
        dates = list(group_dates)

        v2_month = v2_daily[v2_daily.index.isin(dates)]
        v8_month = v8_daily[v8_daily.index.isin(dates)]

        rows.append({
            "month": month,
            "v2_avg_return": round(v2_month.mean(), 4) if not v2_month.empty else None,
            "v8_avg_return": round(v8_month.mean(), 4) if not v8_month.empty else None,
            "v2_win_rate": round((v2_month > 0).mean() * 100, 2) if not v2_month.empty else None,
            "v8_win_rate": round((v8_month > 0).mean() * 100, 2) if not v8_month.empty else None,
            "v2_active_days": int(len(v2_month)),
            "v8_active_days": int(len(v8_month)),
        })

    return pd.DataFrame(rows)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    df = add_features(df)

    return_col = get_return_col(df)
    holdout, holdout_start = holdout_data(df)

    print(f"Holdout starts: {holdout_start.date()}")
    print(f"Return column: {return_col}")

    baseline = pd.to_numeric(holdout[return_col], errors="coerce").dropna().mean()

    v2 = v2_picks(holdout, return_col)
    v8 = v8_picks(holdout, return_col)

    v2_daily = equal_weight_daily_returns(v2)
    v8_daily = weighted_v8_daily_returns(v8)

    v2_metrics = evaluate_daily_returns(v2_daily, baseline)
    v8_metrics = evaluate_daily_returns(v8_daily, baseline)

    monthly = monthly_breakdown(v2_daily, v8_daily)
    monthly.to_csv(MONTHLY_FILE, index=False)

    summary = {
        "holdout_start": str(holdout_start.date()),
        "return_column": return_col,
        "baseline_avg_return": round(float(baseline), 4),
        "v2_scanner": {
            "description": "Current scanner approximation: five_day_change > 0, volume_ratio >= 1.0, top 5 by pre_score.",
            "metrics": v2_metrics,
            "trades": int(len(v2)),
        },
        "v8_portfolio_optimizer": {
            "description": "V8 portfolio: relative strength rank >= 0.90, five_day_change >= 5, top 7, max 2 per sector, rank-weighted, 75% exposure, 25% max position, 4% stop, 20% take profit.",
            "metrics": v8_metrics,
            "trades": int(len(v8)),
        },
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))

    print("\nCOMPARISON SUMMARY")
    print("------------------")
    print(f"Baseline average return: {baseline:.4f}%")

    print("\nV2 CURRENT SCANNER")
    print(v2_metrics)
    print(f"Trades: {len(v2)}")

    print("\nV8 PORTFOLIO OPTIMIZER")
    print(v8_metrics)
    print(f"Trades: {len(v8)}")

    print("\nMONTHLY BREAKDOWN")
    print(monthly.to_string(index=False))

    print(f"\nSaved summary: {SUMMARY_FILE}")
    print(f"Saved monthly: {MONTHLY_FILE}")


if __name__ == "__main__":
    main()