import { readFile } from "fs/promises";
import path from "path";

export type ChangeCandidate = {
  ticker: string;
  rank: number;
  sector: string;
  action: string;
  confidence: number | null;
  score: number | null;
  expected_return_pct: number | null;
  best_hold_period_days: number | null;
  historical_matches: number;
  risk: string;
};

export type ResearchChanges = {
  schema_version: string;
  generated_at: string;
  package_id?: string | null;
  status: "ready" | "insufficient_history";
  current_date: string | null;
  previous_date: string | null;
  current_source: string | null;
  previous_source: string | null;
  summary: {
    new_candidates: number;
    removed_candidates: number;
    rank_changes: number;
    action_changes: number;
    confidence_changes: number;
    expected_return_changes: number;
    sector_changes: number;
  };
  new_candidates: ChangeCandidate[];
  removed_candidates: ChangeCandidate[];
  rank_changes: Array<{
    ticker: string;
    previous_rank: number;
    current_rank: number;
    movement: number;
  }>;
  action_changes: Array<{
    ticker: string;
    previous_action: string;
    current_action: string;
  }>;
  confidence_changes: Array<{
    ticker: string;
    previous_confidence: number;
    current_confidence: number;
    change_points: number;
  }>;
  expected_return_changes: Array<{
    ticker: string;
    previous_expected_return_pct: number;
    current_expected_return_pct: number;
    change_points: number;
  }>;
  sector_changes: Array<{
    ticker: string;
    previous_sector: string;
    current_sector: string;
  }>;
  top_opportunity_change: {
    previous: ChangeCandidate | null;
    current: ChangeCandidate | null;
  };
};

export async function loadResearchChanges(): Promise<ResearchChanges | null> {
  try {
    const filePath = path.join(process.cwd(), "..", "data", "research_changes.json");
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as ResearchChanges;
  } catch {
    return null;
  }
}
