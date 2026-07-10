"use client";

import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import { WebSnapshot } from "@/lib/webSnapshot";

const colors = [
  "#000000",
  "#525252",
  "#171717",
  "#a3a3a3",
  "#737373",
  "#262626",
  "#d4d4d4",
  "#404040",
];

function formatCurrency(value: number) {
  return `$${value.toLocaleString()}`;
}

function formatPercent(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function polarToCartesian(cx: number, cy: number, r: number, angle: number) {
  const angleInRadians = ((angle - 90) * Math.PI) / 180;

  return {
    x: cx + r * Math.cos(angleInRadians),
    y: cy + r * Math.sin(angleInRadians),
  };
}

function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number
) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";

  return [
    "M",
    start.x,
    start.y,
    "A",
    r,
    r,
    0,
    largeArcFlag,
    0,
    end.x,
    end.y,
  ].join(" ");
}

export default function PortfolioSummary() {
  const [snapshot, setSnapshot] = useState<WebSnapshot | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  useEffect(() => {
    fetch("/web_snapshot.json", { cache: "no-store" })
      .then((res) => res.json())
      .then(setSnapshot)
      .catch(() => setSnapshot(null));
  }, []);

  if (!snapshot) {
    return (
      <Card className="p-9">
        <div className="text-lg text-neutral-500">
          Loading portfolio intelligence...
        </div>
      </Card>
    );
  }

  const summary = snapshot.portfolio_summary;
  const candidates = snapshot.ranked_candidates.slice(0, 8);
  const totalScore = candidates.reduce(
    (sum, item) => sum + Math.max(item.score, 1),
    0
  );

  const allocation = candidates.map((item, index) => {
    const percent = Math.max((item.score / totalScore) * 100, 3);
    return {
      ...item,
      percent,
      value: Math.round((summary.total_value * percent) / 100),
      color: colors[index % colors.length],
    };
  });

  const active = activeIndex === null ? null : allocation[activeIndex];

  const stats = [
    { label: "Return", value: `${summary.total_return.toFixed(1)}%` },
    {
      label: "10D Edge",
      value: formatPercent(summary.expected_10_day_return),
    },
    { label: "Confidence", value: `${summary.ai_confidence.toFixed(0)}%` },
    { label: "Holdings", value: `${summary.positions}` },
    { label: "Cash", value: `${summary.cash_percent}%` },
  ];

  const allocationWithAngles = allocation.reduce<
    Array<
      (typeof allocation)[number] & {
        startAngle: number;
        endAngle: number;
        midAngle: number;
      }
    >
  >((items, item) => {
    const previous = items.length > 0 ? items[items.length - 1] : null;
    const startAngle = previous ? previous.endAngle : 0;
    const endAngle = startAngle + item.percent * 3.6;
    const midAngle = (startAngle + endAngle) / 2;

    return [
      ...items,
      {
        ...item,
        startAngle,
        endAngle,
        midAngle,
      },
    ];
  }, []);

  return (
    <Card className="p-9">
      <div className="grid grid-cols-1 items-center gap-10 xl:grid-cols-[1fr_300px]">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.26em] text-neutral-400">
            Portfolio Overview
          </div>

          <div className="mt-4 flex items-end gap-4">
            <h1 className="text-6xl font-black leading-none tracking-[-0.075em]">
              {summary.status}.
            </h1>

            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-neutral-600">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {summary.health_label}
            </div>
          </div>

          <p className="mt-6 max-w-2xl text-lg leading-8 text-neutral-600">
            {summary.summary}
          </p>

          <div className="mt-8 grid max-w-2xl grid-cols-5 gap-6">
            {stats.map((stat) => (
              <div key={stat.label}>
                <div className="text-3xl font-black tracking-[-0.06em]">
                  {stat.value}
                </div>

                <div className="mt-1 text-sm text-neutral-500">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col items-center justify-center">
          <div
            className="relative h-[250px] w-[250px]"
            onMouseLeave={() => setActiveIndex(null)}
          >
            <svg
              viewBox="0 0 260 260"
              className="h-full w-full overflow-visible"
            >
              {allocationWithAngles.map((item, index) => {
                const isActive = index === activeIndex;
                const offset = isActive ? 7 : 0;
                const offsetPoint = polarToCartesian(
                  0,
                  0,
                  offset,
                  item.midAngle
                );

                return (
                  <path
                    key={item.ticker}
                    d={describeArc(
                      130,
                      130,
                      92,
                      item.startAngle,
                      item.endAngle
                    )}
                    fill="none"
                    stroke={item.color}
                    strokeWidth={isActive ? 39 : 33}
                    strokeLinecap="butt"
                    transform={`translate(${offsetPoint.x}, ${offsetPoint.y})`}
                    className="cursor-pointer transition-all duration-300 ease-out"
                    onMouseEnter={() => setActiveIndex(index)}
                  />
                );
              })}
            </svg>

            <div className="absolute inset-[76px] flex flex-col items-center justify-center text-center">
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
                {active ? active.ticker : "Portfolio"}
              </div>

              <div className="mt-2 text-[32px] font-black tracking-[-0.08em]">
                {active
                  ? formatCurrency(active.value)
                  : formatCurrency(summary.total_value)}
              </div>

              <div
                className={`mt-1 text-[11px] ${
                  active && active.expected_return < 0
                    ? "text-red-600"
                    : "text-emerald-600"
                }`}
              >
                {active
                  ? `${formatPercent(active.expected_return)} · ${active.percent.toFixed(1)}%`
                  : `${formatPercent(summary.expected_10_day_return)} expected`}
              </div>
            </div>
          </div>

          <div className="mt-2 text-center text-xs leading-5 text-neutral-500">
            Hover to inspect allocation.
          </div>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-7 border-t border-neutral-200 pt-7 xl:grid-cols-[0.75fr_1.25fr]">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
            Research Ratings
          </div>

          <div className="mt-4 space-y-3">
            {snapshot.today_actions.map((item) => (
              <div
                key={item.ticker}
                className="rounded-2xl border border-neutral-200 bg-white p-4 transition-all duration-200 hover:-translate-y-1 hover:border-black hover:shadow-sm"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="text-2xl font-black tracking-[-0.05em]">
                    {item.ticker}
                  </div>

                  <span className="rounded-full bg-black px-3.5 py-1.5 text-xs font-bold text-white">
                    Research Rating: {item.badge}
                  </span>
                </div>

                <div className="mt-3 text-xl font-black tracking-[-0.04em]">
                  Research note: {item.action}
                </div>

                <p className="mt-1 text-sm leading-6 text-neutral-600">
                  {item.reason}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
            Research Candidate Breakdown
          </div>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-600">
            These are the highest-ranked research ratings from today’s Python
            AI engine output. Paper execution is authorized only by the raw
            scanner action.
          </p>

          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            {allocation.map((item, index) => {
              const isActive = index === activeIndex;

              return (
                <div
                  key={item.ticker}
                  onMouseEnter={() => setActiveIndex(index)}
                  onMouseLeave={() => setActiveIndex(null)}
                  className={`rounded-2xl border bg-white p-3.5 transition-all duration-200 ${
                    isActive
                      ? "-translate-y-1 border-black shadow-sm"
                      : "border-neutral-200"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />

                    <div className="text-base font-bold tracking-tight">
                      {item.ticker}
                    </div>
                  </div>

                  <div className="mt-2 text-xl font-black tracking-[-0.05em]">
                    {formatCurrency(item.value)}
                  </div>

                  <div
                    className={`mt-1 text-xs ${
                      item.expected_return >= 0
                        ? "text-emerald-600"
                        : "text-red-600"
                    }`}
                  >
                    {formatPercent(item.expected_return)} · Research Rating: {item.action}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Card>
  );
}
