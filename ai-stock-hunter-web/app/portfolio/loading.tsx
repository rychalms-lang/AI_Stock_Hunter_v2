import Card from "@/components/ui/Card";

export default function PortfolioLoading() {
  return (
    <main className="min-h-screen bg-[#fafafa] px-5 py-8 text-black md:px-12">
      <Card className="p-9">
        <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
          Portfolio
        </div>
        <div className="mt-4 text-3xl font-black tracking-[-0.06em] text-black">
          Loading mock paper portfolio...
        </div>
      </Card>
    </main>
  );
}
