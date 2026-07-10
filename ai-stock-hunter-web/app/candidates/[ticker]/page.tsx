import Link from "next/link";
import { readFile } from "fs/promises";
import path from "path";

import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import PaperTradingStateCard from "@/components/paperTrading/PaperTradingStateCard";
import { paperTradingDisclaimer } from "@/components/paperTrading/PaperTradingBanner";
import Card from "@/components/ui/Card";
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

function formatTimestamp(value?: string) {
  if (!value) return "Unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
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
    ? `The web analysis layer assigns a research rating of ${researchRating.action}. `
    : "";

  return `${ratingText}${pick.ticker} appeared in today’s scanner queue as rank ${pick.rank} with scanner action ${pick.action}, ${pick.confidence.toFixed(
    0
  )}% scanner confidence, ${pct(pick.expected_return_pct)} expected return, ${pick.historical_matches.toLocaleString()} historical matches, and a ${pick.best_hold_period_days}-day suggested hold under a ${regime} market regime. Paper trades are authorized only by the raw scanner action.`;
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
            Candidate Not Found
          </div>
          <h1 className="mt-4 text-5xl font-black tracking-[-0.08em] md:text-7xl">
            {ticker.toUpperCase()}
          </h1>
          <p className="mt-5 max-w-2xl text-sm leading-6 text-black/58">
            This ticker was not found in the current paper-trading daily picks
            export. The dashboard queue only links candidates present in the
            loaded JSON data.
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
}: {
  data: PaperTradingData;
  pick: DailyPick;
  researchRating?: AIRecommendation;
  openPosition?: OpenPosition;
  closedTrade?: ClosedTrade;
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
              Morning Brief / Candidates
            </Link>
            <div className="mt-5 text-sm font-semibold text-black/48">
              {pick.sector} / Scanner Action: {pick.action} / Generated{" "}
              {formatTimestamp(data.dailyPicks.generated_at)}
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
          <MemoMetric label="Research Rating" value={researchRating?.action ?? "Unavailable"} />
          <MemoMetric label="Scanner Action" value={pick.action} />
          <MemoMetric label="Paper Execution" value={executionStatus} />
          <MemoMetric label="Rank" value={`#${pick.rank}`} />
          <MemoMetric label="Confidence" value={`${pick.confidence.toFixed(0)}%`} />
          <MemoMetric label="Expected" value={pct(pick.expected_return_pct)} />
          <MemoMetric label="Hold" value={`${pick.best_hold_period_days}D`} />
          <MemoMetric label="Matches" value={pick.historical_matches.toLocaleString()} />
        </section>

        <div className="grid grid-cols-1 gap-16 xl:grid-cols-[0.68fr_0.32fr]">
          <div className="space-y-16">
            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Signal Summary" />
              <p className="mt-5 text-xl font-medium leading-9 text-black/68">
                {signalSummary(pick, regime, researchRating)}
              </p>
              <p className="mt-5 max-w-3xl text-xs leading-5 text-black/42">
                Research ratings summarize the web analysis layer. Paper trades
                are authorized only by the raw scanner action.
              </p>
            </section>

            <section className="reveal memo-panel border-t border-transparent pt-1">
              <SectionLabel title="Scanner Evidence" />
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
                  label="Historical Matches"
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
              <SectionLabel title="AI Explanation" />
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
                    Similar Historical Cases
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
              <SectionLabel title="Research Metadata" />
              <div className="mt-5 space-y-1 text-sm leading-6 text-black/48">
                <div>{pick.strategy.name} {pick.strategy.version} / {pick.strategy.status}</div>
                <div>Research rating: {researchRating?.action ?? "Unavailable"}</div>
                <div>Scanner action: {pick.action}</div>
                <div>Paper execution: {executionStatus}</div>
                <div>Market regime: {regime}</div>
                <div>
                  {data.dailyPicks.source_file
                    ? `Source: ${data.dailyPicks.source_file}`
                    : "Source file unavailable"}
                </div>
              </div>
            </section>

            <section className="memo-panel border-t border-transparent pt-4">
              <SectionLabel title="Paper Execution" />
              <div className="mt-5 text-3xl font-black tracking-[-0.07em] text-black">
                {executionStatus}
              </div>
              <p className="mt-5 text-sm leading-6 text-black/58">
                {pick.paper_trade_decision_reason}
              </p>

              <div className="mt-6 space-y-3">
                <MiniStatus
                  label="Scanner Action"
                  value={pick.action}
                />
                <MiniStatus
                  label="Paper Execution"
                  value={executionStatus}
                />
                <MiniStatus
                  label="Eligibility"
                  value={pick.paper_trade_candidate ? "Eligible" : "Not eligible"}
                />
                <MiniStatus label="Decision" value={pick.paper_trade_decision} />
                <MiniStatus
                  label="Price Data"
                  value={data.portfolioSummary.price_data_status ?? "fresh"}
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
              <SectionLabel title="Source Metadata" />
              <div className="mt-6 space-y-3">
                <MiniStatus label="Pick ID" value={pick.pick_id} />
                <MiniStatus label="Trade Date" value={pick.trade_date} />
                <MiniStatus
                  label="Scanner Version"
                  value={pick.research_metadata.scanner_version}
                />
                <MiniStatus
                  label="Feature Version"
                  value={pick.research_metadata.feature_version}
                />
                <MiniStatus
                  label="Generated From"
                  value={pick.research_metadata.generated_from}
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

export default async function CandidatePage({ params }: PageProps) {
  const { ticker } = await params;
  const [result, snapshot] = await Promise.all([
    loadPaperTradingData(),
    loadWebSnapshot(),
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
    />
  );
}
