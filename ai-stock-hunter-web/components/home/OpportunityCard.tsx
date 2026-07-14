"use client";

import { useEffect, useState } from "react";

import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import Metric from "@/components/ui/Metric";
import { WebSnapshot } from "@/lib/webSnapshot";

function formatPercent(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function badgeTone(action: string) {
  if (action === "BUY") return "green";
  if (action === "AVOID") return "red";
  if (action === "WATCH") return "amber";
  return "black";
}

export default function OpportunityCard() {
  const [snapshot, setSnapshot] = useState<WebSnapshot | null>(null);

  useEffect(() => {
    async function loadSnapshot() {
      const response = await fetch("/web_snapshot.json", {
        cache: "no-store",
      });

      const data = await response.json();
      setSnapshot(data);
    }

    loadSnapshot();
  }, []);

  if (!snapshot) {
    return (
      <section className="mt-12">
        <div className="mb-5 text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
          Today’s Highest Conviction AI Research Rating
        </div>

        <Card className="p-10">
          <div className="text-lg text-black/48">
            Loading AI recommendation...
          </div>
        </Card>
      </section>
    );
  }

  const opportunity = snapshot.top_opportunity;

  const evidencePoints = [
    `${opportunity.historical_matches} comparable historical setups.`,
    `${formatPercent(opportunity.expected_return)} expected return over ${opportunity.best_hold_period_days} days.`,
    `${opportunity.confidence.toFixed(0)}% AI confidence.`,
    `${opportunity.risk} risk profile.`,
    `Sector: ${opportunity.sector}.`,
  ];

  return (
    <section className="mt-12">
      <div className="mb-5 text-xs font-black uppercase tracking-[0.25em] text-black/42">
        Top Opportunity · Evidence View
      </div>

      <Card className="p-8 md:p-10">
        <div className="flex flex-col justify-between gap-10 xl:flex-row">
          <div>
            <div className="text-sm font-black uppercase tracking-[0.22em] text-black/42">
              {opportunity.sector}
            </div>

            <div className="mt-3 text-[88px] font-black leading-none tracking-[-0.12em] text-black md:text-[120px]">
              {opportunity.ticker}
            </div>

            <div className="mt-6">
              <Badge tone={badgeTone(opportunity.action)}>
                {`AI Research Rating: ${opportunity.action}`}
              </Badge>
            </div>
          </div>

          <div className="max-w-md xl:text-right">
            <div className="text-sm font-bold uppercase tracking-[0.22em] text-black/42">
              AI Confidence
            </div>

            <div className="mt-4 text-8xl font-black tracking-[-0.1em] text-black/40">
              {opportunity.confidence.toFixed(0)}%
            </div>

            <p className="mt-5 text-base leading-7 text-black/56">
              This AI research rating is powered by the web analysis layer and
              today’s generated market snapshot. It does not authorize paper
              simulated trades.
            </p>
          </div>
        </div>

        <div className="mt-10 grid grid-cols-2 border-y border-black/10 md:grid-cols-5">
          <Metric
            label="Expected Return"
            value={formatPercent(opportunity.expected_return)}
            className="border-r border-black/10"
          />

          <Metric
            label="Risk"
            value={opportunity.risk}
            className="border-r border-black/10"
          />

          <Metric
            label="Historical Matches"
            value={opportunity.historical_matches.toLocaleString()}
            className="border-r border-black/10"
          />

          <Metric
            label="Score"
            value={opportunity.score.toFixed(2)}
            className="border-r border-black/10"
          />

          <Metric
            label="Hold"
            value={`${opportunity.best_hold_period_days}D`}
          />
        </div>

        <div className="mt-10 grid grid-cols-1 gap-10 xl:grid-cols-[0.9fr_1.1fr]">
          <div>
            <div className="text-3xl font-black tracking-[-0.06em] text-black">
              Suggested holding period:
            </div>

            <div className="mt-3 text-5xl font-black tracking-[-0.08em] text-black">
              {opportunity.best_hold_period_days} days
            </div>

            <p className="mt-5 text-base leading-7 text-black/56">
              {opportunity.reason}
            </p>
          </div>

          <div>
            <div className="text-3xl font-black tracking-[-0.06em] text-black">
              Why the AI likes this
            </div>

            <div className="mt-6 space-y-4">
              {evidencePoints.map((point) => (
                <div
                  key={point}
                  className="flex items-start gap-4 border-b border-black/10 pb-4 last:border-b-0"
                >
                  <span className="mt-1 text-black/40">✓</span>
                  <p className="text-base leading-7 text-black/62">
                    {point}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-10 border-t border-black/10 pt-5 text-xs leading-5 text-black/40">
          Evidence is generated for research review. Paper trading simulation only.
          No real trades are placed. This is research and decision support, not
          investment advice. Research ratings summarize the web analysis layer.
          Simulated trades are authorized only by the Strategy Signal.
        </div>
      </Card>
    </section>
  );
}
