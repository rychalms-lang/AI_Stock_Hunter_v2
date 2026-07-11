import { NextResponse } from "next/server";
import { loadMarketSnapshot } from "@/lib/marketSnapshotServer";

export const runtime = "nodejs";

export async function GET() {
  const result = await loadMarketSnapshot();
  if (result.status !== "ready") {
    return NextResponse.json(result, { status: result.status === "missing" ? 404 : 500 });
  }
  return NextResponse.json(result.data, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
