export type StrategyLabMode = "historical_replay" | "environment_comparison" | "sensitivity_analysis";

export type StrategyLabPreset = {
  schema_version: string;
  environment_id: string;
  name: string;
  preset_source: string;
  account_rules: Record<string, number | string | boolean | null>;
  risk_limits: Record<string, number | string | boolean | null>;
  trading_restrictions: Record<string, number | string | boolean | string[] | null>;
  consistency_rules: Record<string, number | string | boolean | null>;
  targets: Record<string, number | string | boolean | null>;
  execution_overrides: Record<string, number | string | boolean | null>;
  validation?: { errors: string[]; warnings: string[] };
};

export type StrategyLabPresetPayload = {
  schema_version: string;
  generated_by: string;
  preset_count: number;
  disclaimer: string;
  presets: StrategyLabPreset[];
};

export type StrategyLabResult = {
  schema_version: string;
  generated_at: string;
  simulation_id: string;
  mode: StrategyLabMode;
  disclaimer: string;
  strategy: { name: string; source_label: string; status: string };
  environment: StrategyLabPreset;
  trade_stream: { path: string; size_bytes: number; modified_at: string };
  validation: { errors: string[]; warnings: string[] };
  accounting: {
    cash: number;
    open_notional: number;
    closed_trade_count: number;
    open_position_count: number;
  };
  metrics: Record<string, number>;
  rule_results: Array<{ rule: string; status: string }>;
  pass_fail: string;
  equity_curve: Array<{ date: string; equity: number; cash: number; open_positions: number; drawdown_pct: number }>;
  timeline: Array<Record<string, string | number>>;
  closed_trades: Array<Record<string, string | number>>;
  missed_opportunities: Array<Record<string, string | number>>;
  violations: Array<{ date: string; rule: string; severity: string; message: string }>;
  assumptions: string[];
};

export type StrategyLabApiResponse =
  | { status: "ok"; result: StrategyLabResult | Record<string, unknown> }
  | { status: "error"; error: string };

export async function runStrategyLabSimulation(request: Record<string, unknown>): Promise<StrategyLabApiResponse> {
  const response = await fetch("/api/strategy-lab/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  const payload = (await response.json()) as StrategyLabApiResponse;
  if (!response.ok && payload.status === "error") {
    return payload;
  }
  return payload;
}
