"use client";

import {
  ClosedTrade,
  EquityPoint,
  PaperTradingData,
  PaperTradingLoadResult,
} from "@/lib/paperTrading";
import { PortfolioGovernance } from "@/lib/governanceDisplay";
import { MarketSnapshot, priceStatusLabel } from "@/lib/marketSnapshot";
import { DisplayPosition, deriveDisplayValuation } from "@/lib/portfolioDisplayValuation";
import { useMarketSnapshot } from "@/lib/useMarketSnapshot";
import { WebSnapshot } from "@/lib/webSnapshot";
import { cleanStatus } from "@/lib/displayText";
import PaperTradingBanner from "./PaperTradingBanner";
import PaperPortfolioBuilder from "./PaperPortfolioBuilder";
import PaperTradingStateCard from "./PaperTradingStateCard";

function money(value: number) {
  return `$${value.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })}`;
}

function pct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function updatedAgo(value?: string | null) {
  if (!value) return "Waiting for fresh market prices";

  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "Update time unavailable";

  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 60) return `Updated ${seconds} seconds ago`;

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `Updated ${minutes} minutes ago`;

  const hours = Math.round(minutes / 60);
  return `Updated ${hours} hours ago`;
}

function optionalPct(value: number | null | undefined, digits = 2) {
  if (typeof value !== "number") return "Insufficient data";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

function pnlClass(value: number) {
  if (value > 0) return "text-emerald-700";
  if (value < 0) return "text-red-600";
  return "text-black/70";
}

function EquityCurve({ points }: { points: EquityPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="border border-black/10 bg-[#f3f3ef] p-6 text-sm text-black/45">
        No equity points available.
      </div>
    );
  }

  const values = points.map((point) => point.total_equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const width = 720;
  const height = 220;
  const padding = 24;

  const pathData = points
    .map((point, index) => {
      const x =
        points.length === 1
          ? width / 2
          : padding +
            (index / (points.length - 1)) * (width - padding * 2);
      const y =
        height -
        padding -
        ((point.total_equity - min) / range) * (height - padding * 2);

      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-[220px] w-full overflow-visible"
        role="img"
        aria-label="Simulated portfolio equity curve"
      >
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="rgba(0,0,0,0.12)"
          strokeWidth="1"
        />
        <path
          d={pathData}
          fill="none"
          className="chart-draw"
          stroke="#111111"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="4"
        />
        {points.map((point, index) => {
          const x =
            points.length === 1
              ? width / 2
              : padding +
                (index / (points.length - 1)) * (width - padding * 2);
          const y =
            height -
            padding -
            ((point.total_equity - min) / range) * (height - padding * 2);

          return (
            <circle
              key={point.date}
              cx={x}
              cy={y}
              r={index === points.length - 1 ? 5 : 3}
              fill={index === points.length - 1 ? "#111111" : "#737373"}
            />
          );
        })}
      </svg>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-black/45 md:grid-cols-4">
        {points.map((point) => (
          <div key={point.date} className="border-t border-black/10 pt-3">
            <div>{point.date}</div>
            <div className="mt-1 font-bold text-black">
              {money(point.total_equity)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OpenPositionsTable({ positions }: { positions: DisplayPosition[] }) {
  if (positions.length === 0) {
    return <EmptyState label="No open simulated positions." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="border-b border-black/10 text-xs uppercase tracking-[0.18em] text-black/40">
          <tr>
            <th className="py-3 pr-4">Ticker</th>
            <th className="py-3 pr-4">Sector</th>
            <th className="py-3 pr-4">Entry</th>
            <th className="py-3 pr-4">Current</th>
            <th className="py-3 pr-4">Today</th>
            <th className="py-3 pr-4">Value</th>
            <th className="py-3 pr-4">Unrealized</th>
            <th className="py-3 pr-4">Quote</th>
            <th className="py-3 pr-4">Hold</th>
            <th className="py-3 pr-4">Risk</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-black/10">
          {positions.map((position) => (
            <tr
              key={position.position_id}
              className="transition-colors duration-200 hover:bg-white"
            >
              <td className="py-4 pr-4 text-xl font-black tracking-[-0.05em] text-black">
                {position.ticker}
              </td>
              <td className="py-4 pr-4 text-black/58">{position.sector}</td>
              <td className="py-4 pr-4">{money(position.entry_price)}</td>
              <td className="py-4 pr-4">{money(position.display_current_price)}</td>
              <td className={`py-4 pr-4 font-bold ${pnlClass(position.display_price_change_today_pct ?? 0)}`}>
                {optionalPct(position.display_price_change_today_pct)}
              </td>
              <td className="py-4 pr-4">{money(position.display_market_value)}</td>
              <td className={`py-4 pr-4 font-bold ${pnlClass(position.display_unrealized_pnl)}`}>
                {money(position.display_unrealized_pnl)} ·{" "}
                {pct(position.display_unrealized_return_pct)}
              </td>
              <td className="py-4 pr-4 text-black/58">
                {priceStatusLabel(position.display_price_status)}
              </td>
              <td className="py-4 pr-4">
                {position.days_held}/{position.planned_hold_period_days}D
              </td>
              <td className="py-4 pr-4">{position.entry_risk}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClosedTradesTable({ trades }: { trades: ClosedTrade[] }) {
  if (trades.length === 0) {
    return <EmptyState label="No closed simulations." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-left text-sm">
        <thead className="border-b border-black/10 text-xs uppercase tracking-[0.18em] text-black/40">
          <tr>
            <th className="py-3 pr-4">Ticker</th>
            <th className="py-3 pr-4">Dates</th>
            <th className="py-3 pr-4">Entry</th>
            <th className="py-3 pr-4">Exit</th>
            <th className="py-3 pr-4">Realized P/L</th>
            <th className="py-3 pr-4">Outcome</th>
            <th className="py-3 pr-4">Regime</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-black/10">
          {trades.map((trade) => (
            <tr
              key={trade.trade_id}
              className="transition-colors duration-200 hover:bg-white"
            >
              <td className="py-4 pr-4 text-xl font-black tracking-[-0.05em] text-black">
                {trade.ticker}
              </td>
              <td className="py-4 pr-4 text-black/58">
                {trade.entry_date} to {trade.exit_date}
              </td>
              <td className="py-4 pr-4">{money(trade.entry_price)}</td>
              <td className="py-4 pr-4">{money(trade.exit_price)}</td>
              <td className={`py-4 pr-4 font-bold ${pnlClass(trade.realized_pnl)}`}>
                {money(trade.realized_pnl)} · {pct(trade.realized_return_pct)}
              </td>
              <td className="py-4 pr-4">{trade.thesis_outcome}</td>
              <td className="py-4 pr-4">{trade.entry_market_regime}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="border border-black/10 bg-[#f3f3ef] p-6 text-sm text-black/45">
      {label}
    </div>
  );
}

function PortfolioContent({
  data,
  webSnapshot,
  governance,
  marketSnapshot,
}: {
  data: PaperTradingData;
  webSnapshot: WebSnapshot | null;
  governance?: PortfolioGovernance;
  marketSnapshot?: MarketSnapshot | null;
}) {
  const { snapshot: currentMarketSnapshot, error: marketSnapshotError } = useMarketSnapshot(marketSnapshot ?? null);
  const displayValuation = deriveDisplayValuation(data, currentMarketSnapshot);
  const summary = data.portfolioSummary.summary;
  const overall = data.performanceStatistics.overall;
  const sectorExposure = summary.sector_exposure;
  const confidenceBuckets = data.performanceStatistics.by_confidence_bucket;
  const marketState = data.portfolioSummary.market_state ?? summary.market_state;
  const lastMarketUpdate =
    data.portfolioSummary.last_market_update ?? summary.last_market_update;
  const livePrices = data.portfolioSummary.live_prices ?? summary.live_prices;
  const priceStatus = data.portfolioSummary.price_data_status ?? "UNAVAILABLE";
  const stalePositions =
    data.portfolioSummary.stale_positions ?? summary.stale_positions ?? 0;

  return (
    <div className="space-y-8">
      <PaperTradingBanner />

      <section className="reveal flex flex-col gap-3 border-y border-[#e8e8e3] py-5 text-sm text-black/52 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-x-8 gap-y-2">
          <span className="font-semibold text-black">
            {cleanStatus(marketState ?? "MARKET_CLOSED")}
          </span>
          <span>{updatedAgo(lastMarketUpdate)}</span>
          <span>
            {livePrices
              ? "Live market prices loaded"
              : priceStatus === "DELAYED"
                ? "Delayed market prices loaded"
                : "Waiting for fresh market prices"}
          </span>
        </div>
        {stalePositions > 0 ? (
          <div className="text-black/45">
            {stalePositions} positions waiting for fresh prices
          </div>
        ) : null}
      </section>

      <section className="reveal border-b border-[#e8e8e3] pb-5">
        <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-black/45">
          <span className="font-semibold text-black/72">
            {cleanStatus(currentMarketSnapshot?.market_state ?? "Unavailable")}
          </span>
          <span>{priceStatusLabel(displayValuation.price_status)}</span>
          <span>
            {displayValuation.usable_quote_count}/{data.openPositions.positions.length} holdings using current quote snapshot
          </span>
          <span>
            {displayValuation.latest_quote_timestamp
              ? `Updated ${updatedAgo(displayValuation.latest_quote_timestamp).replace("Updated ", "")}`
              : "Waiting for current market prices"}
          </span>
          {marketSnapshotError ? <span className="text-amber-700">Retaining last quote snapshot</span> : null}
        </div>
      </section>

      <section className="reveal grid grid-cols-2 gap-x-10 gap-y-6 border-b border-[#e8e8e3] py-8 md:grid-cols-4 xl:grid-cols-8">
        <ReportMetric label="Total Equity" value={money(displayValuation.display_total_equity)} />
        <ReportMetric label="Cash" value={money(displayValuation.cash)} />
        <ReportMetric label="Invested" value={money(displayValuation.display_invested_value)} />
        <ReportMetric label="Total Return" value={pct(displayValuation.display_total_return_pct)} />
        <ReportMetric label="Open Positions" value={`${summary.open_positions_count}`} />
        <ReportMetric label="Closed Trades" value={`${summary.closed_trades_count}`} />
        <ReportMetric label="Realized P/L" value={money(displayValuation.realized_pnl)} />
        <ReportMetric label="Unrealized P/L" value={money(displayValuation.display_unrealized_pnl)} />
        <ReportMetric label="Win Rate" value={optionalPct(overall.win_rate_pct, 0)} />
      </section>

      <PaperPortfolioBuilder
        data={data}
        webSnapshot={webSnapshot}
        governance={governance}
        marketSnapshot={marketSnapshot ?? null}
      />

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="reveal border-b border-[#e8e8e3] pb-10">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
            Simple Equity Curve
          </div>
          <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
            {pct(displayValuation.display_total_return_pct)} display return.
          </h2>
          <div className="mt-8">
            <EquityCurve points={data.equityCurve.points} />
          </div>
        </section>

        <section className="reveal reveal-delay-1 border-b border-[#e8e8e3] pb-10">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
            Performance Statistics
          </div>
          <div className="mt-6 grid grid-cols-2 gap-5">
            <Stat label="Trades" value={`${overall.total_trades}`} />
            <Stat label="Winners" value={`${overall.winning_trades}`} />
            <Stat label="Avg Return" value={optionalPct(overall.average_return_pct)} />
            <Stat label="Max Drawdown" value={optionalPct(overall.max_drawdown_pct)} />
            <Stat label="Realized P/L" value={money(overall.total_realized_pnl)} />
            <Stat
              label="Unrealized P/L"
              value={money(overall.total_unrealized_pnl)}
            />
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
        <section className="reveal border-b border-[#e8e8e3] pb-10">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
            Sector Exposure
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-[-0.06em] text-black">
            Concentration by simulated capital.
          </h2>

          <div className="mt-6 space-y-4">
            {sectorExposure.length > 0 ? (
              sectorExposure.map((sector) => (
                <ExposureBar
                  key={sector.sector}
                  label={sector.sector}
                  value={`${sector.portfolio_pct.toFixed(1)}%`}
                  width={sector.portfolio_pct}
                  detail={`${sector.position_count} positions · ${money(sector.value)}`}
                />
              ))
            ) : (
              <EmptyState label="No sector exposure available." />
            )}
          </div>
        </section>

        <section className="reveal reveal-delay-1 border-b border-[#e8e8e3] pb-10">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
            Confidence Buckets
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-[-0.06em] text-black">
            Win rate by signal strength.
          </h2>

          <div className="mt-6 space-y-4">
            {confidenceBuckets.length > 0 ? (
              confidenceBuckets.map((bucket) => (
                <ExposureBar
                  key={bucket.bucket}
                  label={bucket.bucket ?? "Unbucketed"}
                  value={optionalPct(bucket.win_rate_pct, 0)}
                  width={bucket.win_rate_pct ?? 0}
                  detail={`${bucket.total_trades} trades · ${optionalPct(bucket.average_return_pct)} avg`}
                />
              ))
            ) : (
              <EmptyState label="No confidence bucket statistics available." />
            )}
          </div>
        </section>
      </div>

      <section className="reveal border-b border-[#e8e8e3] pb-10">
        <div className="mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
              Open Positions
            </div>
            <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
              Active mock exposure.
            </h2>
          </div>
          <div className="text-sm text-black/45">
            {data.openPositions.positions.length} positions
          </div>
        </div>
        <OpenPositionsTable positions={displayValuation.positions} />
      </section>

      <section className="reveal border-b border-[#e8e8e3] pb-10">
        <div className="mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
              Closed Trades
            </div>
            <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
              Completed simulations.
            </h2>
          </div>
          <div className="text-sm text-black/45">
            {data.closedTrades.trades.length} trades
          </div>
        </div>
        <ClosedTradesTable trades={data.closedTrades.trades} />
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-black/10 pt-4">
      <div className="text-xs text-black/42">{label}</div>
      <div className="mt-2 text-3xl font-black tracking-[-0.06em] text-black">
        {value}
      </div>
    </div>
  );
}

function ExposureBar({
  label,
  value,
  width,
  detail,
}: {
  label: string;
  value: string;
  width: number;
  detail: string;
}) {
  const clampedWidth = Math.max(0, Math.min(width, 100));

  return (
    <div className="memo-panel border-t border-transparent pt-1">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="font-bold text-black">{label}</div>
          <div className="mt-1 text-xs text-black/42">{detail}</div>
        </div>
        <div className="font-mono text-sm font-bold text-black/40">{value}</div>
      </div>
      <div className="mt-3 h-2 bg-black/10">
        <div
          className="h-full origin-left bg-black transition-transform duration-700 ease-out"
          style={{ width: `${clampedWidth}%` }}
        />
      </div>
    </div>
  );
}

export default function PaperTradingPortfolio({
  result,
  webSnapshot = null,
  governance,
  marketSnapshot,
}: {
  result: PaperTradingLoadResult;
  webSnapshot?: WebSnapshot | null;
  governance?: PortfolioGovernance;
  marketSnapshot?: MarketSnapshot | null;
}) {
  if (result.status !== "ready") {
    return (
      <div className="space-y-8">
        <PaperTradingBanner />
        <PaperTradingStateCard result={result} />
      </div>
    );
  }

  return (
    <PortfolioContent
      data={result.data}
      webSnapshot={webSnapshot}
      governance={governance}
      marketSnapshot={marketSnapshot ?? null}
    />
  );
}

function ReportMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="reveal">
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-2 text-3xl font-black tracking-[-0.06em] text-black">
        {value}
      </div>
    </div>
  );
}
