export const paperTradingDisclaimer =
  "Paper trading simulation only. No real trades are executed. This is research software and not investment advice.";

export default function PaperTradingBanner() {
  return (
    <div className="border border-black bg-black px-6 py-5 text-white shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.28em] text-neutral-300">
            Paper Trading (Mock Data)
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-200">
            {paperTradingDisclaimer}
          </p>
        </div>

        <div className="rounded-full border border-neutral-700 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-neutral-200">
          V8 Champion
        </div>
      </div>
    </div>
  );
}
