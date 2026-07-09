import Card from "@/components/ui/Card";
import Metric from "@/components/ui/Metric";
import {
  ClosedTrade,
  EquityPoint,
  OpenPosition,
  PaperTradingData,
  PaperTradingLoadResult,
} from "@/lib/paperTrading";
import PaperTradingBanner from "./PaperTradingBanner";
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

function pnlClass(value: number) {
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-red-300";
  return "text-white/70";
}

function EquityCurve({ points }: { points: EquityPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="border border-white/10 bg-white/[0.03] p-6 text-sm text-white/45">
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
        aria-label="Mock paper trading equity curve"
      >
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="1"
        />
        <path
          d={pathData}
          fill="none"
          stroke="#d7ff5f"
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
              fill={index === points.length - 1 ? "#d7ff5f" : "#ffffff"}
            />
          );
        })}
      </svg>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-white/45 md:grid-cols-4">
        {points.map((point) => (
          <div key={point.date} className="border-t border-white/10 pt-3">
            <div>{point.date}</div>
            <div className="mt-1 font-bold text-white">
              {money(point.total_equity)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OpenPositionsTable({ positions }: { positions: OpenPosition[] }) {
  if (positions.length === 0) {
    return <EmptyState label="No open paper positions." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="border-b border-white/10 text-xs uppercase tracking-[0.18em] text-white/40">
          <tr>
            <th className="py-3 pr-4">Ticker</th>
            <th className="py-3 pr-4">Sector</th>
            <th className="py-3 pr-4">Entry</th>
            <th className="py-3 pr-4">Current</th>
            <th className="py-3 pr-4">Value</th>
            <th className="py-3 pr-4">Unrealized</th>
            <th className="py-3 pr-4">Hold</th>
            <th className="py-3 pr-4">Risk</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {positions.map((position) => (
            <tr key={position.position_id}>
              <td className="py-4 pr-4 text-xl font-black tracking-[-0.05em] text-white">
                {position.ticker}
              </td>
              <td className="py-4 pr-4 text-white/58">{position.sector}</td>
              <td className="py-4 pr-4">{money(position.entry_price)}</td>
              <td className="py-4 pr-4">{money(position.current_price)}</td>
              <td className="py-4 pr-4">{money(position.current_value)}</td>
              <td className={`py-4 pr-4 font-bold ${pnlClass(position.unrealized_pnl)}`}>
                {money(position.unrealized_pnl)} ·{" "}
                {pct(position.unrealized_return_pct)}
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
    return <EmptyState label="No closed paper trades." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-left text-sm">
        <thead className="border-b border-white/10 text-xs uppercase tracking-[0.18em] text-white/40">
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
        <tbody className="divide-y divide-white/10">
          {trades.map((trade) => (
            <tr key={trade.trade_id}>
              <td className="py-4 pr-4 text-xl font-black tracking-[-0.05em] text-white">
                {trade.ticker}
              </td>
              <td className="py-4 pr-4 text-white/58">
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
    <div className="border border-white/10 bg-white/[0.03] p-6 text-sm text-white/45">
      {label}
    </div>
  );
}

function PortfolioContent({ data }: { data: PaperTradingData }) {
  const summary = data.portfolioSummary.summary;
  const overall = data.performanceStatistics.overall;
  const sectorExposure = summary.sector_exposure;
  const confidenceBuckets = data.performanceStatistics.by_confidence_bucket;

  return (
    <div className="space-y-8">
      <PaperTradingBanner />

      <Card className="p-0">
        <div className="grid grid-cols-1 divide-y divide-white/10 md:grid-cols-4 md:divide-x md:divide-y-0">
          <Metric
            label="Portfolio Summary"
            value={money(summary.total_equity)}
          />
          <Metric label="Total Return" value={pct(summary.total_return_pct)} />
          <Metric
            label="Open Positions"
            value={`${summary.open_positions_count}`}
          />
          <Metric label="Win Rate" value={`${overall.win_rate_pct.toFixed(0)}%`} />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="p-8">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
            Simple Equity Curve
          </div>
          <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-white">
            {pct(summary.total_return_pct)} mock return.
          </h2>
          <div className="mt-8">
            <EquityCurve points={data.equityCurve.points} />
          </div>
        </Card>

        <Card className="p-8">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
            Performance Statistics
          </div>
          <div className="mt-6 grid grid-cols-2 gap-5">
            <Stat label="Trades" value={`${overall.total_trades}`} />
            <Stat label="Winners" value={`${overall.winning_trades}`} />
            <Stat label="Avg Return" value={pct(overall.average_return_pct)} />
            <Stat label="Max Drawdown" value={pct(overall.max_drawdown_pct)} />
            <Stat label="Realized P/L" value={money(overall.total_realized_pnl)} />
            <Stat
              label="Unrealized P/L"
              value={money(overall.total_unrealized_pnl)}
            />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
        <Card className="p-8">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
            Sector Exposure
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-[-0.06em] text-white">
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
        </Card>

        <Card className="p-8">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
            Confidence Buckets
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-[-0.06em] text-white">
            Win rate by signal strength.
          </h2>

          <div className="mt-6 space-y-4">
            {confidenceBuckets.length > 0 ? (
              confidenceBuckets.map((bucket) => (
                <ExposureBar
                  key={bucket.bucket}
                  label={bucket.bucket ?? "Unbucketed"}
                  value={`${bucket.win_rate_pct.toFixed(0)}%`}
                  width={bucket.win_rate_pct}
                  detail={`${bucket.total_trades} trades · ${pct(bucket.average_return_pct)} avg`}
                />
              ))
            ) : (
              <EmptyState label="No confidence bucket statistics available." />
            )}
          </div>
        </Card>
      </div>

      <Card className="p-8">
        <div className="mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
              Open Positions
            </div>
            <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-white">
              Active mock exposure.
            </h2>
          </div>
          <div className="text-sm text-white/45">
            {data.openPositions.positions.length} positions
          </div>
        </div>
        <OpenPositionsTable positions={data.openPositions.positions} />
      </Card>

      <Card className="p-8">
        <div className="mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
              Closed Trades
            </div>
            <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-white">
              Completed simulations.
            </h2>
          </div>
          <div className="text-sm text-white/45">
            {data.closedTrades.trades.length} trades
          </div>
        </div>
        <ClosedTradesTable trades={data.closedTrades.trades} />
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-white/10 pt-4">
      <div className="text-xs text-white/42">{label}</div>
      <div className="mt-2 text-3xl font-black tracking-[-0.06em] text-white">
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
    <div>
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="font-bold text-white">{label}</div>
          <div className="mt-1 text-xs text-white/42">{detail}</div>
        </div>
        <div className="font-mono text-sm font-bold text-[#d7ff5f]">{value}</div>
      </div>
      <div className="mt-3 h-2 bg-white/10">
        <div className="h-full bg-[#d7ff5f]" style={{ width: `${clampedWidth}%` }} />
      </div>
    </div>
  );
}

export default function PaperTradingPortfolio({
  result,
}: {
  result: PaperTradingLoadResult;
}) {
  if (result.status !== "ready") {
    return (
      <div className="space-y-8">
        <PaperTradingBanner />
        <PaperTradingStateCard result={result} />
      </div>
    );
  }

  return <PortfolioContent data={result.data} />;
}
