"use client";

import { useEffect, useState } from "react";

import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";
import PortfolioSummary from "@/components/portfolio/PortfolioSummary";
import PortfolioPositionCard from "@/components/portfolio/PortfolioPositionCard";
import { WebSnapshot } from "@/lib/webSnapshot";

export default function PortfolioPage() {
  const [snapshot, setSnapshot] = useState<WebSnapshot | null>(null);

  useEffect(() => {
    fetch("/web_snapshot.json", { cache: "no-store" })
      .then((res) => res.json())
      .then(setSnapshot)
      .catch(() => setSnapshot(null));
  }, []);

  return (
    <main className="min-h-screen bg-[#f5f5f2] text-[#111111]">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-12 py-10">
          <div className="mx-auto max-w-7xl">
            <div className="mb-14">
              <div className="text-sm text-neutral-500">AI Stock Hunter OS</div>
              <h1 className="mt-2 text-7xl font-black tracking-[-0.08em]">
                Portfolio.
              </h1>
            </div>

            <PortfolioSummary />

            <div className="mt-12 space-y-8">
              {snapshot ? (
                snapshot.ranked_candidates.slice(0, 10).map((candidate) => (
                  <PortfolioPositionCard
                    key={candidate.ticker}
                    recommendation={candidate}
                  />
                ))
              ) : (
                <div className="text-neutral-500">
                  Loading live recommendations...
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}