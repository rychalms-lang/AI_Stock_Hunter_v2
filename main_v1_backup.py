import os
import smtplib
import pandas as pd
from datetime import datetime
from email.message import EmailMessage

import yfinance as yf
from dotenv import dotenv_values
from openai import OpenAI

AI_CANDIDATE_LIMIT = 10
MIN_AVG_VOLUME = 1_000_000

config = dotenv_values(".env")

EMAIL_ADDRESS = config.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = config.get("EMAIL_PASSWORD")
OPENAI_API_KEY = config.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

today = datetime.now().strftime("%Y-%m-%d")

os.makedirs("reports", exist_ok=True)
os.makedirs("performance", exist_ok=True)

with open("tickers.txt", "r") as f:
    stocks = list(dict.fromkeys([line.strip().upper() for line in f if line.strip()]))

sector_map = {
    "AAPL": "Mega Cap Tech", "MSFT": "Mega Cap Tech", "GOOGL": "Mega Cap Tech",
    "META": "Mega Cap Tech", "AMZN": "Mega Cap Tech", "NFLX": "Mega Cap Tech",
    "TSLA": "EV / Consumer Tech",

    "NVDA": "Semiconductors", "AMD": "Semiconductors", "AVGO": "Semiconductors",
    "MU": "Semiconductors", "ARM": "Semiconductors", "TSM": "Semiconductors",
    "QCOM": "Semiconductors", "INTC": "Semiconductors", "SMCI": "Semiconductors",
    "MRVL": "Semiconductors", "ON": "Semiconductors", "MPWR": "Semiconductors",
    "KLAC": "Semiconductors", "LRCX": "Semiconductors", "AMAT": "Semiconductors",
    "CDNS": "Semiconductor Software", "SNPS": "Semiconductor Software",
    "ADI": "Semiconductors", "NXPI": "Semiconductors",

    "PLTR": "AI / Data", "AI": "AI / Data", "BBAI": "AI / Data",
    "SOUN": "AI / Data", "TEM": "AI / Healthcare", "PATH": "Automation / AI",

    "SNOW": "Cloud Software", "DDOG": "Cloud Software", "NET": "Cloud Software",
    "MDB": "Cloud Software", "ESTC": "Cloud Software", "DOCN": "Cloud Software",
    "CRM": "Cloud Software", "NOW": "Cloud Software", "ORCL": "Cloud Software",
    "SAP": "Cloud Software", "ADBE": "Software", "INTU": "Software",
    "WDAY": "Software", "GTLB": "Software", "ASAN": "Software", "TWLO": "Software",

    "OKTA": "Cybersecurity", "CRWD": "Cybersecurity", "PANW": "Cybersecurity",
    "ZS": "Cybersecurity", "S": "Cybersecurity",

    "SHOP": "E-Commerce", "UBER": "Consumer Platforms", "ABNB": "Consumer Platforms",
    "RBLX": "Gaming / Metaverse", "SE": "International Tech", "ROKU": "Streaming / Ads",
    "DUOL": "Consumer Apps", "APP": "Ad Tech", "TTD": "Ad Tech",
    "PINS": "Social Media", "SPOT": "Streaming", "HIMS": "Consumer Health",
    "CELH": "Consumer Staples Growth",

    "HOOD": "Fintech / Crypto", "SOFI": "Fintech", "COIN": "Crypto", "MSTR": "Crypto",

    "RKLB": "Space", "LUNR": "Space", "ASTS": "Space",
    "ACHR": "Aviation / eVTOL", "JOBY": "Aviation / eVTOL",

    "LMT": "Defense", "RTX": "Defense", "NOC": "Defense", "GD": "Defense",
    "HII": "Defense", "KTOS": "Defense", "BA": "Aerospace",

    "GE": "Industrials", "GEV": "Energy Infrastructure", "CAT": "Industrials",
    "DE": "Industrials", "ETN": "Industrials", "PH": "Industrials",
    "HON": "Industrials", "MMM": "Industrials", "UPS": "Transports",
    "FDX": "Transports", "UNP": "Transports", "CSX": "Transports",

    "JPM": "Financials", "GS": "Financials", "MS": "Financials",
    "BAC": "Financials", "WFC": "Financials", "BLK": "Financials",
    "SCHW": "Financials", "KKR": "Financials", "BX": "Financials",
    "V": "Payments", "MA": "Payments", "AXP": "Payments",
    "COF": "Financials", "C": "Financials", "USB": "Financials", "PNC": "Financials",

    "LLY": "Healthcare", "NVO": "Healthcare", "UNH": "Healthcare",
    "ISRG": "Healthcare", "VRTX": "Healthcare", "ABBV": "Healthcare",
    "MRK": "Healthcare", "PFE": "Healthcare", "TMO": "Healthcare",
    "DHR": "Healthcare", "BSX": "Healthcare", "SYK": "Healthcare",
    "MDT": "Healthcare", "ABT": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",

    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    "HAL": "Energy", "EOG": "Energy", "OXY": "Energy", "MPC": "Energy",
    "PSX": "Energy", "VLO": "Energy", "LNG": "Energy", "WMB": "Energy", "KMI": "Energy",

    "COST": "Consumer Defensive", "WMT": "Consumer Defensive", "TGT": "Consumer Defensive",
    "HD": "Consumer Cyclical", "LOW": "Consumer Cyclical", "SBUX": "Consumer Cyclical",
    "MCD": "Consumer Defensive", "CMG": "Consumer Cyclical", "NKE": "Consumer Cyclical",
    "TJX": "Consumer Cyclical", "BKNG": "Travel", "MAR": "Travel",
    "DIS": "Entertainment", "LULU": "Consumer Cyclical", "EL": "Consumer Defensive",

    "FCX": "Materials", "NEM": "Gold / Materials", "LIN": "Materials",
    "APD": "Materials", "MLM": "Materials", "VMC": "Materials",
    "NUE": "Steel", "STLD": "Steel", "AA": "Aluminum", "MOS": "Agriculture / Materials",

    "NEE": "Utilities", "SO": "Utilities", "DUK": "Utilities", "AEP": "Utilities",
    "XEL": "Utilities", "CEG": "Utilities / Nuclear", "PEG": "Utilities", "SRE": "Utilities",

    "PLD": "REITs", "EQIX": "REITs", "AMT": "REITs", "O": "REITs",
    "SPG": "REITs", "PSA": "REITs", "DLR": "REITs", "WELL": "REITs",

    "RY.TO": "Canada / Banks", "TD.TO": "Canada / Banks", "BMO.TO": "Canada / Banks",
    "CM.TO": "Canada / Banks", "NA.TO": "Canada / Banks",

    "CNQ.TO": "Canada / Energy", "SU.TO": "Canada / Energy", "CVE.TO": "Canada / Energy",
    "TOU.TO": "Canada / Energy", "ARX.TO": "Canada / Energy",

    "AEM.TO": "Canada / Mining", "ABX.TO": "Canada / Mining", "WPM.TO": "Canada / Mining",
    "FNV.TO": "Canada / Mining", "NTR.TO": "Canada / Materials", "CCO.TO": "Canada / Uranium",

    "CP.TO": "Canada / Rail", "CNR.TO": "Canada / Rail",
    "ATD.TO": "Canada / Consumer Defensive", "TFII.TO": "Canada / Transport",
    "WSP.TO": "Canada / Industrials",

    "SHOP.TO": "Canada / Tech", "CSU.TO": "Canada / Tech", "DSG.TO": "Canada / Tech",
    "OTEX.TO": "Canada / Tech", "KXS.TO": "Canada / Tech", "LSPD.TO": "Canada / Tech",

    "BCE.TO": "Canada / Telecom", "T.TO": "Canada / Telecom", "RCI-B.TO": "Canada / Telecom",

    "DOL.TO": "Canada / Consumer Defensive", "EMP-A.TO": "Canada / Consumer Defensive",
    "MRU.TO": "Canada / Consumer Defensive",

    "ENB.TO": "Canada / Pipelines", "TRP.TO": "Canada / Pipelines",
    "PPL.TO": "Canada / Pipelines", "EMA.TO": "Canada / Utilities", "FTS.TO": "Canada / Utilities",

    "SPY": "Market ETF", "QQQ": "Market ETF", "IWM": "Market ETF", "DIA": "Market ETF",
    "SMH": "Sector ETF", "SOXX": "Sector ETF", "XLF": "Sector ETF", "XLV": "Sector ETF",
    "XLE": "Sector ETF", "XLI": "Sector ETF", "XLY": "Sector ETF", "XLP": "Sector ETF",
    "XLU": "Sector ETF", "XLB": "Sector ETF", "XLRE": "Sector ETF",
}


def get_sector(ticker):
    return sector_map.get(ticker, "Other / Uncategorized")


def get_company_profile(ticker):
    try:
        info = yf.Ticker(ticker).info
        name = info.get("longName", ticker)
        industry = info.get("industry", "Unknown industry")
        business_summary = info.get("longBusinessSummary", "")

        if business_summary:
            business_summary = business_summary[:700]

        return name, industry, business_summary

    except Exception:
        return ticker, "Unknown industry", ""


def get_headlines(ticker):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news

        headlines = []

        for item in news[:5]:
            title = ""

            if "content" in item and isinstance(item["content"], dict):
                title = item["content"].get("title", "")

            if not title:
                title = item.get("title", "")

            if title:
                headlines.append(title)

        return headlines

    except Exception as e:
        print(f"News failed for {ticker}: {e}")
        return []


def ai_stock_analysis(ticker, sector, metrics, headlines):
    if not OPENAI_API_KEY:
        return 50, "Neutral", "No OpenAI API key found, so no AI stock brief was generated."

    company_name, industry, business_summary = get_company_profile(ticker)

    headline_text = chr(10).join("- " + h for h in headlines) if headlines else "No recent headlines found."

    prompt = f"""
You are writing a concise trader-focused stock brief.

Ticker: {ticker}
Company: {company_name}
Sector Category: {sector}
Industry: {industry}

Company Description:
{business_summary}

Metrics:
Open Price: {metrics["latest_open"]}
Close Price: {metrics["latest_close"]}
Open-to-Close Change: {metrics["open_to_close_change"]}%
5-Day Change: {metrics["five_day_change"]}%
20-Day Change: {metrics["twenty_day_change"]}%
Volume Ratio: {metrics["volume_ratio"]}x
Relative Strength vs SPY: {metrics["relative_strength"]}%

Recent Headlines:
{headline_text}

Return your response in this exact format:

SCORE: number from 0 to 100
LABEL: Bullish, Neutral, or Bearish
BRIEF: 4-6 concise sentences covering:
- what the company does
- why it may be moving
- the bullish case
- the main risk/caution
- what to watch next

Do not recommend buying or selling.
Do not use hype.
Be realistic and practical.
"""

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        text = response.output_text.strip()

        score = 50
        label = "Neutral"
        brief = text

        for line in text.splitlines():
            if line.startswith("SCORE:"):
                score = float(line.replace("SCORE:", "").strip())
            elif line.startswith("LABEL:"):
                label = line.replace("LABEL:", "").strip()
            elif line.startswith("BRIEF:"):
                brief = line.replace("BRIEF:", "").strip()

        score = max(0, min(100, score))

        if label not in ["Bullish", "Neutral", "Bearish"]:
            label = "Neutral"

        if "BRIEF:" in text:
            brief = text.split("BRIEF:", 1)[1].strip()

        return score, label, brief

    except Exception as e:
        print(f"AI analysis failed for {ticker}: {e}")
        return 50, "Neutral", "AI analysis failed. Basic price and volume signals are still included."


def calculate_confidence(stock, sentiment_score):
    confidence = 50
    reasons = []
    risks = []

    if stock["five_day_change"] > 5:
        confidence += 10
        reasons.append("Strong 5-day momentum")

    if stock["twenty_day_change"] > 10:
        confidence += 10
        reasons.append("Strong 20-day trend")

    if stock["relative_strength"] > 10:
        confidence += 10
        reasons.append("Strong relative strength vs SPY")

    if stock["volume_ratio"] > 1.2:
        confidence += 10
        reasons.append("Above-average volume confirmation")

    if stock["open_to_close_change"] > 1:
        confidence += 10
        reasons.append("Positive open-to-close action")

    if sentiment_score >= 70:
        confidence += 10
        reasons.append("Bullish AI news analysis")

    if stock["twenty_day_change"] > 40:
        confidence -= 10
        risks.append("Very extended 20-day move")

    if stock["open_to_close_change"] < -1:
        confidence -= 10
        risks.append("Weak intraday close")

    if sentiment_score <= 40:
        confidence -= 15
        risks.append("Bearish AI news analysis")

    if stock["volume_ratio"] > 4:
        confidence -= 5
        risks.append("Extreme volume spike may indicate exhaustion")

    confidence = max(0, min(100, confidence))

    if not reasons:
        reasons.append("No major confirmation signals")

    if not risks:
        risks.append("No major risk flags detected")

    return confidence, reasons, risks


spy = yf.Ticker("SPY").history(period="3mo")
spy_return = ((spy["Close"].iloc[-1] / spy["Close"].iloc[-20]) - 1) * 100

preliminary_results = []

for ticker in stocks:
    try:
        hist = yf.Ticker(ticker).history(period="3mo")

        if len(hist) < 20:
            continue

        latest_open = hist["Open"].iloc[-1]
        latest_close = hist["Close"].iloc[-1]
        current = latest_close

        five_day = hist["Close"].iloc[-5]
        twenty_day = hist["Close"].iloc[-20]

        momentum = ((current / five_day) - 1) * 100
        stock_return = ((current / twenty_day) - 1) * 100
        relative_strength = stock_return - spy_return

        open_to_close_change = ((latest_close / latest_open) - 1) * 100
        five_day_change = momentum
        twenty_day_change = stock_return

        avg_volume = hist["Volume"].tail(20).mean()
        today_volume = hist["Volume"].iloc[-1]

        if avg_volume < MIN_AVG_VOLUME:
            continue

        volume_ratio = today_volume / avg_volume

        if momentum <= 0:
            continue

        pre_score = (
            momentum * 0.5
            + volume_ratio * 20
            + relative_strength * 0.5
        )

        preliminary_results.append({
            "ticker": ticker,
            "sector": get_sector(ticker),
            "latest_open": round(latest_open, 2),
            "latest_close": round(latest_close, 2),
            "open_to_close_change": round(open_to_close_change, 2),
            "five_day_change": round(five_day_change, 2),
            "twenty_day_change": round(twenty_day_change, 2),
            "momentum": round(momentum, 2),
            "volume_ratio": round(volume_ratio, 2),
            "relative_strength": round(relative_strength, 2),
            "avg_volume": round(avg_volume, 0),
            "pre_score": round(pre_score, 2)
        })

    except Exception as e:
        print(f"Error with {ticker}: {e}")

preliminary_results = sorted(
    preliminary_results,
    key=lambda x: x["pre_score"],
    reverse=True
)

top_candidates = preliminary_results[:AI_CANDIDATE_LIMIT]

print(f"Stocks loaded: {len(stocks)}")
print(f"Passed filters: {len(preliminary_results)}")
print(f"AI analysis calls: {len(top_candidates)}")

results = []

for stock in top_candidates:
    ticker = stock["ticker"]

    headlines = get_headlines(ticker)

    metrics = {
        "latest_open": stock["latest_open"],
        "latest_close": stock["latest_close"],
        "open_to_close_change": stock["open_to_close_change"],
        "five_day_change": stock["five_day_change"],
        "twenty_day_change": stock["twenty_day_change"],
        "volume_ratio": stock["volume_ratio"],
        "relative_strength": stock["relative_strength"],
    }

    sentiment_score, sentiment_label, analysis_brief = ai_stock_analysis(
        ticker,
        stock["sector"],
        metrics,
        headlines
    )

    confidence_score, confidence_reasons, risk_flags = calculate_confidence(
        stock,
        sentiment_score
    )

    final_score = (
        stock["momentum"] * 0.35
        + stock["volume_ratio"] * 15
        + stock["relative_strength"] * 0.35
        + sentiment_score * 0.15
    )

    results.append({
        "ticker": ticker,
        "sector": stock["sector"],
        "latest_open": stock["latest_open"],
        "latest_close": stock["latest_close"],
        "open_to_close_change": stock["open_to_close_change"],
        "five_day_change": stock["five_day_change"],
        "twenty_day_change": stock["twenty_day_change"],
        "momentum": stock["momentum"],
        "volume_ratio": stock["volume_ratio"],
        "relative_strength": stock["relative_strength"],
        "avg_volume": stock["avg_volume"],
        "sentiment_score": round(sentiment_score, 2),
        "sentiment_label": sentiment_label,
        "confidence_score": confidence_score,
        "confidence_reasons": " | ".join(confidence_reasons),
        "risk_flags": " | ".join(risk_flags),
        "score": round(final_score, 2),
        "analysis_brief": analysis_brief,
        "headline_1": headlines[0] if len(headlines) > 0 else "",
        "headline_2": headlines[1] if len(headlines) > 1 else "",
        "headline_3": headlines[2] if len(headlines) > 2 else ""
    })

results = sorted(
    results,
    key=lambda x: x["score"],
    reverse=True
)

df = pd.DataFrame(results)

csv_path = f"reports/{today}.csv"
df.to_csv(csv_path, index=False)

history_path = "performance/picks_history.csv"
history_df = df.copy()
history_df.insert(0, "date", today)

if os.path.exists(history_path):
    existing = pd.read_csv(history_path)
    history_df = pd.concat([existing, history_df], ignore_index=True)

history_df.to_csv(history_path, index=False)

sector_counts = {}

for stock in results:
    sector = stock["sector"]
    sector_counts[sector] = sector_counts.get(sector, 0) + 1

sector_summary = sorted(
    sector_counts.items(),
    key=lambda x: x[1],
    reverse=True
)

report_path = f"reports/{today}.txt"

with open(report_path, "w") as file:
    file.write("AI STOCK HUNTER REPORT\n")
    file.write(f"Date: {today}\n")
    file.write(f"Stocks loaded: {len(stocks)}\n")
    file.write(f"Passed filters: {len(preliminary_results)}\n")
    file.write(f"AI analysis calls: {len(top_candidates)}\n")
    file.write(f"Minimum average volume: {MIN_AVG_VOLUME:,}\n\n")

    file.write("TOP SECTORS IN FINAL PICKS\n")

    for sector, count in sector_summary:
        file.write(f"- {sector}: {count}\n")

    file.write("\nTOP PICKS\n\n")

    for i, stock in enumerate(results, start=1):
        file.write(
            f"{i}. {stock['ticker']} ({stock['sector']})\n"
            f"Score: {stock['score']}\n"
            f"Confidence: {stock['confidence_score']}%\n"
            f"Open: ${stock['latest_open']}\n"
            f"Close: ${stock['latest_close']}\n"
            f"Open-to-Close: {stock['open_to_close_change']}%\n"
            f"5-Day Change: {stock['five_day_change']}%\n"
            f"20-Day Change: {stock['twenty_day_change']}%\n"
            f"Momentum: {stock['momentum']}%\n"
            f"Volume: {stock['volume_ratio']}x\n"
            f"Avg Volume: {stock['avg_volume']:,}\n"
            f"Relative Strength: {stock['relative_strength']}%\n"
            f"AI News Sentiment: {stock['sentiment_label']} ({stock['sentiment_score']})\n\n"
            f"Why It Ranked:\n"
        )

        for reason in stock["confidence_reasons"].split(" | "):
            file.write(f"- {reason}\n")

        file.write("\nRisk Flags:\n")

        for risk in stock["risk_flags"].split(" | "):
            file.write(f"- {risk}\n")

        file.write(f"\nStock Brief:\n{stock['analysis_brief']}\n")

        if stock["headline_1"]:
            file.write("\nRecent Headlines:\n")
            file.write(f"- {stock['headline_1']}\n")

        if stock["headline_2"]:
            file.write(f"- {stock['headline_2']}\n")

        if stock["headline_3"]:
            file.write(f"- {stock['headline_3']}\n")

        file.write("\n" + "-" * 60 + "\n\n")

print(f"CSV saved to: {csv_path}")
print(f"Performance history saved to: {history_path}")
print(f"Report saved to: {report_path}")

print("\nTOP SECTORS\n")

for sector, count in sector_summary:
    print(f"{sector}: {count}")

print("\nTOP PICKS\n")

for stock in results:
    print(
        f"{stock['ticker']} | "
        f"{stock['sector']} | "
        f"Score: {stock['score']} | "
        f"Confidence: {stock['confidence_score']}% | "
        f"O/C: {stock['open_to_close_change']}% | "
        f"5D: {stock['five_day_change']}% | "
        f"20D: {stock['twenty_day_change']}% | "
        f"AI: {stock['sentiment_label']} ({stock['sentiment_score']})"
    )

if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
    print("Email not sent: missing credentials.")
else:
    msg = EmailMessage()
    msg["Subject"] = f"AI Stock Hunter Report - {today}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS

    with open(report_path, "r") as file:
        msg.set_content(file.read())

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print("Email sent successfully.")

    except Exception as e:
        print(f"Email failed: {e}")