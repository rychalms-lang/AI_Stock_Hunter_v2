"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  PaperTradingData,
  PaperTradingLoadResult,
} from "@/lib/paperTrading";
import { SystemStatus } from "@/lib/systemStatus";
import { WebSnapshot } from "@/lib/webSnapshot";
import { ResearchChanges } from "@/lib/researchChanges";
import { paperTradingDisclaimer } from "@/components/paperTrading/PaperTradingBanner";

type MarketClock = {
  label: string;
  detail: string;
  tone: "open" | "closed" | "pending";
};

function formatPercent(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatTimestamp(value?: string) {
  if (!value) return "Timestamp unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function minutesUntil(target: Date, now: Date) {
  return Math.max(0, Math.round((target.getTime() - now.getTime()) / 60000));
}

function formatDuration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (hours <= 0) return `${remainingMinutes}m`;
  return `${hours}h ${remainingMinutes}m`;
}

function getNextOpen(now: Date) {
  const next = new Date(now);
  next.setHours(9, 30, 0, 0);

  if (now.getDay() === 6) {
    next.setDate(now.getDate() + 2);
  } else if (now.getDay() === 0) {
    next.setDate(now.getDate() + 1);
  } else if (now >= next) {
    next.setDate(now.getDate() + 1);
  }

  while (next.getDay() === 0 || next.getDay() === 6) {
    next.setDate(next.getDate() + 1);
  }

  return next;
}

function getMarketClock(now: Date): MarketClock {
  const day = now.getDay();
  const open = new Date(now);
  const close = new Date(now);
  open.setHours(9, 30, 0, 0);
  close.setHours(16, 0, 0, 0);

  if (day > 0 && day < 6 && now >= open && now < close) {
    return {
      label: "Market is open",
      detail: `${formatDuration(minutesUntil(close, now))} until close`,
      tone: "open",
    };
  }

  if (day > 0 && day < 6 && now < open) {
    return {
      label: `Market opens in ${formatDuration(minutesUntil(open, now))}`,
      detail: "Countdown uses local time. No live market API required.",
      tone: "pending",
    };
  }

  const nextOpen = getNextOpen(now);

  return {
    label: "Market is closed",
    detail: `Next open in ${formatDuration(minutesUntil(nextOpen, now))}`,
    tone: "closed",
  };
}

function actionCounts(candidates: WebSnapshot["ranked_candidates"]) {
  return candidates.reduce<Record<string, number>>((counts, candidate) => {
    counts[candidate.action] = (counts[candidate.action] ?? 0) + 1;
    return counts;
  }, {});
}

function findDailyPick(
  data: PaperTradingData | null,
  ticker?: string
) {
  if (!data || !ticker) return undefined;

  return data.dailyPicks.picks.find(
    (pick) => pick.ticker.toUpperCase() === ticker.toUpperCase()
  );
}

function paperExecutionLabel(
  data: PaperTradingData | null,
  ticker?: string
) {
  const pick = findDailyPick(data, ticker);

  if (!data || !ticker) return "Unavailable";

  const openPosition = data.openPositions.positions.find(
    (position) => position.ticker.toUpperCase() === ticker.toUpperCase()
  );
  if (openPosition) return "Open";

  const closedTrade = data.closedTrades.trades.find(
    (trade) => trade.ticker.toUpperCase() === ticker.toUpperCase()
  );
  if (closedTrade) return "Closed";

  if (!pick) return "Not eligible";
  if (pick.paper_trade_decision === "eligible_scanner_export") {
    return data.portfolioSummary.stale_price_data
      ? "Waiting for fresh price data"
      : "Eligible";
  }

  return "Not eligible";
}

function dataStatus(data: PaperTradingData) {
  const files = [
    data.dailyPicks.mock_data,
    data.openPositions.mock_data,
    data.closedTrades.mock_data,
    data.portfolioSummary.mock_data,
    data.equityCurve.mock_data,
    data.performanceStatistics.mock_data,
  ];

  if (files.every(Boolean)) return "Mock data";
  if (files.every((file) => !file)) return "Live scanner exports";
  return "Mixed scanner/mock";
}

function buildNarrative(snapshot: WebSnapshot, paperData: PaperTradingData | null) {
  const top = snapshot.top_opportunity;
  const scannerPick = findDailyPick(paperData, top.ticker);
  const scannerAction = scannerPick?.action ?? "unavailable";
  const execution = paperExecutionLabel(paperData, top.ticker).toLowerCase();
  const counts = actionCounts(snapshot.ranked_candidates);
  const countSummary = Object.entries(counts)
    .map(([action, count]) => `${count} ${action.toLowerCase()}`)
    .join(", ");

  return `${top.ticker} carries a research rating of ${top.action} under a ${snapshot.market_regime.label} regime, while its scanner action is ${scannerAction} and paper execution is ${execution}. The web analysis layer shows ${top.confidence.toFixed(
    0
  )}% confidence, ${formatPercent(top.expected_return)} expected return, ${top.historical_matches.toLocaleString()} historical matches, and a suggested ${top.best_hold_period_days}-day hold. Research ratings summarize ${countSummary || "no action counts"} across ${snapshot.ranked_candidates.length} candidates; paper trades are authorized only by the raw scanner action.`;
}

export default function MorningBrief({
  paperTrading,
  initialSnapshot,
  systemStatus,
  researchChanges,
}: {
  paperTrading: PaperTradingLoadResult;
  initialSnapshot: WebSnapshot | null;
  systemStatus: SystemStatus | null;
  researchChanges: ResearchChanges | null;
}) {
  const [snapshot, setSnapshot] = useState<WebSnapshot | null>(initialSnapshot);
  const [clock, setClock] = useState<MarketClock>(() => getMarketClock(new Date()));

  useEffect(() => {
    fetch("/web_snapshot.json", { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error("Snapshot unavailable");
        return res.json();
      })
      .then((data) => {
        setSnapshot(data);
      })
      .catch(() => {
        setSnapshot(initialSnapshot);
      });
  }, [initialSnapshot]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setClock(getMarketClock(new Date()));
    }, 30000);

    return () => window.clearInterval(timer);
  }, []);

  const paperReady = paperTrading.status === "ready";
  const paperData = paperReady ? paperTrading.data : null;
  const dailyPicks = paperData?.dailyPicks.picks ?? [];
  const candidates = snapshot?.ranked_candidates ?? [];
  const queue = dailyPicks.length > 0 ? dailyPicks.slice(0, 8) : candidates.slice(0, 8);
  const top = snapshot?.top_opportunity ?? candidates[0];
  const topScannerPick = findDailyPick(paperData, top?.ticker);
  const topPaperExecution = paperExecutionLabel(paperData, top?.ticker);
  const generatedAt =
    paperData?.dailyPicks.generated_at ?? snapshot?.generated_at ?? undefined;
  const statusLabel = paperData ? dataStatus(paperData) : "Paper data unavailable";
  const healthLabel = systemStatus
    ? systemStatus.daily_pipeline.status === "healthy" &&
      (systemStatus.paper_refresh.status === "healthy" ||
        systemStatus.paper_refresh.status === "unknown")
      ? "System healthy"
      : "System needs review"
    : "System status unavailable";

  return (
    <section className="page-enter space-y-12">
      <header className="reveal pb-4">
        <div className="grid grid-cols-1 gap-9 xl:grid-cols-[20px_minmax(0,1fr)_300px] xl:items-start">
          <div className="alpha-rail hidden h-[300px] xl:block" aria-hidden="true" />
          <div>
            <div className="mb-5 text-xs font-black uppercase tracking-[0.28em] text-black/40">
              Morning Brief
            </div>

            <h1 className="max-w-4xl text-[clamp(3.5rem,7vw,7.5rem)] font-black leading-[0.94] tracking-[-0.075em] text-black">
              Good morning. Your research brief is ready.
            </h1>

            <p className="mt-7 max-w-3xl text-lg leading-8 text-black/58 md:text-xl">
              Scanner complete. Today&apos;s research ratings are ready for review.
              Paper execution remains governed by the raw scanner action, V8
              remains Champion, and no broker is connected.
            </p>

            <div className="reveal reveal-delay-1 mt-8 flex flex-wrap gap-x-10 gap-y-4 border-y border-[#e8e8e3] py-4 text-sm text-black/45">
              <InlineDatum label="Session" value={clock.label} />
              <InlineDatum label="Top Opportunity" value={top?.ticker ?? "-"} />
              <InlineDatum label="Research Rating" value={top?.action ?? "-"} />
              <InlineDatum label="Scanner Action" value={topScannerPick?.action ?? "-"} />
              <InlineDatum label="Paper Execution" value={topPaperExecution} />
              <InlineDatum label="Market Regime" value={snapshot?.market_regime.label ?? "-"} />
              <InlineDatum label="System" value={healthLabel} />
              <InlineDatum label="Generated" value={formatTimestamp(generatedAt)} />
            </div>
          </div>

          <div className="reveal reveal-delay-2 border-l border-[#e8e8e3] pl-6 pt-2">
            <div className="text-xs font-black uppercase tracking-[0.24em] text-black/35">
              Top Research Case
            </div>
            {top ? (
              <Link
                href={`/candidates/${top.ticker}`}
                className="mt-4 block text-[clamp(3rem,4.5vw,5rem)] font-black leading-none tracking-[-0.09em] text-black transition-colors hover:text-black/62"
              >
                {top.ticker}
              </Link>
            ) : (
              <div className="mt-4 text-[clamp(3rem,4.5vw,5rem)] font-black leading-none tracking-[-0.09em] text-black">
                -
              </div>
            )}
            <div className="mt-5 grid grid-cols-2 gap-4 border-t border-[#e8e8e3] pt-5">
              <QuietStat label="Research Rating" value={top?.action ?? "-"} />
              <QuietStat label="Scanner Action" value={topScannerPick?.action ?? "-"} />
              <QuietStat label="Paper Execution" value={topPaperExecution} />
              <QuietStat
                label="Confidence"
                value={top ? `${top.confidence.toFixed(0)}%` : "-"}
              />
              <QuietStat
                label="Expected"
                value={top ? formatPercent(top.expected_return) : "-"}
              />
            </div>
            <Link
              href="/mission-control"
              className="mt-7 inline-flex text-xs font-black uppercase tracking-[0.18em] text-black/42 transition-colors hover:text-black"
            >
              Open Mission Control →
            </Link>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-14 xl:grid-cols-[1fr_320px]">
        <section className="reveal reveal-delay-1">
          <div className="mb-3 flex flex-col gap-3 border-b border-[#e8e8e3] pb-7 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
                Today&apos;s Research Queue
              </div>
              <h2 className="mt-3 text-4xl font-black tracking-[-0.07em] text-black md:text-5xl">
                Candidates worth opening.
              </h2>
            </div>
            <div className="text-sm text-black/40">
              {queue.length} visible / {snapshot?.ranked_candidates.length ?? "-"} total
            </div>
          </div>
          <p className="mb-5 max-w-3xl text-xs leading-5 text-black/42">
            Research ratings summarize the web analysis layer. Paper trades are
            authorized only by the raw scanner action.
          </p>
          <div className="divide-y divide-[#e8e8e3]">
            {queue.length > 0 ? (
              queue.map((candidate, index) => (
                <ResearchQueueRow
                  key={`${candidate.ticker}-${index}`}
                  rank={index + 1}
                  candidate={candidate}
                  delay={index * 55}
                />
              ))
            ) : (
              <div className="py-8 text-sm text-black/48">
                No scanner candidates are available yet.
              </div>
            )}
          </div>
        </section>

        <aside className="reveal reveal-delay-2 space-y-12 border-l border-[#e8e8e3] pl-8">
          <WhatChanged changes={researchChanges} />

          <section className="memo-panel border-t border-transparent pt-1">
            <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
              Why It Matters Today
            </div>
            <p className="mt-5 text-base font-medium leading-8 text-black/62">
              {snapshot
                ? buildNarrative(snapshot, paperData)
                : "Waiting for the latest scanner snapshot before generating the evidence narrative."}
            </p>
          </section>

          <section className="memo-panel border-t border-transparent pt-1">
            <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
              System Status
            </div>
            <div className="mt-6 space-y-4">
              <StatusItem label="Scanner export loaded" value={snapshot ? "Yes" : "Pending"} />
              <StatusItem label="Paper trading mode enforced" value={paperReady ? "Yes" : "Pending"} />
              <StatusItem label="No broker connected" value="Yes" />
              <StatusItem label="V8 remains Champion" value="Yes" />
              <StatusItem label="Mock/live data status" value={statusLabel} />
              <StatusItem label="Operational health" value={healthLabel} />
            </div>
            <p className="mt-7 border-t border-black/10 pt-5 text-xs leading-5 text-black/42">
              {paperTradingDisclaimer}
            </p>
          </section>
        </aside>
      </div>
    </section>
  );
}

function WhatChanged({ changes }: { changes: ResearchChanges | null }) {
  const largestMover = changes?.rank_changes?.[0];
  const actionChange = changes?.action_changes?.[0];
  const confidenceShift = changes?.confidence_changes?.[0];
  const topChanged =
    changes?.top_opportunity_change.previous?.ticker &&
    changes?.top_opportunity_change.current?.ticker &&
    changes.top_opportunity_change.previous.ticker !==
      changes.top_opportunity_change.current.ticker;

  return (
    <section className="memo-panel border-t border-transparent pt-1">
      <div className="text-xs font-black uppercase tracking-[0.25em] text-black/35">
        What Changed
      </div>
      {changes?.status === "ready" ? (
        <div className="mt-5 space-y-4 text-sm leading-6 text-black/58">
          <div>
            {changes.summary.new_candidates} new candidates,{" "}
            {changes.summary.removed_candidates} removed.
          </div>
          {largestMover ? (
            <div>
              Largest rank mover: {largestMover.ticker} from #
              {largestMover.previous_rank} to #{largestMover.current_rank}.
            </div>
          ) : null}
          {actionChange ? (
            <div>
              Action change: {actionChange.ticker} moved from{" "}
              {actionChange.previous_action} to {actionChange.current_action}.
            </div>
          ) : null}
          {topChanged ? (
            <div>
              Top opportunity changed from{" "}
              {changes.top_opportunity_change.previous?.ticker} to{" "}
              {changes.top_opportunity_change.current?.ticker}.
            </div>
          ) : null}
          {confidenceShift ? (
            <div>
              Confidence shift: {confidenceShift.ticker} moved{" "}
              {confidenceShift.change_points > 0 ? "+" : ""}
              {confidenceShift.change_points.toFixed(1)} points.
            </div>
          ) : null}
          <Link
            href="/research/archive"
            className="inline-flex text-xs font-black uppercase tracking-[0.18em] text-black/42 hover:text-black"
          >
            Open archive comparison →
          </Link>
        </div>
      ) : (
        <p className="mt-5 text-sm leading-6 text-black/48">
          Waiting for two scanner reports before a day-over-day comparison can
          be prepared.
        </p>
      )}
    </section>
  );
}

type QueueCandidate = WebSnapshot["ranked_candidates"][number] | PaperTradingData["dailyPicks"]["picks"][number];

function getExpectedReturn(candidate: QueueCandidate) {
  return "expected_return_pct" in candidate
    ? candidate.expected_return_pct
    : candidate.expected_return;
}

function isDailyPick(candidate: QueueCandidate): candidate is PaperTradingData["dailyPicks"]["picks"][number] {
  return "expected_return_pct" in candidate;
}

function ResearchQueueRow({
  rank,
  candidate,
  delay,
}: {
  rank: number;
  candidate: QueueCandidate;
  delay: number;
}) {
  return (
    <div
      className="interactive-row reveal grid grid-cols-1 gap-4 py-7 md:grid-cols-[56px_1fr_0.5fr_0.5fr_0.5fr_0.5fr_136px] md:items-center md:px-3"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="font-mono text-sm font-semibold text-black/32">
        #{rank.toString().padStart(2, "0")}
      </div>
      <div>
        <Link
          href={`/candidates/${candidate.ticker}`}
          className="block text-3xl font-black tracking-[-0.06em] text-black transition-colors hover:text-black/58"
        >
          {candidate.ticker}
        </Link>
        <div className="mt-2 text-xs text-black/42">{candidate.sector}</div>
      </div>
      <QueueStat
        label={isDailyPick(candidate) ? "Scanner Action" : "Research Rating"}
        value={candidate.action}
      />
      <QueueStat label="Confidence" value={`${candidate.confidence.toFixed(0)}%`} />
      <QueueStat label="Expected" value={formatPercent(getExpectedReturn(candidate))} />
      <QueueStat label="Hold" value={`${candidate.best_hold_period_days}D`} />
      <Link
        href={`/candidates/${candidate.ticker}`}
        className="subtle-link text-xs font-black uppercase tracking-[0.18em] text-black/38 opacity-70 transition-colors hover:text-black"
      >
        View Research →
      </Link>
    </div>
  );
}

function QueueStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-1 font-black text-black">{value}</div>
    </div>
  );
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-black/10 pb-4 last:border-b-0 last:pb-0">
      <div className="text-sm text-black/58">{label}</div>
      <div className="border border-black/10 bg-[#f3f3ef] px-3 py-1 text-xs font-black uppercase tracking-[0.14em] text-black/70">
        {value === "Yes" ? (
          <span className="pulse-dot mr-2 inline-block h-1.5 w-1.5 rounded-full bg-[#7fb000]" />
        ) : null}
        {value}
      </div>
    </div>
  );
}

function InlineDatum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-black/30">{label}</span>{" "}
      <span className="font-semibold text-black/72">{value}</span>
    </div>
  );
}

function QuietStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-black uppercase tracking-[0.2em] text-black/30">
        {label}
      </div>
      <div className="mt-2 text-xl font-black tracking-[-0.04em] text-black/82">
        {value}
      </div>
    </div>
  );
}
