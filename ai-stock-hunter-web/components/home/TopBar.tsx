export default function TopBar() {
  return (
    <header className="mb-16 flex items-start justify-between">
      <div>
        <div className="text-sm text-neutral-500">Private Alpha</div>
        <h1 className="mt-2 text-7xl font-black tracking-[-0.08em]">
          Good morning, Riley.
        </h1>
      </div>

      <div className="hidden text-right lg:block">
        <div className="text-sm text-neutral-500">Saturday, July 4</div>
        <button className="mt-3 rounded-full bg-black px-5 py-2 text-sm font-semibold text-white">
          Replay Yesterday
        </button>
      </div>
    </header>
  );
}