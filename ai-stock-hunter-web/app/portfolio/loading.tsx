import Card from "@/components/ui/Card";

export default function PortfolioLoading() {
  return (
    <main className="min-h-screen bg-[#050608] px-5 py-8 text-white md:px-12">
      <Card className="p-9">
        <div className="text-xs font-black uppercase tracking-[0.25em] text-[#d7ff5f]">
          Portfolio
        </div>
        <div className="mt-4 text-3xl font-black tracking-[-0.06em] text-white">
          Loading mock paper portfolio...
        </div>
      </Card>
    </main>
  );
}
