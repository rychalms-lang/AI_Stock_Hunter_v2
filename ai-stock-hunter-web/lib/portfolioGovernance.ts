import { readFile } from "fs/promises";
import path from "path";
import {
  GovernanceData,
  PortfolioGovernance,
  PortfolioProposal,
} from "./governanceDisplay";

const STATE_DIR = path.join(process.cwd(), "..", "data", "paper_trading", "state");

export function defaultGovernance(): PortfolioGovernance {
  return {
    schema_version: "1.0",
    mode: "ai_assisted",
    updated_at: null,
    updated_by: "system_default",
    effective_from: null,
    previous_mode: null,
    mode_version: 1,
    pending_transition: null,
  };
}

async function readJson<T>(fileName: string): Promise<T | null> {
  try {
    const raw = await readFile(path.join(STATE_DIR, fileName), "utf8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function loadGovernanceData(): Promise<GovernanceData> {
  const [governance, proposals] = await Promise.all([
    readJson<PortfolioGovernance>("portfolio_governance.json"),
    readJson<{ proposals?: PortfolioProposal[] }>("pending_proposals.json"),
  ]);

  const normalized = governance?.mode
    ? governance
    : defaultGovernance();

  return {
    governance: normalized,
    proposals: proposals?.proposals ?? [],
  };
}
