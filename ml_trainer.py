import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.ensemble import RandomForestClassifier

from settings import PERFORMANCE_DIR

TRAINING_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"
MODEL_FILE = f"{PERFORMANCE_DIR}/ai_stock_model_7d.pkl"

TARGET_COL = "future_7d_win"

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

    df = df.dropna(subset=NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COL])

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET_COL].astype(bool)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        shuffle=True
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )

    model = RandomForestClassifier(
        n_estimators=250,
        max_depth=8,
        min_samples_leaf=50,
        random_state=42,
        n_jobs=-1
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model)
        ]
    )

    print("Training ML model...")
    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)
    probabilities = pipeline.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions)
    recall = recall_score(y_test, predictions)
    auc = roc_auc_score(y_test, probabilities)

    print()
    print("ML MODEL RESULTS")
    print("----------------")
    print(f"Rows used: {len(df)}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"ROC AUC: {auc:.4f}")

    joblib.dump(pipeline, MODEL_FILE)

    print()
    print(f"Model saved to: {MODEL_FILE}")


if __name__ == "__main__":
    main()