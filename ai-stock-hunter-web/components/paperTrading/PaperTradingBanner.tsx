export const paperTradingDisclaimer =
  "Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice.";

export default function PaperTradingBanner() {
  return (
    <div className="border border-[#d7ff5f]/30 bg-[#101216] px-6 py-5 text-white shadow-[0_18px_60px_rgba(0,0,0,0.28)]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.28em] text-[#d7ff5f]">
            PAPER TRADING (MOCK DATA)
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-white/62">
            {paperTradingDisclaimer}
          </p>
        </div>

        <div className="inline-flex w-fit border border-[#d7ff5f]/30 bg-[#d7ff5f]/10 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-[#d7ff5f]">
          V8 Champion
        </div>
      </div>
    </div>
  );
}
