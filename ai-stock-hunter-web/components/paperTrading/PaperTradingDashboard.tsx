import Card from "@/components/ui/Card";
import Metric from "@/components/ui/Metric";
import {
  PaperTradingData,
  PaperTradingLoadResult,
} from "@/lib/paperTrading";
import PaperTradingBanner from "./PaperTradingBanner";
import PaperTradingStateCard from "./PaperTradingStateCard";

function money(value: number) {
  return `$${value.toLocaleString(undefined, {
    maximumFractionDigits: 0,
  })}`;
}

function pct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatMarketState(value?: string) {
  if (value === "OPEN") return "Market Open";
  if (value === "PRE_MARKET") return "Pre Market";
  if (value === "AFTER_HOURS") return "After Hours";
  return "Market Closed";
}

function updatedAgo(value?: string | null) {
  if (!value) return "Waiting for fresh market prices";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "Update time unavailable";
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 60) return `Updated ${seconds} seconds ago`;
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? `Updated ${minutes} minutes ago` : `Updated ${Math.round(minutes / 60)} hours ago`;
}

function optionalPct(value: number | null | undefined, digits = 2) {
  if (typeof value !== "number") return "Insufficient data";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

function DashboardContent({ data }: { data: PaperTradingData }) {
  const summary = data.portfolioSummary.summary;
  const overall = data.performanceStatistics.overall;
  const picks = data.dailyPicks.picks.slice(0, 5);
  const marketState = data.portfolioSummary.market_state ?? summary.market_state;
  const lastMarketUpdate =
    data.portfolioSummary.last_market_update ?? summary.last_market_update;
  const livePrices = data.portfolioSummary.live_prices ?? summary.live_prices;

  return (
    <section className="mt-12 space-y-6">
      <PaperTradingBanner />

      <div className="flex flex-col gap-2 border-y border-black/10 py-4 text-sm text-black/52 md:flex-row md:items-center md:justify-between">
        <span className="font-semibold text-black">{formatMarketState(marketState)}</span>
        <span>{updatedAgo(lastMarketUpdate)}</span>
        <span>
          {livePrices
            ? "Live market prices loaded"
            : "Waiting for fresh market prices"}
        </span>
      </div>

      <Card className="p-0">
        <div className="grid grid-cols-1 divide-y divide-black/10 md:grid-cols-5 md:divide-x md:divide-y-0">
          <Metric
            label="Paper Portfolio Value"
            value={money(summary.total_equity)}
          />
          <Metric label="Total Return" value={pct(summary.total_return_pct)} />
          <Metric label="Win Rate" value={optionalPct(overall.win_rate_pct, 0)} />
          <Metric
            label="Active Positions"
            value={`${summary.open_positions_count}`}
          />
          <Metric label="Today's Picks" value={`${data.dailyPicks.picks.length}`} />
        </div>
      </Card>

      <Card className="p-8">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
              Today&apos;s Picks · Scanner Feed
            </div>
            <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
              Research queue feeding paper mode.
            </h2>
          </div>

          <div className="text-sm text-black/45">
            Generated {data.dailyPicks.generated_at}
          </div>
        </div>

        <div className="mt-6 divide-y divide-black/10">
          {picks.map((pick) => (
            <div
              key={pick.pick_id}
              className="grid grid-cols-2 gap-4 py-4 md:grid-cols-[0.6fr_1fr_0.7fr_0.7fr_0.7fr]"
            >
              <div>
                <div className="text-2xl font-black tracking-[-0.05em] text-black">
                  {pick.ticker}
                </div>
                <div className="text-xs text-black/42">{pick.sector}</div>
              </div>

              <div className="text-sm leading-6 text-black/60">
                {pick.ai_explanation.summary}
              </div>

              <div>
                <div className="text-xs text-black/42">Scanner Action</div>
                <div className="mt-1 font-black text-black">{pick.action}</div>
              </div>

              <div>
                <div className="text-xs text-black/42">Confidence</div>
                <div className="mt-1 font-black text-black">
                  {pick.confidence.toFixed(0)}%
                </div>
              </div>

              <div>
                <div className="text-xs text-black/42">Expected</div>
                <div className="mt-1 font-black text-black">
                  {pct(pick.expected_return_pct)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </section>
  );
}

export default function PaperTradingDashboard({
  result,
}: {
  result: PaperTradingLoadResult;
}) {
  if (result.status !== "ready") {
    return (
      <section className="mt-12 space-y-6">
        <PaperTradingBanner />
        <PaperTradingStateCard result={result} />
      </section>
    );
  }

  return <DashboardContent data={result.data} />;
}
