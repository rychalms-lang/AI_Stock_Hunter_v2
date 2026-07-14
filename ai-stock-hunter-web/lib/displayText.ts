export const terminology = {
  activeStrategy: "Active Strategy",
  activeStrategyV8: "Active Strategy: V8",
  experimentalStrategy: "Experimental Strategy",
  aiResearchRating: "AI Research Rating",
  strategySignal: "Strategy Signal",
  simulatedTradeStatus: "Simulated Trade Status",
  simulatedTrading: "Simulated Trading",
  portfolioControl: "Portfolio Control",
  tradingMode: "Trading Mode",
  dataStatus: "Data Status",
  todayOpportunities: "Today's Opportunities",
  researchList: "Research List",
  historicalComparisons: "Historical Comparisons",
  dataSources: "Data Sources",
  dailyUpdate: "Daily Update",
};

export const explainers = {
  aiResearchRating: "The platform's overall research view.",
  strategySignal: "The signal produced by the active strategy.",
  simulatedTradeStatus: "Whether the simulated portfolio acted on the signal.",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  after_hours: "After hours",
  ai_assisted: "AI Assisted",
  ai_managed: "AI Managed",
  approved: "Approved",
  avoid: "Avoid",
  buy: "Buy",
  cancelled: "Cancelled",
  cautious: "Cautious",
  challenger: "Experimental",
  champion: "Active",
  closed: "Closed",
  command_failed: "Command failed",
  command_parse_error: "Command failed",
  current: "Current",
  current_display_valuation: "Current valuation",
  daily_pipeline: "Daily update",
  daily_scanner: "Daily research update",
  daily_update: "Daily update",
  defensive: "Defensive",
  delayed: "Delayed",
  disabled: "Disabled",
  eligible: "Eligible",
  eligible_scanner_export: "Eligible for simulated trading",
  enabled: "Enabled",
  error: "Error",
  executed: "Executed",
  excellent: "Excellent",
  expired: "Expired",
  failed: "Failed",
  failed_artifact_present: "Failed run recorded",
  failed_data_unavailable: "Market data unavailable",
  fresh: "Current",
  governance_active: "Active",
  governance_unavailable: "Unavailable",
  healthy: "Healthy",
  high: "High",
  hold: "Hold",
  info: "Info",
  insufficient_history: "Needs more history",
  insufficient_ticker_data_coverage: "Insufficient market data",
  invalid: "Invalid data",
  invalid_action: "Invalid action",
  invalid_mode: "Invalid mode",
  last_ledger_price: "Last recorded price",
  live: "Live",
  live_data: "Live data",
  low: "Low",
  manual_test: "Manual test",
  market_closed: "Market closed",
  market_snapshot: "Market snapshot",
  medium: "Medium",
  mismatch: "Needs review",
  missing: "Missing data",
  mock: "Mock data",
  mixed_research_data: "Mixed research data",
  no_positions: "No positions",
  no_price_requests: "No price requests",
  open: "Open",
  paper_trading_engine: "Simulated portfolio engine",
  paper_trading_exporter: "Simulated portfolio exporter",
  paper_trading_phase_1_mock: "Phase 1 mock data",
  paper_trading_update: "Simulated portfolio update",
  partial_current_display_valuation: "Partial current valuation",
  pending: "Pending",
  pre_market: "Waiting for market open",
  production: "Production",
  production_research_data: "Production research data",
  ready: "Ready",
  rejected: "Rejected",
  review: "Review",
  risk_controlled: "Risk controlled",
  scanner_automatic: "Added by V8",
  stale: "Out of date",
  strategy_directed: "Added by V8",
  success: "Success",
  unavailable: "Unavailable",
  unknown: "Unavailable",
  user_directed: "Added by User",
  user_managed: "User Managed",
  waiting_for_current_market_prices: "Waiting for current market prices",
  waiting_for_fresh_market_prices: "Waiting for the next market update",
  warning: "Needs attention",
  watch: "Watch",
  watch_only: "Watch only",
  watch_scanner_export: "Watch only",
  yahoo: "Yahoo Finance",
  yfinance: "Yahoo Finance",
};

export function formatDateTime(value?: string | null) {
  if (!value || value === "Not yet recorded" || value === "Unavailable") {
    return value ?? "Unavailable";
  }

  const date = parseDate(value);
  if (!date) return "Date unavailable";
  if (isDateOnly(value)) return formatDate(value);

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatDate(value?: string | null) {
  if (!value) return "Unavailable";
  const date = parseDate(value);
  if (!date) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function cleanStatus(value?: string | number | boolean | null) {
  if (value === true) return "Enabled";
  if (value === false) return "Disabled";
  if (value === null || value === undefined || value === "") return "Unavailable";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : "Unavailable";

  const text = String(value).trim();
  const normalized = text.toLowerCase();

  if (STATUS_LABELS[normalized]) return STATUS_LABELS[normalized];
  if (looksTechnical(text)) return "Status unavailable";

  return text;
}

export function strategyStatusLabel(status?: string | null) {
  if (!status) return "Active";
  if (status.toLowerCase() === "champion") return "Active";
  if (status.toLowerCase() === "challenger") return "Experimental";
  return cleanStatus(status);
}

export function sourceLabel(path?: string | null) {
  return researchSourceLabel(path);
}

export function researchSourceLabel(path?: string | null) {
  const date = sourceDate(path);
  if (!date) return "Official research update";
  return `Official research update for ${formatDate(date)}`;
}

export function technicalSourceLabel(path?: string | null) {
  if (!path) return "Unavailable";
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

export function formatPercent(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Not yet available";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function parseDate(value: string) {
  const text = value.trim();
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]), 12)
    : new Date(text);

  return Number.isNaN(date.getTime()) ? null : date;
}

function isDateOnly(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value.trim());
}

function sourceDate(path?: string | null) {
  if (!path) return null;
  const fileName = path.split("/").filter(Boolean).at(-1) ?? path;
  const match = /^(\d{4}-\d{2}-\d{2})_v\d+\.csv$/.exec(fileName);
  return match?.[1] ?? null;
}

function looksTechnical(value: string) {
  return (
    /[_/{}()[\]=]/.test(value) ||
    /^[A-Z0-9_]+$/.test(value) ||
    /^[a-z0-9]+(?:[_-][a-z0-9]+)+$/.test(value)
  );
}
