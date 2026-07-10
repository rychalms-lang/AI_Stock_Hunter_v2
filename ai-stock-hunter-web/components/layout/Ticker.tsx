"use client";

import { useEffect, useState } from "react";
import { WebSnapshot } from "@/lib/webSnapshot";

export default function Ticker() {
  const [snapshot, setSnapshot] = useState<WebSnapshot | null>(null);

  useEffect(() => {
    fetch("/web_snapshot.json", { cache: "no-store" })
      .then((res) => res.json())
      .then(setSnapshot)
      .catch(() => setSnapshot(null));
  }, []);

  const items =
    snapshot?.ranked_candidates.slice(0, 12).map((item) => ({
      symbol: item.ticker,
      value: `${item.expected_return > 0 ? "+" : ""}${item.expected_return.toFixed(2)}%`,
      label: `Rating: ${item.action}`,
      up: item.expected_return >= 0,
    })) ?? [];

  return (
    <div className="border-b border-[#e8e8e3] bg-[#fafafa] text-black">
      <div className="mx-auto flex h-9 max-w-[1600px] items-center gap-6 overflow-hidden px-5 text-[11px] md:px-10 xl:px-16">
        <div className="shrink-0 font-semibold uppercase tracking-[0.2em] text-black/35">
          Research Tape
        </div>
        <div className="flex min-w-0 items-center gap-5 overflow-hidden">
        {items.slice(0, 6).map((item, index) => (
          <div
            key={`${item.symbol}-${index}`}
            className="flex shrink-0 items-center gap-2 font-mono text-black/55 transition-colors duration-200 hover:text-black"
          >
            <span className="font-bold text-black/75">{item.symbol}</span>
            <span>{item.label}</span>
            <span
              className={`font-semibold ${
                item.up ? "text-emerald-700" : "text-red-600"
              }`}
            >
              {item.value}
            </span>
          </div>
        ))}
        </div>
      </div>
    </div>
  );
}
