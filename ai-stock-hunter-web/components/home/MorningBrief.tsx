"use client";

import { useEffect, useState } from "react";
import { WebSnapshot } from "@/lib/webSnapshot";

export default function MorningBrief() {
  const [snapshot, setSnapshot] = useState<WebSnapshot | null>(null);

  useEffect(() => {
    fetch("/web_snapshot.json", { cache: "no-store" })
      .then((res) => res.json())
      .then(setSnapshot)
      .catch(() => setSnapshot(null));
  }, []);

  const top = snapshot?.top_opportunity;
  const summary = snapshot?.portfolio_summary;

  return (
    <section className="max-w-6xl">
      <div className="mb-6 text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
        Today’s Brief · Prepared Overnight
      </div>

      <p className="text-6xl font-semibold leading-[1.08] tracking-[-0.075em] text-neutral-950">
        {top
          ? `${top.ticker} is today’s strongest AI-ranked opportunity.`
          : "Loading today’s AI market brief."}
      </p>

      <p className="mt-8 max-w-5xl text-xl leading-9 text-neutral-600">
        {top && summary
          ? `${top.ticker} is rated ${top.action} with ${top.confidence.toFixed(
              0
            )}% confidence, ${top.historical_matches} historical matches, and an expected ${top.best_hold_period_days}-day return of ${top.expected_return.toFixed(
              2
            )}%. ${summary.summary}`
          : "The AI engine is preparing today’s recommendation set."}
      </p>

      <div className="mt-8 flex flex-wrap gap-4 text-sm text-neutral-500">
        <span>
          Market regime: {snapshot?.market_regime.label ?? "Loading"}
        </span>
        <span>•</span>
        <span>
          AI confidence:{" "}
          {summary ? `${summary.ai_confidence.toFixed(0)}%` : "Loading"}
        </span>
        <span>•</span>
        <span>
          Candidates: {snapshot?.ranked_candidates.length ?? "Loading"}
        </span>
      </div>
    </section>
  );
}