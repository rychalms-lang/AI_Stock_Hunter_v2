import { promises as fs } from "node:fs";
import path from "node:path";
import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import StrategyLabWorkbench from "@/components/strategyLab/StrategyLabWorkbench";
import { StrategyLabPresetPayload } from "@/lib/strategyLab";

export const dynamic = "force-dynamic";

async function loadPresets(): Promise<StrategyLabPresetPayload> {
  const presetPath = path.join(process.cwd(), "..", "data", "strategy_lab", "built_in_presets.json");
  const raw = await fs.readFile(presetPath, "utf8");
  return JSON.parse(raw) as StrategyLabPresetPayload;
}

export default async function StrategyLabPage() {
  const payload = await loadPresets();

  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-10 md:px-8 xl:px-14">
          <div className="mx-auto max-w-7xl page-enter">
            <header className="border-b border-[#e8e8e3] pb-12">
              <div className="text-xs font-black uppercase tracking-[0.3em] text-black/35">
                Trading Environment Simulator
              </div>
              <h1 className="mt-4 max-w-5xl text-5xl font-semibold tracking-[-0.07em] text-black md:text-7xl">
                Test the account. Preserve the strategy.
              </h1>
              <p className="mt-6 max-w-3xl text-base leading-7 text-black/56">
                Replay the existing V8 Champion trade stream through cash, drawdown,
                consistency, exposure, and evaluation rules. The lab simulates the
                environment around the strategy; it does not change scanner scoring,
                V8 logic, or paper-trading execution.
              </p>
              <div className="mt-8 grid gap-px overflow-hidden border border-[#e8e8e3] bg-[#e8e8e3] md:grid-cols-4">
                {[
                  ["Strategy", "V8 Active"],
                  ["Challenger", "V9 Experimental"],
                  ["Modes", "Replay / Compare / Sensitivity"],
                  ["Presets", String(payload.preset_count)],
                ].map(([label, value]) => (
                  <div className="bg-white p-5" key={label}>
                    <div className="text-xs font-black uppercase tracking-[0.22em] text-black/35">
                      {label}
                    </div>
                    <div className="mt-2 text-lg font-semibold tracking-[-0.03em]">{value}</div>
                  </div>
                ))}
              </div>
            </header>

            <div className="mt-12">
              <StrategyLabWorkbench presets={payload.presets} />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
