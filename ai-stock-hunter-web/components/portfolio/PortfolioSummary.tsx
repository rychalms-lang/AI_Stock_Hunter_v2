"use client";

import { useState } from "react";
import Card from "@/components/ui/Card";
import {
  OpenPosition,
  PaperTradingData,
  PaperTradingLoadResult,
} from "@/lib/paperTrading";
import { GovernanceData, modeCapabilities } from "@/lib/governanceDisplay";
import { MarketSnapshot, priceStatusLabel as marketPriceStatusLabel } from "@/lib/marketSnapshot";
import { DisplayPosition, deriveDisplayValuation } from "@/lib/portfolioDisplayValuation";
import { useMarketSnapshot } from "@/lib/useMarketSnapshot";
import { WebSnapshot } from "@/lib/webSnapshot";
import PaperPortfolioBuilder from "@/components/paperTrading/PaperPortfolioBuilder";
import { cleanStatus } from "@/lib/displayText";

type SortKey = "market_value" | "weight" | "unrealized_return" | "days_held";
type OriginFilter = "all" | "strategy_directed" | "user_directed";
type AllocationSlice = {
  id: string;
  label: string;
  value: number;
  weight: number;
  color: string;
  position: DisplayPosition | null;
  startAngle: number;
  endAngle: number;
  midAngle: number;
};

type PortfolioSummaryProps = {
  result: PaperTradingLoadResult;
  webSnapshot: WebSnapshot | null;
  governance?: GovernanceData;
  marketSnapshot?: MarketSnapshot | null;
};

const colors = [
  "#050505",
  "#525252",
  "#8a8a82",
  "#b8b8b0",
  "#7f7f76",
  "#d7d7cf",
  "#2c2c2c",
  "#a7b86b",
];

function money(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Unavailable";
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function pct(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Insufficient data";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatTimestamp(value?: string | null) {
  if (!value) return "Waiting for next market update";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function marketValue(position: OpenPosition | DisplayPosition) {
  if ("display_market_value" in position) return position.display_market_value;
  return (
    safeNumber(position.market_value) ??
    safeNumber(position.current_value) ??
    safeNumber(position.notional_cost) ??
    null
  );
}

function safeNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function positionWeight(position: OpenPosition | DisplayPosition, totalEquity: number) {
  const value = marketValue(position);
  if (!value || totalEquity <= 0) return null;
  return (value / totalEquity) * 100;
}

function originLabel(position: OpenPosition | DisplayPosition) {
  if (position.origin === "user_directed") return "Added by User";
  return "Added by V8";
}

function originFilterValue(position: OpenPosition | DisplayPosition): Exclude<OriginFilter, "all"> {
  return position.origin === "user_directed" ? "user_directed" : "strategy_directed";
}

function priceStatusLabel(position: OpenPosition | DisplayPosition) {
  if ("display_price_status" in position) return marketPriceStatusLabel(position.display_price_status);
  if (position.stale_price_data) return "Out of date";
  return cleanStatus(position.price_status);
}

function pnlTone(value: number | null | undefined) {
  if (typeof value !== "number") return "text-black/45";
  if (value > 0) return "text-emerald-700";
  if (value < 0) return "text-red-600";
  return "text-black/60";
}

function portfolioState(openCount: number, cashPct: number) {
  if (openCount === 0) return "Fully in cash.";
  if (openCount === 1) return "1 open position.";
  if (openCount >= 5) return "Broadly invested.";
  if (cashPct >= 70) return "Cash-heavy.";
  return "Moderate exposure.";
}

function polarToCartesian(cx: number, cy: number, r: number, angle: number) {
  const angleInRadians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(angleInRadians),
    y: cy + r * Math.sin(angleInRadians),
  };
}

function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number
) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

function openBuilder() {
  window.dispatchEvent(new CustomEvent("paper-builder:open"));
}

export default function PortfolioSummary({
  result,
  webSnapshot,
  governance,
  marketSnapshot,
}: PortfolioSummaryProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("market_value");
  const [originFilter, setOriginFilter] = useState<OriginFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (result.status !== "ready") {
    return (
      <Card className="p-9">
        <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
          Simulated Portfolio Overview
        </div>
        <h2 className="mt-4 text-4xl font-black tracking-[-0.07em] text-black">
          Simulated portfolio unavailable.
        </h2>
        <p className="mt-4 text-base leading-7 text-black/52">{result.message}</p>
      </Card>
    );
  }

  return (
    <LedgerOverview
      data={result.data}
      webSnapshot={webSnapshot}
      governance={governance}
      initialMarketSnapshot={marketSnapshot ?? null}
    />
  );

  function LedgerOverview({
    data,
    webSnapshot,
    governance,
    initialMarketSnapshot,
  }: {
    data: PaperTradingData;
    webSnapshot: WebSnapshot | null;
    governance?: GovernanceData;
    initialMarketSnapshot: MarketSnapshot | null;
  }) {
    const { snapshot: currentMarketSnapshot } = useMarketSnapshot(initialMarketSnapshot);
    const displayValuation = deriveDisplayValuation(data, currentMarketSnapshot);
    const summary = data.portfolioSummary.summary;
    const positions = displayValuation.positions;
    const totalEquity = displayValuation.display_total_equity;
    const cash = displayValuation.cash;
    const invested = displayValuation.display_invested_value;
    const cashPct = displayValuation.display_cash_pct;
    const stalePositions = displayValuation.missing_quote_count;
    const headline = portfolioState(positions.length, cashPct);
    const governanceMessage = governance
      ? modeCapabilities(governance.governance.mode).message
      : "Portfolio control mode unavailable.";
    const allocationSlices = buildAllocationSlices(positions, cash, totalEquity);
    const activeSlice = activeIndex === null ? null : allocationSlices[activeIndex];
    const pendingProposalCount =
      governance?.proposals.filter((proposal) => proposal.status === "pending").length ?? 0;
    const governanceMode = governance?.governance.mode ?? "ai_managed";

    const filteredPositions = (() => {
      const visible = positions.filter((position) => {
        if (originFilter === "all") return true;
        return originFilterValue(position) === originFilter;
      });

      return visible.sort((a, b) => {
        if (sortKey === "days_held") {
          return (safeNumber(b.days_held) ?? 0) - (safeNumber(a.days_held) ?? 0);
        }
        if (sortKey === "unrealized_return") {
          return (
            b.display_unrealized_return_pct -
            a.display_unrealized_return_pct
          );
        }
        if (sortKey === "weight") {
          return (
            (positionWeight(b, totalEquity) ?? -Infinity) -
            (positionWeight(a, totalEquity) ?? -Infinity)
          );
        }
        return (marketValue(b) ?? -Infinity) - (marketValue(a) ?? -Infinity);
      });
    })();

    const supportingText =
      positions.length === 0
        ? "No simulated positions are currently open. The simulated account remains fully in cash."
        : `${positions.length} open simulated position${positions.length === 1 ? "" : "s"} with ${money(
            invested
          )} invested and ${money(cash)} held in cash.`;

    return (
      <div className="space-y-10">
        <PaperPortfolioBuilder
          data={data}
          webSnapshot={webSnapshot}
          governance={governance?.governance}
          marketSnapshot={currentMarketSnapshot}
          hideLauncher
        />

        <Card className="p-0">
          <div className="grid grid-cols-1 gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="p-7 md:p-9">
              <div className="text-xs font-black uppercase tracking-[0.26em] text-black/40">
                Simulated Portfolio Overview
              </div>

              <div className="mt-5 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h2 className="text-5xl font-black tracking-[-0.075em] text-black md:text-7xl">
                    {headline}
                  </h2>
                  <p className="mt-5 max-w-3xl text-lg leading-8 text-black/55">
                    {governanceMessage} {supportingText}
                  </p>
                </div>

                <div className="lg:text-right">
                  <div className="text-xs uppercase tracking-[0.18em] text-black/35">
                    Total Equity
                  </div>
                  <div className="mt-2 text-5xl font-black tracking-[-0.075em] text-black">
                    {money(totalEquity)}
                  </div>
                </div>
              </div>

              {stalePositions > 0 ? (
                <div className="mt-6 border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                  {stalePositions} position{stalePositions === 1 ? " is" : "s are"} using
                  the last recorded price because a usable market quote is unavailable.
                </div>
              ) : null}

              <div className="mt-8 grid grid-cols-2 gap-x-8 gap-y-6 border-y border-[#e8e8e3] py-7 md:grid-cols-5">
                <OverviewMetric label="Cash" value={money(cash)} />
                <OverviewMetric label="Invested" value={money(invested)} />
                <OverviewMetric label="Total Return" value={pct(displayValuation.display_total_return_pct)} />
                <OverviewMetric
                  label="Unrealized P/L"
                  value={money(displayValuation.display_unrealized_pnl)}
                  tone={pnlTone(displayValuation.display_unrealized_pnl)}
                />
                <OverviewMetric label="Realized P/L" value={money(summary.realized_pnl)} tone={pnlTone(summary.realized_pnl)} />
                <OverviewMetric label="Open Positions" value={`${summary.open_positions_count ?? positions.length}`} />
                <OverviewMetric label="Closed Trades" value={`${summary.closed_trades_count ?? data.closedTrades.trades.length}`} />
                <OverviewMetric label="Cash %" value={`${cashPct.toFixed(1)}%`} />
                <OverviewMetric label="Out-of-Date Positions" value={`${stalePositions}`} />
                <OverviewMetric
                  label="Price Status"
                  value={marketPriceStatusLabel(displayValuation.price_status)}
                />
              </div>

              <div className="mt-6 grid grid-cols-1 gap-4 text-sm text-black/50 md:grid-cols-3">
                <StatusDatum label="Market State" value={cleanStatus(currentMarketSnapshot?.market_state ?? data.portfolioSummary.market_state ?? summary.market_state)} />
                <StatusDatum label="Current Display Valuation" value={formatTimestamp(displayValuation.latest_quote_timestamp)} />
                <StatusDatum label="Portfolio Update" value={formatTimestamp(data.portfolioSummary.generated_at)} />
              </div>
            </div>

            <div className="border-t border-[#e8e8e3] p-7 md:p-9 xl:border-l xl:border-t-0">
              <AllocationChart
                slices={allocationSlices}
                activeIndex={activeIndex}
                setActiveIndex={setActiveIndex}
                totalEquity={totalEquity}
              />

              <div className="mt-5 min-h-[82px] border-t border-[#e8e8e3] pt-5 text-sm text-black/52">
                {activeSlice ? (
                  <div>
                    <div className="font-bold text-black">{activeSlice.label}</div>
                    <div className="mt-1">
                      {money(activeSlice.value)} / {activeSlice.weight.toFixed(1)}% of portfolio
                    </div>
                    {activeSlice.position ? (
                      <div className={`mt-1 ${pnlTone(activeSlice.position.display_unrealized_pnl)}`}>
                        {money(activeSlice.position.display_unrealized_pnl)} / {pct(activeSlice.position.display_unrealized_return_pct)} unrealized / {originLabel(activeSlice.position)}
                      </div>
                    ) : (
                      <div className="mt-1">Cash reserve</div>
                    )}
                  </div>
                ) : (
                  <div>Hover a slice to inspect current value, weight, P/L, and origin.</div>
                )}
              </div>
            </div>
          </div>
        </Card>

        {positions.length === 0 ? (
          <Card className="p-9">
            <h3 className="text-4xl font-black tracking-[-0.07em] text-black">
              Current Holdings
            </h3>
            <p className="mt-4 max-w-3xl text-lg leading-8 text-black/55">
              No simulated positions are currently open. The simulated account is
              fully in cash.
            </p>

            <div className="mt-7 grid grid-cols-2 gap-6 md:grid-cols-5">
              <OverviewMetric label="Total Equity" value={money(totalEquity)} />
              <OverviewMetric label="Available Cash" value={money(cash)} />
              <OverviewMetric label="Invested Value" value={money(0)} />
              <OverviewMetric label="Open Positions" value="0" />
              <OverviewMetric label="Price Status" value={marketPriceStatusLabel(displayValuation.price_status)} />
            </div>

            <HoldingsModeAction mode={governanceMode} pendingProposalCount={pendingProposalCount} />
          </Card>
        ) : (
          <Card className="p-0">
            <div className="flex flex-col gap-4 border-b border-[#e8e8e3] p-7 md:p-9 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                  Current Holdings
                </div>
                <h3 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
                  Open simulated positions.
                </h3>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-black/50">
                  Positions shown here are recorded in the simulated portfolio. Research
                  opportunities stay out of holdings until a simulated entry is
                  actually created.
                </p>
              </div>

              <div className="flex flex-col gap-3 lg:items-end">
                <HoldingsModeAction mode={governanceMode} pendingProposalCount={pendingProposalCount} compact />
                <div className="flex flex-wrap gap-3">
                  <select
                    value={originFilter}
                    onChange={(event) => setOriginFilter(event.target.value as OriginFilter)}
                    className="border border-[#e8e8e3] bg-white px-3 py-2 text-sm"
                    aria-label="Filter holdings by origin"
                  >
                    <option value="all">All origins</option>
                    <option value="strategy_directed">Added by V8</option>
                    <option value="user_directed">Added by User</option>
                  </select>
                  <select
                    value={sortKey}
                    onChange={(event) => setSortKey(event.target.value as SortKey)}
                    className="border border-[#e8e8e3] bg-white px-3 py-2 text-sm"
                    aria-label="Sort holdings"
                  >
                    <option value="market_value">Market value</option>
                    <option value="weight">Portfolio weight</option>
                    <option value="unrealized_return">Unrealized return</option>
                    <option value="days_held">Days held</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="divide-y divide-[#e8e8e3]">
              {filteredPositions.length > 0 ? (
                filteredPositions.map((position) => (
                  <HoldingRow
                    key={position.position_id}
                    position={position}
                    totalEquity={totalEquity}
                    expanded={expandedId === position.position_id}
                    onToggle={() =>
                      setExpandedId(
                        expandedId === position.position_id ? null : position.position_id
                      )
                    }
                  />
                ))
              ) : (
                <div className="p-8 text-sm text-black/50">
                  No holdings match the selected origin filter.
                </div>
              )}
            </div>
          </Card>
        )}

        <PerformanceSection data={data} displayValuation={displayValuation} />
        <AllocationRiskSection positions={positions} totalEquity={totalEquity} stalePositions={stalePositions} />
        <ActivitySection data={data} />
      </div>
    );
  }
}

function buildAllocationSlices(
  positions: DisplayPosition[],
  cash: number,
  totalEquity: number
): AllocationSlice[] {
  const baseSlices: Array<Omit<AllocationSlice, "startAngle" | "endAngle" | "midAngle">> = positions
    .map((position, index) => {
      const value = marketValue(position);
      if (!value || totalEquity <= 0) return null;
      return {
        id: position.position_id,
        label: position.ticker,
        value,
        weight: (value / totalEquity) * 100,
        color: colors[index % colors.length],
        position,
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  if (totalEquity > 0 && cash > 0) {
    baseSlices.push({
      id: "cash",
      label: "Cash",
      value: cash,
      weight: (cash / totalEquity) * 100,
      color: "#eeeeea",
      position: null,
    });
  }

  if (baseSlices.length === 0 && totalEquity > 0) {
    baseSlices.push({
      id: "cash",
      label: "Cash",
      value: totalEquity,
      weight: 100,
      color: "#eeeeea",
      position: null,
    });
  }

  let angle = 0;
  return baseSlices.map((slice) => {
    const startAngle = angle;
    const endAngle = angle + slice.weight * 3.6;
    angle = endAngle;
    return {
      ...slice,
      startAngle,
      endAngle,
      midAngle: (startAngle + endAngle) / 2,
    };
  });
}

function AllocationChart({
  slices,
  activeIndex,
  setActiveIndex,
  totalEquity,
}: {
  slices: AllocationSlice[];
  activeIndex: number | null;
  setActiveIndex: (index: number | null) => void;
  totalEquity: number;
}) {
  const active = activeIndex === null ? null : slices[activeIndex];
  const cashOnly = slices.length === 1 && slices[0]?.id === "cash";

  return (
    <div className="flex flex-col items-center">
      <div
        className="relative h-[260px] w-[260px]"
        onMouseLeave={() => setActiveIndex(null)}
      >
        <svg viewBox="0 0 260 260" className="h-full w-full overflow-visible">
          {slices.map((slice, index) => {
            const isActive = activeIndex === index;
            return (
              <path
                key={slice.id}
                d={describeArc(130, 130, 92, slice.startAngle, slice.endAngle)}
                fill="none"
                stroke={slice.color}
                strokeWidth={isActive ? 38 : 32}
                className="cursor-pointer transition-all duration-200"
                onMouseEnter={() => setActiveIndex(index)}
              />
            );
          })}
        </svg>

        <div className="absolute inset-[72px] flex flex-col items-center justify-center text-center">
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-black/35">
            {active ? active.label : cashOnly ? "100% Cash" : "Total Equity"}
          </div>
          <div className="mt-2 text-[30px] font-black tracking-[-0.08em] text-black">
            {active ? money(active.value) : money(totalEquity)}
          </div>
          <div className="mt-1 text-[11px] text-black/42">
            {active ? `${active.weight.toFixed(1)}% weight` : "Simulated account"}
          </div>
        </div>
      </div>
    </div>
  );
}

function HoldingsModeAction({
  mode,
  pendingProposalCount,
  compact = false,
}: {
  mode: string;
  pendingProposalCount: number;
  compact?: boolean;
}) {
  if (mode === "user_managed") {
    return (
      <button
        type="button"
        onClick={openBuilder}
        className={`border border-black bg-black text-sm font-bold text-white transition duration-200 hover:-translate-y-0.5 hover:bg-black/85 ${
          compact ? "px-4 py-2" : "mt-8 px-5 py-3"
        }`}
      >
        Add position
      </button>
    );
  }

  if (mode === "ai_assisted") {
    return pendingProposalCount > 0 ? (
      <div className={`text-sm font-bold text-black/62 ${compact ? "" : "mt-8"}`}>
        {pendingProposalCount} suggested simulated trade{pendingProposalCount === 1 ? "" : "s"} awaiting review.
      </div>
    ) : (
      <div className={`text-sm text-black/45 ${compact ? "" : "mt-8"}`}>
        No simulated trade suggestions are waiting for review.
      </div>
    );
  }

  return (
    <div className={`text-sm text-black/45 ${compact ? "" : "mt-8"}`}>
      Manual position creation is disabled in AI Managed mode.
    </div>
  );
}

function PerformanceSection({
  data,
  displayValuation,
}: {
  data: PaperTradingData;
  displayValuation: ReturnType<typeof deriveDisplayValuation>;
}) {
  const stats = data.performanceStatistics.overall;
  const points = data.equityCurve.points;

  return (
    <Card className="p-7 md:p-9">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
            Performance
          </div>
          <h3 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
            Portfolio performance.
          </h3>
        </div>
        <div className="text-sm text-black/45">
          Updated {formatTimestamp(data.portfolioSummary.generated_at)}
        </div>
      </div>

      <div className="mt-7 grid grid-cols-2 gap-x-8 gap-y-6 border-y border-[#e8e8e3] py-7 md:grid-cols-4">
        <OverviewMetric label="Total Return" value={pct(displayValuation.display_total_return_pct)} />
        <OverviewMetric label="Win Rate" value={pct(stats.win_rate_pct)} />
        <OverviewMetric label="Realized P/L" value={money(stats.total_realized_pnl)} tone={pnlTone(stats.total_realized_pnl)} />
        <OverviewMetric label="Unrealized P/L" value={money(displayValuation.display_unrealized_pnl)} tone={pnlTone(displayValuation.display_unrealized_pnl)} />
        <OverviewMetric label="Total Trades" value={`${stats.total_trades}`} />
        <OverviewMetric label="Average Return" value={pct(stats.average_return_pct)} />
        <OverviewMetric label="Max Drawdown" value={pct(stats.max_drawdown_pct)} tone={pnlTone(-Math.abs(stats.max_drawdown_pct ?? 0))} />
        <OverviewMetric
          label="Avg Hold"
          value={
            safeNumber(stats.average_hold_days) === null
              ? "Insufficient data"
              : `${safeNumber(stats.average_hold_days)?.toFixed(1)}D`
          }
        />
      </div>

      <EquityCurvePreview points={points} />
    </Card>
  );
}

function EquityCurvePreview({ points }: { points: PaperTradingData["equityCurve"]["points"] }) {
  if (points.length === 0) {
    return (
      <div className="mt-7 border-t border-[#e8e8e3] pt-6 text-sm text-black/45">
        Equity curve will appear after the first portfolio snapshot.
      </div>
    );
  }

  const values = points.map((point) => point.total_equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 720;
  const height = 150;
  const path = points
    .map((point, index) => {
      const x = points.length === 1 ? 0 : (index / (points.length - 1)) * width;
      const y = height - ((point.total_equity - min) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  const latest = points[points.length - 1];

  return (
    <div className="mt-7">
      <div className="flex items-center justify-between gap-4 border-t border-[#e8e8e3] pt-6">
        <div className="text-sm font-bold text-black/62">Simple equity curve</div>
        <div className="text-sm text-black/45">
          {latest.date} / {money(latest.total_equity)}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-5 h-[150px] w-full overflow-visible">
        <path d={path} fill="none" stroke="#050505" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}

function AllocationRiskSection({
  positions,
  totalEquity,
  stalePositions,
}: {
  positions: DisplayPosition[];
  totalEquity: number;
  stalePositions: number;
}) {
  const sectorRows = groupPositions(positions, totalEquity, (position) => position.sector || "Unknown");
  const originRows = groupPositions(positions, totalEquity, originLabel);
  const riskRows = groupPositions(
    positions,
    totalEquity,
    (position) => position.entry_risk ?? position.risk_label ?? "Unknown"
  );

  return (
    <Card className="p-7 md:p-9">
      <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
        Portfolio Risk
      </div>
      <h3 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
        Exposure map.
      </h3>

      <div className="mt-7 grid grid-cols-1 gap-8 xl:grid-cols-3">
        <ExposureTable title="Sector Exposure" rows={sectorRows} />
        <ExposureTable title="Position Source" rows={originRows} />
        <ExposureTable title="Risk Buckets" rows={riskRows} />
      </div>

      <div className="mt-7 grid grid-cols-2 gap-6 border-t border-[#e8e8e3] pt-6 md:grid-cols-4">
        <OverviewMetric label="Open Positions" value={`${positions.length}`} />
        <OverviewMetric label="Largest Position" value={largestPositionWeight(positions, totalEquity)} />
        <OverviewMetric label="Out-of-Date Prices" value={`${stalePositions}`} />
        <OverviewMetric label="Current Price Coverage" value={positions.length === 0 ? "No positions" : pct(((positions.length - stalePositions) / positions.length) * 100)} />
      </div>
    </Card>
  );
}

function ActivitySection({ data }: { data: PaperTradingData }) {
  const trades = data.closedTrades.trades.slice(0, 8);

  return (
    <Card className="p-7 md:p-9">
      <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
        Activity / Closed Trades
      </div>
      <h3 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
        Completed simulations.
      </h3>

      {trades.length === 0 ? (
        <p className="mt-5 max-w-3xl text-base leading-7 text-black/50">
          No completed simulations yet. Closed simulations will appear here after
          an exit is recorded.
        </p>
      ) : (
        <div className="mt-7 divide-y divide-[#e8e8e3] border-y border-[#e8e8e3]">
          {trades.map((trade) => (
            <div
              key={trade.trade_id}
              className="grid grid-cols-2 gap-x-6 gap-y-4 py-5 md:grid-cols-[1fr_1fr_1fr_1fr_1.2fr]"
            >
              <RowMetric label="Ticker" value={trade.ticker} />
              <RowMetric label="Return" value={pct(trade.realized_return_pct)} tone={pnlTone(trade.realized_return_pct)} />
              <RowMetric label="Realized P/L" value={money(trade.realized_pnl)} tone={pnlTone(trade.realized_pnl)} />
              <RowMetric label="Hold" value={`${trade.actual_hold_days}D`} />
              <RowMetric label="Exit" value={trade.exit_reason} />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function HoldingRow({
  position,
  totalEquity,
  expanded,
  onToggle,
}: {
  position: DisplayPosition;
  totalEquity: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const value = marketValue(position);
  const weight = positionWeight(position, totalEquity);
  const stale = !position.display_uses_live_quote;

  return (
    <button
      type="button"
      onClick={onToggle}
      className="block w-full p-6 text-left transition duration-200 hover:bg-[#fafafa] md:p-8"
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_1.25fr]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-4xl font-black tracking-[-0.07em] text-black">
              {position.ticker}
            </div>
            <span className="border border-[#e8e8e3] px-2.5 py-1 text-xs font-bold text-black/50">
              {originLabel(position)}
            </span>
            {stale ? (
              <span className="border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-900">
                Last recorded price
              </span>
            ) : null}
          </div>
          <div className="mt-2 text-sm text-black/45">{position.sector}</div>
        </div>

        <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
          <RowMetric label="Qty" value={`${position.quantity ?? "Unavailable"}`} />
          <RowMetric label="Value" value={money(value)} />
          <RowMetric label="Weight" value={weight === null ? "Insufficient data" : `${weight.toFixed(2)}%`} />
          <RowMetric
            label="Today"
            value={pct(position.display_price_change_today_pct)}
            tone={pnlTone(position.display_price_change_today_pct)}
          />
          <RowMetric
            label="Unrealized"
            value={`${money(position.display_unrealized_pnl)} / ${pct(position.display_unrealized_return_pct)}`}
            tone={pnlTone(position.display_unrealized_pnl)}
          />
        </div>
      </div>

      {expanded ? (
        <div className="mt-7 grid grid-cols-2 gap-5 border-t border-[#e8e8e3] pt-6 md:grid-cols-4 xl:grid-cols-6">
          <RowMetric label="Entry Price" value={money(position.entry_price)} />
          <RowMetric label="Current Price" value={money(position.display_current_price)} />
          <RowMetric label="Today’s Change" value={pct(position.display_price_change_today_pct)} tone={pnlTone(position.display_price_change_today_pct)} />
          <RowMetric label="Market Value" value={money(position.display_market_value)} />
          <RowMetric label="Unrealized P/L" value={money(position.display_unrealized_pnl)} tone={pnlTone(position.display_unrealized_pnl)} />
          <RowMetric label="Unrealized Return" value={pct(position.display_unrealized_return_pct)} tone={pnlTone(position.display_unrealized_return_pct)} />
          <RowMetric label="Days Held" value={`${position.days_held ?? "Unavailable"}`} />
          <RowMetric label="Planned Hold" value={`${position.planned_hold_period_days ?? "Unavailable"}D`} />
          <RowMetric label="Stop Loss" value={money(position.stop_loss_price)} />
          <RowMetric label="Take Profit" value={money(position.take_profit_price)} />
          <RowMetric label="Risk" value={position.entry_risk ?? position.risk_label ?? "Unavailable"} />
          <RowMetric label="Price Status" value={priceStatusLabel(position)} />
          <RowMetric label="Last Updated" value={formatTimestamp(position.display_quote_timestamp)} />
          <RowMetric label="Source" value={position.display_price_source} />
          <RowMetric label="Opened" value={formatTimestamp(position.opened_at)} />
          <RowMetric label="Strategy Signal" value={position.scanner_action ?? position.entry_action ?? "Unavailable"} />
        </div>
      ) : null}
    </button>
  );
}

function groupPositions(
  positions: DisplayPosition[],
  totalEquity: number,
  labelFor: (position: DisplayPosition) => string
) {
  const map = new Map<string, { label: string; value: number; count: number }>();

  positions.forEach((position) => {
    const label = labelFor(position);
    const value = marketValue(position) ?? 0;
    const current = map.get(label) ?? { label, value: 0, count: 0 };
    current.value += value;
    current.count += 1;
    map.set(label, current);
  });

  return Array.from(map.values())
    .map((row) => ({
      ...row,
      weight: totalEquity > 0 ? (row.value / totalEquity) * 100 : 0,
    }))
    .sort((a, b) => b.value - a.value);
}

function largestPositionWeight(positions: DisplayPosition[], totalEquity: number) {
  if (positions.length === 0 || totalEquity <= 0) return "No positions";
  const largest = Math.max(...positions.map((position) => marketValue(position) ?? 0));
  return `${((largest / totalEquity) * 100).toFixed(1)}%`;
}

function ExposureTable({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: number; weight: number; count: number }>;
}) {
  return (
    <div>
      <div className="text-sm font-black tracking-[-0.02em] text-black">{title}</div>
      <div className="mt-4 divide-y divide-[#e8e8e3] border-y border-[#e8e8e3]">
        {rows.length === 0 ? (
          <div className="py-4 text-sm text-black/45">No exposure yet.</div>
        ) : (
          rows.slice(0, 6).map((row) => (
            <div key={row.label} className="grid grid-cols-[1fr_auto] gap-4 py-4">
              <div className="min-w-0">
                <div className="truncate text-sm font-bold text-black/75">{row.label}</div>
                <div className="mt-1 text-xs text-black/38">
                  {row.count} position{row.count === 1 ? "" : "s"}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-black">{row.weight.toFixed(1)}%</div>
                <div className="mt-1 text-xs text-black/38">{money(row.value)}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function OverviewMetric({
  label,
  value,
  tone = "text-black",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">{label}</div>
      <div className={`mt-2 text-2xl font-black tracking-[-0.055em] ${tone}`}>
        {value}
      </div>
    </div>
  );
}

function RowMetric({
  label,
  value,
  tone = "text-black",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-xs uppercase tracking-[0.16em] text-black/35">{label}</div>
      <div className={`mt-1 break-words text-base font-bold ${tone}`}>{value}</div>
    </div>
  );
}

function StatusDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-[#e8e8e3] pt-3">
      <span className="text-black/35">{label}: </span>
      <span className="font-bold text-black/65">{value}</span>
    </div>
  );
}
