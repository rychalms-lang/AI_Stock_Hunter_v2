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
    <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1.35fr_0.65fr]">
      <div className="border border-white/10 bg-[#0d0f13] p-8 md:p-10">
        <div className="mb-5 text-xs font-black uppercase tracking-[0.25em] text-white/42">
          AI Commentary · Morning Brief
        </div>

        <p className="max-w-5xl text-4xl font-semibold leading-[1.05] tracking-[-0.07em] text-white md:text-6xl">
          {top
            ? `${top.ticker} leads today’s research queue.`
            : "Loading today’s research queue."}
        </p>

        <p className="mt-7 max-w-4xl text-base leading-8 text-white/58 md:text-lg">
          {top && summary
            ? `${top.ticker} is rated ${top.action} with ${top.confidence.toFixed(
                0
              )}% confidence, ${top.historical_matches} historical matches, and an expected ${top.best_hold_period_days}-day return of ${top.expected_return.toFixed(
                2
              )}%. ${summary.summary}`
            : "The AI engine is preparing today’s recommendation set."}
        </p>

        <div className="mt-8 grid grid-cols-1 gap-3 text-sm text-white/58 md:grid-cols-3">
          <BriefPill label="Market Regime" value={snapshot?.market_regime.label ?? "Loading"} />
          <BriefPill
            label="AI Confidence"
            value={summary ? `${summary.ai_confidence.toFixed(0)}%` : "Loading"}
          />
          <BriefPill
            label="Candidates"
            value={`${snapshot?.ranked_candidates.length ?? "Loading"}`}
          />
        </div>
      </div>

      <div className="border border-white/10 bg-[#0d0f13] p-8">
        <div className="text-xs font-black uppercase tracking-[0.25em] text-white/42">
          Market Regime
        </div>
        <div className="mt-5 text-5xl font-black tracking-[-0.08em] text-white">
          {snapshot?.market_regime.label ?? "Loading"}
        </div>
        <div className="mt-4 h-2 bg-white/10">
          <div
            className="h-full bg-[#d7ff5f]"
            style={{ width: `${snapshot?.market_regime.score ?? 0}%` }}
          />
        </div>
        <div className="mt-4 flex items-center justify-between text-xs uppercase tracking-[0.18em] text-white/38">
          <span>Risk Off</span>
          <span>Risk On</span>
        </div>
        <p className="mt-8 text-sm leading-6 text-white/52">
          Regime data is rendered as decision support for research review only.
          It does not authorize live execution.
        </p>
      </div>
    </section>
  );
}

function BriefPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-white/10 bg-white/[0.03] p-4">
      <div className="text-[10px] font-black uppercase tracking-[0.2em] text-white/35">
        {label}
      </div>
      <div className="mt-2 text-xl font-black tracking-[-0.04em] text-white">
        {value}
      </div>
    </div>
  );
}
