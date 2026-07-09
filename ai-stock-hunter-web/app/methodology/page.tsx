import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import Card from "@/components/ui/Card";
import { paperTradingDisclaimer } from "@/components/paperTrading/PaperTradingBanner";

const steps = [
  "Scanner output is treated as research evidence, not execution authority.",
  "V8 remains Champion until a challenger clears approved validation.",
  "Paper trading records simulated outcomes and preserves research metadata.",
  "Frontend pages render prepared JSON state and do not make trading decisions.",
];

export default function MethodologyPage() {
  return (
    <main className="min-h-screen bg-[#050608] text-white">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-8 md:px-8 xl:px-12">
          <div className="mx-auto max-w-7xl">
            <header className="mb-10 border-b border-white/10 pb-8">
              <div className="text-xs font-black uppercase tracking-[0.28em] text-[#d7ff5f]">
                Operating Methodology
              </div>
              <h1 className="mt-3 text-5xl font-black tracking-[-0.08em] md:text-7xl">
                Methodology.
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-white/48">
                The platform is research-first, evidence-driven, and designed
                around a measured Champion/Challenger workflow.
              </p>
            </header>

            <div className="grid grid-cols-1 gap-8 xl:grid-cols-[0.7fr_0.3fr]">
              <Card className="p-8">
                <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
                  Workflow Guardrails
                </div>

                <div className="mt-8 space-y-5">
                  {steps.map((step, index) => (
                    <div
                      key={step}
                      className="grid grid-cols-[48px_1fr] gap-4 border-b border-white/10 pb-5 last:border-b-0"
                    >
                      <div className="font-mono text-sm font-black text-[#d7ff5f]">
                        {(index + 1).toString().padStart(2, "0")}
                      </div>
                      <div className="text-lg font-semibold leading-7 text-white/76">
                        {step}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="border-[#d7ff5f]/30 p-8">
                <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
                  Safety Language
                </div>
                <p className="mt-5 text-base leading-7 text-white/62">
                  {paperTradingDisclaimer}
                </p>
              </Card>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
