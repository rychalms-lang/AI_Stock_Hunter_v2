export type PriceStatus =
  | "LIVE"
  | "DELAYED"
  | "STALE"
  | "MARKET_CLOSED"
  | "UNAVAILABLE"
  | string;

export type MarketQuote = {
  ticker: string;
  current_price: number | null;
  previous_close: number | null;
  price_change: number | null;
  price_change_pct: number | null;
  bid?: number | null;
  ask?: number | null;
  day_open?: number | null;
  day_high?: number | null;
  day_low?: number | null;
  volume?: number | null;
  quote_timestamp: string;
  provider_timestamp?: string | null;
  market_state: string;
  source: string;
  delay_seconds?: number | null;
  price_age_seconds?: number | null;
  price_status: PriceStatus;
  error?: string | null;
};

export type MarketSnapshot = {
  schema_version: string;
  generated_at: string;
  market_state: string;
  provider: string;
  quote_status: PriceStatus;
  tickers_requested?: string[];
  tickers_updated?: number;
  quotes: Record<string, MarketQuote>;
  errors: Array<{
    ticker: string;
    error: string;
    price_status: PriceStatus;
  }>;
};

export type MarketSnapshotLoadResult =
  | { status: "ready"; data: MarketSnapshot }
  | { status: "missing"; message: string }
  | { status: "invalid"; message: string };

export function quoteForTicker(snapshot: MarketSnapshot | null, ticker?: string) {
  if (!snapshot || !ticker) return null;
  return snapshot.quotes[ticker.toUpperCase()] ?? null;
}

export function usableQuoteStatus(status?: string | null) {
  return status === "LIVE" || status === "DELAYED" || status === "MARKET_CLOSED";
}

export function priceStatusLabel(status?: string | null) {
  if (status === "LIVE") return "Live";
  if (status === "DELAYED") return "Delayed";
  if (status === "STALE") return "Stale";
  if (status === "MARKET_CLOSED") return "Market closed";
  if (status === "UNAVAILABLE") return "Unavailable";
  if (status === "LAST_LEDGER_PRICE") return "Last ledger price";
  if (status === "PARTIAL_CURRENT_DISPLAY_VALUATION") return "Partial current display valuation";
  if (status === "CURRENT_DISPLAY_VALUATION") return "Current display valuation";
  if (status === "WAITING_FOR_CURRENT_MARKET_PRICES") return "Waiting for current market prices";
  if (status === "NO_POSITIONS") return "No positions";
  return status ?? "Unavailable";
}

export function formatQuoteAge(value?: string | null) {
  if (!value) return "Update time unavailable";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return value;
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 60) return `Updated ${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `Updated ${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `Updated ${hours}h ago`;
}
