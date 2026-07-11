"use client";

import { useState } from "react";
import Card from "@/components/ui/Card";
import {
  OpenPosition,
  PaperTradingData,
  PaperTradingLoadResult,
} from "@/lib/paperTrading";
import { GovernanceData, modeCapabilities } from "@/lib/governanceDisplay";
import { WebSnapshot } from "@/lib/webSnapshot";

type SortKey = "market_value" | "weight" | "unrealized_return" | "days_held";
type OriginFilter = "all" | "strategy_directed" | "user_directed";
type AllocationSlice = {
  id: string;
  label: string;
  value: number;
  weight: number;
  color: string;
  position: OpenPosition | null;
  startAngle: number;
  endAngle: number;
  midAngle: number;
};

type PortfolioSummaryProps = {
  result: PaperTradingLoadResult;
  webSnapshot: WebSnapshot | null;
  governance?: GovernanceData;
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
  if (!value) return "Awaiting fresh price";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function marketValue(position: OpenPosition) {
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

function positionWeight(position: OpenPosition, totalEquity: number) {
  const value = marketValue(position);
  if (!value || totalEquity <= 0) return null;
  return (value / totalEquity) * 100;
}

function originLabel(position: OpenPosition) {
  if (position.origin === "user_directed") return "User Directed";
  return "Strategy Directed";
}

function originFilterValue(position: OpenPosition): Exclude<OriginFilter, "all"> {
  return position.origin === "user_directed" ? "user_directed" : "strategy_directed";
}

function priceStatusLabel(position: OpenPosition) {
  if (position.stale_price_data) return "Stale";
  if (position.price_status === "fresh" || position.price_status === "delayed") {
    return position.price_status === "fresh" ? "Fresh" : "Delayed";
  }
  return position.price_status ?? "Unavailable";
}

function pnlTone(value: number | null | undefined) {
  if (typeof value !== "number") return "text-black/45";
  if (value > 0) return "text-emerald-700";
  if (value < 0) return "text-red-600";
  return "text-black/60";
}

function portfolioState(openCount: number, cashPct: number) {
  if (openCount === 0) return "Fully in cash.";
  if (openCount === 1) return "Concentrated.";
  if (openCount >= 5) return "Diversified.";
  if (cashPct >= 70) return "Cash-heavy.";
  return "Selective.";
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
}: PortfolioSummaryProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("market_value");
  const [originFilter, setOriginFilter] = useState<OriginFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (result.status !== "ready") {
    return (
      <Card className="p-9">
        <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
          Paper Portfolio Overview
        </div>
        <h2 className="mt-4 text-4xl font-black tracking-[-0.07em] text-black">
          Ledger unavailable.
        </h2>
        <p className="mt-4 text-base leading-7 text-black/52">{result.message}</p>
      </Card>
    );
  }

  return <LedgerOverview data={result.data} webSnapshot={webSnapshot} governance={governance} />;

  function LedgerOverview({
    data,
    webSnapshot,
    governance,
  }: {
    data: PaperTradingData;
    webSnapshot: WebSnapshot | null;
    governance?: GovernanceData;
  }) {
    const summary = data.portfolioSummary.summary;
    const positions = data.openPositions.positions ?? [];
    const totalEquity = safeNumber(summary.total_equity) ?? 0;
    const cash = safeNumber(summary.cash) ?? 0;
    const invested = safeNumber(summary.invested_value) ?? 0;
    const cashPct = totalEquity > 0 ? (cash / totalEquity) * 100 : 0;
    const stalePositions =
      data.portfolioSummary.stale_positions ?? summary.stale_positions ?? 0;
    const headline = portfolioState(positions.length, cashPct);
    const governanceMessage = governance
      ? modeCapabilities(governance.governance.mode).message
      : "Paper portfolio control mode unavailable.";
    const allocationSlices = buildAllocationSlices(positions, cash, totalEquity);
    const activeSlice = activeIndex === null ? null : allocationSlices[activeIndex];

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
            (safeNumber(b.unrealized_return_pct) ?? -Infinity) -
            (safeNumber(a.unrealized_return_pct) ?? -Infinity)
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
        ? "No simulated positions are currently open. The paper account remains fully in cash."
        : `${positions.length} open paper position${positions.length === 1 ? "" : "s"} with ${money(
            invested
          )} invested and ${money(cash)} held in cash.`;

    return (
      <div className="space-y-10">
        <Card className="p-0">
          <div className="grid grid-cols-1 gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="p-7 md:p-9">
              <div className="text-xs font-black uppercase tracking-[0.26em] text-black/40">
                Paper Portfolio Overview
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
                  {stalePositions} position{stalePositions === 1 ? " is" : "s are"} awaiting
                  fresh market prices. Last known prices are shown where available.
                </div>
              ) : null}

              <div className="mt-8 grid grid-cols-2 gap-x-8 gap-y-6 border-y border-[#e8e8e3] py-7 md:grid-cols-5">
                <OverviewMetric label="Cash" value={money(cash)} />
                <OverviewMetric label="Invested" value={money(invested)} />
                <OverviewMetric label="Total Return" value={pct(summary.total_return_pct)} />
                <OverviewMetric label="Unrealized P/L" value={money(summary.unrealized_pnl)} tone={pnlTone(summary.unrealized_pnl)} />
                <OverviewMetric label="Realized P/L" value={money(summary.realized_pnl)} tone={pnlTone(summary.realized_pnl)} />
                <OverviewMetric label="Open Positions" value={`${summary.open_positions_count ?? positions.length}`} />
                <OverviewMetric label="Closed Trades" value={`${summary.closed_trades_count ?? data.closedTrades.trades.length}`} />
                <OverviewMetric label="Cash %" value={`${cashPct.toFixed(1)}%`} />
                <OverviewMetric label="Stale Positions" value={`${stalePositions}`} />
                <OverviewMetric label="Price Status" value={data.portfolioSummary.price_data_status ?? "Insufficient data"} />
              </div>

              <div className="mt-6 grid grid-cols-1 gap-4 text-sm text-black/50 md:grid-cols-3">
                <StatusDatum label="Market State" value={data.portfolioSummary.market_state ?? summary.market_state ?? "Unavailable"} />
                <StatusDatum label="Latest Valuation" value={formatTimestamp(data.portfolioSummary.last_market_update ?? summary.last_market_update)} />
                <StatusDatum label="Ledger Refresh" value={formatTimestamp(data.portfolioSummary.generated_at)} />
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
                      <div className={`mt-1 ${pnlTone(activeSlice.position.unrealized_pnl)}`}>
                        {money(activeSlice.position.unrealized_pnl)} / {pct(activeSlice.position.unrealized_return_pct)} unrealized / {originLabel(activeSlice.position)}
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
              Fully in cash.
            </h3>
            <p className="mt-4 max-w-3xl text-lg leading-8 text-black/55">
              No simulated positions are currently open. Add a user-directed
              position from today&apos;s research queue or wait for an eligible
              automatic scanner entry.
            </p>

            <div className="mt-7 grid grid-cols-2 gap-6 md:grid-cols-5">
              <OverviewMetric label="Total Equity" value={money(totalEquity)} />
              <OverviewMetric label="Available Cash" value={money(cash)} />
              <OverviewMetric label="Invested Value" value={money(0)} />
              <OverviewMetric label="Open Positions" value="0" />
              <OverviewMetric label="Price Status" value={data.portfolioSummary.price_data_status ?? "Insufficient data"} />
            </div>

            <button
              type="button"
              onClick={openBuilder}
              className="mt-8 border border-black bg-black px-5 py-3 text-sm font-bold text-white transition duration-200 hover:-translate-y-0.5 hover:bg-black/85"
            >
              Add position
            </button>
          </Card>
        ) : (
          <Card className="p-0">
            <div className="flex flex-col gap-4 border-b border-[#e8e8e3] p-7 md:p-9 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                  Current Holdings
                </div>
                <h3 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
                  Ledger-backed positions only.
                </h3>
              </div>

              <div className="flex flex-wrap gap-3">
                <select
                  value={originFilter}
                  onChange={(event) => setOriginFilter(event.target.value as OriginFilter)}
                  className="border border-[#e8e8e3] bg-white px-3 py-2 text-sm"
                  aria-label="Filter holdings by origin"
                >
                  <option value="all">All origins</option>
                  <option value="strategy_directed">Strategy directed</option>
                  <option value="user_directed">User directed</option>
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

        <Card className="p-7 md:p-9">
          <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
            AI Research Candidates
          </div>
          <h3 className="mt-2 text-3xl font-black tracking-[-0.06em] text-black">
            Research only.
          </h3>
          <p className="mt-3 max-w-3xl text-base leading-7 text-black/55">
            These are current research candidates. They are not portfolio
            holdings unless added to the paper ledger.
          </p>

          <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
            {(webSnapshot?.ranked_candidates ?? data.dailyPicks.picks)
              .slice(0, 5)
              .map((candidate) => (
                <div key={candidate.ticker} className="border-t border-[#e8e8e3] pt-4">
                  <div className="text-2xl font-black tracking-[-0.06em] text-black">
                    {candidate.ticker}
                  </div>
                  <div className="mt-1 text-sm text-black/45">
                    {candidate.sector}
                  </div>
                  <div className="mt-3 text-sm font-bold text-black/70">
                    Research Rating: {candidate.action}
                  </div>
                </div>
              ))}
          </div>
        </Card>
      </div>
    );
  }
}

function buildAllocationSlices(
  positions: OpenPosition[],
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
            {active ? `${active.weight.toFixed(1)}% weight` : "Paper account"}
          </div>
        </div>
      </div>
    </div>
  );
}

function HoldingRow({
  position,
  totalEquity,
  expanded,
  onToggle,
}: {
  position: OpenPosition;
  totalEquity: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const value = marketValue(position);
  const weight = positionWeight(position, totalEquity);
  const stale = position.stale_price_data || position.price_status === "unavailable";

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
                Awaiting fresh price
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
            label="Unrealized"
            value={`${money(position.unrealized_pnl)} / ${pct(position.unrealized_return_pct)}`}
            tone={pnlTone(position.unrealized_pnl)}
          />
        </div>
      </div>

      {expanded ? (
        <div className="mt-7 grid grid-cols-2 gap-5 border-t border-[#e8e8e3] pt-6 md:grid-cols-4 xl:grid-cols-6">
          <RowMetric label="Entry Price" value={money(position.entry_price)} />
          <RowMetric label="Current Price" value={money(position.current_price)} />
          <RowMetric label="Days Held" value={`${position.days_held ?? "Unavailable"}`} />
          <RowMetric label="Planned Hold" value={`${position.planned_hold_period_days ?? "Unavailable"}D`} />
          <RowMetric label="Stop Loss" value={money(position.stop_loss_price)} />
          <RowMetric label="Take Profit" value={money(position.take_profit_price)} />
          <RowMetric label="Risk" value={position.entry_risk ?? position.risk_label ?? "Unavailable"} />
          <RowMetric label="Price Status" value={priceStatusLabel(position)} />
          <RowMetric label="Last Quote" value={formatTimestamp(position.last_price_update)} />
          <RowMetric label="Source" value={position.price_source ?? "Unavailable"} />
          <RowMetric label="Opened" value={formatTimestamp(position.opened_at)} />
          <RowMetric label="Paper Action" value={position.scanner_action ?? position.entry_action ?? "Unavailable"} />
        </div>
      ) : null}
    </button>
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
