import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import { loadPaperTradingData } from "@/lib/paperTrading";
import { loadSystemStatus, SystemStatus } from "@/lib/systemStatus";

function display(value?: string | number | boolean | null) {
  if (value === true) return "Enabled";
  if (value === false) return "Not installed";
  if (value === null || value === undefined || value === "") return "Unavailable";
  return String(value);
}

function formatTimestamp(value?: string | null) {
  if (!value || value === "Not yet recorded" || value === "Unavailable") {
    return value ?? "Unavailable";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function statusTone(status?: string) {
  if (status === "healthy" || status === "OPEN" || status === "Champion") {
    return "bg-[#7fb000]";
  }
  if (status === "warning" || status === "stale" || status === "PRE_MARKET") {
    return "bg-amber-500";
  }
  if (status === "failed") return "bg-red-600";
  return "bg-black/25";
}

function StatusLine({
  label,
  value,
  state,
}: {
  label: string;
  value: string;
  state?: string;
}) {
  return (
    <div className="interactive-row grid grid-cols-1 gap-2 border-t border-[#e8e8e3] py-5 md:grid-cols-[1fr_220px] md:items-center">
      <div className="text-sm font-medium text-black/62">{label}</div>
      <div className="flex items-center gap-3 text-sm font-black text-black">
        <span className={`h-2 w-2 rounded-full ${statusTone(state ?? value)}`} />
        {value}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-[#e8e8e3] pt-4">
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-2 text-3xl font-black tracking-[-0.06em] text-black">
        {value}
      </div>
    </div>
  );
}

function EventLog({ status }: { status: SystemStatus | null }) {
  const events = status?.events ?? [];

  return (
    <section className="reveal reveal-delay-2 border-b border-[#e8e8e3] pb-12">
      <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
        Latest System Events
      </div>
      <h2 className="mt-3 text-4xl font-black tracking-[-0.07em]">
        Operating record.
      </h2>

      <div className="mt-8 divide-y divide-[#e8e8e3]">
        {events.length > 0 ? (
          events.map((event, index) => (
            <div
              key={`${event.timestamp}-${index}`}
              className="interactive-row grid grid-cols-1 gap-3 py-5 md:grid-cols-[140px_90px_1fr]"
            >
              <div className="font-mono text-xs text-black/42">
                {formatTimestamp(event.timestamp)}
              </div>
              <div className="text-xs font-black uppercase tracking-[0.16em] text-black/45">
                {event.level}
              </div>
              <div className="text-sm leading-6 text-black/62">{event.message}</div>
            </div>
          ))
        ) : (
          <div className="py-6 text-sm text-black/45">
            Waiting for first live run.
          </div>
        )}
      </div>
    </section>
  );
}

export default async function MissionControlPage() {
  const [status, paperTrading] = await Promise.all([
    loadSystemStatus(),
    loadPaperTradingData(),
  ]);
  const paperReady = paperTrading.status === "ready";
  const paperData = paperReady ? paperTrading.data : null;
  const openPositions = paperData?.openPositions.positions.length ?? 0;
  const stalePositions =
    status?.paper_portfolio.stale_positions ??
    paperData?.portfolioSummary.stale_positions ??
    paperData?.portfolioSummary.summary.stale_positions ??
    0;
  const candidates =
    status?.scanner.candidate_count ?? paperData?.dailyPicks.picks.length ?? 0;

  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />
      <div className="flex">
        <Sidebar />
        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-14 md:px-10 xl:px-16">
          <div className="page-enter mx-auto max-w-[1400px]">
            <header className="reveal grid grid-cols-1 gap-12 border-b border-[#e8e8e3] pb-14 xl:grid-cols-[1fr_360px] xl:items-end">
              <div>
                <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
                  Mission Control
                </div>
                <h1 className="mt-6 max-w-5xl text-6xl font-black leading-[0.94] tracking-[-0.08em] md:text-8xl">
                  System healthy, or honestly waiting.
                </h1>
                <p className="mt-8 max-w-3xl text-xl leading-9 text-black/58">
                  Operational telemetry for scanner exports, paper-ledger
                  refreshes, automation, and V8 Champion status. Every value is
                  read from system files; unavailable data stays unavailable.
                </p>
              </div>

              <aside className="border-l border-[#e8e8e3] pl-7">
                <div className="text-xs font-black uppercase tracking-[0.24em] text-black/35">
                  Current State
                </div>
                <div className="mt-5 flex items-center gap-3 text-5xl font-black tracking-[-0.08em]">
                  <span className={`h-3 w-3 rounded-full ${statusTone(status?.market_state)}`} />
                  {status?.market_state ?? "Unavailable"}
                </div>
                <div className="mt-5 text-sm leading-6 text-black/45">
                  Status generated {formatTimestamp(status?.generated_at)}
                </div>
              </aside>
            </header>

            <section className="reveal reveal-delay-1 grid grid-cols-2 gap-x-10 gap-y-7 border-b border-[#e8e8e3] py-10 md:grid-cols-5">
              <Metric label="Candidates" value={display(candidates)} />
              <Metric label="Open Paper Positions" value={display(openPositions)} />
              <Metric label="Stale Positions" value={display(stalePositions)} />
              <Metric
                label="Last Export"
                value={formatTimestamp(status?.scanner.last_export_timestamp)}
              />
              <Metric label="V8 Status" value={status?.strategy.status ?? "Champion"} />
            </section>

            <div className="grid grid-cols-1 gap-14 py-14 xl:grid-cols-[1fr_0.8fr]">
              <section className="reveal space-y-10">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Core Runtime
                  </div>
                  <div className="mt-6">
                    <StatusLine
                      label="Daily scanner status"
                      value={status?.daily_pipeline.status ?? "unknown"}
                      state={status?.daily_pipeline.status}
                    />
                    <StatusLine
                      label="Last successful scanner run"
                      value={formatTimestamp(status?.daily_pipeline.last_success_at)}
                    />
                    <StatusLine
                      label="Last scanner market date"
                      value={status?.daily_pipeline.last_market_date ?? "Unavailable"}
                    />
                    <StatusLine
                      label="Last paper-ledger refresh"
                      value={formatTimestamp(status?.paper_refresh.last_success_at)}
                      state={status?.paper_refresh.status}
                    />
                    <StatusLine
                      label="Current data freshness"
                      value={status?.paper_portfolio.price_status ?? "Unavailable"}
                      state={status?.paper_refresh.status}
                    />
                  </div>
                </div>

                <div>
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Automation
                  </div>
                  <div className="mt-6">
                    <StatusLine
                      label="Daily pipeline"
                      value={display(status?.automation.daily_pipeline_enabled)}
                    />
                    <StatusLine
                      label="Paper refresh"
                      value={display(status?.automation.paper_refresh_enabled)}
                    />
                    <StatusLine
                      label="Daily label"
                      value={status?.automation.daily_pipeline_label ?? "Unavailable"}
                    />
                    <StatusLine
                      label="Refresh label"
                      value={status?.automation.paper_refresh_label ?? "Unavailable"}
                    />
                  </div>
                </div>
              </section>

              <aside className="reveal reveal-delay-1 space-y-9 border-l border-[#e8e8e3] pl-8">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Freshness
                  </div>
                  <div className="mt-6 space-y-5">
                    <Mini label="Daily picks" value={status?.data_freshness.daily_picks} />
                    <Mini label="Portfolio" value={status?.data_freshness.portfolio} />
                    <Mini label="Web snapshot" value={status?.data_freshness.web_snapshot} />
                    <Mini label="Source report" value={status?.scanner.source_file} />
                  </div>
                </div>

                <div className="border-t border-[#e8e8e3] pt-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Paper Refresh
                  </div>
                  <div className="mt-6 grid grid-cols-3 gap-5">
                    <Mini label="Updated" value={display(status?.paper_refresh.positions_updated)} />
                    <Mini label="Stale" value={display(status?.paper_refresh.positions_stale)} />
                    <Mini label="Closed" value={display(status?.paper_refresh.positions_closed)} />
                  </div>
                </div>

                <div className="border-t border-[#e8e8e3] pt-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Portfolio Governance
                  </div>
                  <div className="mt-6 grid grid-cols-2 gap-5">
                    <Mini label="Mode" value={status?.portfolio_governance?.label} />
                    <Mini label="Authority" value={status?.portfolio_governance?.decision_authority} />
                    <Mini
                      label="Automation"
                      value={
                        status?.portfolio_governance
                          ? status.portfolio_governance.automatic_entries_enabled
                            ? "Entries enabled"
                            : "Approval/manual"
                          : "Unavailable"
                      }
                    />
                    <Mini
                      label="Pending approvals"
                      value={display(status?.portfolio_governance?.pending_proposal_count)}
                    />
                    <Mini
                      label="Last transition"
                      value={formatTimestamp(status?.portfolio_governance?.last_mode_change)}
                    />
                    <Mini label="Status" value={status?.portfolio_governance?.governance_status} />
                  </div>
                </div>
              </aside>
            </div>

            <EventLog status={status} />
          </div>
        </section>
      </div>
    </main>
  );
}

function Mini({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="border-t border-[#e8e8e3] pt-4">
      <div className="text-xs uppercase tracking-[0.18em] text-black/35">
        {label}
      </div>
      <div className="mt-2 break-words text-sm font-bold text-black/68">
        {display(value)}
      </div>
    </div>
  );
}
