"use client";

import { useEffect, useState } from "react";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
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
          Today’s Highest Conviction
        </div>

        <Card className="p-10">
          <div className="text-lg text-neutral-500">
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
      <div className="mb-5 text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
        Today’s Highest Conviction
      </div>

      <Card className="p-10">
        <div className="flex flex-col justify-between gap-10 xl:flex-row">
          <div>
            <div className="text-lg text-neutral-500">
              {opportunity.sector}
            </div>

            <div className="mt-2 text-[110px] font-black leading-none tracking-[-0.12em]">
              {opportunity.ticker}
            </div>

            <div className="mt-6">
              <Badge tone={badgeTone(opportunity.action)}>
                {opportunity.action}
              </Badge>
            </div>
          </div>

          <div className="max-w-md xl:text-right">
            <div className="text-sm font-bold uppercase tracking-[0.22em] text-neutral-500">
              AI Confidence
            </div>

            <div className="mt-4 text-8xl font-black tracking-[-0.1em]">
              {opportunity.confidence.toFixed(0)}%
            </div>

            <p className="mt-5 text-base leading-7 text-neutral-600">
              This recommendation is now powered by the Python research engine
              and today’s generated market snapshot.
            </p>
          </div>
        </div>

        <div className="mt-10 grid grid-cols-2 border-y border-neutral-200 md:grid-cols-5">
          <Metric
            label="Expected Return"
            value={formatPercent(opportunity.expected_return)}
            className="border-r border-neutral-200"
          />

          <Metric
            label="Risk"
            value={opportunity.risk}
            className="border-r border-neutral-200"
          />

          <Metric
            label="Historical Matches"
            value={opportunity.historical_matches.toLocaleString()}
            className="border-r border-neutral-200"
          />

          <Metric
            label="Score"
            value={opportunity.score.toFixed(2)}
            className="border-r border-neutral-200"
          />

          <Metric
            label="Hold"
            value={`${opportunity.best_hold_period_days}D`}
          />
        </div>

        <div className="mt-10 grid grid-cols-1 gap-10 xl:grid-cols-[0.9fr_1.1fr]">
          <div>
            <div className="text-3xl font-black tracking-[-0.06em]">
              Suggested holding period:
            </div>

            <div className="mt-3 text-5xl font-black tracking-[-0.08em]">
              {opportunity.best_hold_period_days} days
            </div>

            <p className="mt-5 text-base leading-7 text-neutral-600">
              {opportunity.reason}
            </p>
          </div>

          <div>
            <div className="text-3xl font-black tracking-[-0.06em]">
              Why the AI likes this
            </div>

            <div className="mt-6 space-y-4">
              {evidencePoints.map((point) => (
                <div
                  key={point}
                  className="flex items-start gap-4 border-b border-neutral-200 pb-4 last:border-b-0"
                >
                  <span className="mt-1 text-emerald-600">✓</span>
                  <p className="text-base leading-7 text-neutral-700">
                    {point}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap gap-3">
          <Button>Read Full Research</Button>
          <Button variant="secondary">Add to Portfolio</Button>
        </div>
      </Card>
    </section>
  );
}