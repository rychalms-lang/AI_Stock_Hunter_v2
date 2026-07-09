import Sidebar from "@/components/layout/Sidebar";
import Ticker from "@/components/layout/Ticker";
import Card from "@/components/ui/Card";

const researchPanels = [
  {
    label: "Scanner Feed",
    title: "Daily evidence review",
    body: "Ranked candidates, market regime context, sector strength, and confidence signals are prepared for analyst review before any paper-trading decision.",
  },
  {
    label: "Research Queue",
    title: "Champion-led investigation",
    body: "V8 remains the Champion baseline. Challenger ideas can be studied here without changing production research logic.",
  },
  {
    label: "Audit Trail",
    title: "Trace every signal",
    body: "Future panels should expose source files, generated timestamps, scanner versions, and explanation evidence for each candidate.",
  },
];

export default function ResearchPage() {
  return (
    <main className="min-h-screen bg-[#050608] text-white">
      <Ticker />

      <div className="flex">
        <Sidebar />

        <section className="min-h-[calc(100vh-48px)] flex-1 px-5 py-8 md:px-8 xl:px-12">
          <div className="mx-auto max-w-7xl">
            <header className="mb-10 border-b border-white/10 pb-8">
              <div className="text-xs font-black uppercase tracking-[0.28em] text-[#d7ff5f]">
                Research Workspace
              </div>
              <h1 className="mt-3 text-5xl font-black tracking-[-0.08em] md:text-7xl">
                Research.
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-white/48">
                A professional surface for candidate review, evidence checks,
                and scanner provenance. Full research modules can be wired here
                without touching strategy code.
              </p>
            </header>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
              {researchPanels.map((panel) => (
                <Card key={panel.label} className="p-8">
                  <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
                    {panel.label}
                  </div>
                  <h2 className="mt-4 text-3xl font-black tracking-[-0.06em]">
                    {panel.title}
                  </h2>
                  <p className="mt-5 text-sm leading-6 text-white/56">
                    {panel.body}
                  </p>
                </Card>
              ))}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
