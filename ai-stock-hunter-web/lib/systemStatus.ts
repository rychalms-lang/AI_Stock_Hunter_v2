import { readFile } from "fs/promises";
import path from "path";

export type SystemEvent = {
  timestamp: string;
  level: "info" | "warning" | "error";
  message: string;
};

export type SystemStatus = {
  schema_version: string;
  generated_at: string;
  market_state: string;
  daily_pipeline: {
    status: "healthy" | "warning" | "failed" | "unknown";
    last_success_at: string;
    last_market_date: string;
    source_report: string;
  };
  paper_refresh: {
    status: "healthy" | "stale" | "failed" | "unknown";
    last_success_at: string;
    positions_updated: number;
    positions_stale: number;
    positions_closed: number;
  };
  data_freshness: {
    daily_picks: string;
    portfolio: string;
    web_snapshot: string;
  };
  strategy: {
    name: string;
    version: string;
    status: string;
  };
  automation: {
    daily_pipeline_enabled: boolean;
    paper_refresh_enabled: boolean;
    daily_pipeline_label: string;
    paper_refresh_label: string;
  };
  scanner: {
    candidate_count: number;
    last_export_timestamp: string;
    source_file: string;
  };
  paper_portfolio: {
    open_positions: number;
    stale_positions: number;
    price_status: string;
    last_market_update: string | null;
  };
  market_snapshot?: {
    provider: string;
    quote_status: string;
    last_successful_quote_refresh: string;
    tickers_requested: number;
    tickers_updated: number;
    failed_quotes: number;
    market_state: string;
  };
  portfolio_governance?: {
    current_mode: string;
    label: string;
    decision_authority: string;
    automatic_entries_enabled: boolean;
    automatic_exits_enabled: boolean;
    manual_entries_enabled: boolean;
    approval_required: boolean;
    pending_proposal_count: number;
    last_mode_change: string | null;
    governance_status: string;
    legacy_position_handling: string;
  };
  events: SystemEvent[];
};

export async function loadSystemStatus(): Promise<SystemStatus | null> {
  try {
    const filePath = path.join(process.cwd(), "..", "data", "system_status.json");
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as SystemStatus;
  } catch {
    return null;
  }
}
