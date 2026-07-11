import { readFile } from "fs/promises";
import path from "path";
import { MarketSnapshot, MarketSnapshotLoadResult } from "./marketSnapshot";

const MARKET_SNAPSHOT_PATH = path.join(process.cwd(), "..", "data", "market_snapshot.json");

export async function loadMarketSnapshot(): Promise<MarketSnapshotLoadResult> {
  try {
    const raw = await readFile(MARKET_SNAPSHOT_PATH, "utf8");
    return { status: "ready", data: JSON.parse(raw) as MarketSnapshot };
  } catch (error) {
    const nodeError = error as NodeJS.ErrnoException;
    if (nodeError.code === "ENOENT") {
      return {
        status: "missing",
        message: "data/market_snapshot.json has not been generated yet.",
      };
    }
    if (error instanceof SyntaxError) {
      return {
        status: "invalid",
        message: "data/market_snapshot.json contains invalid JSON.",
      };
    }
    return {
      status: "invalid",
      message: "Market snapshot could not be loaded.",
    };
  }
}
