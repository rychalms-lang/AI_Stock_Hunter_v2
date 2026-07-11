from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, time
from typing import Dict, Iterable, Optional
from zoneinfo import ZoneInfo


MARKET_TIMEZONE = ZoneInfo("America/New_York")
LIVE_STATUSES = {"LIVE", "DELAYED"}
STALE_AFTER_SECONDS = 30 * 60


@dataclass
class MarketQuote:
    ticker: str
    current_price: Optional[float]
    previous_close: Optional[float]
    price_change: Optional[float]
    price_change_pct: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    day_open: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]
    volume: Optional[int]
    quote_timestamp: str
    provider_timestamp: Optional[str]
    market_state: str
    source: str
    delay_seconds: Optional[int]
    price_age_seconds: Optional[int]
    price_status: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        # Backward-compatible aliases used by the existing paper ledger.
        payload["price"] = self.current_price
        payload["price_change_today"] = self.price_change_pct
        payload["last_price_update"] = self.provider_timestamp or self.quote_timestamp
        payload["price_source"] = self.source
        return payload


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def get_market_state(self, now: Optional[datetime] = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, ticker: str) -> MarketQuote:
        raise NotImplementedError

    def get_quotes(self, tickers: Iterable[str]) -> Dict[str, MarketQuote]:
        return {ticker.upper(): self.get_quote(ticker) for ticker in tickers}


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


def _round_money(value: Optional[float]) -> Optional[float]:
    return round(value, 2) if value is not None else None


def _round_pct(value: Optional[float]) -> Optional[float]:
    return round(value, 2) if value is not None else None


def _safe_float(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        result = float(value)
        if result != result or result in {float("inf"), float("-inf")}:
            return None
        return result
    except Exception:
        return None


def _safe_int(value: object) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _parse_timestamp(value: object) -> Optional[datetime]:
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif hasattr(value, "to_pydatetime"):
            parsed = value.to_pydatetime()
        else:
            parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=MARKET_TIMEZONE)
        return parsed.astimezone(MARKET_TIMEZONE)
    except Exception:
        return None


class YFinanceMarketDataProvider(MarketDataProvider):
    name = "yfinance"

    def __init__(self, stale_after_seconds: int = STALE_AFTER_SECONDS):
        self.stale_after_seconds = stale_after_seconds

    def get_market_state(self, now: Optional[datetime] = None) -> str:
        return market_state(now)

    def get_quote(self, ticker: str) -> MarketQuote:
        normalized = ticker.upper()
        request_time = datetime.now(MARKET_TIMEZONE)
        request_timestamp = request_time.isoformat(timespec="seconds")
        state = self.get_market_state(request_time)

        try:
            import yfinance as yf

            stock = yf.Ticker(normalized)
            fast_info = getattr(stock, "fast_info", {}) or {}

            current_price = self._read_fast_info(fast_info, "last_price")
            previous_close = self._read_fast_info(fast_info, "previous_close")
            day_open = self._read_fast_info(fast_info, "open")
            day_high = self._read_fast_info(fast_info, "day_high")
            day_low = self._read_fast_info(fast_info, "day_low")
            volume = _safe_int(self._read_fast_info(fast_info, "last_volume"))
            bid = None
            ask = None
            provider_time = None

            info = {}
            try:
                info = getattr(stock, "info", {}) or {}
            except Exception:
                info = {}
            if isinstance(info, dict):
                bid = _safe_float(info.get("bid"))
                ask = _safe_float(info.get("ask"))
                volume = volume or _safe_int(info.get("volume"))

            history = None
            if current_price is None or provider_time is None:
                try:
                    history = stock.history(period="1d", interval="1m", prepost=True)
                except Exception:
                    history = None
                if history is not None and not history.empty:
                    latest = history.iloc[-1]
                    if current_price is None:
                        current_price = _safe_float(latest.get("Close"))
                    if day_open is None:
                        day_open = _safe_float(history["Open"].dropna().iloc[0]) if not history["Open"].dropna().empty else None
                    if day_high is None:
                        day_high = _safe_float(history["High"].max())
                    if day_low is None:
                        day_low = _safe_float(history["Low"].min())
                    if volume is None:
                        volume = _safe_int(latest.get("Volume"))
                    provider_time = _parse_timestamp(history.index[-1])

            if current_price is None:
                try:
                    history = stock.history(period="5d")
                except Exception:
                    history = None
                if history is not None and not history.empty:
                    current_price = _safe_float(history["Close"].iloc[-1])
                    provider_time = provider_time or _parse_timestamp(history.index[-1])
                    if previous_close is None and len(history) >= 2:
                        previous_close = _safe_float(history["Close"].iloc[-2])

            return self._build_quote(
                ticker=normalized,
                current_price=current_price,
                previous_close=previous_close,
                bid=bid,
                ask=ask,
                day_open=day_open,
                day_high=day_high,
                day_low=day_low,
                volume=volume,
                request_time=request_time,
                provider_time=provider_time,
                state=state,
            )
        except Exception as exc:
            return self._unavailable_quote(normalized, request_timestamp, state, str(exc))

    def _build_quote(
        self,
        ticker: str,
        current_price: Optional[float],
        previous_close: Optional[float],
        bid: Optional[float],
        ask: Optional[float],
        day_open: Optional[float],
        day_high: Optional[float],
        day_low: Optional[float],
        volume: Optional[int],
        request_time: datetime,
        provider_time: Optional[datetime],
        state: str,
    ) -> MarketQuote:
        request_timestamp = request_time.isoformat(timespec="seconds")
        provider_timestamp = provider_time.isoformat(timespec="seconds") if provider_time else None
        price_age = (
            max(0, int((request_time - provider_time).total_seconds()))
            if provider_time
            else None
        )

        if current_price is None or current_price <= 0:
            return self._unavailable_quote(ticker, request_timestamp, state, "No valid market price returned.")

        price_change = None
        price_change_pct = None
        if previous_close and previous_close > 0:
            price_change = current_price - previous_close
            price_change_pct = ((current_price / previous_close) - 1) * 100

        if state == "CLOSED":
            status = "MARKET_CLOSED"
        elif price_age is not None and price_age > self.stale_after_seconds:
            status = "STALE"
        else:
            # yfinance does not provide a real-time quote contract here, so do
            # not present usable intraday data as real time.
            status = "DELAYED"

        return MarketQuote(
            ticker=ticker,
            current_price=_round_money(current_price),
            previous_close=_round_money(previous_close),
            price_change=_round_money(price_change),
            price_change_pct=_round_pct(price_change_pct),
            bid=_round_money(bid),
            ask=_round_money(ask),
            day_open=_round_money(day_open),
            day_high=_round_money(day_high),
            day_low=_round_money(day_low),
            volume=volume,
            quote_timestamp=request_timestamp,
            provider_timestamp=provider_timestamp,
            market_state=state,
            source=self.name,
            delay_seconds=None,
            price_age_seconds=price_age,
            price_status=status,
        )

    def _unavailable_quote(self, ticker: str, timestamp: str, state: str, error: str) -> MarketQuote:
        return MarketQuote(
            ticker=ticker,
            current_price=None,
            previous_close=None,
            price_change=None,
            price_change_pct=None,
            bid=None,
            ask=None,
            day_open=None,
            day_high=None,
            day_low=None,
            volume=None,
            quote_timestamp=timestamp,
            provider_timestamp=None,
            market_state=state,
            source=self.name,
            delay_seconds=None,
            price_age_seconds=None,
            price_status="UNAVAILABLE",
            error=error,
        )

    @staticmethod
    def _read_fast_info(fast_info: object, key: str) -> Optional[float]:
        try:
            if isinstance(fast_info, dict):
                value = fast_info.get(key)
            else:
                value = getattr(fast_info, key)
            return _safe_float(value)
        except Exception:
            return None


class MarketDataService:
    """
    Replaceable market-data boundary for scanner-adjacent and paper workflows.

    The default provider uses yfinance as a fallback source. Its usable intraday
    quotes are treated as DELAYED unless a future provider has a real-time
    contract and can explicitly report LIVE.
    """

    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.provider = provider or YFinanceMarketDataProvider()
        self._cache: Dict[str, MarketQuote] = {}

    def get_market_state(self) -> str:
        return self.provider.get_market_state()

    def get_quote(self, ticker: str) -> Dict[str, object]:
        normalized = ticker.upper()
        if normalized not in self._cache:
            self._cache[normalized] = self.provider.get_quote(normalized)
        return self._cache[normalized].to_dict()

    def get_quotes(self, tickers: Iterable[str]) -> Dict[str, Dict[str, object]]:
        results: Dict[str, Dict[str, object]] = {}
        for ticker in tickers:
            normalized = ticker.upper()
            if normalized:
                results[normalized] = self.get_quote(normalized)
        return results


def is_usable_price_status(status: object) -> bool:
    return str(status).upper() in LIVE_STATUSES or str(status).lower() in {"fresh", "delayed"}
