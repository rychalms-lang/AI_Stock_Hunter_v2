import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";
import PortfolioGovernanceControl from "@/components/portfolio/PortfolioGovernanceControl";
import PortfolioSummary from "@/components/portfolio/PortfolioSummary";
import { loadGovernanceData } from "@/lib/portfolioGovernance";
import { loadPaperTradingData } from "@/lib/paperTrading";
import { loadWebSnapshotFromData } from "@/lib/webSnapshot";
import { loadMarketSnapshot } from "@/lib/marketSnapshotServer";

export default async function PortfolioPage() {
  const [paperTrading, webSnapshot, governance, marketSnapshot] = await Promise.all([
    loadPaperTradingData(),
    loadWebSnapshotFromData(),
    loadGovernanceData(),
    loadMarketSnapshot(),
  ]);

  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-10 md:px-10 xl:px-16">
          <div className="page-enter mx-auto max-w-[1400px]">
            <div className="reveal mb-8 border-b border-[#e8e8e3] pb-7">
              <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
                    Paper Portfolio
                  </div>
                  <h1 className="mt-4 text-5xl font-black tracking-[-0.08em] text-black md:text-7xl">
                    Portfolio.
                  </h1>
                  <p className="mt-4 max-w-3xl text-base leading-7 text-black/52 md:text-lg">
                    What you currently own, how it is performing, and who controls
                    simulated portfolio decisions.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-x-8 gap-y-4 text-sm md:grid-cols-4 xl:text-right">
                  <HeaderFact
                    label="Market"
                    value={
                      marketSnapshot.status === "ready"
                        ? marketSnapshot.data.market_state
                        : "Unavailable"
                    }
                  />
                  <HeaderFact
                    label="Price update"
                    value={
                      marketSnapshot.status === "ready"
                        ? marketSnapshot.data.generated_at
                        : "Waiting"
                    }
                  />
                  <HeaderFact label="Mode" value={governance.governance.mode.replace("_", " ")} />
                  <HeaderFact
                    label="Ledger"
                    value={
                      paperTrading.status === "ready"
                        ? paperTrading.data.portfolioSummary.generated_at
                        : "Unavailable"
                    }
                  />
                </div>
              </div>

              <p className="mt-6 text-xs leading-5 text-black/42">
                Paper trading simulation only. No real trades are placed. This is
                research and decision support, not investment advice.
              </p>
            </div>

            <div className="space-y-8">
              <PortfolioGovernanceControl data={governance} />
              <PortfolioSummary
                result={paperTrading}
                webSnapshot={webSnapshot}
                governance={governance}
                marketSnapshot={marketSnapshot.status === "ready" ? marketSnapshot.data : null}
              />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function HeaderFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-t border-[#e8e8e3] pt-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-black/35">{label}</div>
      <div className="mt-1 truncate text-sm font-bold capitalize text-black/70">{value}</div>
    </div>
  );
}
