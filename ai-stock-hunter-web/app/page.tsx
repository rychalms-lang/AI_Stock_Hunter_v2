import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";

import TopBar from "@/components/home/TopBar";
import MorningBrief from "@/components/home/MorningBrief";
import SignalStrip from "@/components/home/SignalStrip";
import OpportunityCard from "@/components/home/OpportunityCard";
import PaperTradingDashboard from "@/components/paperTrading/PaperTradingDashboard";
import { loadPaperTradingData } from "@/lib/paperTrading";

export default async function Home() {
  const paperTrading = await loadPaperTradingData();

  return (
    <main className="min-h-screen bg-[#050608] text-white">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-8 md:px-8 xl:px-12">
          <div className="mx-auto max-w-7xl">
            <TopBar />
            <MorningBrief />
            <SignalStrip />
            <OpportunityCard />
            <PaperTradingDashboard result={paperTrading} />
          </div>
        </section>
      </div>
    </main>
  );
}
