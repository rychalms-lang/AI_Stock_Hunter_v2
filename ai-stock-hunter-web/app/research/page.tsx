import Link from "next/link";

import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import { paperTradingDisclaimer } from "@/components/paperTrading/PaperTradingBanner";
import { loadPaperTradingData } from "@/lib/paperTrading";
import { loadResearchArchive } from "@/lib/researchArchive";
import { loadResearchChanges } from "@/lib/researchChanges";
import { loadSystemStatus } from "@/lib/systemStatus";
import { cleanStatus, formatDate, formatDateTime, sourceLabel, terminology } from "@/lib/displayText";

function pct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export default async function ResearchPage() {
  const [paperTrading, systemStatus, archive, changes] = await Promise.all([
    loadPaperTradingData(),
    loadSystemStatus(),
    loadResearchArchive(),
    loadResearchChanges(),
  ]);
  const data = paperTrading.status === "ready" ? paperTrading.data : null;
  const picks = data?.dailyPicks.picks.slice(0, 6) ?? [];
  const generatedAt = data?.dailyPicks.generated_at;
  const sourceFile = data?.dailyPicks.source_file;
  const topPick = picks[0];
  const archiveCount = archive?.items.length ?? 0;
  const latestArchive = archive?.items[0];

  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-14 md:px-10 xl:px-16">
          <div className="page-enter mx-auto max-w-[1400px]">
            <header className="reveal grid grid-cols-1 gap-12 border-b border-[#e8e8e3] pb-14 xl:grid-cols-[28px_1fr_360px] xl:items-end">
              <div className="alpha-rail hidden h-[360px] xl:block" aria-hidden="true" />

              <div>
                <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
                  Today&apos;s Research
                </div>
                <h1 className="mt-6 max-w-5xl text-6xl font-black leading-[0.92] tracking-[-0.08em] md:text-8xl">
                  Understand why stocks are being surfaced.
                </h1>
                <p className="mt-9 max-w-3xl text-xl leading-9 text-black/58">
                  Review today&apos;s opportunities, what changed since the prior
                  update, and the evidence behind each research rating.
                </p>
                <div className="mt-8 flex flex-wrap gap-x-9 gap-y-3 border-y border-[#e8e8e3] py-4 text-sm text-black/45">
                  <span>
                    <span className="text-black/30">Market Status</span>{" "}
                    <span className="font-semibold text-black/72">
                      {cleanStatus(systemStatus?.market_state)}
                    </span>
                  </span>
                  <span>
                    <span className="text-black/30">Historical Comparisons</span>{" "}
                    <span className="font-semibold text-black/72">
                      {picks.reduce((total, pick) => total + pick.historical_matches, 0).toLocaleString()}
                    </span>
                  </span>
                  <span>
                    <span className="text-black/30">Archive</span>{" "}
                    <span className="font-semibold text-black/72">
                      {archiveCount} reports indexed
                    </span>
                  </span>
                  <span>
                    <span className="text-black/30">Latest / Prior</span>{" "}
                    <span className="font-semibold text-black/72">
                      {formatDate(changes?.current_date)} /{" "}
                      {formatDate(changes?.previous_date)}
                    </span>
                  </span>
                </div>
              </div>

              <aside className="border-l border-[#e8e8e3] pl-7">
                <div className="text-xs font-black uppercase tracking-[0.24em] text-black/35">
                  Latest Research Update
                </div>
                <div className="mt-5 text-4xl font-black tracking-[-0.07em]">
                  {picks.length} opportunities
                </div>
                <div className="mt-5 space-y-2 text-sm leading-6 text-black/48">
                  <div>{formatDateTime(generatedAt)}</div>
                  <div>{sourceLabel(sourceFile)}</div>
                  <div>Active Strategy: V8</div>
                  <div>
                    {systemStatus?.daily_pipeline.status
                      ? `Daily update ${cleanStatus(systemStatus.daily_pipeline.status)}`
                      : "Daily update unavailable"}
                  </div>
                </div>
              </aside>
            </header>

            <div className="grid grid-cols-1 gap-16 py-16 xl:grid-cols-[1fr_320px]">
              <section className="reveal reveal-delay-1">
                <div className="mb-8 flex flex-col gap-3 border-b border-[#e8e8e3] pb-7 md:flex-row md:items-end md:justify-between">
                  <div>
                    <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
                      Research List
                    </div>
                    <h2 className="mt-3 text-4xl font-black tracking-[-0.07em] md:text-5xl">
                      Opportunities prepared.
                    </h2>
                  </div>
                  {topPick ? (
                    <Link
                      href={`/candidates/${topPick.ticker}`}
                      className="subtle-link text-xs font-black uppercase tracking-[0.18em] text-black/42 hover:text-black"
                    >
                      Open top case →
                    </Link>
                  ) : null}
                  <Link
                    href="/research/archive"
                    className="subtle-link text-xs font-black uppercase tracking-[0.18em] text-black/42 hover:text-black"
                  >
                    Archive →
                  </Link>
                  {latestArchive ? (
                    <Link
                      href={`/research/archive/${latestArchive.date}`}
                      className="subtle-link text-xs font-black uppercase tracking-[0.18em] text-black/42 hover:text-black"
                    >
                      Latest detail →
                    </Link>
                  ) : null}
                </div>

                <div className="divide-y divide-[#e8e8e3]">
                  {picks.length > 0 ? (
                    picks.map((pick, index) => (
                      <Link
                        key={pick.pick_id}
                        href={`/candidates/${pick.ticker}`}
                        className="interactive-row reveal grid grid-cols-1 gap-4 py-7 md:grid-cols-[56px_1fr_0.45fr_0.45fr_0.45fr_120px] md:items-center md:px-3"
                        style={{ animationDelay: `${index * 55}ms` }}
                      >
                        <div className="font-mono text-sm font-semibold text-black/32">
                          #{pick.rank.toString().padStart(2, "0")}
                        </div>
                        <div>
                          <div className="text-3xl font-black tracking-[-0.06em]">
                            {pick.ticker}
                          </div>
                          <div className="mt-2 text-xs text-black/42">
                            {pick.sector}
                          </div>
                        </div>
                        <ResearchDatum label={terminology.strategySignal} value={pick.action} />
                        <ResearchDatum
                          label="Confidence"
                          value={`${pick.confidence.toFixed(0)}%`}
                        />
                        <ResearchDatum
                          label="Expected"
                          value={pct(pick.expected_return_pct)}
                        />
                        <div className="subtle-link text-xs font-black uppercase tracking-[0.18em] text-black/38">
                          View →
                        </div>
                      </Link>
                    ))
                  ) : (
                    <div className="py-8 text-sm text-black/48">
                      Research list is unavailable because today&apos;s research data
                      could not be loaded.
                    </div>
                  )}
                </div>
              </section>

              <aside className="reveal reveal-delay-2 space-y-12 border-l border-[#e8e8e3] pl-8">
                <section className="memo-panel border-t border-transparent pt-1">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
                    Research Summary
                  </div>
                  <p className="mt-5 text-base font-medium leading-8 text-black/62">
                    This workspace is for reviewing opportunities, comparing
                    changes, and understanding the evidence behind today&apos;s
                    research view. It does not place trades.
                  </p>
                  <p className="mt-5 border-t border-[#e8e8e3] pt-5 text-xs leading-5 text-black/42">
                    AI Research Ratings summarize the overall research view.
                    Strategy Signals show what the active strategy produced.
                  </p>
                </section>

                <section className="memo-panel border-t border-transparent pt-1">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
                    What Changed
                  </div>
                  <p className="mt-5 text-base font-medium leading-8 text-black/62">
                    {changes?.status === "ready"
                      ? `${changes.summary.new_candidates} new opportunities, ${changes.summary.removed_candidates} removed, ${changes.summary.rank_changes} rank movements, and ${changes.summary.action_changes} signal changes versus ${formatDate(changes.previous_date)}.`
                      : "Waiting for another research update before a reliable change summary can be prepared."}
                  </p>
                  {changes?.rank_changes?.[0] ? (
                    <p className="mt-4 text-sm leading-6 text-black/48">
                      Largest mover: {changes.rank_changes[0].ticker} from #
                      {changes.rank_changes[0].previous_rank} to #
                      {changes.rank_changes[0].current_rank}.
                    </p>
                  ) : null}
                </section>

                <section className="memo-panel border-t border-transparent pt-1">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
                    Guardrails
                  </div>
                  <div className="mt-5 space-y-4 text-sm leading-6 text-black/58">
                    <div>Research evidence only.</div>
                    <div>Active Strategy: V8.</div>
                    <div>Simulated trading only.</div>
                    <div>No broker connected.</div>
                  </div>
                  <p className="mt-7 border-t border-[#e8e8e3] pt-5 text-xs leading-5 text-black/42">
                    {paperTradingDisclaimer}
                  </p>
                </section>
              </aside>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function ResearchDatum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-1 font-black text-black">{value}</div>
    </div>
  );
}
