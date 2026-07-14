export function formatCurrency(value: number | undefined): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value ?? 0);
}

export function formatPercent(value: number | undefined): string {
  const safe = value ?? 0;
  return `${safe > 0 ? "+" : ""}${safe.toFixed(2)}%`;
}

export function formatNumber(value: number | undefined): string {
  return new Intl.NumberFormat("en-US").format(value ?? 0);
}

export function formatRuleName(value: string): string {
  const labels: Record<string, string> = {
    profit_target: "Profit target",
    overall_drawdown: "Overall drawdown",
    daily_loss_limit: "Daily loss limit",
    trailing_drawdown: "Trailing drawdown",
    consistency: "Consistency rule",
    minimum_trading_days: "Minimum trading days",
  };
  return labels[value] ?? "Rule check";
}

export function formatResultStatus(value: string): string {
  const labels: Record<string, string> = {
    passed: "Passed",
    failed: "Failed",
    in_progress: "In progress",
    not_met: "Not met",
    warning: "Warning",
  };
  return labels[value] ?? "Needs review";
}

export function resultTone(value: string): string {
  if (value === "passed") return "text-[#5d7f00]";
  if (value === "failed") return "text-red-700";
  return "text-black/52";
}

export function formatTradeStream(path: string): string {
  if (path.includes("balanced_v8_vs_v9")) return "Balanced V8/V9 historical trade stream";
  return "Approved historical trade stream";
}
