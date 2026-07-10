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
        w-[232px]
        flex-shrink-0
        overflow-y-auto
        border-r
        border-black/10
        bg-white
        px-6
        py-9
        text-black
        lg:block
      "
    >
      <div className="mb-14">
        <div className="text-[11px] font-black uppercase tracking-[0.28em] text-black/40">
          AI Stock Hunter
        </div>
        <div className="mt-3 text-2xl font-black leading-none tracking-[-0.07em]">
          Research
        </div>
        <div className="mt-5 space-y-1 text-xs leading-5 text-black/45">
          <div>V8 Champion</div>
          <div>Paper mode only</div>
        </div>
      </div>

      <nav className="space-y-0.5">
        {navItems.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between border-l py-2.5 pl-4 pr-2 text-[14px] transition-all duration-200 ${
                active
                  ? "border-[#9bd322] text-black"
                  : "border-transparent text-black/48 hover:border-black/15 hover:text-black"
            }`}
            >
              <span className="font-bold">{item.label}</span>
              <span
                className={`text-xs ${
                  active ? "text-[#6d9f00]" : "text-black/20 group-hover:text-black/45"
                }`}
              >
                /
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-16 border-t border-[#e8e8e3] pt-6 text-xs leading-5 text-black/42">
        Research software. No broker connected.
      </div>
    </aside>
  );
}
