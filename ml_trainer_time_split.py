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
MODEL_FILE = f"{PERFORMANCE_DIR}/ai_stock_model_7d_time_split.pkl"

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
]

CATEGORICAL_FEATURES = [
    "sector",
    "market_regime",
]


def main():
    if not os.path.exists(TRAINING_FILE):
        print("Missing historical_training_data.csv. Run historical_trainer.py first.")
        return

    df = pd.read_csv(TRAINING_FILE)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

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
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=75,
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

    print("Training time-split ML model...")
    print(f"Training rows: {len(train_df)}")
    print(f"Testing rows: {len(test_df)}")
    print(f"Train through: {TRAIN_END_DATE}")
    print(f"Test from: {TEST_START_DATE}")

    pipeline.fit(X_train, y_train)

    probabilities = pipeline.predict_proba(X_test)[:, 1]

    # Use 0.55 threshold instead of 0.50 to make it more selective.
    threshold = 0.55
    predictions = probabilities >= threshold

    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions, zero_division=0)
    recall = recall_score(y_test, predictions, zero_division=0)
    auc = roc_auc_score(y_test, probabilities)

    print()
    print("TIME-SPLIT ML MODEL RESULTS")
    print("---------------------------")
    print(f"Threshold: {threshold}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"ROC AUC: {auc:.4f}")

    test_results = test_df[["date", "ticker", "sector", "market_regime", "future_7d_return", "future_7d_win"]].copy()
    test_results["predicted_probability"] = probabilities
    test_results["prediction"] = predictions

    output_predictions = f"{PERFORMANCE_DIR}/ml_time_split_predictions.csv"
    test_results.to_csv(output_predictions, index=False)

    joblib.dump(pipeline, MODEL_FILE)

    print()
    print(f"Model saved to: {MODEL_FILE}")
    print(f"Predictions saved to: {output_predictions}")

    print()
    print("Top 20 highest probability setups in test period:")
    print(
        test_results
        .sort_values("predicted_probability", ascending=False)
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()