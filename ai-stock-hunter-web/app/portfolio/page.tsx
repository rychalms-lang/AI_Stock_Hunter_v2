import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";
import PortfolioSummary from "@/components/portfolio/PortfolioSummary";
import PaperTradingPortfolio from "@/components/paperTrading/PaperTradingPortfolio";
import { loadPaperTradingData } from "@/lib/paperTrading";

export default async function PortfolioPage() {
  const paperTrading = await loadPaperTradingData();

  return (
    <main className="min-h-screen bg-[#f5f5f2] text-[#111111]">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-12 py-10">
          <div className="mx-auto max-w-7xl">
            <div className="mb-14">
              <div className="text-sm text-neutral-500">AI Stock Hunter OS</div>
              <h1 className="mt-2 text-7xl font-black tracking-[-0.08em]">
                Portfolio.
              </h1>
            </div>

            <div className="space-y-12">
              <PaperTradingPortfolio result={paperTrading} />

              <div>
                <div className="mb-5 text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
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
