import Link from "next/link";
import { readFile } from "fs/promises";
import path from "path";

import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import PaperTradingStateCard from "@/components/paperTrading/PaperTradingStateCard";
import { paperTradingDisclaimer } from "@/components/paperTrading/PaperTradingBanner";
import { LiveQuoteContext } from "@/components/market/LiveQuoteContext";
import Card from "@/components/ui/Card";
import { MarketSnapshot } from "@/lib/marketSnapshot";
import { loadMarketSnapshot } from "@/lib/marketSnapshotServer";
import { cleanStatus, explainers, formatDate, formatDateTime, sourceLabel, strategyStatusLabel, terminology } from "@/lib/displayText";
import {
  ClosedTrade,
  DailyPick,
  loadPaperTradingData,
  OpenPosition,
  PaperTradingData,
} from "@/lib/paperTrading";
import { AIRecommendation, WebSnapshot } from "@/lib/webSnapshot";

type PageProps = {
  params: Promise<{
    ticker: string;
  }>;
};

function money(value: number) {
  return `$${value.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })}`;
}

function pct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function metricValue(value: number | null | undefined, suffix = "") {
  if (typeof value !== "number") return null;
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;
}

function findCandidate(data: PaperTradingData, ticker: string) {
  const normalizedTicker = ticker.toUpperCase();

  return data.dailyPicks.picks.find(
    (pick) => pick.ticker.toUpperCase() === normalizedTicker
  );
}

function findOpenPosition(data: PaperTradingData, pick: DailyPick) {
  return data.openPositions.positions.find(
    (position) =>
      position.ticker.toUpperCase() === pick.ticker.toUpperCase() ||
      position.source_pick_id === pick.pick_id
  );
}

function findClosedTrade(data: PaperTradingData, pick: DailyPick) {
  return data.closedTrades.trades.find(
    (trade) =>
      trade.ticker.toUpperCase() === pick.ticker.toUpperCase() ||
      trade.source_pick_id === pick.pick_id
  );
}

async function loadWebSnapshot() {
  try {
    const filePath = path.join(process.cwd(), "..", "data", "web_snapshot.json");
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as WebSnapshot;
  } catch {
    return null;
  }
}

function findResearchRating(snapshot: WebSnapshot | null, ticker: string) {
  const normalizedTicker = ticker.toUpperCase();

  return snapshot?.ranked_candidates.find(
    (candidate) => candidate.ticker.toUpperCase() === normalizedTicker
  );
}

function paperExecutionStatus(
  data: PaperTradingData,
  pick: DailyPick,
  openPosition?: OpenPosition,
  closedTrade?: ClosedTrade
) {
  if (openPosition) return "Open";
  if (closedTrade) return "Closed";

  if (pick.paper_trade_decision === "eligible_scanner_export") {
    return data.portfolioSummary.stale_price_data
      ? "Waiting for fresh price data"
      : "Eligible";
  }

  return "Not eligible";
}

function signalSummary(
  pick: DailyPick,
  regime: string,
  researchRating?: AIRecommendation
) {
  const ratingText = researchRating
    ? `AI Research Rating: ${researchRating.action}. `
    : "";

  return `${ratingText}${pick.ticker} ranks #${pick.rank} in today’s research list with a strategy signal of ${pick.action}, ${pick.confidence.toFixed(
    0
  )}% confidence, ${pct(pick.expected_return_pct)} expected return, ${pick.historical_matches.toLocaleString()} similar historical setups, and a ${pick.best_hold_period_days}-day suggested hold under a ${regime} market regime. Simulated trades act only when the active strategy signal allows it.`;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-14 md:px-10 xl:px-16">
          <div className="page-enter">{children}</div>
        </section>
      </div>
    </main>
  );
}

function NotFoundState({ ticker }: { ticker: string }) {
  return (
    <Shell>
      <div className="mx-auto max-w-5xl">
        <Card className="p-10">
          <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
            Stock Analysis Not Found
          </div>
          <h1 className="mt-4 text-5xl font-black tracking-[-0.08em] md:text-7xl">
            {ticker.toUpperCase()}
          </h1>
          <p className="mt-5 max-w-2xl text-sm leading-6 text-black/58">
            This ticker was not found in the current research list. The Morning
            Brief only links stocks that exist in the latest loaded research
            data.
          </p>
          <Link
            href="/"
            className="mt-8 inline-flex border border-black bg-black px-5 py-3 text-xs font-black uppercase tracking-[0.18em] text-white"
          >
            Back to Morning Brief
          </Link>
        </Card>
      </div>
    </Shell>
  );
}

function EvidenceMetric({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  if (!value) return null;

  return (
    <div className="border-t border-[#e8e8e3] pt-4">
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-2 text-2xl font-black tracking-[-0.05em] text-black">
        {value}
      </div>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;

  return (
    <div>
      <div className="text-xs font-black uppercase tracking-[0.22em] text-black/40">
        {title}
      </div>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <div
            key={item}
            className="border-l border-black/20 pl-4 text-sm leading-6 text-black/62"
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniStatus({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-[#e8e8e3] py-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-1 break-words text-sm font-semibold text-black/72">{value}</div>
    </div>
  );
}

function SectionLabel({ title }: { title: string }) {
  return (
    <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
      {title}
    </div>
  );
}

function CandidateDetail({
  data,
  pick,
  researchRating,
  openPosition,
  closedTrade,
  marketSnapshot,
}: {
  data: PaperTradingData;
  pick: DailyPick;
  researchRating?: AIRecommendation;
  openPosition?: OpenPosition;
  closedTrade?: ClosedTrade;
  marketSnapshot: MarketSnapshot | null;
}) {
  const regime = data.dailyPicks.market_regime.label;
  const executionStatus = paperExecutionStatus(
    data,
    pick,
    openPosition,
    closedTrade
  );

  return (
    <Shell>
      <article className="mx-auto max-w-7xl">
        <header className="reveal mb-12 border-b border-[#e8e8e3] pb-12">
          <div>
            <Link
              href="/"
              className="text-xs font-black uppercase tracking-[0.24em] text-black/45"
            >
              Morning Brief / Stock Analysis
            </Link>
            <div className="mt-5 text-sm font-semibold text-black/48">
              {pick.sector} / {terminology.strategySignal}: {pick.action} / Updated{" "}
              {formatDateTime(data.dailyPicks.generated_at)}
            </div>
            <h1 className="mt-6 text-8xl font-black leading-none tracking-[-0.1em] md:text-[150px]">
              {pick.ticker}
            </h1>
            <p className="mt-8 max-w-4xl text-2xl font-medium leading-10 text-black/68">
              {signalSummary(pick, regime, researchRating)}
            </p>
          </div>
        </header>

        <section className="reveal reveal-delay-1 mb-14 grid grid-cols-2 gap-x-8 gap-y-6 border-b border-[#e8e8e3] pb-10 md:grid-cols-4 xl:grid-cols-8">
          <MemoMetric label={terminology.aiResearchRating} value={researchRating?.action ?? "Unavailable"} />
          <MemoMetric label={terminology.strategySignal} value={pick.action} />
          <MemoMetric label={terminology.simulatedTradeStatus} value={executionStatus} />
          <MemoMetric label="Rank" value={`#${pick.rank}`} />
          <MemoMetric label="Confidence" value={`${pick.confidence.toFixed(0)}%`} />
          <MemoMetric label="Expected" value={pct(pick.expected_return_pct)} />
          <MemoMetric label="Hold" value={`${pick.best_hold_period_days}D`} />
          <MemoMetric label="Matches" value={pick.historical_matches.toLocaleString()} />
        </section>

        <div className="grid grid-cols-1 gap-16 xl:grid-cols-[0.68fr_0.32fr]">
          <div className="space-y-16">
            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Research Summary" />
              <p className="mt-5 text-xl font-medium leading-9 text-black/68">
                {signalSummary(pick, regime, researchRating)}
              </p>
              <p className="mt-5 max-w-3xl text-xs leading-5 text-black/42">
                {explainers.aiResearchRating} {explainers.strategySignal}{" "}
                {explainers.simulatedTradeStatus}
              </p>
            </section>

            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Why This Stock Appears" />
              <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-3">
                <MemoNarrative
                  title="Research thesis"
                  body={`${pick.ticker} ranked #${pick.rank} with ${pick.confidence.toFixed(
                    0
                  )}% confidence, ${pct(pick.expected_return_pct)} expected return, ${pick.historical_matches.toLocaleString()} historical matches, and ${pick.volume_ratio.toFixed(
                    2
                  )}x volume ratio.`}
                />
                <MemoNarrative
                  title="Bull case"
                  body={
                    pick.ai_explanation.strengths[0] ??
                    "No explicit strength notes were available for this stock."
                  }
                />
                <MemoNarrative
                  title="Risk case"
                  body={
                    pick.ai_explanation.risks[0] ??
                    "No explicit risk notes were available for this stock."
                  }
                />
              </div>
            </section>

            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Current Market Context" />
              <div className="mt-5">
                <LiveQuoteContext
                  ticker={pick.ticker}
                  scannerReferencePrice={pick.latest_close}
                  initialSnapshot={marketSnapshot}
                />
              </div>
            </section>

            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Strategy Evidence" />
              <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
                <EvidenceMetric
                  label="5D Change"
                  value={metricValue(pick.five_day_change_pct, "%")}
                />
                <EvidenceMetric
                  label="20D Change"
                  value={metricValue(pick.twenty_day_change_pct, "%")}
                />
                <EvidenceMetric
                  label="Relative Strength"
                  value={metricValue(pick.relative_strength_pct, "%")}
                />
                <EvidenceMetric
                  label="Volume Ratio"
                  value={metricValue(pick.volume_ratio, "x")}
                />
                <EvidenceMetric label="Latest Open" value={money(pick.latest_open)} />
                <EvidenceMetric label="Latest Close" value={money(pick.latest_close)} />
                <EvidenceMetric label="Score" value={metricValue(pick.score)} />
                <EvidenceMetric
                  label="Confidence"
                  value={metricValue(pick.confidence, "%")}
                />
              </div>
            </section>

            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Historical Evidence" />
              <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
                <EvidenceMetric
                  label="Historical Comparisons"
                  value={pick.historical_matches.toLocaleString()}
                />
                <EvidenceMetric
                  label="Historical Best Avg Return"
                  value={metricValue(pick.historical_best_avg_return_pct, "%")}
                />
                <EvidenceMetric
                  label="Win Probability"
                  value={metricValue(pick.win_probability_pct, "%")}
                />
                <EvidenceMetric
                  label="Best Hold Period"
                  value={`${pick.best_hold_period_days} days`}
                />
              </div>
            </section>

            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="AI Research Explanation" />
              <p className="mt-5 text-lg leading-8 text-black/62">
                {pick.ai_explanation.summary}
              </p>

              <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
                <ListBlock title="Strengths" items={pick.ai_explanation.strengths} />
                <ListBlock title="Risks" items={pick.ai_explanation.risks} />
              </div>

              {pick.ai_explanation.similar_historical_cases.length > 0 ? (
                <div className="mt-8">
                  <div className="text-xs font-black uppercase tracking-[0.22em] text-black/40">
                    Similar Historical Setups
                  </div>
                  <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
                    {pick.ai_explanation.similar_historical_cases.map((item) => (
                      <div
                        key={item.label}
                        className="border-t border-[#e8e8e3] pt-4"
                      >
                        <div className="font-bold text-black">{item.label}</div>
                        <div className="mt-3 text-sm leading-6 text-black/56">
                          {item.count.toLocaleString()} cases ·{" "}
                          {pct(item.average_return_pct)} avg ·{" "}
                          {item.win_rate_pct.toFixed(0)}% win rate
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          </div>

          <aside className="reveal reveal-delay-2 space-y-12 border-l border-[#e8e8e3] pl-8 xl:sticky xl:top-16 xl:self-start">
            <section className="memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Data Sources" />
              <div className="mt-5 space-y-1 text-sm leading-6 text-black/48">
                <div>Active Strategy: {pick.strategy.name} {pick.strategy.version} / {strategyStatusLabel(pick.strategy.status)}</div>
                <div>{terminology.aiResearchRating}: {researchRating?.action ?? "Unavailable"}</div>
                <div>{terminology.strategySignal}: {pick.action}</div>
                <div>{terminology.simulatedTradeStatus}: {executionStatus}</div>
                <div>Market regime: {regime}</div>
                <div>
                  {data.dailyPicks.source_file
                    ? `Research source: ${sourceLabel(data.dailyPicks.source_file)}`
                    : "Research source unavailable"}
                </div>
                <div>Research update: {formatDateTime(data.dailyPicks.generated_at)}</div>
                <div>
                  Portfolio updated: {formatDateTime(data.portfolioSummary.generated_at)}
                </div>
              </div>
            </section>

            <section className="memo-panel border-t border-transparent pt-4">
              <SectionLabel title="Simulated Trade Status" />
              <div className="mt-5 text-3xl font-black tracking-[-0.07em] text-black">
                {executionStatus}
              </div>
              <p className="mt-5 text-sm leading-6 text-black/58">
                {pick.paper_trade_decision_reason}
              </p>

              <div className="mt-6 space-y-3">
                <MiniStatus label={terminology.strategySignal} value={pick.action} />
                <MiniStatus label={terminology.simulatedTradeStatus} value={executionStatus} />
                <MiniStatus
                  label="Eligibility"
                  value={pick.paper_trade_candidate ? "Eligible" : "Not eligible"}
                />
                <MiniStatus label="Decision" value={cleanStatus(pick.paper_trade_decision)} />
                <MiniStatus
                  label="Price Data"
                  value={cleanStatus(data.portfolioSummary.price_data_status ?? "fresh")}
                />
                <MiniStatus
                  label="Open Match"
                  value={openPosition ? openPosition.position_id : "None"}
                />
                <MiniStatus
                  label="Closed Match"
                  value={closedTrade ? closedTrade.trade_id : "None"}
                />
              </div>

              <p className="mt-7 border-t border-black/10 pt-5 text-xs leading-5 text-black/42">
                {paperTradingDisclaimer}
              </p>
            </section>

            <section className="memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Technical Details" />
              <div className="mt-6 space-y-3">
                <MiniStatus label="Pick ID" value={pick.pick_id} />
                <MiniStatus label="Research Date" value={formatDate(pick.trade_date)} />
                <MiniStatus
                  label="Daily Update Version"
                  value={pick.research_metadata.scanner_version}
                />
                <MiniStatus
                  label="Feature Version"
                  value={pick.research_metadata.feature_version}
                />
                <MiniStatus
                  label="Research Source Type"
                  value={cleanStatus(pick.research_metadata.generated_from)}
                />
              </div>
            </section>
          </aside>
        </div>
      </article>
    </Shell>
  );
}

function MemoMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-2 text-2xl font-black tracking-[-0.05em] text-black">
        {value}
      </div>
    </div>
  );
}

function MemoNarrative({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-t border-[#e8e8e3] pt-4">
      <div className="text-xs font-black uppercase tracking-[0.2em] text-black/35">
        {title}
      </div>
      <p className="mt-3 text-sm leading-6 text-black/62">{body}</p>
    </div>
  );
}

export default async function CandidatePage({ params }: PageProps) {
  const { ticker } = await params;
  const [result, snapshot, marketSnapshot] = await Promise.all([
    loadPaperTradingData(),
    loadWebSnapshot(),
    loadMarketSnapshot(),
  ]);

  if (result.status !== "ready") {
    return (
      <Shell>
        <div className="mx-auto max-w-5xl">
          <PaperTradingStateCard result={result} />
        </div>
      </Shell>
    );
  }

  const pick = findCandidate(result.data, ticker);

  if (!pick) {
    return <NotFoundState ticker={ticker} />;
  }

  return (
    <CandidateDetail
      data={result.data}
      pick={pick}
      researchRating={findResearchRating(snapshot, pick.ticker)}
      openPosition={findOpenPosition(result.data, pick)}
      closedTrade={findClosedTrade(result.data, pick)}
      marketSnapshot={marketSnapshot.status === "ready" ? marketSnapshot.data : null}
    />
  );
}
