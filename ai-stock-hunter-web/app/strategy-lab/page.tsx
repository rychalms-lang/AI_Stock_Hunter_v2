import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import Card from "@/components/ui/Card";

const labItems = [
  ["Champion", "V8", "Approved production research baseline for paper trading."],
  ["Challenger", "V9", "Experimental candidate that must beat V8 through validation."],
  ["Protocol", "Validation", "Out-of-sample, walk-forward, drawdown, and approval review."],
];

export default function StrategyLabPage() {
  return (
    <main className="min-h-screen bg-[#fafafa] text-black">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-8 md:px-8 xl:px-12">
          <div className="mx-auto max-w-7xl">
            <header className="mb-10 border-b border-black/10 pb-8">
              <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
                Champion / Challenger
              </div>
              <h1 className="mt-3 text-5xl font-black tracking-[-0.08em] md:text-7xl">
                Strategy Lab.
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-black/48">
                A controlled destination for comparing strategy candidates while
                keeping production scoring, portfolio logic, and training flows
                isolated from UI work.
              </p>
            </header>

            <Card className="p-0">
              <div className="grid grid-cols-1 divide-y divide-black/10 lg:grid-cols-3 lg:divide-x lg:divide-y-0">
                {labItems.map(([label, value, description]) => (
                  <div key={label} className="p-8">
                    <div className="text-xs font-black uppercase tracking-[0.25em] text-black/42">
                      {label}
                    </div>
                    <div className="mt-3 text-5xl font-black tracking-[-0.08em] text-black/40">
                      {value}
                    </div>
                    <p className="mt-5 text-sm leading-6 text-black/56">
                      {description}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </section>
      </div>
    </main>
  );
}
