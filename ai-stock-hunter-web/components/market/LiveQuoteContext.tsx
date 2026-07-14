"use client";

import {
  MarketSnapshot,
  formatQuoteAge,
  priceStatusLabel,
  quoteForTicker,
} from "@/lib/marketSnapshot";
import { cleanStatus } from "@/lib/displayText";
import { useMarketSnapshot } from "@/lib/useMarketSnapshot";

function money(value?: number | null) {
  if (typeof value !== "number") return "Unavailable";
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function pct(value?: number | null) {
  if (typeof value !== "number") return "Unavailable";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function tone(value?: number | null) {
  if (typeof value !== "number") return "text-black/55";
  if (value > 0) return "text-emerald-700";
  if (value < 0) return "text-red-600";
  return "text-black/55";
}

export function MarketSnapshotStatus({
  initialSnapshot = null,
}: {
  initialSnapshot?: MarketSnapshot | null;
}) {
  const { snapshot, error } = useMarketSnapshot(initialSnapshot);

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-black/45">
      <span className="font-semibold text-black/72">
        {cleanStatus(snapshot?.market_state ?? "Unavailable")}
      </span>
      <span>{priceStatusLabel(snapshot?.quote_status)}</span>
      <span>{formatQuoteAge(snapshot?.generated_at)}</span>
      <span>{snapshot?.provider ? `Source: ${snapshot.provider}` : "Source unavailable"}</span>
      {error ? <span className="text-amber-700">Retaining last quote snapshot</span> : null}
    </div>
  );
}

export function LiveQuoteContext({
  ticker,
  scannerReferencePrice,
  initialSnapshot = null,
  compact = false,
}: {
  ticker: string;
  scannerReferencePrice?: number | null;
  initialSnapshot?: MarketSnapshot | null;
  compact?: boolean;
}) {
  const { snapshot, error, isLoading } = useMarketSnapshot(initialSnapshot);
  const quote = quoteForTicker(snapshot, ticker);
  const current = quote?.current_price ?? null;
  const sinceScanner =
    typeof current === "number" &&
    typeof scannerReferencePrice === "number" &&
    scannerReferencePrice > 0
      ? ((current / scannerReferencePrice) - 1) * 100
      : null;

  return (
    <section className={compact ? "text-sm" : "border-t border-[#e8e8e3] pt-5"}>
      <div className="text-xs font-black uppercase tracking-[0.22em] text-black/35">
        Current Market Price
      </div>
      <div className="mt-3 grid grid-cols-2 gap-5 md:grid-cols-4">
        <QuoteDatum label="Research Reference" value={money(scannerReferencePrice)} />
        <QuoteDatum label="Current Market" value={money(current)} />
        <QuoteDatum label="Since Research Update" value={pct(sinceScanner)} valueClass={tone(sinceScanner)} />
        <QuoteDatum label="Intraday" value={pct(quote?.price_change_pct)} valueClass={tone(quote?.price_change_pct)} />
        {!compact ? (
          <>
            <QuoteDatum label="Day Range" value={`${money(quote?.day_low)} / ${money(quote?.day_high)}`} />
            <QuoteDatum label="Bid / Ask" value={`${money(quote?.bid)} / ${money(quote?.ask)}`} />
            <QuoteDatum label="Status" value={priceStatusLabel(quote?.price_status)} />
            <QuoteDatum label="Quote Time" value={formatQuoteAge(quote?.provider_timestamp ?? quote?.quote_timestamp)} />
          </>
        ) : null}
      </div>
      <p className="mt-4 text-xs leading-5 text-black/42">
        Current market movement updates valuation only. Research metrics remain
        based on the original daily update.
        {isLoading ? " Loading quote snapshot." : ""}
        {error ? " Latest quote refresh failed; retaining last successful snapshot." : ""}
      </p>
    </section>
  );
}

function QuoteDatum({
  label,
  value,
  valueClass = "text-black/72",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.18em] text-black/35">{label}</div>
      <div className={`mt-1 font-bold ${valueClass}`}>{value}</div>
    </div>
  );
}
