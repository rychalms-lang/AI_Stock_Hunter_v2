"use client";

import { KeyboardEvent, useEffect, useMemo, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { DailyPick, PaperTradingData } from "@/lib/paperTrading";
import { PortfolioGovernance } from "@/lib/governanceDisplay";
import { WebSnapshot } from "@/lib/webSnapshot";

type SortKey = "rank" | "confidence" | "expected_return_pct" | "risk";

type BuilderProps = {
  data: PaperTradingData;
  webSnapshot: WebSnapshot | null;
  governance?: PortfolioGovernance;
};

type ApiResult = {
  ok: boolean;
  code?: string;
  message?: string;
  position?: {
    quantity: number;
    entry_price: number;
    executed_dollar_amount: number;
    price_status?: string;
  };
};

const RISK_ORDER: Record<string, number> = {
  Low: 1,
  Medium: 2,
  High: 3,
};

const STOP_LOSS_PCT = -5;
const TAKE_PROFIT_PCT = 10;

function money(value: number) {
  return `$${value.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })}`;
}

function pct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function requestId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function researchRating(webSnapshot: WebSnapshot | null, ticker: string) {
  return (
    webSnapshot?.ranked_candidates.find(
      (candidate) => candidate.ticker.toUpperCase() === ticker.toUpperCase()
    )?.action ?? "Unavailable"
  );
}

function isEligible(pick: DailyPick) {
  return (
    pick.action === "BUY" &&
    pick.paper_trade_candidate &&
    pick.paper_trade_decision === "eligible_scanner_export"
  );
}

function executionState(pick: DailyPick, data: PaperTradingData) {
  const open = data.openPositions.positions.find(
    (position) =>
      position.ticker.toUpperCase() === pick.ticker.toUpperCase() ||
      position.source_pick_id === pick.pick_id
  );
  if (open) return "Open";

  const closed = data.closedTrades.trades.find(
    (trade) =>
      trade.ticker.toUpperCase() === pick.ticker.toUpperCase() ||
      trade.source_pick_id === pick.pick_id
  );
  if (closed) return "Closed";

  if (data.portfolioSummary.stale_price_data) return "Waiting for fresh price data";
  return isEligible(pick) ? "Eligible" : "Not eligible";
}

export default function PaperPortfolioBuilder({ data, webSnapshot, governance }: BuilderProps) {
  const router = useRouter();
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const openButtonRef = useRef<HTMLButtonElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState(
    data.dailyPicks.picks[0]?.ticker ?? ""
  );
  const [amount, setAmount] = useState("1000");
  const [sector, setSector] = useState("All");
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [onlyEligible, setOnlyEligible] = useState(false);
  const [acknowledgeOverride, setAcknowledgeOverride] = useState(false);
  const [note, setNote] = useState("");
  const [result, setResult] = useState<ApiResult | null>(null);
  const [isPending, startTransition] = useTransition();

  const heldTickers = useMemo(
    () =>
      new Set(
        data.openPositions.positions.map((position) =>
          position.ticker.toUpperCase()
        )
      ),
    [data.openPositions.positions]
  );

  const sectors = useMemo(
    () => ["All", ...Array.from(new Set(data.dailyPicks.picks.map((pick) => pick.sector))).sort()],
    [data.dailyPicks.picks]
  );

  const candidates = useMemo(() => {
    const filtered = data.dailyPicks.picks.filter((pick) => {
      if (sector !== "All" && pick.sector !== sector) return false;
      if (onlyEligible && !isEligible(pick)) return false;
      return true;
    });

    return filtered.sort((a, b) => {
      if (sortKey === "rank") return a.rank - b.rank;
      if (sortKey === "risk") {
        return (RISK_ORDER[a.risk] ?? 9) - (RISK_ORDER[b.risk] ?? 9);
      }
      return Number(b[sortKey] ?? 0) - Number(a[sortKey] ?? 0);
    });
  }, [data.dailyPicks.picks, onlyEligible, sector, sortKey]);

  const selected =
    candidates.find((pick) => pick.ticker === selectedTicker) ??
    data.dailyPicks.picks.find((pick) => pick.ticker === selectedTicker) ??
    candidates[0] ??
    data.dailyPicks.picks[0];
  const selectedIndex = Math.max(
    candidates.findIndex((pick) => pick.pick_id === selected?.pick_id),
    0
  );

  const numericAmount = Number(amount);
  const latestClose = selected?.latest_close ?? 0;
  const estimatedShares =
    latestClose > 0 && Number.isFinite(numericAmount)
      ? Math.floor(numericAmount / latestClose)
      : 0;
  const estimatedNotional = estimatedShares * latestClose;
  const alreadyHeld = selected ? heldTickers.has(selected.ticker.toUpperCase()) : false;
  const needsOverride = selected ? !isEligible(selected) : false;
  const cashRemaining = Math.max(data.portfolioSummary.summary.cash - estimatedNotional, 0);
  const reservePct =
    data.portfolioSummary.summary.total_equity > 0
      ? (cashRemaining / data.portfolioSummary.summary.total_equity) * 100
      : 0;
  const positionWeight =
    data.portfolioSummary.summary.total_equity > 0
      ? (estimatedNotional / data.portfolioSummary.summary.total_equity) * 100
      : 0;
  const currentSectorExposure =
    data.portfolioSummary.summary.sector_exposure.find(
      (item) => item.sector === selected?.sector
    )?.portfolio_pct ?? 0;
  const projectedSectorExposure = currentSectorExposure + positionWeight;
  const stopLoss = latestClose * (1 + STOP_LOSS_PCT / 100);
  const takeProfit = latestClose * (1 + TAKE_PROFIT_PCT / 100);
  const canSubmit =
    Boolean(selected) &&
    Number.isFinite(numericAmount) &&
    numericAmount > 0 &&
    estimatedShares > 0 &&
    !alreadyHeld &&
    (!needsOverride || acknowledgeOverride);
  const manualAddDisabled = governance?.mode === "ai_managed";

  function closeBuilder() {
    setIsOpen(false);
    window.requestAnimationFrame(() => {
      openButtonRef.current?.focus();
    });
  }

  useEffect(() => {
    if (!isOpen) return;

    const previousOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeBuilder();
        return;
      }

      if (event.key !== "Tab" || !modalRef.current) return;

      const focusable = Array.from(
        modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );

      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen]);

  useEffect(() => {
    function onOpenBuilder() {
      setIsOpen(true);
    }

    window.addEventListener("paper-builder:open", onOpenBuilder);
    return () => window.removeEventListener("paper-builder:open", onOpenBuilder);
  }, []);

  function navigateCandidates(event: KeyboardEvent<HTMLDivElement>) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (candidates.length === 0) return;

    let nextIndex = selectedIndex;
    if (event.key === "ArrowDown") nextIndex = Math.min(selectedIndex + 1, candidates.length - 1);
    if (event.key === "ArrowUp") nextIndex = Math.max(selectedIndex - 1, 0);
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = candidates.length - 1;

    const next = candidates[nextIndex];
    setSelectedTicker(next.ticker);
    setAcknowledgeOverride(false);
    setResult(null);
  }

  async function submit() {
    if (!selected || !canSubmit) return;
    if (manualAddDisabled) return;
    setResult(null);

    startTransition(async () => {
      const response = await fetch("/api/paper-portfolio/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: selected.ticker,
          amount: numericAmount,
          sourcePickId: selected.pick_id,
          note,
          requestId: requestId(),
          acknowledgeOverride,
        }),
      });

      const payload = (await response.json()) as ApiResult;
      setResult(payload);
      if (payload.ok) {
        router.refresh();
      }
    });
  }

  if (!selected) {
    return null;
  }

  const portalTarget = typeof document === "undefined" ? null : document.body;

  return (
    <section className="reveal border-b border-[#e8e8e3] pb-10">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
            User-Directed Paper Builder
          </div>
          <h2 className="mt-2 text-4xl font-black tracking-[-0.07em] text-black">
            Add a simulated position from today&apos;s queue.
          </h2>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-black/52">
            User-directed positions are separate from automatic V8 paper entries.
            The server re-reads the recommendation and market quote before any
            simulated position is recorded.
          </p>
          {manualAddDisabled ? (
            <p className="mt-3 text-sm font-bold text-black/45">
              Manual position creation is unavailable while AI Managed mode is active.
            </p>
          ) : null}
        </div>
        <button
          ref={openButtonRef}
          type="button"
          disabled={manualAddDisabled}
          onClick={() => setIsOpen(true)}
          className="w-full border border-black bg-black px-5 py-3 text-sm font-bold text-white transition duration-200 hover:-translate-y-0.5 hover:bg-black/85 disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 md:w-auto"
        >
          Add position
        </button>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-x-10 gap-y-5 border-t border-[#e8e8e3] pt-5 text-sm md:grid-cols-4">
        <BuilderFact label="Available cash" value={money(data.portfolioSummary.summary.cash)} />
        <BuilderFact label="Scanner candidates" value={`${data.dailyPicks.picks.length}`} />
        <BuilderFact
          label="Automatic eligible"
          value={`${data.dailyPicks.picks.filter(isEligible).length}`}
        />
        <BuilderFact label="Open positions" value={`${data.openPositions.positions.length}`} />
      </div>

      {isOpen && portalTarget
        ? createPortal(
        <div className="builder-overlay">
          <div
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="paper-builder-title"
            className="builder-workspace builder-shell flex flex-col"
          >
            <header className="flex shrink-0 flex-col gap-5 border-b border-[#e8e8e3] bg-white px-5 py-5 md:px-8 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-3 text-[12px] font-black uppercase tracking-[0.2em] text-black/38">
                  <span>1 Select</span>
                  <span className="h-px w-8 bg-black/16" />
                  <span>2 Configure</span>
                  <span className="h-px w-8 bg-black/16" />
                  <span>3 Confirm</span>
                </div>
                <h3
                  id="paper-builder-title"
                  className="mt-3 text-[clamp(2.25rem,3vw,2.75rem)] font-black tracking-[-0.07em] text-black"
                >
                  Build paper portfolio
                </h3>
                <p className="mt-2 max-w-3xl text-base leading-7 text-black/56 md:text-lg">
                  Select from today&apos;s AI research queue and create a
                  user-directed simulated position.
                </p>
              </div>

              <div className="flex shrink-0 flex-wrap items-center gap-5 xl:justify-end">
                <HeaderStat label="Available cash" value={money(data.portfolioSummary.summary.cash)} />
                <HeaderStat label="Recommendations" value={`${data.dailyPicks.picks.length}`} />
                <HeaderStat label="Eligible" value={`${data.dailyPicks.picks.filter(isEligible).length}`} />
                <button
                  ref={closeButtonRef}
                  type="button"
                  aria-label="Close paper portfolio builder"
                  onClick={closeBuilder}
                  className="builder-focus min-h-12 min-w-12 border border-black/12 bg-[#f8f8f6] px-5 py-3 text-base font-bold text-black transition duration-200 hover:border-black/35 hover:bg-white"
                >
                  Close
                </button>
              </div>
            </header>

            <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(360px,0.4fr)_minmax(0,0.6fr)]">
              <section className="flex min-h-0 flex-col border-b border-[#e8e8e3] bg-white lg:border-b-0 lg:border-r">
                <div className="shrink-0 px-5 py-5 md:px-7">
                  <div className="space-y-5">
                    <div className="min-w-0">
                      <div className="builder-label">Candidate queue</div>
                      <h4 className="mt-2 text-2xl font-black leading-tight tracking-[-0.055em] text-black md:text-[28px]">
                        Choose the research candidate.
                      </h4>
                      <p className="mt-2 text-[15px] leading-6 text-black/50">
                        Review today&apos;s queue and select one candidate to configure.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <select
                        aria-label="Filter by sector"
                        value={sector}
                        onChange={(event) => setSector(event.target.value)}
                        className="builder-focus min-h-12 min-w-0 border border-[#deded8] bg-white px-4 text-base text-black"
                      >
                        {sectors.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                      <select
                        aria-label="Sort candidates"
                        value={sortKey}
                        onChange={(event) => setSortKey(event.target.value as SortKey)}
                        className="builder-focus min-h-12 min-w-0 border border-[#deded8] bg-white px-4 text-base text-black"
                      >
                        <option value="rank">Rank</option>
                        <option value="confidence">Confidence</option>
                        <option value="expected_return_pct">Expected return</option>
                        <option value="risk">Risk</option>
                      </select>
                      <label className="builder-focus flex min-h-12 items-center gap-3 border border-[#deded8] bg-white px-4 text-base text-black/64 sm:col-span-2">
                        <input
                          type="checkbox"
                          checked={onlyEligible}
                          onChange={(event) => setOnlyEligible(event.target.checked)}
                        />
                        Eligible only
                      </label>
                    </div>
                  </div>
                </div>

                <div
                  role="listbox"
                  aria-label="Paper portfolio candidates"
                  tabIndex={0}
                  onKeyDown={navigateCandidates}
                  className="builder-scroll min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-3 pb-5 md:px-5"
                >
                  <div className="space-y-3">
                    {candidates.map((pick) => {
                      const active = pick.ticker === selected.ticker;
                      const held = heldTickers.has(pick.ticker.toUpperCase());
                      const state = held ? "Already held" : executionState(pick, data);

                      return (
                        <button
                          key={pick.pick_id}
                          type="button"
                          role="option"
                          aria-selected={active}
                          onClick={() => {
                            setSelectedTicker(pick.ticker);
                            setAcknowledgeOverride(false);
                            setResult(null);
                          }}
                          className={`builder-focus block min-h-[124px] w-full min-w-0 bg-white px-4 py-5 text-left transition duration-200 hover:-translate-y-0.5 hover:border-black/24 hover:shadow-[0_18px_50px_rgba(0,0,0,0.06)] ${
                            active
                              ? "border-2 border-black shadow-[0_20px_60px_rgba(0,0,0,0.08)]"
                              : "border border-[#e8e8e3]"
                          }`}
                        >
                          <div className="flex min-w-0 items-start gap-4">
                            <div className="flex shrink-0 items-start gap-3">
                              <span
                                className={`mt-1 h-12 w-1 ${
                                  active ? "bg-[#7fb000]" : "bg-black/10"
                                }`}
                              />
                              <span className="font-mono text-sm text-black/38">
                                #{String(pick.rank).padStart(2, "0")}
                              </span>
                            </div>

                            <div className="min-w-0 flex-1">
                              <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
                                <div className="min-w-0">
                                  <div className="truncate text-[26px] font-black tracking-[-0.065em] text-black">
                                    {pick.ticker}
                                  </div>
                                  <div className="mt-1 truncate text-base text-black/50">{pick.sector}</div>
                                </div>
                                <span className="shrink-0 text-sm font-bold text-black/45">
                                  {state}
                                </span>
                              </div>
                            </div>
                          </div>

                          <div className="mt-5 grid min-w-0 grid-cols-2 gap-x-4 gap-y-4 border-t border-[#ededeb] pt-4 sm:grid-cols-3 xl:grid-cols-4">
                            <BuilderDatum label="Research Rating" value={researchRating(webSnapshot, pick.ticker)} />
                            <BuilderDatum label="Scanner Action" value={pick.action} />
                            <BuilderDatum label="Confidence" value={`${pick.confidence.toFixed(0)}%`} />
                            <BuilderDatum label="Expected" value={pct(pick.expected_return_pct)} />
                            <MiniDatum label="Risk" value={pick.risk} />
                            <MiniDatum label="Hold" value={`${pick.best_hold_period_days}D`} />
                            <MiniDatum label="Eligibility" value={state} />
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </section>

              <aside className="flex min-h-0 min-w-0 flex-col bg-white">
                <div className="builder-scroll min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-6 md:px-8">
                  <SectionKicker step="2" label="Configure" />
                  <div className="mt-3 flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div className="min-w-0">
                      <h4 className="truncate text-[clamp(2.75rem,4.2vw,3.5rem)] font-black leading-none tracking-[-0.085em] text-black">
                        {selected.ticker}
                      </h4>
                      <div className="mt-3 text-base leading-7 text-black/52 md:text-lg">
                        {selected.sector} / {selected.risk} risk / {selected.best_hold_period_days}D hold
                      </div>
                    </div>
                    <div className="shrink-0 text-base font-bold text-black/46 sm:text-right">
                      Rank #{selected.rank}
                    </div>
                  </div>

                  <div className="mt-7 border-y border-[#e8e8e3] py-6">
                    <SectionTitle label="AI research summary" />
                    <p className="mt-3 text-[17px] leading-8 text-black/58">
                      {selected.ai_explanation?.summary ??
                        "Scanner evidence is available for this candidate."}
                    </p>
                  </div>

                  <div className="mt-7">
                    <SectionTitle label="Allocation" />
                    <label className="mt-4 block text-sm font-bold text-black/48">
                      Dollar amount
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="100"
                      value={amount}
                      onChange={(event) => setAmount(event.target.value)}
                      className="builder-focus mt-2 h-16 w-full border border-[#deded8] bg-[#fafafa] px-5 text-[26px] font-black tracking-[-0.045em] text-black"
                    />
                  </div>

                  <div className="mt-7">
                    <SectionTitle label="Position preview" />
                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                      <PreviewTile label="Estimated price" value={money(latestClose)} />
                      <PreviewTile label="Estimated shares" value={`${estimatedShares}`} />
                      <PreviewTile label="Invested amount" value={money(estimatedNotional)} />
                      <PreviewTile label="Cash remaining" value={money(cashRemaining)} />
                      <PreviewTile label="Reserve" value={`${reservePct.toFixed(1)}%`} />
                      <PreviewTile label="Position weight" value={`${positionWeight.toFixed(2)}%`} />
                      <PreviewTile label="Sector exposure" value={`${projectedSectorExposure.toFixed(1)}%`} />
                      <PreviewTile label="Planned hold" value={`${selected.best_hold_period_days}D`} />
                    </div>
                  </div>

                  <div className="mt-7 border-t border-[#e8e8e3] pt-6">
                    <SectionTitle label="Risk controls" />
                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <PreviewTile label="Stop loss" value={money(stopLoss)} />
                      <PreviewTile label="Take profit" value={money(takeProfit)} />
                    </div>
                  </div>

                  <div className="mt-7 border-t border-[#e8e8e3] pt-6">
                    <SectionKicker step="3" label="Confirm" />
                    <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <BuilderFact label="Research Rating" value={researchRating(webSnapshot, selected.ticker)} />
                      <BuilderFact label="Scanner Action" value={selected.action} />
                      <BuilderFact label="Paper Execution" value={executionState(selected, data)} />
                      <BuilderFact label="Historical Matches" value={selected.historical_matches.toLocaleString()} />
                    </div>

                    <label className="mt-6 block text-sm font-bold text-black/48">
                      Optional note
                    </label>
                    <textarea
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      rows={3}
                      maxLength={500}
                      className="builder-focus mt-2 w-full resize-none border border-[#deded8] bg-[#fafafa] px-4 py-3 text-base leading-7 text-black"
                      placeholder="Reason for adding this simulated position"
                    />

                    {needsOverride ? (
                      <label className="builder-focus mt-5 flex items-start gap-3 border border-[#e8e8e3] bg-[#fafafa] p-4 text-base leading-7 text-black/62">
                        <input
                          className="mt-1 min-h-5 min-w-5"
                          type="checkbox"
                          checked={acknowledgeOverride}
                          onChange={(event) => setAcknowledgeOverride(event.target.checked)}
                        />
                        <span>
                          I understand this candidate is not automatically eligible.
                          This creates a user-directed simulation only.
                        </span>
                      </label>
                    ) : null}

                    {alreadyHeld ? (
                      <div className="mt-5 border border-[#e8e8e3] bg-[#fafafa] p-4 text-base text-black/60">
                        This ticker already has an open simulated position.
                      </div>
                    ) : null}

                    {result ? (
                      <div
                        className={`mt-5 border p-4 text-base ${
                          result.ok
                            ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                            : "border-red-200 bg-red-50 text-red-900"
                        }`}
                      >
                        {result.ok
                          ? `Created ${result.position?.quantity ?? 0} simulated shares at ${money(
                              result.position?.entry_price ?? 0
                            )}.`
                          : result.message ?? "The simulated position was not created."}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div className="shrink-0 border-t border-[#e8e8e3] bg-white px-5 py-5 md:px-8">
                  <button
                    type="button"
                    disabled={!canSubmit || isPending || manualAddDisabled}
                    onClick={submit}
                    className="builder-focus min-h-14 w-full border border-black bg-black px-6 py-4 text-base font-bold text-white transition duration-200 hover:-translate-y-0.5 hover:bg-black/86 disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20"
                  >
                    {isPending ? "Creating simulation..." : "Create simulated position"}
                  </button>
                  <p className="mt-4 text-sm leading-6 text-black/42">
                    Paper trading simulation only. No real trades are placed. This
                    is research and decision support, not investment advice.
                  </p>
                </div>
              </aside>
            </div>
          </div>
        </div>,
        portalTarget
      )
        : null}
    </section>
  );
}

function BuilderFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[13px] uppercase tracking-[0.16em] text-black/38">{label}</div>
      <div className="mt-1 break-words text-lg font-bold text-black">{value}</div>
    </div>
  );
}

function BuilderDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[12px] uppercase tracking-[0.16em] text-black/35">{label}</div>
      <div className="mt-1 truncate text-[20px] font-black tracking-[-0.035em] text-black">{value}</div>
    </div>
  );
}

function HeaderStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-l border-[#e8e8e3] pl-5">
      <div className="text-[12px] uppercase tracking-[0.18em] text-black/35">{label}</div>
      <div className="mt-1 whitespace-nowrap text-xl font-black tracking-[-0.04em] text-black">{value}</div>
    </div>
  );
}

function MiniDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[12px] uppercase tracking-[0.16em] text-black/35">{label}</div>
      <div className="mt-1 truncate text-base font-bold text-black/72">{value}</div>
    </div>
  );
}

function SectionKicker({ step, label }: { step: string; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-black text-sm font-black text-white">
        {step}
      </span>
      <span className="builder-label">{label}</span>
    </div>
  );
}

function SectionTitle({ label }: { label: string }) {
  return (
    <div className="text-[22px] font-black tracking-[-0.045em] text-black">
      {label}
    </div>
  );
}

function PreviewTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 bg-[#f8f8f6] p-4">
      <div className="text-[12px] uppercase tracking-[0.16em] text-black/35">{label}</div>
      <div className="mt-2 break-words text-[22px] font-black tracking-[-0.055em] text-black">
        {value}
      </div>
    </div>
  );
}
