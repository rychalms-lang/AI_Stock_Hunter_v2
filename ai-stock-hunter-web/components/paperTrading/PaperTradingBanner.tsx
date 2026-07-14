export const paperTradingDisclaimer =
  "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice.";

export default function PaperTradingBanner() {
  return (
    <div className="reveal border border-[#e8e8e3] bg-white px-6 py-5 text-black transition-colors duration-200 hover:border-black/20">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
            PAPER TRADING (MOCK DATA)
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-black/62">
            {paperTradingDisclaimer}
          </p>
        </div>

        <div className="inline-flex w-fit border border-black/10 bg-[#f3f3ef] px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-black/55">
          V8 Active
        </div>
      </div>
    </div>
  );
}
