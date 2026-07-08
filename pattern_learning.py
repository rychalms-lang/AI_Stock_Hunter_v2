import os
import pandas as pd

from settings import PERFORMANCE_DIR

TRAINING_FILE = f"{PERFORMANCE_DIR}/historical_training_data.csv"

HOLD_PERIODS = [1, 3, 5, 7, 10]


def load_training_data():
    if not os.path.exists(TRAINING_FILE):
        return None

    return pd.read_csv(TRAINING_FILE)


def bucket_value(value, bucket_size):
    try:
        return round(float(value) / bucket_size) * bucket_size
    except Exception:
        return None


def classify_setup(stock):
    """
    Converts a live stock setup into broad historical buckets.
    This avoids needing an exact match.
    """

    return {
        "sector": stock.get("sector", "Other / Uncategorized"),
        "market_regime": stock.get("market_regime", "Unknown"),
        "five_day_bucket": bucket_value(stock.get("five_day_change", 0), 5),
        "twenty_day_bucket": bucket_value(stock.get("twenty_day_change", 0), 10),
        "relative_strength_bucket": bucket_value(stock.get("relative_strength", 0), 10),
        "volume_bucket": bucket_value(stock.get("volume_ratio", 1), 0.5),
    }


def find_similar_setups(stock, min_matches=30):
    df = load_training_data()

    if df is None or df.empty:
        return None

    setup = classify_setup(stock)

    filtered = df.copy()

    # Start specific, then loosen if not enough matches.
    filters = [
        ("sector", setup["sector"]),
        ("market_regime", setup["market_regime"]),
    ]

    for column, value in filters:
        if value and column in filtered.columns:
            temp = filtered[filtered[column] == value]

            if len(temp) >= min_matches:
                filtered = temp

    # Numeric similarity filters.
    numeric_filters = [
        ("five_day_change", setup["five_day_bucket"], 5),
        ("twenty_day_change", setup["twenty_day_bucket"], 10),
        ("relative_strength", setup["relative_strength_bucket"], 10),
        ("volume_ratio", setup["volume_bucket"], 0.5),
    ]

    for column, bucket, tolerance in numeric_filters:
        if bucket is None or column not in filtered.columns:
            continue

        temp = filtered[
            (filtered[column] >= bucket - tolerance)
            & (filtered[column] <= bucket + tolerance)
        ]

        if len(temp) >= min_matches:
            filtered = temp

    if len(filtered) == 0:
        return None

    return filtered


def summarize_historical_performance(matches):
    if matches is None or len(matches) == 0:
        return {
            "historical_matches": 0,
            "best_hold_period": "Unknown",
            "best_avg_return": 0,
            "summary": "No historical matches found."
        }

    result = {
        "historical_matches": len(matches)
    }

    best_hold = None
    best_avg_return = -999

    for hold in HOLD_PERIODS:
        return_col = f"future_{hold}d_return"
        win_col = f"future_{hold}d_win"

        if return_col not in matches.columns:
            continue

        avg_return = matches[return_col].mean()
        median_return = matches[return_col].median()
        win_rate = matches[win_col].mean() * 100

        result[f"{hold}d_avg_return"] = round(avg_return, 2)
        result[f"{hold}d_median_return"] = round(median_return, 2)
        result[f"{hold}d_win_rate"] = round(win_rate, 2)

        if avg_return > best_avg_return:
            best_avg_return = avg_return
            best_hold = hold

    result["best_hold_period"] = f"{best_hold} days" if best_hold else "Unknown"
    result["best_avg_return"] = round(best_avg_return, 2)

    result["summary"] = (
        f"Found {len(matches)} similar historical setups. "
        f"Best historical hold period was {result['best_hold_period']} "
        f"with an average return of {result['best_avg_return']}%."
    )

    return result


def analyze_pattern(stock):
    matches = find_similar_setups(stock)
    return summarize_historical_performance(matches)