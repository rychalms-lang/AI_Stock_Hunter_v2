import { PaperTradingLoadResult } from "@/lib/paperTrading";
import { ResearchChanges } from "@/lib/researchChanges";
import { SystemStatus } from "@/lib/systemStatus";
import { WebSnapshot } from "@/lib/webSnapshot";

function sourceName(value?: string | null) {
  if (!value) return null;
  return value.split("/").filter(Boolean).at(-1) ?? value;
}

function sourceDate(value?: string | null) {
  const name = sourceName(value);
  if (!name || !name.endsWith("_v2.csv")) return null;
  return name.replace("_v2.csv", "");
}

function upperTicker(value?: string | null) {
  return value ? value.toUpperCase() : null;
}

export type ResearchPackageReady = {
  status: "ready";
  packageId: string | null;
  snapshot: WebSnapshot;
  paperTrading: Extract<PaperTradingLoadResult, { status: "ready" }>;
  researchChanges: ResearchChanges | null;
  systemStatus: SystemStatus | null;
  marketDate: string | null;
  sourceReport: string | null;
  generatedAt: string;
  topOpportunity: WebSnapshot["ranked_candidates"][number];
};

export type ResearchPackageMismatch = {
  status: "mismatch";
  title: string;
  message: string;
  mismatches: string[];
  customerSummary: string;
  technicalDiagnostics: {
    expectedPackageId: string | null;
    actualPackageIdPerFile: Record<string, string | null>;
    expectedSourceReport: string | null;
    actualSourceReportPerFile: Record<string, string | null>;
    expectedMarketDate: string | null;
    actualMarketDatePerFile: Record<string, string | null>;
    rankOnePerFile: Record<string, string | null>;
  };
  snapshot: WebSnapshot | null;
  paperTrading: PaperTradingLoadResult;
  researchChanges: ResearchChanges | null;
  systemStatus: SystemStatus | null;
};

export type ResearchPackageResult = ResearchPackageReady | ResearchPackageMismatch;

export function resolveResearchPackage({
  snapshot,
  paperTrading,
  researchChanges,
  systemStatus,
}: {
  snapshot: WebSnapshot | null;
  paperTrading: PaperTradingLoadResult;
  researchChanges: ResearchChanges | null;
  systemStatus: SystemStatus | null;
}): ResearchPackageResult {
  const mismatches: string[] = [];
  const paperReady = paperTrading.status === "ready";
  const officialSource = sourceName(systemStatus?.daily_pipeline.source_report);
  const officialDate = systemStatus?.daily_pipeline.last_market_date ?? null;
  const expectedPackageId = systemStatus?.research_package?.expected_package_id ?? systemStatus?.package_id ?? null;
  const snapshotPackageId = snapshot?.package_id ?? null;
  const dailyPackageId = paperReady ? paperTrading.data.dailyPicks.package_id ?? null : null;
  const changesPackageId = researchChanges?.package_id ?? null;
  const snapshotSource = sourceName(snapshot?.source_file);
  const snapshotDate = snapshot?.source_market_date ?? sourceDate(snapshot?.source_file);
  const dailySource = paperReady ? sourceName(paperTrading.data.dailyPicks.source_file) : null;
  const dailyDate = paperReady ? paperTrading.data.dailyPicks.trade_date : null;
  const changesSource = sourceName(researchChanges?.current_source);
  const changesDate = researchChanges?.current_date ?? null;
  const snapshotTop = upperTicker(snapshot?.top_opportunity?.ticker);
  const rankOne = upperTicker(snapshot?.ranked_candidates?.[0]?.ticker);
  const dailyRankOne = paperReady
    ? upperTicker(paperTrading.data.dailyPicks.picks[0]?.ticker)
    : null;
  const changesTop = upperTicker(researchChanges?.top_opportunity_change.current?.ticker);

  if (expectedPackageId) {
    if (snapshotPackageId && snapshotPackageId !== expectedPackageId) {
      mismatches.push(`Website research package ${snapshotPackageId} does not match official package ${expectedPackageId}.`);
    }
    if (dailyPackageId && dailyPackageId !== expectedPackageId) {
      mismatches.push(`Strategy Signal package ${dailyPackageId} does not match official package ${expectedPackageId}.`);
    }
    if (changesPackageId && changesPackageId !== expectedPackageId) {
      mismatches.push(`Change summary package ${changesPackageId} does not match official package ${expectedPackageId}.`);
    }
  }

  if (snapshot && !snapshotPackageId) mismatches.push("Website research package ID is missing.");
  if (paperReady && !dailyPackageId) mismatches.push("Strategy Signal package ID is missing.");
  if (researchChanges && !changesPackageId) mismatches.push("Change summary package ID is missing.");

  if (!snapshot) mismatches.push("Website research snapshot is unavailable.");
  if (!paperReady) mismatches.push("Strategy Signal data is unavailable.");
  if (snapshot && !snapshot.ranked_candidates?.length) {
    mismatches.push("The research snapshot has no ranked opportunities.");
  }
  if (snapshotTop && rankOne && snapshotTop !== rankOne) {
    mismatches.push(`Top opportunity ${snapshotTop} does not match rank #1 ${rankOne}.`);
  }
  if (officialSource && snapshotSource && officialSource !== snapshotSource) {
    mismatches.push(`Website research source ${snapshotSource} does not match official source ${officialSource}.`);
  }
  if (officialSource && dailySource && officialSource !== dailySource) {
    mismatches.push(`Strategy Signal source ${dailySource} does not match official source ${officialSource}.`);
  }
  if (officialSource && changesSource && officialSource !== changesSource) {
    mismatches.push(`Change summary source ${changesSource} does not match official source ${officialSource}.`);
  }
  if (officialDate && snapshotDate && officialDate !== snapshotDate) {
    mismatches.push(`Website research date ${snapshotDate} does not match official date ${officialDate}.`);
  }
  if (officialDate && dailyDate && officialDate !== dailyDate) {
    mismatches.push(`Strategy Signal date ${dailyDate} does not match official date ${officialDate}.`);
  }
  if (officialDate && changesDate && officialDate !== changesDate) {
    mismatches.push(`Change summary date ${changesDate} does not match official date ${officialDate}.`);
  }
  if (rankOne && dailyRankOne && rankOne !== dailyRankOne) {
    mismatches.push(`Rank #1 ${rankOne} does not match Strategy Signal rank #1 ${dailyRankOne}.`);
  }
  if (rankOne && changesTop && rankOne !== changesTop) {
    mismatches.push(`Change summary top ${changesTop} does not match displayed rank #1 ${rankOne}.`);
  }

  if (mismatches.length > 0 || !snapshot || !paperReady || !snapshot.ranked_candidates?.[0]) {
    return {
      status: "mismatch",
      title: "Research update incomplete",
      message: "The latest research files do not describe the same official production report, so the Morning Brief is paused instead of mixing stale and current data.",
      mismatches,
      customerSummary: "Research package generation is incomplete. The previous internally consistent package remains the trusted view until the next successful publication.",
      technicalDiagnostics: {
        expectedPackageId,
        actualPackageIdPerFile: {
          web_snapshot: snapshotPackageId,
          daily_picks: dailyPackageId,
          research_changes: changesPackageId,
        },
        expectedSourceReport: systemStatus?.daily_pipeline.source_report ?? null,
        actualSourceReportPerFile: {
          web_snapshot: snapshot?.source_file ?? null,
          daily_picks: paperReady ? paperTrading.data.dailyPicks.source_file ?? null : null,
          research_changes: researchChanges?.current_source ?? null,
        },
        expectedMarketDate: officialDate,
        actualMarketDatePerFile: {
          web_snapshot: snapshotDate,
          daily_picks: dailyDate,
          research_changes: changesDate,
        },
        rankOnePerFile: {
          web_snapshot: rankOne,
          daily_picks: dailyRankOne,
          research_changes: changesTop,
        },
      },
      snapshot,
      paperTrading,
      researchChanges,
      systemStatus,
    };
  }

  return {
    status: "ready",
    packageId: expectedPackageId ?? snapshotPackageId ?? dailyPackageId,
    snapshot,
    paperTrading,
    researchChanges,
    systemStatus,
    marketDate: officialDate ?? snapshotDate ?? dailyDate,
    sourceReport: snapshot.source_file,
    generatedAt: snapshot.generated_at,
    topOpportunity: snapshot.ranked_candidates[0],
  };
}
