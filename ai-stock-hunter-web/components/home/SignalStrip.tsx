"use client";

import { useEffect, useState } from "react";
import Metric from "@/components/ui/Metric";
import { WebSnapshot } from "@/lib/webSnapshot";

export default function SignalStrip() {
  const [snapshot, setSnapshot] = useState<WebSnapshot | null>(null);

  useEffect(() => {
    fetch("/web_snapshot.json", { cache: "no-store" })
      .then((res) => res.json())
      .then(setSnapshot)
      .catch(() => setSnapshot(null));
  }, []);

  const summary = snapshot?.portfolio_summary;
  const top = snapshot?.top_opportunity;

  return (
    <section className="mt-6 border border-white/10 bg-[#0a0c10]">
      <div className="grid grid-cols-2 divide-y divide-white/10 md:grid-cols-5 md:divide-x md:divide-y-0">
        <Metric
          label="Market Regime"
          value={snapshot?.market_regime.label ?? "Loading"}
        />
        <Metric
          label="Top Pick"
          value={top?.ticker ?? "—"}
        />
        <Metric
          label="AI Confidence"
          value={summary ? `${summary.ai_confidence.toFixed(0)}%` : "—"}
        />
        <Metric
          label="Expected 10D"
          value={
            summary
              ? `${summary.expected_10_day_return > 0 ? "+" : ""}${summary.expected_10_day_return.toFixed(2)}%`
              : "—"
          }
        />
        <Metric
          label="Candidates"
          value={snapshot ? `${snapshot.ranked_candidates.length}` : "—"}
        />
      </div>
    </section>
  );
}
