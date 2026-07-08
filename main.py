import os
import smtplib
import pandas as pd
from datetime import datetime
from email.message import EmailMessage
from dotenv import dotenv_values

from settings import AI_CANDIDATE_LIMIT, REPORTS_DIR, PERFORMANCE_DIR
from scanner import scan_market
from market_regime import get_market_regime
from sector_strength import rank_sectors
from sector_map import get_sector
from confidence import calculate_confidence
from portfolio import build_portfolio
from reporter import create_text_report, create_html_report
from pattern_learning import analyze_pattern


config = dotenv_values(".env")

EMAIL_ADDRESS = config.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = config.get("EMAIL_PASSWORD")


def get_sector_rank(stock_sector, sector_rankings):
    sector_keywords = {
        "Semiconductors": "Semiconductors",
        "Healthcare": "Healthcare",
        "Industrials": "Industrials",
        "Financials": "Financials",
        "Energy": "Energy",
        "Utilities": "Utilities",
        "Materials": "Materials",
        "REITs": "Real Estate",
        "Consumer Defensive": "Consumer Staples",
        "Consumer Cyclical": "Consumer Discretionary",
        "Mega Cap Tech": "Technology",
        "Cloud Software": "Technology",
        "Software": "Technology",
        "Cybersecurity": "Technology",
        "AI / Data": "Technology",
        "AI / Healthcare": "Healthcare",
        "Gaming / Metaverse": "Technology",
        "EV / Consumer Tech": "Consumer Discretionary",
        "Canada / Banks": "Financials",
        "Canada / Energy": "Energy",
        "Canada / Mining": "Materials",
        "Canada / Materials": "Materials",
        "Canada / Uranium": "Materials",
        "Canada / Consumer Defensive": "Consumer Staples",
        "Canada / Industrials": "Industrials",
        "Canada / Tech": "Technology",
        "Canada / Utilities": "Utilities",
        "Canada / Pipelines": "Energy",
    }

    broad_sector = sector_keywords.get(stock_sector)

    if not broad_sector:
        return None

    for i, sector in enumerate(sector_rankings, start=1):
        if sector["sector"] == broad_sector:
            return i

    return None


def apply_historical_confidence_adjustment(confidence_data, pattern_data):
    historical_adjustment = 0
    historical_notes = []

    best_avg_return = pattern_data.get("best_avg_return", 0)
    historical_matches = pattern_data.get("historical_matches", 0)

    win_rates = [
        pattern_data.get("1d_win_rate", 0),
        pattern_data.get("3d_win_rate", 0),
        pattern_data.get("5d_win_rate", 0),
        pattern_data.get("7d_win_rate", 0),
        pattern_data.get("10d_win_rate", 0),
    ]

    best_win_rate = max(win_rates) if win_rates else 0

    if historical_matches < 30:
        historical_adjustment -= 10
        historical_notes.append("Low historical sample size")

    if best_avg_return >= 3:
        historical_adjustment += 15
        historical_notes.append("Strong historical average return")
    elif best_avg_return >= 1:
        historical_adjustment += 5
        historical_notes.append("Positive historical average return")
    elif best_avg_return < 0.5:
        historical_adjustment -= 15
        historical_notes.append("Weak historical average return")

    if best_win_rate >= 65:
        historical_adjustment += 10
        historical_notes.append("Strong historical win rate")
    elif best_win_rate >= 58:
        historical_adjustment += 5
        historical_notes.append("Positive historical win rate")
    elif best_win_rate < 50:
        historical_adjustment -= 10
        historical_notes.append("Weak historical win rate")

    confidence_data["confidence_score"] = max(
        0,
        min(100, confidence_data["confidence_score"] + historical_adjustment)
    )

    confidence_data["confidence_reasons"].extend([
        note for note in historical_notes
        if "Strong" in note or "Positive" in note
    ])

    confidence_data["risk_flags"].extend([
        note for note in historical_notes
        if "Weak" in note or "Low" in note
    ])

    return confidence_data


def add_final_scoring(scanned_stocks, market, sectors):
    enriched = []

    for stock in scanned_stocks[:AI_CANDIDATE_LIMIT]:
        sector = get_sector(stock["ticker"])
        sector_rank = get_sector_rank(sector, sectors)

        sentiment_score = 50
        sentiment_label = "Neutral"
        analysis_brief = "AI analysis module not connected yet in v2."

        pattern_data = analyze_pattern({
            **stock,
            "sector": sector,
            "market_regime": market["regime"]
        })

        confidence_data = calculate_confidence(
            stock,
            sentiment_score=sentiment_score,
            market_regime=market,
            sector_rank=sector_rank
        )

        confidence_data = apply_historical_confidence_adjustment(
            confidence_data,
            pattern_data
        )

        final_score = (
            stock["five_day_change"] * 0.35
            + stock["volume_ratio"] * 15
            + stock["relative_strength"] * 0.35
            + sentiment_score * 0.15
            + confidence_data["confidence_score"] * 0.10
            + pattern_data.get("best_avg_return", 0) * 0.75
        )

        enriched.append({
            **stock,
            "sector": sector,
            "sector_rank": sector_rank,
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "analysis_brief": analysis_brief,
            "confidence_score": confidence_data["confidence_score"],
            "confidence_reasons": confidence_data["confidence_reasons"],
            "risk_flags": confidence_data["risk_flags"],
            "historical_matches": pattern_data.get("historical_matches", 0),
            "best_hold_period": pattern_data.get("best_hold_period", "Unknown"),
            "best_avg_return": pattern_data.get("best_avg_return", 0),
            "historical_summary": pattern_data.get("summary", ""),
            "pattern_1d_avg_return": pattern_data.get("1d_avg_return", 0),
            "pattern_3d_avg_return": pattern_data.get("3d_avg_return", 0),
            "pattern_5d_avg_return": pattern_data.get("5d_avg_return", 0),
            "pattern_7d_avg_return": pattern_data.get("7d_avg_return", 0),
            "pattern_10d_avg_return": pattern_data.get("10d_avg_return", 0),
            "pattern_1d_win_rate": pattern_data.get("1d_win_rate", 0),
            "pattern_3d_win_rate": pattern_data.get("3d_win_rate", 0),
            "pattern_5d_win_rate": pattern_data.get("5d_win_rate", 0),
            "pattern_7d_win_rate": pattern_data.get("7d_win_rate", 0),
            "pattern_10d_win_rate": pattern_data.get("10d_win_rate", 0),
            "score": round(final_score, 2)
        })

    return sorted(enriched, key=lambda x: x["score"], reverse=True)


def save_outputs(ranked_stocks, market, sectors, portfolio):
    today = datetime.now().strftime("%Y-%m-%d")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(PERFORMANCE_DIR, exist_ok=True)

    text_report = create_text_report(market, sectors, ranked_stocks, portfolio)
    html_report = create_html_report(market, sectors, ranked_stocks, portfolio)

    txt_path = f"{REPORTS_DIR}/{today}_v2.txt"
    html_path = f"{REPORTS_DIR}/{today}_v2.html"
    csv_path = f"{REPORTS_DIR}/{today}_v2.csv"
    history_path = f"{PERFORMANCE_DIR}/picks_history_v2.csv"

    with open(txt_path, "w") as f:
        f.write(text_report)

    with open(html_path, "w") as f:
        f.write(html_report)

    df = pd.DataFrame(ranked_stocks)
    df.to_csv(csv_path, index=False)

    history_df = df.copy()
    history_df.insert(0, "date", today)

    if os.path.exists(history_path):
        existing = pd.read_csv(history_path)
        history_df = pd.concat([existing, history_df], ignore_index=True)

    history_df.to_csv(history_path, index=False)

    return text_report, html_report, txt_path, html_path, csv_path, history_path


def send_email(text_report, html_report):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Email not sent: missing EMAIL_ADDRESS or EMAIL_PASSWORD.")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    msg = EmailMessage()
    msg["Subject"] = f"AI Stock Hunter v2 Market Brief - {today}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS

    msg.set_content(text_report)
    msg.add_alternative(html_report, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print("HTML email sent successfully.")

    except Exception as e:
        print(f"Email failed: {e}")


def main():
    print("Starting AI Stock Hunter v2...")

    market = get_market_regime()
    print(f"Market Regime: {market['regime']} ({market['market_score']}/100)")

    sectors = rank_sectors()
    print("Top Sectors:")
    for sector in sectors[:5]:
        print(f"- {sector['sector']}: {sector['sector_score']}")

    scanned_stocks = scan_market()
    print(f"Stocks passed scanner: {len(scanned_stocks)}")

    ranked_stocks = add_final_scoring(scanned_stocks, market, sectors)

    portfolio = build_portfolio(ranked_stocks)

    text_report, html_report, txt_path, html_path, csv_path, history_path = save_outputs(
        ranked_stocks,
        market,
        sectors,
        portfolio
    )

    print(f"Text report saved: {txt_path}")
    print(f"HTML report saved: {html_path}")
    print(f"CSV saved: {csv_path}")
    print(f"History saved: {history_path}")

    print("\nTOP PICKS\n")
    for stock in ranked_stocks:
        print(
            f"{stock['ticker']} | "
            f"{stock['sector']} | "
            f"Score: {stock['score']} | "
            f"Confidence: {stock['confidence_score']}% | "
            f"Matches: {stock['historical_matches']} | "
            f"Best Hold: {stock['best_hold_period']} | "
            f"Best Avg Return: {stock['best_avg_return']}%"
        )

    send_email(text_report, html_report)


if __name__ == "__main__":
    main()