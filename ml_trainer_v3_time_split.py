import os
import json
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


warnings.filterwarnings("ignore")


INPUT_PATH = "data/historical_training_data_v3_features.csv"
OUTPUT_DIR = "performance/ml_v3_time_split_fast"

TARGETS = [
    "future_1d_win",
    "future_3d_win",
    "future_5d_win",
    "future_7d_win",
    "future_10d_win",
]

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
            f"Could not find {INPUT_PATH}. Run feature_engineering_v3.py first."
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


def evaluate_predictions(y_true, probabilities):
    predictions = (probabilities >= 0.50).astype(int)

    return {
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "positive_rate": float(predictions.mean()),
        "average_probability": float(probabilities.mean()),
    }


def baseline_auc(test_df, target):
    y_true = test_df[target].astype(int)

    baseline_cols = [
        "pre_score",
        "return_5d_rank_pct",
        "return_20d_rank_pct",
        "relative_strength_rank_pct",
        "volume_ratio_rank_pct",
        "stock_vs_sector_20d_rank_pct",
        "momentum_per_vol_20d_rank_pct",
    ]

    results = []

    for col in baseline_cols:
        if col not in test_df.columns:
            continue

        valid = test_df[col].notna()

        if valid.sum() < 100:
            continue

        try:
            auc = roc_auc_score(y_true[valid], test_df.loc[valid, col])
        except ValueError:
            auc = np.nan

        results.append({
            "baseline": col,
            "roc_auc": float(auc) if not pd.isna(auc) else np.nan,
        })

    return results


def top_n_daily_test(test_df, probabilities, target):
    temp = test_df[["date", "ticker", target]].copy()
    temp["ml_probability"] = probabilities

    results = []

    for top_n in [5, 10, 20, 50]:
        temp["rank"] = temp.groupby("date")["ml_probability"].rank(
            ascending=False,
            method="first",
        )

        selected = temp[temp["rank"] <= top_n]

        results.append({
            "selection": f"top_{top_n}_per_day",
            "rows": int(len(selected)),
            "win_rate": float(selected[target].mean()),
            "avg_probability": float(selected["ml_probability"].mean()),
        })

    return results


def train_target(df, target, features):
    clean_df = df.dropna(subset=[target]).copy()
    clean_df[target] = clean_df[target].astype(int)

    train_df, validation_df, test_df, train_end_date, validation_end_date = chronological_split(clean_df)

    X_train = train_df[features]
    y_train = train_df[target]

    X_validation = validation_df[features]
    y_validation = validation_df[target]

    X_test = test_df[features]
    y_test = test_df[target]

    models = {
        "logistic_regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
            )),
        ]),
        "random_forest_fast": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(
                n_estimators=150,
                max_depth=7,
                min_samples_leaf=150,
                random_state=42,
                n_jobs=-1,
                class_weight="balanced_subsample",
            )),
        ]),
    }

    print("\n" + "=" * 70)
    print(f"TARGET: {target}")
    print("=" * 70)
    print(f"Train rows:      {len(train_df):,}")
    print(f"Validation rows: {len(validation_df):,}")
    print(f"Test rows:       {len(test_df):,}")
    print(f"Features:        {len(features):,}")

    target_result = {
        "target": target,
        "rows": int(len(clean_df)),
        "features": int(len(features)),
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(validation_df)),
        "test_rows": int(len(test_df)),
        "train_end_date": str(pd.to_datetime(train_end_date).date()),
        "validation_end_date": str(pd.to_datetime(validation_end_date).date()),
        "models": [],
        "baselines": baseline_auc(test_df, target),
    }

    for model_name, model in models.items():
        print(f"\nTraining {model_name}...")

        model.fit(X_train, y_train)

        validation_probs = model.predict_proba(X_validation)[:, 1]
        test_probs = model.predict_proba(X_test)[:, 1]

        validation_metrics = evaluate_predictions(y_validation, validation_probs)
        test_metrics = evaluate_predictions(y_test, test_probs)

        top_n_results = top_n_daily_test(test_df, test_probs, target)

        target_result["models"].append({
            "model": model_name,
            "validation": validation_metrics,
            "test": test_metrics,
            "top_n_daily": top_n_results,
        })

        print(f"Validation ROC AUC: {validation_metrics['roc_auc']:.4f}")
        print(f"Test ROC AUC:       {test_metrics['roc_auc']:.4f}")
        print(f"Test precision:     {test_metrics['precision']:.4f}")
        print(f"Test recall:        {test_metrics['recall']:.4f}")

        print("Top-N daily win rates:")
        for row in top_n_results:
            print(
                f"  {row['selection']}: "
                f"win_rate={row['win_rate']:.4f}, "
                f"rows={row['rows']:,}"
            )

    print("\nBaseline AUCs:")
    for row in target_result["baselines"]:
        print(f"  {row['baseline']}: {row['roc_auc']:.4f}")

    return target_result


def save_results(results):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(
        OUTPUT_DIR,
        f"ml_v3_time_split_fast_results_{timestamp}.json",
    )

    txt_path = os.path.join(
        OUTPUT_DIR,
        f"ml_v3_time_split_fast_summary_{timestamp}.txt",
    )

    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    with open(txt_path, "w") as f:
        f.write("AI STOCK HUNTER V3 - FAST TIME-SPLIT ML RESULTS\n")
        f.write("=" * 70 + "\n\n")

        for target_result in results["targets"]:
            f.write(f"TARGET: {target_result['target']}\n")
            f.write("-" * 70 + "\n")
            f.write(f"Rows: {target_result['rows']:,}\n")
            f.write(f"Features: {target_result['features']:,}\n")
            f.write(f"Train rows: {target_result['train_rows']:,}\n")
            f.write(f"Validation rows: {target_result['validation_rows']:,}\n")
            f.write(f"Test rows: {target_result['test_rows']:,}\n")
            f.write(f"Train end date: {target_result['train_end_date']}\n")
            f.write(f"Validation end date: {target_result['validation_end_date']}\n\n")

            f.write("MODEL RESULTS\n")
            for model_result in target_result["models"]:
                f.write(f"\n{model_result['model']}\n")
                f.write(
                    f"Validation ROC AUC: "
                    f"{model_result['validation']['roc_auc']:.4f}\n"
                )
                f.write(
                    f"Test ROC AUC: "
                    f"{model_result['test']['roc_auc']:.4f}\n"
                )
                f.write(
                    f"Test precision: "
                    f"{model_result['test']['precision']:.4f}\n"
                )
                f.write(
                    f"Test recall: "
                    f"{model_result['test']['recall']:.4f}\n"
                )

                f.write("Top-N daily win rates:\n")
                for row in model_result["top_n_daily"]:
                    f.write(
                        f"  {row['selection']}: "
                        f"win_rate={row['win_rate']:.4f}, "
                        f"rows={row['rows']:,}, "
                        f"avg_probability={row['avg_probability']:.4f}\n"
                    )

            f.write("\nBASELINE AUCS\n")
            for row in target_result["baselines"]:
                f.write(f"{row['baseline']}: {row['roc_auc']:.4f}\n")

            f.write("\n\n")

    return json_path, txt_path


def main():
    print("AI STOCK HUNTER V3 - FAST TIME-SPLIT ML TRAINER")
    print("=" * 70)

    df = load_data()
    features = get_feature_columns(df)

    print(f"Loaded rows: {len(df):,}")
    print(f"Loaded columns: {len(df.columns):,}")
    print(f"Usable numeric features: {len(features):,}")

    results = {
        "created_at": datetime.now().isoformat(),
        "input_path": INPUT_PATH,
        "targets": [],
    }

    for target in TARGETS:
        target_result = train_target(df, target, features)
        results["targets"].append(target_result)

    json_path, txt_path = save_results(results)

    print("\n" + "=" * 70)
    print("FAST V3 ML TIME-SPLIT TEST COMPLETE")
    print("=" * 70)
    print(f"JSON results: {json_path}")
    print(f"Summary:      {txt_path}")

    print("\nDecision rule:")
    print("Do NOT adopt ML live unless it beats the existing momentum strategy")
    print("in realistic walk-forward testing.")


if __name__ == "__main__":
    main()