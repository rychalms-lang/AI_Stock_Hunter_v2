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
      label: item.action,
      up: item.expected_return >= 0,
    })) ?? [];

  return (
    <div className="h-12 overflow-hidden border-b border-white/10 bg-[#050608] text-white">
      <div className="ticker-track flex h-full w-max items-center">
        {[...items, ...items, ...items, ...items].map((item, index) => (
          <div
            key={`${item.symbol}-${index}`}
            className="flex h-full min-w-[188px] items-center justify-center border-r border-white/10 px-5 font-mono"
          >
            <span className="mr-3 text-sm font-bold">{item.symbol}</span>
            <span className="mr-3 text-xs text-white/55">{item.label}</span>
            <span
              className={`text-xs font-semibold ${
                item.up ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {item.value}
            </span>
          </div>
        ))}
      </div>

      <style jsx>{`
        .ticker-track {
          animation: ticker-scroll 28s linear infinite;
        }

        .ticker-track:hover {
          animation-play-state: paused;
        }

        @keyframes ticker-scroll {
          from {
            transform: translateX(0);
          }

          to {
            transform: translateX(-50%);
          }
        }
      `}</style>
    </div>
  );
}
