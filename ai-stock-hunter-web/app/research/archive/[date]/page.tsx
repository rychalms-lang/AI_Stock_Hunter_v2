import Link from "next/link";

import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import {
  loadResearchArchiveItem,
  ResearchArchiveCandidate,
} from "@/lib/researchArchive";

type PageProps = {
  params: Promise<{
    date: string;
  }>;
};

function pct(value: number | null | undefined) {
  if (typeof value !== "number") return "Unavailable";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function num(value: number | null | undefined) {
  if (typeof value !== "number") return "Unavailable";
  return value.toLocaleString();
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />
      <div className="flex">
        <Sidebar />
        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-14 md:px-10 xl:px-16">
          <div className="page-enter mx-auto max-w-[1400px]">{children}</div>
        </section>
      </div>
    </main>
  );
}

export default async function ArchiveDetailPage({ params }: PageProps) {
  const { date } = await params;
  const item = await loadResearchArchiveItem(date);

  if (!item) {
    return (
      <Shell>
        <div className="max-w-4xl border-b border-[#e8e8e3] pb-12">
          <Link
            href="/research/archive"
            className="text-xs font-black uppercase tracking-[0.22em] text-black/42 hover:text-black"
          >
            Research / Archive
          </Link>
          <h1 className="mt-6 text-6xl font-black tracking-[-0.08em] md:text-8xl">
            Report unavailable.
          </h1>
          <p className="mt-6 text-lg leading-8 text-black/58">
            No archive index entry exists for {date}. Waiting for a generated
            archive package.
          </p>
        </div>
      </Shell>
    );
  }

  const candidates = item.candidates ?? [];

  return (
    <Shell>
      <article>
        <header className="reveal grid grid-cols-1 gap-12 border-b border-[#e8e8e3] pb-14 xl:grid-cols-[1fr_360px] xl:items-end">
          <div>
            <Link
              href="/research/archive"
              className="text-xs font-black uppercase tracking-[0.22em] text-black/42 hover:text-black"
            >
              Research / Archive
            </Link>
            <h1 className="mt-6 text-6xl font-black leading-[0.94] tracking-[-0.08em] md:text-8xl">
              Scanner state for {item.date}.
            </h1>
            <p className="mt-8 max-w-3xl text-xl leading-9 text-black/58">
              Historical scanner package indexed from the source report. This
              page shows signals only, not realized outcomes.
            </p>
          </div>

          <aside className="border-l border-[#e8e8e3] pl-7">
            <div className="text-xs font-black uppercase tracking-[0.24em] text-black/35">
              Top Opportunity
            </div>
            <div className="mt-5 text-5xl font-black tracking-[-0.08em]">
              {item.top_opportunity.ticker}
            </div>
            <div className="mt-5 space-y-2 text-sm leading-6 text-black/48">
              <div>{item.source_report}</div>
              <div>{item.candidate_count} candidates</div>
              <div>{item.strategy?.name ?? "V8"} {item.strategy?.status ?? "Champion"}</div>
            </div>
          </aside>
        </header>

        <section className="reveal reveal-delay-1 grid grid-cols-2 gap-x-10 gap-y-6 border-b border-[#e8e8e3] py-10 md:grid-cols-6">
          <MemoMetric label="Report Date" value={item.date} />
          <MemoMetric label="Candidates" value={`${item.candidate_count}`} />
          <MemoMetric label="Market Regime" value={item.market_regime} />
          <MemoMetric label="Action" value={item.top_opportunity.action} />
          <MemoMetric label="Confidence" value={pct(item.top_opportunity.confidence)} />
          <MemoMetric label="Score" value={num(item.top_opportunity.score)} />
        </section>

        <section className="reveal reveal-delay-2 py-12">
          <div className="mb-7 flex flex-col gap-3 border-b border-[#e8e8e3] pb-6 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                Ranked Candidates
              </div>
              <h2 className="mt-3 text-4xl font-black tracking-[-0.07em]">
                Historical scanner queue.
              </h2>
            </div>
            <div className="text-sm text-black/42">
              Source schema: {item.source_metadata?.schema ?? "Unavailable"}
            </div>
          </div>

          <div className="divide-y divide-[#e8e8e3]">
            {candidates.length > 0 ? (
              candidates.map((candidate, index) => (
                <CandidateRow
                  key={`${candidate.ticker}-${candidate.rank}`}
                  candidate={candidate}
                  delay={index * 45}
                />
              ))
            ) : (
              <div className="py-8 text-sm text-black/48">
                No candidate rows were available in the archive index.
              </div>
            )}
          </div>
        </section>

        <section className="reveal border-t border-[#e8e8e3] pt-8 text-xs leading-6 text-black/42">
          Future-return or outcome fields are intentionally not presented here.
          Outcome tracking belongs to a later validated exporter.
        </section>
      </article>
    </Shell>
  );
}

function CandidateRow({
  candidate,
  delay,
}: {
  candidate: ResearchArchiveCandidate;
  delay: number;
}) {
  return (
    <div
      className="interactive-row reveal grid grid-cols-1 gap-4 py-7 md:grid-cols-[56px_1fr_0.45fr_0.45fr_0.45fr_0.45fr_0.45fr] md:items-center md:px-3"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="font-mono text-sm font-semibold text-black/32">
        #{candidate.rank.toString().padStart(2, "0")}
      </div>
      <div>
        <div className="text-3xl font-black tracking-[-0.06em]">
          {candidate.ticker}
        </div>
        <div className="mt-2 text-xs text-black/42">{candidate.sector}</div>
      </div>
      <Datum label="Action" value={candidate.action} />
      <Datum label="Confidence" value={pct(candidate.confidence)} />
      <Datum label="Score" value={num(candidate.score)} />
      <Datum label="Expected" value={pct(candidate.expected_return_pct)} />
      <Datum
        label="Matches"
        value={
          typeof candidate.historical_matches === "number"
            ? candidate.historical_matches.toLocaleString()
            : "Unavailable"
        }
      />
    </div>
  );
}

function MemoMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-2 text-2xl font-black tracking-[-0.05em] text-black">
        {value}
      </div>
    </div>
  );
}

function Datum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-1 font-black text-black">{value}</div>
    </div>
  );
}
