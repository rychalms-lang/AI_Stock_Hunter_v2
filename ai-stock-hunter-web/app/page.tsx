import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";

import MorningBrief from "@/components/home/MorningBrief";
import { loadPaperTradingData } from "@/lib/paperTrading";

export default async function Home() {
  const paperTrading = await loadPaperTradingData();

  return (
    <main className="min-h-screen bg-[#fafafa] text-[#111111]">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-12 md:px-10 xl:px-16">
          <div className="mx-auto max-w-[1400px]">
            <MorningBrief paperTrading={paperTrading} />
          </div>
        </section>
      </div>
    </main>
  );
}
