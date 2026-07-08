import os
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


warnings.filterwarnings("ignore")


INPUT_PATH = "data/historical_training_data_v3_features.csv"
OUTPUT_DIR = "performance/ml_v3_return_comparison"

TARGET_WIN = "future_3d_win"
TARGET_RETURN = "future_3d_return"

EXCLUDE_COLUMNS = [
    "date",
    "ticker",
    "sector",
    "market_regime",
    "future_1d_return",
    "future_1d_win",
    "future_3d_return",
    "future_3d_win",
    "future_5d_return",
    "future_5d_win",
    "future_7d_return",
    "future_7d_win",
    "future_10d_return",
    "future_10d_win",
]


def load_data():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Missing {INPUT_PATH}. Run feature_engineering_v3.py first."
        )

    df = pd.read_csv(INPUT_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df


def get_feature_columns(df):
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    return [col for col in numeric_cols if col not in EXCLUDE_COLUMNS]


def chronological_split(df, train_pct=0.70, validation_pct=0.15):
    dates = sorted(df["date"].dropna().unique())

    train_end_idx = int(len(dates) * train_pct)
    validation_end_idx = int(len(dates) * (train_pct + validation_pct))

    train_end_date = dates[train_end_idx]
    validation_end_date = dates[validation_end_idx]

    train_df = df[df["date"] <= train_end_date].copy()
    validation_df = df[
        (df["date"] > train_end_date)
        & (df["date"] <= validation_end_date)
    ].copy()
    test_df = df[df["date"] > validation_end_date].copy()

    return train_df, validation_df, test_df, train_end_date, validation_end_date


def train_logistic_model(train_df, features):
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
        )),
    ])

    X_train = train_df[features]
    y_train = train_df[TARGET_WIN].astype(int)

    model.fit(X_train, y_train)

    return model


def add_ml_probabilities(model, test_df, features):
    test_df = test_df.copy()
    test_df["ml_probability"] = model.predict_proba(test_df[features])[:, 1]
    return test_df


def evaluate_ranker(df, rank_column, label, higher_is_better=True):
    results = []

    temp = df.copy()
    temp = temp.dropna(subset=[rank_column, TARGET_RETURN, TARGET_WIN])

    if len(temp) == 0:
        return results

    ascending = not higher_is_better

    for top_n in [5, 10, 20, 50]:
        temp["daily_rank"] = temp.groupby("date")[rank_column].rank(
            ascending=ascending,
            method="first",
        )

        selected = temp[temp["daily_rank"] <= top_n].copy()

        if len(selected) == 0:
            continue

        daily_returns = selected.groupby("date")[TARGET_RETURN].mean()

        results.append({
            "strategy": label,
            "top_n": top_n,
            "total_picks": int(len(selected)),
            "trading_days": int(daily_returns.count()),
            "average_trade_return": float(selected[TARGET_RETURN].mean()),
            "median_trade_return": float(selected[TARGET_RETURN].median()),
            "win_rate": float(selected[TARGET_WIN].mean()),
            "average_daily_portfolio_return": float(daily_returns.mean()),
            "median_daily_portfolio_return": float(daily_returns.median()),
            "daily_return_std": float(daily_returns.std()),
            "best_daily_return": float(daily_returns.max()),
            "worst_daily_return": float(daily_returns.min()),
        })

    return results


def evaluate_all_rankers(test_df):
    rankers = [
        ("ml_probability", "ML Logistic Probability", True),
        ("pre_score", "Current Pre Score", True),
        ("return_5d_rank_pct", "5D Momentum Rank", True),
        ("return_20d_rank_pct", "20D Momentum Rank", True),
        ("relative_strength_rank_pct", "Relative Strength Rank", True),
        ("volume_ratio_rank_pct", "Volume Ratio Rank", True),
        ("stock_vs_sector_20d_rank_pct", "Stock vs Sector Rank", True),
        ("momentum_per_vol_20d_rank_pct", "Momentum Per Vol Rank", True),
    ]

    all_results = []

    for col, label, higher_is_better in rankers:
        if col not in test_df.columns:
            continue

        all_results.extend(
            evaluate_ranker(
                test_df,
                col,
                label,
                higher_is_better=higher_is_better,
            )
        )

    return pd.DataFrame(all_results)


def save_results(results_df, train_end_date, validation_end_date):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(
        OUTPUT_DIR,
        f"ml_v3_return_comparison_{timestamp}.csv",
    )

    txt_path = os.path.join(
        OUTPUT_DIR,
        f"ml_v3_return_comparison_summary_{timestamp}.txt",
    )

    results_df.to_csv(csv_path, index=False)

    with open(txt_path, "w") as f:
        f.write("AI STOCK HUNTER V3 - RETURN COMPARISON\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Target win label: {TARGET_WIN}\n")
        f.write(f"Target return: {TARGET_RETURN}\n")
        f.write(f"Train end date: {pd.to_datetime(train_end_date).date()}\n")
        f.write(f"Validation end date: {pd.to_datetime(validation_end_date).date()}\n\n")

        f.write("Results sorted by average daily portfolio return:\n\n")

        sorted_results = results_df.sort_values(
            "average_daily_portfolio_return",
            ascending=False,
        )

        f.write(sorted_results.to_string(index=False))
        f.write("\n\n")

        best = sorted_results.iloc[0]

        f.write("BEST RESULT\n")
        f.write("-" * 70 + "\n")
        f.write(f"Strategy: {best['strategy']}\n")
        f.write(f"Top N: {int(best['top_n'])}\n")
        f.write(f"Average trade return: {best['average_trade_return']:.4f}%\n")
        f.write(f"Average daily portfolio return: {best['average_daily_portfolio_return']:.4f}%\n")
        f.write(f"Win rate: {best['win_rate']:.4f}\n")
        f.write(f"Worst daily return: {best['worst_daily_return']:.4f}%\n\n")

        f.write("Decision rule:\n")
        f.write("ML should not be adopted unless it beats the current pre_score/momentum baseline on realistic return metrics.\n")

    return csv_path, txt_path


def main():
    print("AI STOCK HUNTER V3 - RETURN COMPARISON")
    print("=" * 70)

    df = load_data()
    features = get_feature_columns(df)

    required = [TARGET_WIN, TARGET_RETURN]
    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"Missing required target columns: {missing}")

    df = df.dropna(subset=[TARGET_WIN, TARGET_RETURN]).copy()

    train_df, validation_df, test_df, train_end_date, validation_end_date = chronological_split(df)

    print(f"Rows:            {len(df):,}")
    print(f"Train rows:      {len(train_df):,}")
    print(f"Validation rows: {len(validation_df):,}")
    print(f"Test rows:       {len(test_df):,}")
    print(f"Features:        {len(features):,}")
    print(f"Target:          {TARGET_RETURN}")

    print("\nTraining logistic regression on 3-day win probability...")
    model = train_logistic_model(train_df, features)

    print("Scoring test period...")
    test_df = add_ml_probabilities(model, test_df, features)

    print("Comparing ML vs momentum baselines...")
    results_df = evaluate_all_rankers(test_df)

    results_df = results_df.sort_values(
        "average_daily_portfolio_return",
        ascending=False,
    ).reset_index(drop=True)

    print("\nRESULTS")
    print("=" * 70)
    print(results_df.to_string(index=False))

    csv_path, txt_path = save_results(
        results_df,
        train_end_date,
        validation_end_date,
    )

    print("\nSaved results:")
    print(f"CSV:     {csv_path}")
    print(f"Summary: {txt_path}")

    best = results_df.iloc[0]

    print("\nBest strategy:")
    print(f"{best['strategy']} | Top {int(best['top_n'])}")
    print(f"Average trade return: {best['average_trade_return']:.4f}%")
    print(f"Average daily portfolio return: {best['average_daily_portfolio_return']:.4f}%")
    print(f"Win rate: {best['win_rate']:.4f}")

    print("\nDecision rule:")
    print("If ML does not beat pre_score or momentum on returns, we do not adopt it.")


if __name__ == "__main__":
    main()