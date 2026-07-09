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

function DashboardContent({ data }: { data: PaperTradingData }) {
  const summary = data.portfolioSummary.summary;
  const overall = data.performanceStatistics.overall;
  const picks = data.dailyPicks.picks.slice(0, 5);

  return (
    <section className="mt-12 space-y-6">
      <PaperTradingBanner />

      <Card className="p-0">
        <div className="grid grid-cols-1 divide-y divide-white/10 md:grid-cols-5 md:divide-x md:divide-y-0">
          <Metric
            label="Paper Portfolio Value"
            value={money(summary.total_equity)}
          />
          <Metric label="Total Return" value={pct(summary.total_return_pct)} />
          <Metric label="Win Rate" value={`${overall.win_rate_pct.toFixed(0)}%`} />
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
            <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
              Today&apos;s Picks · Scanner Feed
            </div>
            <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-white">
              Research queue feeding paper mode.
            </h2>
          </div>

          <div className="text-sm text-white/45">
            Generated {data.dailyPicks.generated_at}
          </div>
        </div>

        <div className="mt-6 divide-y divide-white/10">
          {picks.map((pick) => (
            <div
              key={pick.pick_id}
              className="grid grid-cols-2 gap-4 py-4 md:grid-cols-[0.6fr_1fr_0.7fr_0.7fr_0.7fr]"
            >
              <div>
                <div className="text-2xl font-black tracking-[-0.05em] text-white">
                  {pick.ticker}
                </div>
                <div className="text-xs text-white/42">{pick.sector}</div>
              </div>

              <div className="text-sm leading-6 text-white/60">
                {pick.ai_explanation.summary}
              </div>

              <div>
                <div className="text-xs text-white/42">Action</div>
                <div className="mt-1 font-black text-white">{pick.action}</div>
              </div>

              <div>
                <div className="text-xs text-white/42">Confidence</div>
                <div className="mt-1 font-black text-white">
                  {pick.confidence.toFixed(0)}%
                </div>
              </div>

              <div>
                <div className="text-xs text-white/42">Expected</div>
                <div className="mt-1 font-black text-white">
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
