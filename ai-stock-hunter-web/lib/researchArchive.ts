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
  source_report: string;
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
