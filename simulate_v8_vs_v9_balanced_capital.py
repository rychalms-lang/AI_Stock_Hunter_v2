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
SUMMARY_FILE = REPORTS_DIR / "balanced_v8_vs_v9_capital_summary.json"
EQUITY_FILE = REPORTS_DIR / "balanced_v8_vs_v9_equity.csv"
MONTHLY_FILE = REPORTS_DIR / "balanced_v8_vs_v9_monthly.csv"
TRADES_FILE = REPORTS_DIR / "balanced_v8_vs_v9_trades.csv"

START_DATE = "2024-01-01"
STARTING_CAPITAL = 2500.00
MAX_ACCOUNT_EXPOSURE = 1.00

RETURN_COLUMNS = {
    10: ["future_10d_return", "future_return_10d", "return_10d"],
}


V8_CONFIG = {
    "name": "V8_CHAMPION",
    "hold_days": 10,
    "max_positions": 7,
    "sector_cap": 2,
    "gross_exposure": 0.75,
    "max_position_weight": 0.25,
    "stop_loss": 4.0,
    "take_profit": 20.0,
    "min_rs_rank": 0.90,
    "min_five_day": 5.0,
    "scoring_features": {
        "momentum_rs_combo_rank_daily": 0.09715610227706029,
        "pre_score_rank_daily": 0.6803264922366499,
        "five_day_change_rank_daily": 0.14646390512185126,
        "relative_strength_rank_daily": 0.07605350036443861,
    },
}


V9_CONFIG = {
    "name": "V9_DEFENSIVE",
    "hold_days": 10,
    "max_positions": 7,
    "sector_cap": 2,
    "gross_exposure": 0.75,
    "max_position_weight": 0.25,
    "stop_loss": 3.0,
    "take_profit": 20.0,
    "min_rs_rank": 0.90,
    "min_five_day": 5.0,
    "scoring_features": {
        "momentum_model": 0.20,
        "relative_strength_model": 0.45,
        "volume_breakout_model": 0.10,
        "sector_leader_model": 0.10,
        "quality_model": 0.15,
    },
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


def get_return_col(df):
    col = find_column(df, RETURN_COLUMNS[10])
    if col is None:
        raise ValueError("No 10-day return column found.")
    return col


def safe_series(df, col):
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


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

    df = df[df["date"] >= pd.Timestamp(START_DATE)].copy()

    for col in df.columns:
        if col not in ["date", "ticker", "sector", "regime"]:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except Exception:
                pass

    print(f"Rows loaded from {START_DATE}: {len(df):,}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    return df


def add_features(df):
    df = df.copy()

    if "five_day_change" in df.columns and "twenty_day_change" in df.columns:
        df["momentum_acceleration"] = df["five_day_change"] - (df["twenty_day_change"] / 4)

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
                df[f"{feature}_sector_rank"] = df.groupby(["date", "sector"])[feature].rank(pct=True)

    return df


def add_v9_model_scores(df):
    df = df.copy()

    df["momentum_model"] = (
        safe_series(df, "five_day_change_rank_daily") * 0.45
        + safe_series(df, "twenty_day_change_rank_daily") * 0.35
        + safe_series(df, "momentum_acceleration_rank_daily") * 0.20
    )

    df["relative_strength_model"] = (
        safe_series(df, "relative_strength_rank_daily") * 0.60
        + safe_series(df, "momentum_rs_combo_rank_daily") * 0.25
        + safe_series(df, "relative_strength_sector_rank") * 0.15
    )

    df["volume_breakout_model"] = (
        safe_series(df, "volume_ratio_rank_daily") * 0.40
        + safe_series(df, "volume_momentum_pressure_rank_daily") * 0.35
        + safe_series(df, "volume_rs_pressure_rank_daily") * 0.25
    )

    df["sector_leader_model"] = (
        safe_series(df, "relative_strength_sector_rank") * 0.40
        + safe_series(df, "five_day_change_sector_rank") * 0.35
        + safe_series(df, "pre_score_sector_rank") * 0.25
    )

    df["quality_model"] = (
        safe_series(df, "pre_score_rank_daily") * 0.65
        + safe_series(df, "score_volume_combo_rank_daily") * 0.20
        + safe_series(df, "volume_ratio_rank_daily") * 0.15
    )

    return df


def apply_stop_take_profit(raw_return, stop_loss=None, take_profit=None):
    value = raw_return

    if stop_loss is not None:
        value = max(value, -abs(stop_loss))

    if take_profit is not None:
        value = min(value, abs(take_profit))

    return value


def score_candidates(day_df, config):
    score = pd.Series(0.0, index=day_df.index)

    for feature, weight in config["scoring_features"].items():
        values = safe_series(day_df, feature)
        score += values.rank(pct=True).fillna(0.0) * weight

    return score


def select_daily_candidates(day_df, config, return_col):
    test = day_df.copy()

    test = test[
        (safe_series(test, "relative_strength_rank_daily") >= config["min_rs_rank"])
        & (safe_series(test, "five_day_change") >= config["min_five_day"])
    ].copy()

    if test.empty:
        return pd.DataFrame()

    test["strategy_score"] = score_candidates(test, config)

    selected_rows = []
    sector_counts = {}

    ranked = test.sort_values("strategy_score", ascending=False)

    for _, row in ranked.iterrows():
        sector = row["sector"] if "sector" in row and pd.notna(row["sector"]) else "Unknown"

        if sector_counts.get(sector, 0) >= config["sector_cap"]:
            continue

        selected_rows.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

        if len(selected_rows) >= config["max_positions"]:
            break

    if not selected_rows:
        return pd.DataFrame()

    picks = pd.DataFrame(selected_rows).copy()
    picks["raw_return"] = pd.to_numeric(picks[return_col], errors="coerce")
    picks = picks.dropna(subset=["raw_return"])

    if picks.empty:
        return pd.DataFrame()

    picks["capped_return"] = picks["raw_return"].apply(
        lambda value: apply_stop_take_profit(
            value,
            stop_loss=config["stop_loss"],
            take_profit=config["take_profit"],
        )
    )

    return picks


def portfolio_weights(picks, config):
    scores = pd.to_numeric(picks["strategy_score"], errors="coerce").fillna(0.0)

    if scores.sum() <= 0:
        weights = pd.Series(1 / len(picks), index=picks.index)
    else:
        weights = scores / scores.sum()

    weights = weights.clip(upper=config["max_position_weight"])

    if weights.sum() <= 0:
        weights = pd.Series(1 / len(picks), index=picks.index)
    else:
        weights = weights / weights.sum()

    return weights


def simulate_strategy(df, config, return_col):
    trading_dates = sorted(df["date"].dropna().unique())

    cash = STARTING_CAPITAL
    open_positions = []
    equity_rows = []
    trade_rows = []

    for current_date in trading_dates:
        current_date = pd.Timestamp(current_date)

        still_open = []
        realized_cash = 0.0

        for position in open_positions:
            if pd.Timestamp(current_date) >= pd.Timestamp(position["exit_date"]):
                exit_value = position["entry_value"] * (1 + position["return_pct"] / 100)
                realized_cash += exit_value
                trade_rows.append({
                    "strategy": config["name"],
                    "entry_date": position["entry_date"],
                    "exit_date": position["exit_date"],
                    "ticker": position["ticker"],
                    "sector": position["sector"],
                    "entry_value": position["entry_value"],
                    "exit_value": exit_value,
                    "return_pct": position["return_pct"],
                    "raw_return_pct": position["raw_return_pct"],
                    "weight": position["weight"],
                })
            else:
                still_open.append(position)

        open_positions = still_open
        cash += realized_cash

        open_value = sum(
            position["entry_value"] * (1 + position["return_pct"] / 100)
            for position in open_positions
        )
        equity_before_new_trades = cash + open_value

        max_allowed_invested = equity_before_new_trades * MAX_ACCOUNT_EXPOSURE
        current_invested = sum(position["entry_value"] for position in open_positions)
        available_investment_room = max(0.0, max_allowed_invested - current_invested)

        day_df = df[df["date"] == current_date]

        picks = select_daily_candidates(day_df, config, return_col)

        invested_today = 0.0

        if not picks.empty and available_investment_room > 1.0 and cash > 1.0:
            target_trade_capital = min(
                cash,
                available_investment_room,
                equity_before_new_trades * config["gross_exposure"] / config["hold_days"],
            )

            if target_trade_capital > 1.0:
                weights = portfolio_weights(picks, config)

                for idx, row in picks.iterrows():
                    entry_value = target_trade_capital * weights.loc[idx]

                    if entry_value <= 0:
                        continue

                    cash -= entry_value
                    invested_today += entry_value

                    open_positions.append({
                        "entry_date": current_date.date().isoformat(),
                        "exit_date": (current_date + pd.offsets.BDay(config["hold_days"])).date(),
                        "ticker": row["ticker"],
                        "sector": row["sector"] if "sector" in row and pd.notna(row["sector"]) else "Unknown",
                        "entry_value": float(entry_value),
                        "return_pct": float(row["capped_return"]),
                        "raw_return_pct": float(row["raw_return"]),
                        "weight": float(weights.loc[idx]),
                    })

        marked_open_value = sum(
            position["entry_value"] * (1 + position["return_pct"] / 100)
            for position in open_positions
        )

        total_equity = cash + marked_open_value
        invested_capital = sum(position["entry_value"] for position in open_positions)

        equity_rows.append({
            "date": current_date.date().isoformat(),
            "strategy": config["name"],
            "cash": cash,
            "open_position_value": marked_open_value,
            "invested_capital": invested_capital,
            "total_equity": total_equity,
            "open_positions": len(open_positions),
            "invested_today": invested_today,
        })

    final_date = pd.Timestamp(trading_dates[-1])

    for position in open_positions:
        exit_value = position["entry_value"] * (1 + position["return_pct"] / 100)
        cash += exit_value
        trade_rows.append({
            "strategy": config["name"],
            "entry_date": position["entry_date"],
            "exit_date": position["exit_date"],
            "ticker": position["ticker"],
            "sector": position["sector"],
            "entry_value": position["entry_value"],
            "exit_value": exit_value,
            "return_pct": position["return_pct"],
            "raw_return_pct": position["raw_return_pct"],
            "weight": position["weight"],
        })

    equity_rows.append({
        "date": (final_date + pd.offsets.BDay(1)).date().isoformat(),
        "strategy": config["name"],
        "cash": cash,
        "open_position_value": 0.0,
        "invested_capital": 0.0,
        "total_equity": cash,
        "open_positions": 0,
        "invested_today": 0.0,
    })

    return pd.DataFrame(equity_rows), pd.DataFrame(trade_rows)


def summarize_equity(equity_df):
    equity = equity_df.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    equity = equity.sort_values("date")

    daily_equity = equity.set_index("date")["total_equity"]
    daily_returns = daily_equity.pct_change().dropna()

    ending_capital = daily_equity.iloc[-1]
    profit = ending_capital - STARTING_CAPITAL
    total_return_pct = (ending_capital / STARTING_CAPITAL - 1) * 100

    years = max((daily_equity.index[-1] - daily_equity.index[0]).days / 365.25, 0.01)
    annualized_return_pct = ((ending_capital / STARTING_CAPITAL) ** (1 / years) - 1) * 100

    if daily_returns.std() == 0 or pd.isna(daily_returns.std()):
        sharpe_like = 0.0
    else:
        sharpe_like = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

    downside = daily_returns[daily_returns < 0].std()

    if downside == 0 or pd.isna(downside):
        sortino_like = 0.0
    else:
        sortino_like = (daily_returns.mean() / downside) * np.sqrt(252)

    peak = daily_equity.cummax()
    drawdown = (daily_equity / peak - 1) * 100

    return {
        "starting_capital": round(STARTING_CAPITAL, 2),
        "ending_capital": round(float(ending_capital), 2),
        "profit_dollars": round(float(profit), 2),
        "total_return_pct": round(float(total_return_pct), 2),
        "annualized_return_pct": round(float(annualized_return_pct), 2),
        "win_rate_pct": round(float((daily_returns > 0).mean() * 100), 2),
        "sharpe_like": round(float(sharpe_like), 4),
        "sortino_like": round(float(sortino_like), 4),
        "max_drawdown_pct": round(float(drawdown.min()), 2),
        "worst_day_pct": round(float(daily_returns.min() * 100), 2),
        "best_day_pct": round(float(daily_returns.max() * 100), 2),
        "active_days": int(len(daily_returns)),
    }


def monthly_returns(equity_df):
    equity = equity_df.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    equity = equity.sort_values("date")

    rows = []

    for month, group in equity.groupby(equity["date"].dt.to_period("M").astype(str)):
        start_value = group["total_equity"].iloc[0]
        end_value = group["total_equity"].iloc[-1]
        month_return = (end_value / start_value - 1) * 100

        rows.append({
            "strategy": group["strategy"].iloc[0],
            "month": month,
            "start_value": round(float(start_value), 2),
            "end_value": round(float(end_value), 2),
            "monthly_return_pct": round(float(month_return), 2),
        })

    return pd.DataFrame(rows)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    df = add_features(df)
    df = add_v9_model_scores(df)
    return_col = get_return_col(df)

    print(f"Return column: {return_col}")
    print(f"Starting capital: ${STARTING_CAPITAL:,.2f}")
    print("Assumptions: TFSA/no tax, $0 fees, fractional shares, no slippage.")
    print("Balanced simulation: no leverage, capital is unavailable while positions are open.")
    print()

    v8_equity, v8_trades = simulate_strategy(df, V8_CONFIG, return_col)
    v9_equity, v9_trades = simulate_strategy(df, V9_CONFIG, return_col)

    all_equity = pd.concat([v8_equity, v9_equity], ignore_index=True)
    all_trades = pd.concat([v8_trades, v9_trades], ignore_index=True)

    v8_summary = summarize_equity(v8_equity)
    v9_summary = summarize_equity(v9_equity)

    monthly = pd.concat(
        [monthly_returns(v8_equity), monthly_returns(v9_equity)],
        ignore_index=True,
    )

    winner = "V8" if v8_summary["ending_capital"] >= v9_summary["ending_capital"] else "V9"

    summary = {
        "period_start": START_DATE,
        "period_end": str(df["date"].max().date()),
        "starting_capital": STARTING_CAPITAL,
        "assumptions": {
            "tax": "TFSA / no tax drag",
            "fees": "$0 commission",
            "fractional_shares": True,
            "slippage": "not included",
            "leverage": "not allowed",
            "capital_constraint": "cash is unavailable while positions are open",
            "position_holding": "10 business days",
        },
        "v8": v8_summary,
        "v9": v9_summary,
        "winner": winner,
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))
    all_equity.to_csv(EQUITY_FILE, index=False)
    monthly.to_csv(MONTHLY_FILE, index=False)
    all_trades.to_csv(TRADES_FILE, index=False)

    print("BALANCED SIMULATION COMPLETE")
    print("----------------------------")
    print(f"Period: {START_DATE} to {df['date'].max().date()}")
    print(f"Starting capital: ${STARTING_CAPITAL:,.2f}")
    print()

    print("V8 CHAMPION")
    print(v8_summary)
    print()

    print("V9 CHALLENGER")
    print(v9_summary)
    print()

    print(f"WINNER: {winner}")
    print()
    print(f"Saved summary: {SUMMARY_FILE}")
    print(f"Saved equity curve: {EQUITY_FILE}")
    print(f"Saved monthly returns: {MONTHLY_FILE}")
    print(f"Saved trades: {TRADES_FILE}")


if __name__ == "__main__":
    main()
