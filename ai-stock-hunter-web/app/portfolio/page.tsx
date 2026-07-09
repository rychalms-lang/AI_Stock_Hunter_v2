import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";
import PortfolioSummary from "@/components/portfolio/PortfolioSummary";
import PaperTradingPortfolio from "@/components/paperTrading/PaperTradingPortfolio";
import { loadPaperTradingData } from "@/lib/paperTrading";

export default async function PortfolioPage() {
  const paperTrading = await loadPaperTradingData();

  return (
    <main className="min-h-screen bg-[#050608] text-white">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-8 md:px-8 xl:px-12">
          <div className="mx-auto max-w-7xl">
            <div className="mb-10 border-b border-white/10 pb-8">
              <div className="text-xs font-black uppercase tracking-[0.28em] text-[#d7ff5f]">
                Paper Portfolio Command Center
              </div>
              <h1 className="mt-3 text-5xl font-black tracking-[-0.08em] text-white md:text-7xl">
                Portfolio.
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-white/48">
                Position state, performance telemetry, sector exposure, and
                confidence buckets for the paper-only research account.
              </p>
            </div>

            <div className="space-y-10">
              <PaperTradingPortfolio result={paperTrading} />

              <div>
                <div className="mb-5 text-xs font-black uppercase tracking-[0.25em] text-white/42">
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
