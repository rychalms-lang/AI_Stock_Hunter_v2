import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import { loadPaperTradingData } from "@/lib/paperTrading";
import { loadSystemStatus, SystemStatus } from "@/lib/systemStatus";
import { cleanStatus, formatDate, formatDateTime, sourceLabel, strategyStatusLabel } from "@/lib/displayText";

function display(value?: string | number | boolean | null) {
  if (value === true) return "Enabled";
  if (value === false) return "Not installed";
  if (value === null || value === undefined || value === "") return "Unavailable";
  return cleanStatus(value);
}

function statusTone(status?: string) {
  const normalized = status?.toLowerCase();
  if (normalized === "healthy" || normalized === "open" || normalized === "champion") {
    return "bg-[#7fb000]";
  }
  if (normalized === "warning" || normalized === "stale" || normalized === "pre_market") {
    return "bg-amber-500";
  }
  if (normalized === "failed") return "bg-red-600";
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
        {cleanStatus(value)}
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
        Recent System Activity
      </div>
      <h2 className="mt-3 text-4xl font-black tracking-[-0.07em]">
        What changed recently.
      </h2>

      <div className="mt-8 divide-y divide-[#e8e8e3]">
        {events.length > 0 ? (
          events.map((event, index) => (
            <div
              key={`${event.timestamp}-${index}`}
              className="interactive-row grid grid-cols-1 gap-3 py-5 md:grid-cols-[140px_90px_1fr]"
            >
              <div className="font-mono text-xs text-black/42">
                {formatDateTime(event.timestamp)}
              </div>
              <div className="text-xs font-black uppercase tracking-[0.16em] text-black/45">
                {cleanStatus(event.level)}
              </div>
              <div className="text-sm leading-6 text-black/62">{event.message}</div>
            </div>
          ))
        ) : (
          <div className="py-6 text-sm text-black/45">
            No recent system activity is available yet.
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
  const opportunities =
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
                  A clear view of the daily research update, market prices,
                  simulated portfolio, automation, website data, and active
                  strategy. If something needs attention, it appears here first.
                </p>
              </div>

              <aside className="border-l border-[#e8e8e3] pl-7">
                <div className="text-xs font-black uppercase tracking-[0.24em] text-black/35">
                  Current State
                </div>
                <div className="mt-5 flex items-center gap-3 text-5xl font-black tracking-[-0.08em]">
                  <span className={`h-3 w-3 rounded-full ${statusTone(status?.market_state)}`} />
                  {cleanStatus(status?.market_state)}
                </div>
                <div className="mt-5 text-sm leading-6 text-black/45">
                  Status updated {formatDateTime(status?.generated_at)}
                </div>
              </aside>
            </header>

            <section className="reveal reveal-delay-1 grid grid-cols-2 gap-x-10 gap-y-7 border-b border-[#e8e8e3] py-10 md:grid-cols-6">
              <Metric label="Opportunities" value={display(opportunities)} />
              <Metric label="Open Simulated Positions" value={display(openPositions)} />
              <Metric label="Out-of-Date Positions" value={display(stalePositions)} />
              <Metric
                label="Website Data"
                value={formatDateTime(status?.scanner.last_export_timestamp)}
              />
              <Metric label="Active Strategy" value={`V8 ${strategyStatusLabel(status?.strategy.status)}`} />
              <Metric label="Research Package" value={cleanStatus(status?.research_package?.status)} />
            </section>

            <div className="grid grid-cols-1 gap-14 py-14 xl:grid-cols-[1fr_0.8fr]">
              <section className="reveal space-y-10">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    System Health
                  </div>
                  <div className="mt-6">
                    <StatusLine
                      label="Daily Research Update"
                      value={cleanStatus(status?.daily_pipeline.status)}
                      state={status?.daily_pipeline.status}
                    />
                    <StatusLine
                      label="Last successful research update"
                      value={formatDateTime(status?.daily_pipeline.last_success_at)}
                    />
                    <StatusLine
                      label="Latest official market date"
                      value={formatDate(status?.daily_pipeline.last_market_date)}
                    />
                    <StatusLine
                      label="Last simulated portfolio refresh"
                      value={formatDateTime(status?.paper_refresh.last_success_at)}
                      state={status?.paper_refresh.status}
                    />
                    <StatusLine
                      label="Portfolio price data"
                      value={cleanStatus(status?.paper_portfolio.price_status)}
                      state={status?.paper_refresh.status}
                    />
                  </div>
                </div>

                <div>
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Research Package
                  </div>
                  <div className="mt-6">
                    <StatusLine
                      label="Consistency"
                      value={cleanStatus(status?.research_package?.status)}
                      state={status?.research_package?.status === "mismatch" ? "failed" : "healthy"}
                    />
                    <StatusLine
                      label="Official market date"
                      value={formatDate(status?.research_package?.official_market_date)}
                    />
                    <StatusLine
                      label="Resolved top opportunity"
                      value={status?.research_package?.top_opportunity_ticker ?? "Unavailable"}
                    />
                    <StatusLine
                      label="Mismatch details"
                      value={
                        status?.research_package?.mismatches?.length
                          ? status.research_package.mismatches.join(" | ")
                          : "None"
                      }
                    />
                  </div>
                </div>

                <div>
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Automation
                  </div>
                  <div className="mt-6">
                    <StatusLine
                      label="Daily Update"
                      value={display(status?.automation.daily_pipeline_enabled)}
                    />
                    <StatusLine
                      label="Simulated Portfolio Refresh"
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
                    <Mini label="Research list" value={formatDateTime(status?.data_freshness.daily_picks)} />
                    <Mini label="Portfolio" value={status?.data_freshness.portfolio} />
                    <Mini label="Website data" value={formatDateTime(status?.data_freshness.web_snapshot)} />
                    <Mini label="Research source" value={sourceLabel(status?.scanner.source_file)} />
                  </div>
                </div>

                <div className="border-t border-[#e8e8e3] pt-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Portfolio Pricing
                  </div>
                  <div className="mt-6 grid grid-cols-2 gap-5">
                    <Mini label="Refresh cadence" value={status?.portfolio_pricing?.refresh_cadence_label} />
                    <Mini label="Last market snapshot" value={formatDateTime(status?.portfolio_pricing?.last_market_snapshot)} />
                    <Mini label="Last durable valuation" value={formatDateTime(status?.portfolio_pricing?.last_durable_valuation)} />
                    <Mini label="Next expected refresh" value={formatDateTime(status?.portfolio_pricing?.next_expected_refresh)} />
                    <Mini label="Requested" value={display(status?.portfolio_pricing?.tickers_requested)} />
                    <Mini label="Updated" value={display(status?.portfolio_pricing?.tickers_updated)} />
                    <Mini label="Out of date" value={display(status?.portfolio_pricing?.tickers_stale)} />
                    <Mini label="Provider" value={status?.portfolio_pricing?.provider} />
                    <Mini label="Quote status" value={cleanStatus(status?.portfolio_pricing?.quote_status)} />
                    <Mini label="Refresh duration" value={status?.portfolio_pricing?.latest_refresh_duration} />
                    <Mini label="Overlap skips" value={display(status?.portfolio_pricing?.overlap_skips)} />
                    <Mini label="Last issue" value={status?.portfolio_pricing?.last_failure_reason ?? "None"} />
                  </div>
                </div>

                <div className="border-t border-[#e8e8e3] pt-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Simulated Portfolio Refresh
                  </div>
                  <div className="mt-6 grid grid-cols-3 gap-5">
                    <Mini label="Updated" value={display(status?.paper_refresh.positions_updated)} />
                    <Mini label="Out of date" value={display(status?.paper_refresh.positions_stale)} />
                    <Mini label="Closed" value={display(status?.paper_refresh.positions_closed)} />
                  </div>
                </div>

                <div className="border-t border-[#e8e8e3] pt-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Market Snapshot
                  </div>
                  <div className="mt-6 grid grid-cols-2 gap-5">
                    <Mini label="Provider" value={status?.market_snapshot?.provider} />
                    <Mini label="Quote status" value={cleanStatus(status?.market_snapshot?.quote_status)} />
                    <Mini
                      label="Last quote refresh"
                      value={formatDateTime(status?.market_snapshot?.last_successful_quote_refresh)}
                    />
                    <Mini label="Requested" value={display(status?.market_snapshot?.tickers_requested)} />
                    <Mini label="Updated" value={display(status?.market_snapshot?.tickers_updated)} />
                    <Mini label="Failed" value={display(status?.market_snapshot?.failed_quotes)} />
                  </div>
                </div>

                <div className="border-t border-[#e8e8e3] pt-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Portfolio Control
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
                      value={formatDateTime(status?.portfolio_governance?.last_mode_change)}
                    />
                    <Mini label="Status" value={cleanStatus(status?.portfolio_governance?.governance_status)} />
                  </div>
                </div>

                <div className="border-t border-[#e8e8e3] pt-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
                    Trade Email Notifications
                  </div>
                  <div className="mt-6 grid grid-cols-2 gap-5">
                    <Mini label="Notifications" value={status?.trade_email_notifications?.enabled ? "Enabled" : "Disabled"} />
                    <Mini label="Recipient" value={status?.trade_email_notifications?.recipient_configured ? "Configured" : "Needs setup"} />
                    <Mini label="Last sent" value={formatDateTime(status?.trade_email_notifications?.last_successful_email)} />
                    <Mini label="Last failed" value={formatDateTime(status?.trade_email_notifications?.last_failed_email)} />
                    <Mini label="Pending retries" value={display(status?.trade_email_notifications?.pending_retries)} />
                    <Mini label="Total sent" value={display(status?.trade_email_notifications?.total_sent)} />
                    <Mini label="Total failed" value={display(status?.trade_email_notifications?.total_failed)} />
                    <Mini label="Last issue" value={status?.trade_email_notifications?.last_failure_reason ?? "None"} />
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
