# AI Stock Hunter Paper Trading Architecture

Last updated: 2026-07-09

This document defines the paper trading architecture for AI Stock Hunter. It is a planning and implementation contract only. It does not authorize real trading, brokerage integration, strategy changes, backtesting changes, V8/V9 changes, simulator changes, machine learning changes, or training changes.

## 1. Purpose

Paper trading converts AI Stock Hunter daily recommendations into simulated positions and measurable forward results.

The purpose is to answer:

- Which daily picks would have become simulated positions?
- Which picks should have been reviewed, watched, skipped, or avoided?
- How did each simulated position perform against its original thesis?
- Which confidence levels, sectors, market regimes, hold periods, and action labels are working?
- How much simulated capital is deployed, in cash, at risk, and exposed to each sector?

Paper trading is not a replacement for backtesting. Backtesting evaluates historical strategy behavior across large datasets. Paper trading tracks the live forward behavior of the current system after recommendations are generated.

## 2. Data Flow

Current source flow:

1. Python scanner and research modules generate daily candidates.
2. Market regime, sector strength, confidence, historical evidence, and portfolio context enrich the picks.
3. Daily outputs are written to reports and data files.
4. The website reads prepared JSON data and renders dashboard and portfolio views.

Future paper trading flow:

1. Daily scanner output is normalized into `data/paper_trading/daily_picks.json`.
2. Phase 1 mock paper-trading data displays simulated portfolio behavior without real automation.
3. Later paper-trading logic will convert eligible daily picks into simulated orders.
4. Simulated orders will create or update open paper positions.
5. Mark-to-market updates will refresh unrealized P/L.
6. Exit rules will close completed paper trades.
7. Portfolio, equity curve, and performance statistics will be regenerated for frontend consumption.

The frontend must render backend-generated state. It must not calculate trading decisions, place trades, connect to a broker, or imply live execution.

## 3. Required JSON Files

All paper trading files should live under:

```text
data/paper_trading/
```

Required files:

- `daily_picks.json`
- `open_positions.json`
- `closed_trades.json`
- `portfolio_summary.json`
- `equity_curve.json`
- `performance_statistics.json`

Every file must include:

- `schema_version`
- `generated_at`
- `disclaimer`
- V8 Champion strategy metadata
- `research_metadata` where appropriate
- clear mock metadata during Phase 1

Required disclaimer:

```text
Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice.
```

## 4. Champion Strategy Metadata

The current Champion Strategy is V8.

V8 is the approved production research baseline for paper trading. V9 and future models are challengers. They must not replace V8 unless they beat V8 through approved validation, including out-of-sample testing, walk-forward testing, performance comparison, drawdown review, and explicit approval.

Required strategy object:

```json
"strategy": {
  "name": "V8",
  "version": "8.0",
  "status": "Champion"
}
```

Rules:

- V8 remains Champion until explicitly promoted out.
- V9 and future models may be labeled `Challenger`, `Research`, or `Deprecated`, but not `Champion` unless approved.
- Every paper trade must preserve the strategy metadata that generated it.
- Historical paper trades must not be rewritten when a new challenger is tested.

## 5. AI Explanation Layer

Picks and paper trades should include an explanation object:

```json
"ai_explanation": {
  "summary": "Evidence-based explanation from backend.",
  "strengths": [],
  "risks": [],
  "similar_historical_cases": []
}
```

Rules:

- Explanations must be evidence-based.
- Explanations cannot invent unsupported reasons.
- Explanations must trace back to scanner fields, historical setup data, confidence, market regime, sector rank, or paper trading outcomes.
- Placeholder explanations must be clearly treated as mock or placeholder content.
- `similar_historical_cases` should summarize aggregate evidence, not fabricated individual examples.

## 6. Research Metadata

Every paper trading file, pick, position, and closed trade should preserve metadata that identifies which system version generated it.

Required object:

```json
"research_metadata": {
  "scanner_version": "current",
  "strategy_version": "V8",
  "feature_version": "current",
  "market_regime_version": "current",
  "generated_from": "daily_scanner"
}
```

Rules:

- Metadata should be copied from daily picks into open positions and closed trades.
- Metadata must not be overwritten when new models or strategies are introduced.
- `generated_from` should identify the source workflow, such as `daily_scanner`, `mock_phase_1`, or `paper_trading_update`.

## 7. Schemas

### 7.1 Daily Picks

File:

```text
data/paper_trading/daily_picks.json
```

Schema:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-09T08:45:00",
  "trade_date": "2026-07-09",
  "mock_data": true,
  "strategy": {
    "name": "V8",
    "version": "8.0",
    "status": "Champion"
  },
  "research_metadata": {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "mock_phase_1"
  },
  "market_regime": {
    "label": "Risk-On",
    "score": 82.5,
    "description": "Mock Phase 1 market regime context."
  },
  "picks": [
    {
      "pick_id": "2026-07-09_AAPL",
      "trade_date": "2026-07-09",
      "ticker": "AAPL",
      "company_name": null,
      "sector": "Mega Cap Tech",
      "sector_rank": 2,
      "rank": 1,
      "action": "REVIEW",
      "score": 54.25,
      "confidence": 84.0,
      "risk": "Low",
      "expected_return_pct": 2.75,
      "win_probability_pct": 68.5,
      "best_hold_period_days": 7,
      "historical_matches": 143,
      "historical_best_avg_return_pct": 2.75,
      "latest_open": 214.35,
      "latest_close": 216.1,
      "five_day_change_pct": 4.2,
      "twenty_day_change_pct": 8.4,
      "relative_strength_pct": 3.1,
      "volume_ratio": 1.62,
      "paper_trade_candidate": true,
      "paper_trade_decision": "eligible_mock",
      "paper_trade_decision_reason": "Meets Phase 1 mock eligibility rules.",
      "strategy": {
        "name": "V8",
        "version": "8.0",
        "status": "Champion"
      },
      "research_metadata": {
        "scanner_version": "current",
        "strategy_version": "V8",
        "feature_version": "current",
        "market_regime_version": "current",
        "generated_from": "mock_phase_1"
      },
      "ai_explanation": {
        "summary": "Mock explanation based on high confidence, positive relative strength, and favorable historical evidence.",
        "strengths": [
          "Confidence is above 80%.",
          "Relative strength is positive.",
          "Historical setup average return is positive."
        ],
        "risks": [
          "Paper trading outcome is unknown.",
          "This is mock Phase 1 data."
        ],
        "similar_historical_cases": [
          {
            "label": "Comparable 7-day setups",
            "count": 143,
            "average_return_pct": 2.75,
            "win_rate_pct": 62.0
          }
        ]
      }
    }
  ],
  "disclaimer": "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice."
}
```

Required pick fields:

- `pick_id`
- `trade_date`
- `ticker`
- `sector`
- `rank`
- `action`
- `score`
- `confidence`
- `risk`
- `expected_return_pct`
- `best_hold_period_days`
- `historical_matches`
- `latest_close`
- `paper_trade_candidate`
- `paper_trade_decision`
- `paper_trade_decision_reason`
- `strategy`
- `research_metadata`
- `ai_explanation`

### 7.2 Open Positions

File:

```text
data/paper_trading/open_positions.json
```

Schema:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-09T16:15:00",
  "as_of_date": "2026-07-09",
  "mock_data": true,
  "strategy": {
    "name": "V8",
    "version": "8.0",
    "status": "Champion"
  },
  "research_metadata": {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "mock_phase_1"
  },
  "account": {
    "account_id": "paper_default",
    "mode": "paper_only",
    "starting_capital": 25000.0,
    "currency": "USD"
  },
  "positions": [
    {
      "position_id": "paper_AAPL_2026-07-09",
      "source_pick_id": "2026-07-09_AAPL",
      "ticker": "AAPL",
      "sector": "Mega Cap Tech",
      "status": "open",
      "opened_at": "2026-07-09T09:35:00",
      "entry_date": "2026-07-09",
      "entry_price": 216.25,
      "current_price": 218.1,
      "quantity": 4.0,
      "notional_cost": 865.0,
      "current_value": 872.4,
      "unrealized_pnl": 7.4,
      "unrealized_return_pct": 0.86,
      "planned_hold_period_days": 7,
      "planned_exit_date": "2026-07-18",
      "days_held": 0,
      "entry_action": "REVIEW",
      "entry_score": 54.25,
      "entry_confidence": 84.0,
      "entry_expected_return_pct": 2.75,
      "entry_risk": "Low",
      "entry_market_regime": "Risk-On",
      "entry_sector_rank": 2,
      "thesis": "Mock paper position created from an eligible V8 Champion signal.",
      "strategy": {
        "name": "V8",
        "version": "8.0",
        "status": "Champion"
      },
      "research_metadata": {
        "scanner_version": "current",
        "strategy_version": "V8",
        "feature_version": "current",
        "market_regime_version": "current",
        "generated_from": "mock_phase_1"
      },
      "ai_explanation": {
        "summary": "Mock open position explanation preserving the original V8 paper signal context.",
        "strengths": [
          "Original signal had high confidence.",
          "Entry was linked to positive historical evidence."
        ],
        "risks": [
          "Unrealized gains can reverse.",
          "This is mock Phase 1 data."
        ],
        "similar_historical_cases": [
          {
            "label": "Comparable 7-day setups at entry",
            "count": 143,
            "average_return_pct": 2.75,
            "win_rate_pct": 62.0
          }
        ]
      },
      "exit_rule": "planned_hold_period",
      "stop_rule": null,
      "take_profit_rule": null,
      "fees": 0.0,
      "slippage": 0.0,
      "notes": "Mock paper position only. No real order was placed."
    }
  ],
  "disclaimer": "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice."
}
```

### 7.3 Closed Trades

File:

```text
data/paper_trading/closed_trades.json
```

Schema:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-18T16:15:00",
  "as_of_date": "2026-07-18",
  "mock_data": true,
  "strategy": {
    "name": "V8",
    "version": "8.0",
    "status": "Champion"
  },
  "research_metadata": {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "mock_phase_1"
  },
  "trades": [
    {
      "trade_id": "trade_MSFT_2026-06-30_2026-07-09",
      "position_id": "paper_MSFT_2026-06-30",
      "source_pick_id": "2026-06-30_MSFT",
      "ticker": "MSFT",
      "sector": "Mega Cap Tech",
      "status": "closed",
      "entry_date": "2026-06-30",
      "exit_date": "2026-07-09",
      "entry_price": 497.5,
      "exit_price": 509.2,
      "quantity": 2.0,
      "notional_cost": 995.0,
      "exit_value": 1018.4,
      "realized_pnl": 23.4,
      "realized_return_pct": 2.35,
      "planned_hold_period_days": 7,
      "actual_hold_days": 7,
      "exit_reason": "planned_hold_period",
      "entry_action": "REVIEW",
      "entry_score": 51.7,
      "entry_confidence": 81.5,
      "entry_expected_return_pct": 2.1,
      "entry_risk": "Low",
      "entry_market_regime": "Risk-On",
      "entry_sector_rank": 2,
      "max_unrealized_gain_pct": 3.1,
      "max_unrealized_loss_pct": -0.8,
      "thesis_outcome": "confirmed_mock",
      "strategy": {
        "name": "V8",
        "version": "8.0",
        "status": "Champion"
      },
      "research_metadata": {
        "scanner_version": "current",
        "strategy_version": "V8",
        "feature_version": "current",
        "market_regime_version": "current",
        "generated_from": "mock_phase_1"
      },
      "ai_explanation": {
        "summary": "Mock closed paper trade with positive realized return over the planned hold period.",
        "strengths": [
          "Realized return was positive.",
          "Exit followed the planned hold period."
        ],
        "risks": [
          "Single mock trade does not prove strategy quality.",
          "Future results may differ."
        ],
        "similar_historical_cases": [
          {
            "label": "Comparable 7-day setups at entry",
            "count": 118,
            "average_return_pct": 2.1,
            "win_rate_pct": 60.2
          }
        ]
      },
      "fees": 0.0,
      "slippage": 0.0,
      "notes": "Mock closed simulation only. No real order was placed."
    }
  ],
  "disclaimer": "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice."
}
```

### 7.4 Portfolio Summary

File:

```text
data/paper_trading/portfolio_summary.json
```

Schema:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-09T16:15:00",
  "as_of_date": "2026-07-09",
  "mock_data": true,
  "strategy": {
    "name": "V8",
    "version": "8.0",
    "status": "Champion"
  },
  "research_metadata": {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "mock_phase_1"
  },
  "account": {
    "account_id": "paper_default",
    "mode": "paper_only",
    "starting_capital": 25000.0,
    "currency": "USD"
  },
  "summary": {
    "cash": 18250.0,
    "invested_value": 6750.0,
    "total_equity": 25072.4,
    "open_positions_count": 8,
    "closed_trades_count": 12,
    "cash_pct": 72.77,
    "invested_pct": 26.92,
    "total_return_pct": 0.29,
    "realized_pnl": 65.0,
    "unrealized_pnl": 7.4,
    "day_pnl": 18.2,
    "day_return_pct": 0.07,
    "max_drawdown_pct": -1.85,
    "largest_position_pct": 3.46,
    "sector_exposure": [
      {
        "sector": "Mega Cap Tech",
        "value": 1725.0,
        "portfolio_pct": 6.88,
        "position_count": 2
      }
    ],
    "risk_exposure": [
      {
        "risk": "Low",
        "value": 5200.0,
        "portfolio_pct": 20.74,
        "position_count": 6
      }
    ]
  },
  "disclaimer": "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice."
}
```

### 7.5 Equity Curve

File:

```text
data/paper_trading/equity_curve.json
```

Schema:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-09T16:15:00",
  "mock_data": true,
  "strategy": {
    "name": "V8",
    "version": "8.0",
    "status": "Champion"
  },
  "research_metadata": {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "mock_phase_1"
  },
  "account": {
    "account_id": "paper_default",
    "mode": "paper_only",
    "starting_capital": 25000.0,
    "currency": "USD"
  },
  "points": [
    {
      "date": "2026-07-09",
      "cash": 18250.0,
      "invested_value": 6750.0,
      "total_equity": 25072.4,
      "daily_pnl": 18.2,
      "daily_return_pct": 0.07,
      "cumulative_pnl": 72.4,
      "cumulative_return_pct": 0.29,
      "drawdown_pct": 0.0,
      "open_positions_count": 8,
      "closed_trades_count": 12
    }
  ],
  "disclaimer": "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice."
}
```

### 7.6 Performance Statistics

File:

```text
data/paper_trading/performance_statistics.json
```

Schema:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-09T16:15:00",
  "as_of_date": "2026-07-09",
  "mock_data": true,
  "strategy": {
    "name": "V8",
    "version": "8.0",
    "status": "Champion"
  },
  "research_metadata": {
    "scanner_version": "current",
    "strategy_version": "V8",
    "feature_version": "current",
    "market_regime_version": "current",
    "generated_from": "mock_phase_1"
  },
  "account": {
    "account_id": "paper_default",
    "mode": "paper_only",
    "starting_capital": 25000.0,
    "currency": "USD"
  },
  "overall": {
    "total_trades": 12,
    "winning_trades": 7,
    "losing_trades": 5,
    "win_rate_pct": 58.33,
    "average_return_pct": 1.12,
    "median_return_pct": 0.85,
    "best_trade_return_pct": 6.4,
    "worst_trade_return_pct": -3.2,
    "average_win_pct": 2.8,
    "average_loss_pct": -1.45,
    "profit_factor": 1.85,
    "total_realized_pnl": 65.0,
    "total_unrealized_pnl": 7.4,
    "max_drawdown_pct": -1.85,
    "average_hold_days": 6.2
  },
  "by_hold_period": [
    {
      "hold_period_days": 7,
      "total_trades": 8,
      "win_rate_pct": 62.5,
      "average_return_pct": 1.45,
      "total_realized_pnl": 48.0
    }
  ],
  "by_action": [
    {
      "action": "REVIEW",
      "total_trades": 10,
      "win_rate_pct": 60.0,
      "average_return_pct": 1.3,
      "total_realized_pnl": 58.0
    }
  ],
  "by_market_regime": [
    {
      "market_regime": "Risk-On",
      "total_trades": 9,
      "win_rate_pct": 66.67,
      "average_return_pct": 1.55,
      "total_realized_pnl": 61.0
    }
  ],
  "by_confidence_bucket": [
    {
      "bucket": "80-100",
      "total_trades": 5,
      "win_rate_pct": 80.0,
      "average_return_pct": 2.05,
      "total_realized_pnl": 49.0
    }
  ],
  "by_sector": [
    {
      "sector": "Mega Cap Tech",
      "total_trades": 4,
      "win_rate_pct": 75.0,
      "average_return_pct": 1.9,
      "total_realized_pnl": 36.0
    }
  ],
  "disclaimer": "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice."
}
```

## 8. Frontend Pages And Components

The frontend should consume these files as read-only data.

Dashboard:

- Market regime card.
- Daily picks table.
- Paper portfolio summary card.
- Disclaimer banner.
- Mock data label during Phase 1.

Portfolio/Paper Trading page:

- Open positions table.
- Closed trades table.
- Equity curve summary.
- Performance statistics cards.
- Sector exposure panel.
- Confidence bucket performance panel.
- Disclaimer banner.
- Mock data label during Phase 1.

Candidate detail page:

- Pick thesis panel.
- AI explanation panel.
- Historical evidence panel.
- Related paper position or closed trade panel.

## 9. Phase 1 Mock Data Versus Later Live Wiring

Phase 1 should establish file contracts and frontend display behavior without implementing real paper-trading automation.

Mock in Phase 1:

- Starting capital.
- Open positions.
- Closed trades.
- Portfolio values.
- Equity curve.
- Performance statistics.
- Paper trade decisions.
- Fees and slippage assumptions.

Wire live in Phase 1:

- JSON file loading.
- V8 Champion metadata display.
- Research metadata display where useful.
- AI explanation object shape.
- Paper trading disclaimers.
- Clear `MOCK PAPER TRADING DATA` labels.

Later live wiring:

- Daily pick normalization from scanner/report output.
- Deterministic simulated order creation.
- Simulated entry prices from decision-time data.
- Mark-to-market updates.
- Planned hold-period exits.
- Closed trade generation.
- Real paper portfolio calculations.
- Real equity curve and performance statistics.

Even when live-wired, the system remains paper trading only.

## 9.1 Paper Trading Refresh Command

Paper trading has two separate backend workflows:

1. Scanner/export run:
   - Generates the current scanner recommendations.
   - Normalizes daily picks into `daily_picks.json`.
   - Opens eligible new paper positions from authoritative raw scanner `BUY` actions.
   - Preserves V8 Champion strategy metadata and research metadata.

2. Refresh run:
   - Uses `refresh_paper_trading.py`.
   - Does not run the scanner.
   - Does not generate new signals.
   - Does not open new paper positions.
   - Loads existing paper-trading state.
   - Fetches current quotes through `MarketDataService`.
   - Updates existing open positions, unrealized P/L, stop-loss exits, take-profit exits, hold-period exits, portfolio summary, equity curve, and performance statistics.
   - Regenerates lifecycle JSON files while leaving `daily_picks.json` and `data/web_snapshot.json` unchanged.

The refresh command is designed for future scheduling. It is non-interactive, safe to run repeatedly, supports dry runs, and should be suitable for cron, launchd, GitHub Actions, or a future hosted job runner. If market prices are unavailable or stale, the refresh command must retain the last known paper price, mark affected positions clearly, and avoid processing exits from stale quotes.

## 9.2 Intraday Market Snapshot

`refresh_market_snapshot.py` creates `data/market_snapshot.json` without rerunning the scanner or changing V8 research outputs.

The market snapshot may be used by the website to display current quote context for:

- open paper-position valuation
- user-directed entry previews
- candidate detail pages
- Mission Control provider/freshness telemetry

The snapshot is not an input to V8 ranking, confidence, expected-return calculation, hold-period recommendations, scanner actions, or backtested rules. V8 remains a daily research strategy unless separate intraday rules are explicitly researched, validated, and approved.

Current public quote statuses are:

- `LIVE`: provider contract explicitly supports real-time data.
- `DELAYED`: usable quote data, but not contractually real time.
- `STALE`: quote timestamp is too old for trading-day valuation or risk controls.
- `MARKET_CLOSED`: current session is closed; values may represent the last available close.
- `UNAVAILABLE`: provider did not return a usable quote.

The current fallback provider is yfinance. Because the project does not have a real-time market-data contract, usable yfinance intraday quotes must be treated as `DELAYED`, not real time. Stale or unavailable quotes must never trigger paper exits or simulated entries.

The frontend may poll `data/market_snapshot.json` through a local API every 30-60 seconds while the page is open, with slower polling when the browser tab is hidden or the market is closed. This polling updates display context only. Durable paper ledger state is refreshed by `refresh_paper_trading.py`.

### 9.2 Local Runtime State

Paper-trading ledger files under `data/paper_trading/state/` are mutable local runtime state. They store account cash, open-position ledger entries, closed-trade ledger entries, processed pick IDs, and equity history used by the paper-trading runtime.

These state files are excluded from Git and should not be committed. The paper-trading engine creates the state directory and default state files automatically when it saves runtime state, so a fresh checkout can start without checked-in ledger files.

The exported frontend JSON files under `data/paper_trading/` remain separate from internal ledger state. The website consumes those export files, not the mutable ledger files. A production deployment will eventually need durable external storage for paper-trading state, such as a database or managed object store, instead of local JSON files.

### 9.3 Scheduling Architecture

Paper-trading automation should use two separate launchd workflows on macOS:

1. Daily scanner/export pipeline:
   - Launchd triggers at 6:00 PM in the Mac's local timezone.
   - The wrapper records the `America/New_York` market date and uses that date for duplicate-run protection.
   - The wrapper should run only after the New York post-close window unless manually forced.
   - Runs after end-of-day U.S. market data is expected to be available.
   - Runs `main.py` from the project venv.
   - Runs `web_exporter.py` after the scanner, because the scanner pipeline does not currently export frontend JSON by itself.
   - May open newly eligible paper positions through the approved scanner/export path.

2. Intraday paper-ledger refresh:
   - Runs `refresh_paper_trading.py` from the project venv.
   - Updates only existing paper positions.
   - Does not generate scanner recommendations.
   - Does not open new paper positions.
   - Uses `America/New_York` for market-session checks, with daylight saving handled by timezone-aware logic.
   - Uses `MarketDataService` market state as the final scheduled-run authority where practical.
   - Exits safely outside the configured market-hours window or when market data is stale or unavailable.

Automation source files live under `automation/`. Runtime logs and lock files are local artifacts and excluded from Git. Launch agents must not be installed or loaded automatically during development; they should be enabled only by an explicit user-run install script.

If the Mac is asleep or powered off at a scheduled time, launchd does not guarantee execution during the missed window or catch-up execution after wake. Existing cron jobs should be inspected manually with `crontab -l` and disabled before launchd is enabled to avoid duplicate scanner runs.

## 10. Safety Rules

Required rules:

- No real trading.
- No brokerage connection.
- No broker API keys.
- No order routing.
- No account linking.
- No live capital.
- Paper trading only.
- No investment advice wording.
- No buttons or labels that imply live execution.
- Use language such as `Review`, `Watch`, `Paper Position`, `Simulated Entry`, and `Closed Simulation`.
- Every paper trading page must display the required disclaimer.
- V9 and future challengers cannot replace V8 without approved validation.
- AI explanations cannot invent unsupported reasons.

## 11. Acceptance Criteria

Data criteria:

- `data/paper_trading/daily_picks.json` exists.
- `data/paper_trading/open_positions.json` exists.
- `data/paper_trading/closed_trades.json` exists.
- `data/paper_trading/portfolio_summary.json` exists.
- `data/paper_trading/equity_curve.json` exists.
- `data/paper_trading/performance_statistics.json` exists.
- Every JSON file includes `schema_version`, `generated_at`, `disclaimer`, V8 Champion `strategy`, and `research_metadata`.
- Daily picks, open positions, and closed trades include `ai_explanation`.
- Mock Phase 1 files are clearly marked as mock data.

Safety criteria:

- No brokerage integration exists.
- No real order placement exists.
- No broker credentials are added.
- User-facing wording avoids investment advice.

Frontend criteria:

- Dashboard can display paper portfolio summary when available.
- Portfolio/Paper Trading page can display open positions, closed trades, equity curve summary, and performance stats.
- All paper trading sections are labeled `MOCK PAPER TRADING DATA` during Phase 1.
- Empty states render cleanly if files contain no positions or trades.

Research criteria:

- No Python strategy files are modified.
- V8, V9, backtesting, simulator, ML, and training logic remain untouched.
- Paper trading state is separate from research backtests.
- Every paper trade preserves metadata needed to trace the generating system version.

Completion criteria:

- No frontend code is modified until explicitly requested.
- No commits are made without approval.
- Future schema changes are documented and versioned.
