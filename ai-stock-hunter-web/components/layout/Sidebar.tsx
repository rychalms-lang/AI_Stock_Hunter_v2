"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { label: "Dashboard", href: "/" },
  { label: "Portfolio", href: "/portfolio" },
  { label: "Research", href: "/research" },
  { label: "Strategy Lab", href: "/strategy-lab" },
  { label: "Methodology", href: "/methodology" },
];

export default function Sidebar() {
  const pathname = usePathname();

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
        border-r
        border-white/10
        bg-[#08090c]
        px-7
        py-8
        text-white
        lg:block
      "
    >
      <div className="mb-12">
        <div className="text-[11px] font-black uppercase tracking-[0.28em] text-[#d7ff5f]">
          AI Stock Hunter
        </div>
        <div className="mt-3 text-3xl font-black leading-none tracking-[-0.08em]">
          Research Terminal
        </div>
        <div className="mt-3 text-xs font-semibold uppercase tracking-[0.22em] text-white/38">
          Champion/Challenger OS
        </div>

        <div className="mt-6 grid grid-cols-2 gap-2">
          <Status label="Engine" value="Online" />
          <Status label="Champion" value="V8" />
        </div>
      </div>

      <nav className="space-y-1">
        {navItems.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between border px-4 py-3 text-[14px] transition-all duration-200 ${
                active
                  ? "border-[#d7ff5f]/50 bg-[#d7ff5f] text-black"
                  : "border-transparent text-white/58 hover:border-white/10 hover:bg-white/[0.06] hover:text-white"
            }`}
            >
              <span className="font-bold">{item.label}</span>
              <span
                className={`text-xs ${
                  active ? "text-black/60" : "text-white/24 group-hover:text-white/50"
                }`}
              >
                /
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-12 border-t border-white/10 pt-7">
        <div className="text-xs font-black uppercase tracking-[0.24em] text-white/35">
          Terminal State
        </div>

        <div className="mt-5 space-y-3 text-sm text-white/58">
          <Check text="Scanner export loaded" />
          <Check text="Paper mode enforced" />
          <Check text="No broker connected" />
          <Check text="V8 remains Champion" />
        </div>
      </div>
    </aside>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-white/10 bg-white/[0.04] p-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/35">
        {label}
      </div>
      <div className="mt-1 text-sm font-black">{value}</div>
    </div>
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
