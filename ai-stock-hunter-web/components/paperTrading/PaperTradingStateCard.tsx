import Card from "@/components/ui/Card";
import { PaperTradingLoadResult } from "@/lib/paperTrading";

type Props = {
  result: Exclude<PaperTradingLoadResult, { status: "ready" }>;
};

export default function PaperTradingStateCard({ result }: Props) {
  const title =
    result.status === "missing"
      ? "Paper trading data is missing."
      : "Paper trading data is invalid.";

  return (
    <Card className="border border-red-200 p-8">
      <div className="text-xs font-black uppercase tracking-[0.25em] text-red-600">
        Paper Trading Data
      </div>

      <h2 className="mt-4 text-3xl font-black tracking-[-0.06em]">
        {title}
      </h2>

      <p className="mt-3 max-w-2xl text-sm leading-6 text-neutral-600">
        {result.message}
      </p>

      {result.file ? (
        <div className="mt-5 inline-flex rounded-full bg-red-50 px-4 py-2 text-xs font-bold text-red-700 ring-1 ring-red-100">
          {result.file}
        </div>
      ) : null}
    </Card>
  );
}
