import { readFile } from "fs/promises";
import path from "path";

export type ResearchArchiveItem = {
  date: string;
  market_regime: string;
  candidate_count: number;
  top_opportunity: {
    ticker: string;
    sector: string;
    action: string;
    confidence: number | null;
    expected_return_pct: number | null;
    score: number | null;
  };
  candidates?: ResearchArchiveCandidate[];
  strategy?: {
    name: string;
    version: string;
    status: string;
  };
  source_metadata?: {
    schema: string;
    future_outcomes_exposed: boolean;
  };
  source_report: string;
};

export type ResearchArchiveCandidate = {
  rank: number;
  ticker: string;
  sector: string;
  action: string;
  confidence: number | null;
  score: number | null;
  expected_return_pct: number | null;
  best_hold_period_days: number | null;
  historical_matches: number | null;
  risk: string;
  reason: string;
  source_fields: {
    latest_open: number | null;
    latest_close: number | null;
    five_day_change_pct: number | null;
    twenty_day_change_pct: number | null;
    relative_strength_pct: number | null;
    volume_ratio: number | null;
    best_avg_return_pct: number | null;
  };
};

export type ResearchArchive = {
  schema_version: string;
  generated_at: string;
  items: ResearchArchiveItem[];
};

export async function loadResearchArchive(): Promise<ResearchArchive | null> {
  try {
    const filePath = path.join(process.cwd(), "..", "data", "research_archive.json");
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as ResearchArchive;
  } catch {
    return null;
  }
}

export async function loadResearchArchiveItem(
  date: string
): Promise<ResearchArchiveItem | null> {
  const archive = await loadResearchArchive();
  return archive?.items.find((item) => item.date === date) ?? null;
}
