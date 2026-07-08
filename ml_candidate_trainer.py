import os
import joblib
import pandas as pd

from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.ensemble import RandomForestClassifier

from settings import PERFORMANCE_DIR

TRAINING_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"
MODEL_FILE = f"{PERFORMANCE_DIR}/ai_candidate_model_7d.pkl"
PREDICTIONS_FILE = f"{PERFORMANCE_DIR}/ml_candidate_predictions.csv"

TARGET_COL = "future_7d_win"
DATE_COL = "date"

TRAIN_END_DATE = "2024-12-31"
TEST_START_DATE = "2025-01-01"

NUMERIC_FEATURES = [
    "five_day_change",
    "twenty_day_change",
    "relative_strength",
    "open_to_close_change",
    "volume_ratio",
    "market_regime_score",
    "pre_score",
]

CATEGORICAL_FEATURES = [
    "sector",
    "market_regime",
]


def filter_scanner_candidates(df):
    df = df.copy()

    df = df[df["five_day_change"] > 0]
    df = df[df["market_regime"] == "Risk-On"]
    df = df[df["twenty_day_change"] <= 50]
    df = df[df["volume_ratio"] >= 0.75]

    return df


def main():
    if not os.path.exists(TRAINING_FILE):
        print("Missing historical_training_data.csv. Run historical_trainer.py first.")
        return

    df = pd.read_csv(TRAINING_FILE)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    df = filter_scanner_candidates(df)

    df = df.dropna(subset=NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COL])

    train_df = df[df[DATE_COL] <= TRAIN_END_DATE].copy()
    test_df = df[df[DATE_COL] >= TEST_START_DATE].copy()

    X_train = train_df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y_train = train_df[TARGET_COL].astype(bool)

    X_test = test_df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y_test = test_df[TARGET_COL].astype(bool)

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )

    model = RandomForestClassifier(
        n_estimators=400,
        max_depth=6,
        min_samples_leaf=100,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model)
        ]
    )

    print("Training candidate-only ML model...")
    print(f"Training rows: {len(train_df)}")
    print(f"Testing rows: {len(test_df)}")

    pipeline.fit(X_train, y_train)

    probabilities = pipeline.predict_proba(X_test)[:, 1]

    thresholds = [0.50, 0.55, 0.60, 0.65]

    print()
    print("CANDIDATE-ONLY ML RESULTS")
    print("-------------------------")
    print(f"ROC AUC: {roc_auc_score(y_test, probabilities):.4f}")
    print()

    for threshold in thresholds:
        predictions = probabilities >= threshold

        accuracy = accuracy_score(y_test, predictions)
        precision = precision_score(y_test, predictions, zero_division=0)
        recall = recall_score(y_test, predictions, zero_division=0)

        selected = predictions.sum()

        print(f"Threshold: {threshold}")
        print(f"Selected setups: {selected}")
        print(f"Accuracy: {accuracy:.4f}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall: {recall:.4f}")
        print("")

    test_results = test_df[
        [
            "date",
            "ticker",
            "sector",
            "market_regime",
            "five_day_change",
            "twenty_day_change",
            "relative_strength",
            "volume_ratio",
            "pre_score",
            "future_7d_return",
            "future_7d_win",
        ]
    ].copy()

    test_results["predicted_probability"] = probabilities
    test_results.to_csv(PREDICTIONS_FILE, index=False)

    joblib.dump(pipeline, MODEL_FILE)

    print(f"Model saved to: {MODEL_FILE}")
    print(f"Predictions saved to: {PREDICTIONS_FILE}")

    print()
    print("Top 20 candidate predictions:")
    print(
        test_results
        .sort_values("predicted_probability", ascending=False)
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()