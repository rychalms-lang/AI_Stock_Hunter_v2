from dataclasses import asdict, dataclass
from datetime import datetime, time
from typing import Dict, Optional
from zoneinfo import ZoneInfo


MARKET_TIMEZONE = ZoneInfo("America/New_York")


@dataclass
class MarketQuote:
    ticker: str
    price: Optional[float]
    previous_close: Optional[float]
    price_change_today: Optional[float]
    market_state: str
    last_price_update: str
    price_source: str
    price_status: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def market_state(now: Optional[datetime] = None) -> str:
    current = now or datetime.now(MARKET_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=MARKET_TIMEZONE)
    else:
        current = current.astimezone(MARKET_TIMEZONE)

    if current.weekday() >= 5:
        return "CLOSED"

    current_time = current.time()
    if time(4, 0) <= current_time < time(9, 30):
        return "PRE_MARKET"
    if time(9, 30) <= current_time < time(16, 0):
        return "OPEN"
    if time(16, 0) <= current_time < time(20, 0):
        return "AFTER_HOURS"
    return "CLOSED"


class MarketDataService:
    """
    Replaceable market-data boundary for scanner and paper-trading workflows.

    The initial provider uses yfinance because the project already depends on it.
    Later providers can implement the same get_quote interface.
    """

    def __init__(self, provider: str = "yfinance"):
        self.provider = provider
        self._cache: Dict[str, MarketQuote] = {}

    def get_market_state(self) -> str:
        return market_state()

    def get_quote(self, ticker: str) -> Dict[str, object]:
        normalized = ticker.upper()
        if normalized in self._cache:
            return self._cache[normalized].to_dict()

        quote = self._fetch_yfinance_quote(normalized)
        self._cache[normalized] = quote
        return quote.to_dict()

    def _fetch_yfinance_quote(self, ticker: str) -> MarketQuote:
        timestamp = datetime.now(MARKET_TIMEZONE).isoformat(timespec="seconds")
        state = self.get_market_state()

        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            fast_info = getattr(stock, "fast_info", {}) or {}
            price = self._read_fast_info(fast_info, "last_price")
            previous_close = self._read_fast_info(fast_info, "previous_close")

            if price is None:
                history = stock.history(period="5d")
                if not history.empty:
                    price = float(history["Close"].iloc[-1])
                    if len(history) >= 2 and previous_close is None:
                        previous_close = float(history["Close"].iloc[-2])

            if price is None or price <= 0:
                return MarketQuote(
                    ticker=ticker,
                    price=None,
                    previous_close=previous_close,
                    price_change_today=None,
                    market_state=state,
                    last_price_update=timestamp,
                    price_source=self.provider,
                    price_status="unavailable",
                    error="No valid market price returned.",
                )

            price_change_today = None
            if previous_close and previous_close > 0:
                price_change_today = round(((price / previous_close) - 1) * 100, 2)

            return MarketQuote(
                ticker=ticker,
                price=round(price, 2),
                previous_close=round(previous_close, 2) if previous_close else None,
                price_change_today=price_change_today,
                market_state=state,
                last_price_update=timestamp,
                price_source=self.provider,
                price_status="fresh",
            )

        except Exception as exc:
            return MarketQuote(
                ticker=ticker,
                price=None,
                previous_close=None,
                price_change_today=None,
                market_state=state,
                last_price_update=timestamp,
                price_source=self.provider,
                price_status="unavailable",
                error=str(exc),
            )

    @staticmethod
    def _read_fast_info(fast_info: object, key: str) -> Optional[float]:
        try:
            if isinstance(fast_info, dict):
                value = fast_info.get(key)
            else:
                value = getattr(fast_info, key)
            return float(value) if value is not None else None
        except Exception:
            return None
