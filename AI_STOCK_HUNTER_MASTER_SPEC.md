# AI Stock Hunter — Master Engineering Specification

## Vision

### Purpose of AI Stock Hunter
AI Stock Hunter is a research-driven quantitative stock analysis and paper-trading platform designed to discover, evaluate, and validate systematic trading strategies using historical evidence before any live deployment.

### Long-term Goals
- Build a professional-grade research platform.
- Continuously improve systematic strategies through measurable experimentation.
- Operate a Champion/Challenger research process.
- Deliver a SaaS-quality paper-trading experience before considering live execution.

# Product Philosophy

- Research-first.
- Evidence-driven.
- Champion/Challenger strategy development.
- Never optimize without validation.

# System Architecture

## Frontend
- Next.js application (`ai-stock-hunter-web`)
- Dashboard
- Portfolio UI
- Shared components

## Backend
- Python research engine
- Strategy engine
- Feature engineering
- Model training
- Simulation
- Reporting

## Data Pipeline
Historical data → Feature engineering → Candidate scoring → Strategy selection → Portfolio construction → Simulation → Reports

## Paper Trading Engine
Uses V8 as the Champion strategy, executes virtual trades, tracks portfolio performance, and never places live trades.

## Strategy Engine
- V8 Champion
- V9 Challenger
- Experimental engines remain isolated until validated.

# Repository Structure

- ai-stock-hunter-web/: Frontend
- data/: Local datasets (ignored)
- performance/: Model artifacts and experiment outputs (ignored)
- reports/: Generated reports (ignored)
- Python modules: Research, simulation, portfolio management, training, utilities.

# Critical Files

Require explicit approval before modification:
- v8_portfolio_optimizer.py
- v9_challenger_ensemble_engine.py
- simulate_v8_vs_v9_balanced_capital.py
- backtest.py
- walk_forward_backtester.py
- realistic_walk_forward_backtester.py
- historical_trainer.py
- ml_trainer.py
- ml_trainer_time_split.py
- ml_candidate_trainer.py
- scanner.py
- portfolio.py
- market_regime.py
- sector_strength.py
- settings.py
- Feature engineering pipeline files

# Development Rules

- Never commit secrets.
- Never commit .env files.
- Never commit generated reports.
- Never commit datasets.
- Never commit model artifacts unless requested.
- Preserve strategy logic unless explicitly instructed.
- Ask before modifying production research code.

# Coding Standards

- Maintain clean architecture.
- Reuse components.
- Keep UI consistent.
- Document major functions.

# Paper Trading Requirements

- V8 is the Champion.
- Display daily picks.
- Simulate trades only.
- Maintain portfolio history.
- Record performance metrics.
- No live trading by default.

# Future Roadmap

## Phase 1
Professional dashboard and paper trading.

## Phase 2
Champion/Challenger analytics and research automation.

## Phase 3
User accounts, watchlists, alerts.

## Phase 4
Professional SaaS platform with optional broker integrations after validation.
