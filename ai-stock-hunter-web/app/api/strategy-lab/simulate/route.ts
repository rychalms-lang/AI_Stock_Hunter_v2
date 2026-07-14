import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const execFileAsync = promisify(execFile);
const allowedTopLevel = new Set([
  "mode",
  "strategy",
  "preset_id",
  "preset_ids",
  "environment",
  "trade_stream",
  "parameter",
  "values",
]);

function validateRequest(payload: unknown): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { ok: false, error: "Request body must be an object." };
  }
  const value = payload as Record<string, unknown>;
  for (const key of Object.keys(value)) {
    if (!allowedTopLevel.has(key)) {
      return { ok: false, error: "Unsupported Strategy Lab request field." };
    }
  }
  const mode = value.mode ?? "historical_replay";
  if (!["historical_replay", "environment_comparison", "sensitivity_analysis"].includes(String(mode))) {
    return { ok: false, error: "Unsupported Strategy Lab mode." };
  }
  const strategy = value.strategy ?? "V8";
  if (!["V8", "V8_CHAMPION", "V9", "V9_DEFENSIVE"].includes(String(strategy))) {
    return { ok: false, error: "Unsupported strategy." };
  }
  if (value.trade_stream && value.trade_stream !== "balanced") {
    return { ok: false, error: "Unsupported trade stream." };
  }
  return { ok: true, value: { ...value, mode, strategy, trade_stream: value.trade_stream ?? "balanced" } };
}

export async function POST(request: NextRequest) {
  let configPath = "";
  try {
    const raw = await request.text();
    if (raw.length > 40_000) {
      return NextResponse.json({ status: "error", error: "Strategy Lab request is too large." }, { status: 413 });
    }
    const parsed = validateRequest(JSON.parse(raw));
    if (!parsed.ok) {
      return NextResponse.json({ status: "error", error: parsed.error }, { status: 400 });
    }

    const projectRoot = path.resolve(process.cwd(), "..");
    configPath = path.join(os.tmpdir(), `strategy-lab-${randomUUID()}.json`);
    await fs.writeFile(configPath, JSON.stringify(parsed.value), "utf8");
    const pythonPath = path.join(projectRoot, "venv", "bin", "python");
    const scriptPath = path.join(projectRoot, "run_environment_simulation.py");
    const { stdout, stderr } = await execFileAsync(
      pythonPath,
      [scriptPath, "--config", configPath],
      { cwd: projectRoot, timeout: 30_000, maxBuffer: 4 * 1024 * 1024 },
    );
    if (stderr.trim()) {
      return NextResponse.json({ status: "error", error: stderr.trim() }, { status: 500 });
    }
    return NextResponse.json(JSON.parse(stdout));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Strategy Lab simulation failed.";
    return NextResponse.json({ status: "error", error: message }, { status: 500 });
  } finally {
    if (configPath) {
      await fs.rm(configPath, { force: true }).catch(() => undefined);
    }
  }
}
