import { readFile } from "fs/promises";
import path from "path";

export type StrategyMetadata = {
  name: string;
  version: string;
  status: string;
};

export type ResearchMetadata = {
  scanner_version: string;
  strategy_version: string;
  feature_version: string;
  market_regime_version: string;
  generated_from: string;
};

export type DataSource = {
  type: string;
  generated_by: string;
  generator_version: string;
};

export type AiExplanation = {
  summary: string;
  strengths: string[];
  risks: string[];
  similar_historical_cases: Array<{
    label: string;
    count: number;
    average_return_pct: number;
    win_rate_pct: number;
  }>;
};

type PaperFileBase = {
  schema_version: string;
  generated_at: string;
  source_file?: string;
  source_market_date?: string;
  stale_price_data?: boolean;
  price_data_status?: string;
  mock_data: boolean;
  data_source?: DataSource;
  strategy: StrategyMetadata;
  research_metadata: ResearchMetadata;
  disclaimer: string;
};

export type DailyPick = {
  pick_id: string;
  trade_date: string;
  ticker: string;
  company_name: string | null;
  sector: string;
  sector_rank: number;
  rank: number;
  action: string;
  score: number;
  confidence: number;
  risk: string;
  expected_return_pct: number;
  win_probability_pct: number;
  best_hold_period_days: number;
  historical_matches: number;
  historical_best_avg_return_pct: number;
  latest_open: number;
  latest_close: number;
  five_day_change_pct: number;
  twenty_day_change_pct: number;
  relative_strength_pct: number;
  volume_ratio: number;
  paper_trade_candidate: boolean;
  paper_trade_decision: string;
  paper_trade_decision_reason: string;
  strategy: StrategyMetadata;
  research_metadata: ResearchMetadata;
  ai_explanation: AiExplanation;
};

export type DailyPicksFile = PaperFileBase & {
  trade_date: string;
  market_regime: {
    label: string;
    score: number;
    description: string;
  };
  picks: DailyPick[];
};

export type OpenPosition = {
  position_id: string;
  source_pick_id: string;
  ticker: string;
  sector: string;
  status: string;
  opened_at: string;
  entry_date: string;
  entry_price: number;
  current_price: number;
  price_change_today?: number | null;
  market_state?: string;
  last_price_update?: string;
  price_source?: string;
  price_status?: string;
  quantity: number;
  notional_cost: number;
  current_value: number;
  unrealized_pnl: number;
  unrealized_return_pct: number;
  planned_hold_period_days: number;
  planned_exit_date: string;
  days_held: number;
  entry_action: string;
  entry_score: number;
  entry_confidence: number;
  entry_expected_return_pct: number;
  entry_risk: string;
  entry_market_regime: string;
  entry_sector_rank: number;
  thesis: string;
  strategy: StrategyMetadata;
  research_metadata: ResearchMetadata;
  ai_explanation: AiExplanation;
  exit_rule: string;
  stop_rule: string | null;
  take_profit_rule: string | null;
  fees: number;
  slippage: number;
  notes: string;
};

export type OpenPositionsFile = PaperFileBase & {
  as_of_date: string;
  account: PaperAccount;
  positions: OpenPosition[];
};

export type ClosedTrade = {
  trade_id: string;
  position_id: string;
  source_pick_id: string;
  ticker: string;
  sector: string;
  status: string;
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  notional_cost: number;
  exit_value: number;
  realized_pnl: number;
  realized_return_pct: number;
  planned_hold_period_days: number;
  actual_hold_days: number;
  exit_reason: string;
  entry_action: string;
  entry_score: number;
  entry_confidence: number;
  entry_expected_return_pct: number;
  entry_risk: string;
  entry_market_regime: string;
  entry_sector_rank: number;
  max_unrealized_gain_pct: number;
  max_unrealized_loss_pct: number;
  thesis_outcome: string;
  strategy: StrategyMetadata;
  research_metadata: ResearchMetadata;
  ai_explanation: AiExplanation;
  fees: number;
  slippage: number;
  notes: string;
};

export type ClosedTradesFile = PaperFileBase & {
  as_of_date: string;
  trades: ClosedTrade[];
};

export type PaperAccount = {
  account_id: string;
  mode: string;
  starting_capital: number;
  currency: string;
};

export type PortfolioSummaryFile = PaperFileBase & {
  as_of_date: string;
  market_state?: string;
  last_market_update?: string | null;
  live_prices?: boolean;
  stale_positions?: number;
  account: PaperAccount;
  summary: {
    cash: number;
    invested_value: number;
    total_equity: number;
    open_positions_count: number;
    closed_trades_count: number;
    cash_pct: number;
    invested_pct: number;
    total_return_pct: number;
    realized_pnl: number;
    unrealized_pnl: number;
    day_pnl: number;
    day_return_pct: number;
    max_drawdown_pct: number;
    largest_position_pct: number;
    sector_exposure: Array<{
      sector: string;
      value: number;
      portfolio_pct: number;
      position_count: number;
    }>;
    risk_exposure: Array<{
      risk: string;
      value: number;
      portfolio_pct: number;
      position_count: number;
    }>;
    market_state?: string;
    last_market_update?: string | null;
    live_prices?: boolean;
    stale_positions?: number;
  };
};

export type EquityPoint = {
  date: string;
  cash: number;
  invested_value: number;
  total_equity: number;
  daily_pnl: number;
  daily_return_pct: number;
  cumulative_pnl: number;
  cumulative_return_pct: number;
  drawdown_pct: number;
  open_positions_count: number;
  closed_trades_count: number;
};

export type EquityCurveFile = PaperFileBase & {
  account: PaperAccount;
  points: EquityPoint[];
};

export type PerformanceStatisticsFile = PaperFileBase & {
  as_of_date: string;
  account: PaperAccount;
  overall: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate_pct: number;
    average_return_pct: number;
    median_return_pct: number;
    best_trade_return_pct: number;
    worst_trade_return_pct: number;
    average_win_pct: number;
    average_loss_pct: number;
    profit_factor: number;
    total_realized_pnl: number;
    total_unrealized_pnl: number;
    max_drawdown_pct: number;
    average_hold_days: number;
  };
  by_hold_period: PerformanceBucket[];
  by_action: PerformanceBucket[];
  by_market_regime: PerformanceBucket[];
  by_confidence_bucket: PerformanceBucket[];
  by_sector: PerformanceBucket[];
};

export type PerformanceBucket = {
  hold_period_days?: number;
  action?: string;
  market_regime?: string;
  bucket?: string;
  sector?: string;
  total_trades: number;
  win_rate_pct: number;
  average_return_pct: number;
  total_realized_pnl: number;
};

export type PaperTradingData = {
  dailyPicks: DailyPicksFile;
  openPositions: OpenPositionsFile;
  closedTrades: ClosedTradesFile;
  portfolioSummary: PortfolioSummaryFile;
  equityCurve: EquityCurveFile;
  performanceStatistics: PerformanceStatisticsFile;
};

export type PaperTradingLoadResult =
  | { status: "ready"; data: PaperTradingData }
  | { status: "missing"; message: string; file?: string }
  | { status: "invalid"; message: string; file?: string };

const PAPER_TRADING_DIR = path.join(process.cwd(), "..", "data", "paper_trading");

async function loadJsonFile<T>(fileName: string): Promise<T> {
  const filePath = path.join(PAPER_TRADING_DIR, fileName);

  try {
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as T;
  } catch (error) {
    const nodeError = error as NodeJS.ErrnoException;

    if (nodeError.code === "ENOENT") {
      throw new PaperTradingDataError(
        "missing",
        `${fileName} is missing from data/paper_trading/.`,
        fileName
      );
    }

    if (error instanceof SyntaxError) {
      throw new PaperTradingDataError(
        "invalid",
        `${fileName} contains invalid JSON.`,
        fileName
      );
    }

    throw new PaperTradingDataError(
      "invalid",
      `${fileName} could not be loaded.`,
      fileName
    );
  }
}

class PaperTradingDataError extends Error {
  status: "missing" | "invalid";
  file?: string;

  constructor(status: "missing" | "invalid", message: string, file?: string) {
    super(message);
    this.status = status;
    this.file = file;
  }
}

export async function loadPaperTradingData(): Promise<PaperTradingLoadResult> {
  try {
    const [
      dailyPicks,
      openPositions,
      closedTrades,
      portfolioSummary,
      equityCurve,
      performanceStatistics,
    ] = await Promise.all([
      loadJsonFile<DailyPicksFile>("daily_picks.json"),
      loadJsonFile<OpenPositionsFile>("open_positions.json"),
      loadJsonFile<ClosedTradesFile>("closed_trades.json"),
      loadJsonFile<PortfolioSummaryFile>("portfolio_summary.json"),
      loadJsonFile<EquityCurveFile>("equity_curve.json"),
      loadJsonFile<PerformanceStatisticsFile>("performance_statistics.json"),
    ]);

    return {
      status: "ready",
      data: {
        dailyPicks,
        openPositions,
        closedTrades,
        portfolioSummary,
        equityCurve,
        performanceStatistics,
      },
    };
  } catch (error) {
    if (error instanceof PaperTradingDataError) {
      return {
        status: error.status,
        message: error.message,
        file: error.file,
      };
    }

    return {
      status: "invalid",
      message: "Paper trading data could not be loaded.",
    };
  }
}
