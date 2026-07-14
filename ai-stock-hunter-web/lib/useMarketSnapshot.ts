"use client";

import { useEffect, useRef, useState } from "react";
import { MarketSnapshot } from "./marketSnapshot";

type SnapshotState = {
  snapshot: MarketSnapshot | null;
  error: string | null;
  isLoading: boolean;
  lastSuccessAt: string | null;
};

function pollMs(snapshot: MarketSnapshot | null, hidden: boolean) {
  if (hidden) return 5 * 60 * 1000;
  if (snapshot?.market_state === "OPEN") return 60 * 1000;
  if (snapshot?.market_state === "PRE_MARKET" || snapshot?.market_state === "AFTER_HOURS") {
    return 2 * 60 * 1000;
  }
  return 5 * 60 * 1000;
}

export function useMarketSnapshot(initialSnapshot: MarketSnapshot | null = null) {
  const [state, setState] = useState<SnapshotState>({
    snapshot: initialSnapshot,
    error: null,
    isLoading: !initialSnapshot,
    lastSuccessAt: initialSnapshot?.generated_at ?? null,
  });
  const abortRef = useRef<AbortController | null>(null);
  const latestSnapshotRef = useRef<MarketSnapshot | null>(initialSnapshot);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function load() {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState((current) => ({ ...current, isLoading: !current.snapshot }));

      try {
        const response = await fetch("/api/market-snapshot", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Market snapshot unavailable");
        const snapshot = (await response.json()) as MarketSnapshot;
        if (cancelled) return;
        latestSnapshotRef.current = snapshot;
        setState({
          snapshot,
          error: null,
          isLoading: false,
          lastSuccessAt: snapshot.generated_at,
        });
      } catch (error) {
        if (controller.signal.aborted || cancelled) return;
        setState((current) => ({
          ...current,
          error: error instanceof Error ? error.message : "Market snapshot unavailable",
          isLoading: false,
        }));
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(
            load,
            pollMs(latestSnapshotRef.current, document.visibilityState === "hidden")
          );
        }
      }
    }

    function onVisibilityChange() {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(
        load,
        pollMs(latestSnapshotRef.current, document.visibilityState === "hidden")
      );
    }

    load();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      cancelled = true;
      abortRef.current?.abort();
      if (timer) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  return state;
}
