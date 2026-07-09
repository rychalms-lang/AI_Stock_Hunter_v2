export default function TopBar() {
  return (
    <header className="mb-10 flex items-start justify-between border-b border-white/10 pb-8">
      <div>
        <div className="text-xs font-black uppercase tracking-[0.28em] text-[#d7ff5f]">
          Private Alpha Terminal
        </div>
        <h1 className="mt-3 text-5xl font-black tracking-[-0.08em] text-white md:text-7xl">
          AI Stock Hunter.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-white/48">
          Daily scanner intelligence, V8 Champion context, and paper-trading
          telemetry in one research surface.
        </p>
      </div>

      <div className="hidden text-right lg:block">
        <div className="text-xs font-black uppercase tracking-[0.22em] text-white/36">
          Strategy Status
        </div>
        <div className="mt-3 inline-flex border border-[#d7ff5f]/40 bg-[#d7ff5f] px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-black">
          V8 Champion
        </div>
      </div>
    </header>
  );
}
