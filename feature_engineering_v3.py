import os
import numpy as np
import pandas as pd


INPUT_PATHS = [
    "data/historical_training_data.csv",
    "historical_training_data.csv",
    "performance/historical_training_data.csv",
]

OUTPUT_PATH = "data/historical_training_data_v3_features.csv"


def find_input_file():
    for path in INPUT_PATHS:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        "Could not find historical_training_data.csv in data/, root, or performance/."
    )


def normalize_columns(df):
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    required = [
        "date",
        "ticker",
        "sector",
        "open",
        "close",
        "five_day_change",
        "twenty_day_change",
        "relative_strength",
        "open_to_close_change",
        "avg_volume",
        "volume_ratio",
        "pre_score",
        "market_regime",
        "market_regime_score",
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    return df


def safe_divide(a, b):
    return np.where((b == 0) | pd.isna(b), np.nan, a / b)


def add_v3_features(df):
    df = df.copy()
    g = df.groupby("ticker", group_keys=False)

    # --------------------------------------------------
    # Core return features already available at trade time
    # --------------------------------------------------
    df["daily_return"] = g["close"].pct_change() * 100

    df["return_3d"] = g["close"].pct_change(3) * 100
    df["return_5d"] = df["five_day_change"]
    df["return_10d"] = g["close"].pct_change(10) * 100
    df["return_20d"] = df["twenty_day_change"]
    df["return_60d"] = g["close"].pct_change(60) * 100
    df["return_120d"] = g["close"].pct_change(120) * 100

    # --------------------------------------------------
    # Momentum quality
    # --------------------------------------------------
    df["momentum_accel_5_20"] = df["return_5d"] - df["return_20d"]
    df["momentum_accel_10_60"] = df["return_10d"] - df["return_60d"]

    df["momentum_consistency_20d"] = g["daily_return"].transform(
        lambda x: x.rolling(20).mean() / x.rolling(20).std()
    )

    df["positive_days_10d"] = g["daily_return"].transform(
        lambda x: (x > 0).rolling(10).sum()
    )

    df["positive_days_20d"] = g["daily_return"].transform(
        lambda x: (x > 0).rolling(20).sum()
    )

    # --------------------------------------------------
    # Moving average distance features
    # --------------------------------------------------
    df["ma_10"] = g["close"].transform(lambda x: x.rolling(10).mean())
    df["ma_20"] = g["close"].transform(lambda x: x.rolling(20).mean())
    df["ma_50"] = g["close"].transform(lambda x: x.rolling(50).mean())
    df["ma_100"] = g["close"].transform(lambda x: x.rolling(100).mean())
    df["ma_200"] = g["close"].transform(lambda x: x.rolling(200).mean())

    df["dist_ma_10"] = (df["close"] / df["ma_10"] - 1) * 100
    df["dist_ma_20"] = (df["close"] / df["ma_20"] - 1) * 100
    df["dist_ma_50"] = (df["close"] / df["ma_50"] - 1) * 100
    df["dist_ma_100"] = (df["close"] / df["ma_100"] - 1) * 100
    df["dist_ma_200"] = (df["close"] / df["ma_200"] - 1) * 100

    df["trend_stack_20_50_200"] = (
        (df["close"] > df["ma_20"])
        & (df["ma_20"] > df["ma_50"])
        & (df["ma_50"] > df["ma_200"])
    ).astype(int)

    # --------------------------------------------------
    # Volatility features
    # --------------------------------------------------
    df["volatility_10d"] = g["daily_return"].transform(lambda x: x.rolling(10).std())
    df["volatility_20d"] = g["daily_return"].transform(lambda x: x.rolling(20).std())
    df["volatility_60d"] = g["daily_return"].transform(lambda x: x.rolling(60).std())

    df["volatility_ratio_20_60"] = safe_divide(
        df["volatility_20d"],
        df["volatility_60d"],
    )

    df["momentum_per_vol_20d"] = safe_divide(
        df["return_20d"],
        df["volatility_20d"],
    )

    # --------------------------------------------------
    # Volume proxy features
    # We do not have true volume, only avg_volume and volume_ratio.
    # So we avoid fake raw-volume calculations.
    # --------------------------------------------------
    df["log_avg_volume"] = np.log1p(df["avg_volume"])

    df["volume_ratio_5d_avg"] = g["volume_ratio"].transform(
        lambda x: x.rolling(5).mean()
    )

    df["volume_ratio_20d_avg"] = g["volume_ratio"].transform(
        lambda x: x.rolling(20).mean()
    )

    df["volume_ratio_change_5d"] = df["volume_ratio"] - df["volume_ratio_5d_avg"]

    df["liquidity_proxy"] = df["close"] * df["avg_volume"]
    df["log_liquidity_proxy"] = np.log1p(df["liquidity_proxy"])

    # --------------------------------------------------
    # High/low proxy features using close only
    # --------------------------------------------------
    df["close_high_20d"] = g["close"].transform(lambda x: x.rolling(20).max())
    df["close_high_60d"] = g["close"].transform(lambda x: x.rolling(60).max())
    df["close_high_120d"] = g["close"].transform(lambda x: x.rolling(120).max())
    df["close_high_252d"] = g["close"].transform(lambda x: x.rolling(252).max())

    df["near_20d_close_high"] = df["close"] / df["close_high_20d"]
    df["near_60d_close_high"] = df["close"] / df["close_high_60d"]
    df["near_120d_close_high"] = df["close"] / df["close_high_120d"]
    df["near_252d_close_high"] = df["close"] / df["close_high_252d"]

    df["new_20d_close_high"] = (df["close"] >= df["close_high_20d"]).astype(int)
    df["new_60d_close_high"] = (df["close"] >= df["close_high_60d"]).astype(int)
    df["new_120d_close_high"] = (df["close"] >= df["close_high_120d"]).astype(int)
    df["new_252d_close_high"] = (df["close"] >= df["close_high_252d"]).astype(int)

    # --------------------------------------------------
    # Gap and intraday features
    # --------------------------------------------------
    df["gap_return"] = (df["open"] / g["close"].shift(1) - 1) * 100
    df["open_to_close_return"] = df["open_to_close_change"]

    df["gap_vs_intraday"] = df["gap_return"] - df["open_to_close_return"]

    # --------------------------------------------------
    # Sector-relative features
    # --------------------------------------------------
    df["sector_return_5d"] = df.groupby(["date", "sector"])["return_5d"].transform("mean")
    df["sector_return_20d"] = df.groupby(["date", "sector"])["return_20d"].transform("mean")
    df["sector_return_60d"] = df.groupby(["date", "sector"])["return_60d"].transform("mean")

    df["stock_vs_sector_5d"] = df["return_5d"] - df["sector_return_5d"]
    df["stock_vs_sector_20d"] = df["return_20d"] - df["sector_return_20d"]
    df["stock_vs_sector_60d"] = df["return_60d"] - df["sector_return_60d"]

    sector_daily = df[["date", "sector", "sector_return_20d"]].drop_duplicates().copy()

    sector_daily["sector_rank_20d"] = sector_daily.groupby("date")[
        "sector_return_20d"
    ].rank(ascending=False, method="dense")

    df = df.merge(
        sector_daily[["date", "sector", "sector_rank_20d"]],
        on=["date", "sector"],
        how="left",
    )

    # --------------------------------------------------
    # Cross-sectional ranks
    # These are important because stock selection is relative.
    # --------------------------------------------------
    rank_cols = [
        "return_5d",
        "return_20d",
        "relative_strength",
        "volume_ratio",
        "pre_score",
        "momentum_per_vol_20d",
        "stock_vs_sector_20d",
        "log_liquidity_proxy",
    ]

    for col in rank_cols:
        df[f"{col}_rank_pct"] = df.groupby("date")[col].rank(pct=True)

    # --------------------------------------------------
    # Candidate flags
    # --------------------------------------------------
    df["v3_candidate"] = (
        (df["return_5d"] > 0)
        & (df["return_20d"] < 50)
        & (df["volume_ratio"] > 0.75)
        & (df["market_regime"].astype(str).str.lower().isin(["risk-on", "risk on", "mixed"]))
    ).astype(int)

    df["v3_momentum_candidate"] = (
        (df["return_5d"] > 2)
        & (df["return_20d"] > 5)
        & (df["return_20d"] < 50)
        & (df["relative_strength"] > 0)
        & (df["volume_ratio"] > 0.75)
    ).astype(int)

    return df


def main():
    input_path = find_input_file()

    print(f"Loading: {input_path}")

    df = pd.read_csv(input_path)

    print(f"Original rows: {len(df):,}")
    print(f"Original columns: {len(df.columns):,}")

    df = normalize_columns(df)
    df = add_v3_features(df)

    os.makedirs("data", exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print("\nV3 FEATURE DATASET CREATED")
    print("--------------------------")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"V3 candidates: {df['v3_candidate'].sum():,}")
    print(f"V3 momentum candidates: {df['v3_momentum_candidate'].sum():,}")

    print("\nImportant note:")
    print("This dataset does NOT fabricate raw volume, ATR, high, or low.")
    print("It only uses features available from your actual historical dataset.")

    print("\nSample columns:")
    print(df.columns.tolist())


if __name__ == "__main__":
    main()