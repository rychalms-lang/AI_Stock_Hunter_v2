const navItems = [
  "Morning Brief",
  "Portfolio",
  "Today’s Picks",
  "Markets",
  "Strategy Lab",
  "Performance",
  "AI Research",
  "Account",
  "Settings",
];

export default function Sidebar() {
  return (
    <aside
  className="
    sticky
    top-0
    hidden
    h-screen
    w-[292px]
    flex-shrink-0
    overflow-y-auto
    bg-[#111111]
    px-7
    py-8
    text-white
    lg:block
  "
>
      <div className="mb-12">
        <div className="text-2xl font-black tracking-[-0.05em]">
          AI Stock Hunter
        </div>
        <div className="mt-2 text-xs font-semibold uppercase tracking-[0.28em] text-white/45">
          Investment OS
        </div>

        <div className="mt-6 flex items-center gap-2 text-sm text-white/70">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          Research Engine Online
        </div>
      </div>

      <nav className="space-y-1">
        {navItems.map((item, index) => (
          <div
            key={item}
            className={`cursor-pointer rounded-xl px-4 py-3 text-[15px] transition-all duration-200 ${
              index === 0
                ? "bg-white text-black"
                : "text-white/62 hover:translate-x-1 hover:bg-white/10 hover:text-white"
            }`}
          >
            {item}
          </div>
        ))}
      </nav>

      <div className="mt-12 border-t border-white/15 pt-7">
        <div className="text-xs font-black uppercase tracking-[0.24em] text-white/40">
          Overnight Work
        </div>

        <div className="mt-5 space-y-3 text-sm text-white/65">
          <Check text="News analyzed" />
          <Check text="5,077 strategies tested" />
          <Check text="Portfolio optimized" />
          <Check text="Morning brief prepared" />
        </div>
      </div>
    </aside>
  );
}

function Check({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-emerald-400">✓</span>
      <span>{text}</span>
    </div>
  );
}