import { MarketQuote, MarketSnapshot, quoteForTicker, usableQuoteStatus } from "./marketSnapshot";
import { OpenPosition, PaperTradingData } from "./paperTrading";

export type DisplayPosition = OpenPosition & {
  display_current_price: number;
  display_market_value: number;
  display_unrealized_pnl: number;
  display_unrealized_return_pct: number;
  display_price_change_today: number | null;
  display_price_change_today_pct: number | null;
  display_quote_timestamp: string | null;
  display_price_status: string;
  display_price_source: string;
  display_uses_live_quote: boolean;
};

export type DisplayPortfolioValuation = {
  positions: DisplayPosition[];
  cash: number;
  realized_pnl: number;
  display_invested_value: number;
  display_total_equity: number;
  display_unrealized_pnl: number;
  display_total_return_pct: number;
  display_cash_pct: number;
  display_invested_pct: number;
  display_day_pnl: number | null;
  display_day_return_pct: number | null;
  usable_quote_count: number;
  missing_quote_count: number;
  latest_quote_timestamp: string | null;
  price_status: string;
};

function num(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function roundMoney(value: number) {
  return Math.round(value * 100) / 100;
}

function roundPct(value: number) {
  return Math.round(value * 100) / 100;
}

function quoteTimestamp(quote: MarketQuote | null) {
  return quote?.provider_timestamp ?? quote?.quote_timestamp ?? null;
}

function usableQuote(quote: MarketQuote | null) {
  return quote && usableQuoteStatus(quote.price_status) && typeof quote.current_price === "number";
}

function displayPosition(position: OpenPosition, quote: MarketQuote | null): DisplayPosition {
  const quantity = num(position.quantity);
  const costBasis = num(position.cost_basis, num(position.notional_cost));
  const hasUsableQuote = Boolean(usableQuote(quote));
  const displayPrice = hasUsableQuote
    ? num(quote?.current_price)
    : num(position.current_price);
  const marketValue = roundMoney(quantity * displayPrice);
  const unrealizedPnl = roundMoney(marketValue - costBasis);
  const unrealizedReturnPct = costBasis > 0 ? roundPct((unrealizedPnl / costBasis) * 100) : 0;

  return {
    ...position,
    display_current_price: roundMoney(displayPrice),
    display_market_value: marketValue,
    display_unrealized_pnl: unrealizedPnl,
    display_unrealized_return_pct: unrealizedReturnPct,
    display_price_change_today: hasUsableQuote ? quote?.price_change ?? null : null,
    display_price_change_today_pct: hasUsableQuote
      ? quote?.price_change_pct ?? null
      : position.price_change_today ?? null,
    display_quote_timestamp: hasUsableQuote
      ? quoteTimestamp(quote)
      : position.last_price_update ?? null,
    display_price_status: hasUsableQuote
      ? quote?.price_status ?? "UNAVAILABLE"
      : "LAST_LEDGER_PRICE",
    display_price_source: hasUsableQuote ? quote?.source ?? "market_snapshot" : "ledger",
    display_uses_live_quote: hasUsableQuote,
  };
}

export function deriveDisplayValuation(
  data: PaperTradingData,
  marketSnapshot: MarketSnapshot | null
): DisplayPortfolioValuation {
  const summary = data.portfolioSummary.summary;
  const startingCapital = num(data.portfolioSummary.account?.starting_capital, 25000);
  const cash = num(summary.cash);
  const realizedPnl = num(summary.realized_pnl);
  const positions = (data.openPositions.positions ?? []).map((position) =>
    displayPosition(position, quoteForTicker(marketSnapshot, position.ticker))
  );

  const invested = roundMoney(
    positions.reduce((total, position) => total + position.display_market_value, 0)
  );
  const unrealizedPnl = roundMoney(
    positions.reduce((total, position) => total + position.display_unrealized_pnl, 0)
  );
  const totalEquity = roundMoney(cash + invested);
  const dayPnlInputs = positions
    .map((position) => {
      const change = position.display_price_change_today;
      return typeof change === "number" ? change * num(position.quantity) : null;
    })
    .filter((value): value is number => typeof value === "number");
  const dayPnl =
    dayPnlInputs.length === positions.length && positions.length > 0
      ? roundMoney(dayPnlInputs.reduce((total, value) => total + value, 0))
      : null;

  const latestQuoteTimestamp =
    positions
      .map((position) => position.display_quote_timestamp)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1) ?? null;
  const usableQuoteCount = positions.filter((position) => position.display_uses_live_quote).length;
  const missingQuoteCount = positions.length - usableQuoteCount;

  return {
    positions,
    cash,
    realized_pnl: realizedPnl,
    display_invested_value: invested,
    display_total_equity: totalEquity,
    display_unrealized_pnl: unrealizedPnl,
    display_total_return_pct: startingCapital > 0
      ? roundPct(((totalEquity - startingCapital) / startingCapital) * 100)
      : 0,
    display_cash_pct: totalEquity > 0 ? roundPct((cash / totalEquity) * 100) : 0,
    display_invested_pct: totalEquity > 0 ? roundPct((invested / totalEquity) * 100) : 0,
    display_day_pnl: dayPnl,
    display_day_return_pct: dayPnl !== null && totalEquity > 0 ? roundPct((dayPnl / totalEquity) * 100) : null,
    usable_quote_count: usableQuoteCount,
    missing_quote_count: missingQuoteCount,
    latest_quote_timestamp: latestQuoteTimestamp,
    price_status:
      positions.length === 0
        ? "NO_POSITIONS"
        : missingQuoteCount === 0
          ? marketSnapshot?.quote_status ?? "CURRENT_DISPLAY_VALUATION"
          : usableQuoteCount > 0
            ? "PARTIAL_CURRENT_DISPLAY_VALUATION"
            : "WAITING_FOR_CURRENT_MARKET_PRICES",
  };
}
