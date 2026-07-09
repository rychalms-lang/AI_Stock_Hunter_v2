import Card from "@/components/ui/Card";

export default function PortfolioLoading() {
  return (
    <main className="min-h-screen bg-[#f5f5f2] px-12 py-10 text-[#111111]">
      <Card className="p-9">
        <div className="text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
          Portfolio
        </div>
        <div className="mt-4 text-3xl font-black tracking-[-0.06em]">
          Loading mock paper portfolio...
        </div>
      </Card>
    </main>
  );
}
