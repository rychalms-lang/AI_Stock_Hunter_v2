import Ticker from "@/components/layout/Ticker";
import Sidebar from "@/components/layout/Sidebar";

import MorningBrief from "@/components/home/MorningBrief";
import { loadPaperTradingData } from "@/lib/paperTrading";
import { loadSystemStatus } from "@/lib/systemStatus";
import { loadWebSnapshotFromData } from "@/lib/webSnapshot";
import { loadResearchChanges } from "@/lib/researchChanges";
import { loadMarketSnapshot } from "@/lib/marketSnapshotServer";
import { resolveResearchPackage } from "@/lib/researchPackage";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export default async function Home() {
  const [paperTrading, snapshot, systemStatus, researchChanges, marketSnapshot] = await Promise.all([
    loadPaperTradingData(),
    loadWebSnapshotFromData(),
    loadSystemStatus(),
    loadResearchChanges(),
    loadMarketSnapshot(),
  ]);
  const researchPackage = resolveResearchPackage({
    snapshot,
    paperTrading,
    systemStatus,
    researchChanges,
  });

  return (
    <main className="min-h-screen bg-[#fafafa] text-[#111111]">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-12 md:px-10 xl:px-16">
          <div className="mx-auto max-w-[1400px]">
            <MorningBrief
              researchPackage={researchPackage}
              marketSnapshot={marketSnapshot.status === "ready" ? marketSnapshot.data : null}
            />
          </div>
        </section>
      </div>
    </main>
  );
}
