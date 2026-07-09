import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";

import TopBar from "@/components/home/TopBar";
import MorningBrief from "@/components/home/MorningBrief";
import SignalStrip from "@/components/home/SignalStrip";
import OpportunityCard from "@/components/home/OpportunityCard";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f5f5f2] text-[#111111]">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-12 py-10">
          <div className="mx-auto max-w-7xl">
            <TopBar />
            <MorningBrief />
            <SignalStrip />
            <OpportunityCard />
          </div>
        </section>
      </div>
    </main>
  );
}