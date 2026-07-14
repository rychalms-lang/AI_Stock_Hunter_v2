export default function TopBar() {
  return (
    <header className="mb-10 flex items-start justify-between border-b border-black/10 pb-8">
      <div>
        <div className="text-xs font-black uppercase tracking-[0.28em] text-black/40">
          Private Alpha Terminal
        </div>
        <h1 className="mt-3 text-5xl font-black tracking-[-0.08em] text-black md:text-7xl">
          AI Stock Hunter.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-black/48">
          Daily research intelligence, Active Strategy V8 context, and simulated
          portfolio state in one research surface.
        </p>
      </div>

      <div className="hidden text-right lg:block">
        <div className="text-xs font-black uppercase tracking-[0.22em] text-black/36">
          Strategy Status
        </div>
        <div className="mt-3 inline-flex border border-black/10 bg-black px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-white">
          V8 Active
        </div>
      </div>
    </header>
  );
}
