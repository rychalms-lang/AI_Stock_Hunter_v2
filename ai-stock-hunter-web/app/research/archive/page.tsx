import Link from "next/link";

import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import { loadResearchArchive } from "@/lib/researchArchive";

function pct(value: number | null) {
  if (typeof value !== "number") return "Unavailable";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatTimestamp(value?: string) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export default async function ResearchArchivePage() {
  const archive = await loadResearchArchive();
  const items = archive?.items ?? [];

  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />
      <div className="flex">
        <Sidebar />
        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-14 md:px-10 xl:px-16">
          <div className="page-enter mx-auto max-w-[1200px]">
            <header className="reveal border-b border-[#e8e8e3] pb-12">
              <Link
                href="/research"
                className="text-xs font-black uppercase tracking-[0.22em] text-black/42 hover:text-black"
              >
                Research / Archive
              </Link>
              <h1 className="mt-6 text-6xl font-black leading-[0.94] tracking-[-0.08em] md:text-8xl">
                Research archive.
              </h1>
              <p className="mt-7 max-w-3xl text-lg leading-8 text-black/58">
                Historical scanner packages indexed from existing report files.
                No missing history is fabricated.
              </p>
              <div className="mt-8 text-sm text-black/42">
                Archive generated {formatTimestamp(archive?.generated_at)}
              </div>
            </header>

            <section className="reveal reveal-delay-1 divide-y divide-[#e8e8e3] py-8">
              {items.length > 0 ? (
                items.map((item, index) => (
                  <Link
                    key={item.source_report}
                    href={`/research/archive/${item.date}`}
                    className="interactive-row grid grid-cols-1 gap-5 py-7 md:grid-cols-[120px_1fr_120px_120px_160px] md:items-center"
                    style={{ animationDelay: `${index * 55}ms` }}
                  >
                    <div className="font-mono text-sm font-semibold text-black/42">
                      {item.date}
                    </div>
                    <div>
                      <div className="text-3xl font-black tracking-[-0.06em]">
                        {item.top_opportunity.ticker}
                      </div>
                      <div className="mt-2 text-xs text-black/42">
                        {item.top_opportunity.sector} / {item.source_report}
                      </div>
                    </div>
                    <ArchiveDatum label="Candidates" value={`${item.candidate_count}`} />
                    <ArchiveDatum label="Action" value={item.top_opportunity.action} />
                    <ArchiveDatum
                      label="Expected"
                      value={pct(item.top_opportunity.expected_return_pct)}
                    />
                  </Link>
                ))
              ) : (
                <div className="py-10 text-sm text-black/48">
                  Waiting for historical scanner reports.
                </div>
              )}
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

function ArchiveDatum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-1 font-black text-black">{value}</div>
    </div>
  );
}
