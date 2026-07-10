import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";
import PortfolioSummary from "@/components/portfolio/PortfolioSummary";
import PaperTradingPortfolio from "@/components/paperTrading/PaperTradingPortfolio";
import { loadPaperTradingData } from "@/lib/paperTrading";

export default async function PortfolioPage() {
  const paperTrading = await loadPaperTradingData();

  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-14 md:px-10 xl:px-16">
          <div className="page-enter mx-auto max-w-[1400px]">
            <div className="reveal mb-14 border-b border-[#e8e8e3] pb-10">
              <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
                Paper Portfolio Command Center
              </div>
              <h1 className="mt-5 text-6xl font-black tracking-[-0.08em] text-black md:text-8xl">
                Portfolio.
              </h1>
              <p className="mt-6 max-w-3xl text-lg leading-8 text-black/52">
                Position state, performance telemetry, sector exposure, and
                confidence buckets for the paper-only research account.
              </p>
            </div>

            <div className="space-y-10">
              <PaperTradingPortfolio result={paperTrading} />

              <div>
                <div className="mb-5 text-xs font-black uppercase tracking-[0.25em] text-black/42">
                  Existing Allocation Model
                </div>
                <PortfolioSummary />
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
