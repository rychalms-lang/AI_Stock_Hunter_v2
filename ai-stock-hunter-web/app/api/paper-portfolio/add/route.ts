import { execFile } from "child_process";
import { existsSync } from "fs";
import path from "path";
import { promisify } from "util";
import { NextRequest, NextResponse } from "next/server";

const execFileAsync = promisify(execFile);

export const runtime = "nodejs";

type AddRequest = {
  ticker?: unknown;
  amount?: unknown;
  sourcePickId?: unknown;
  note?: unknown;
  requestId?: unknown;
  acknowledgeOverride?: unknown;
};

const TICKER_RE = /^[A-Z0-9.\-]{1,12}$/;
const REQUEST_ID_RE = /^[A-Za-z0-9_.:-]{8,80}$/;

function jsonError(message: string, status = 400, code = "invalid_request") {
  return NextResponse.json({ ok: false, code, message }, { status });
}

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function pythonPath(projectRoot: string) {
  const venvPython = path.join(projectRoot, "venv", "bin", "python");
  return existsSync(venvPython) ? venvPython : "python3";
}

export async function POST(request: NextRequest) {
  let body: AddRequest;

  try {
    body = (await request.json()) as AddRequest;
  } catch {
    return jsonError("Request body must be valid JSON.");
  }

  const ticker = text(body.ticker).toUpperCase();
  const sourcePickId = text(body.sourcePickId);
  const note = text(body.note).slice(0, 500);
  const requestId = text(body.requestId);
  const amount = Number(body.amount);

  if (!TICKER_RE.test(ticker)) {
    return jsonError("Ticker is invalid.", 400, "invalid_ticker");
  }

  if (!sourcePickId || sourcePickId.length > 80) {
    return jsonError("Source pick ID is invalid.", 400, "invalid_source_pick_id");
  }

  if (!REQUEST_ID_RE.test(requestId)) {
    return jsonError("Request ID is invalid.", 400, "invalid_request_id");
  }

  if (!Number.isFinite(amount) || amount <= 0) {
    return jsonError("Amount must be greater than zero.", 400, "invalid_amount");
  }

  const projectRoot = path.resolve(process.cwd(), "..");
  const scriptPath = path.join(projectRoot, "manage_paper_portfolio.py");
  const args = [
    scriptPath,
    "add",
    "--ticker",
    ticker,
    "--amount",
    String(amount),
    "--source-pick-id",
    sourcePickId,
    "--request-id",
    requestId,
  ];

  if (note) {
    args.push("--note", note);
  }

  if (body.acknowledgeOverride === true) {
    args.push("--acknowledge-override");
  }

  try {
    const { stdout } = await execFileAsync(pythonPath(projectRoot), args, {
      cwd: projectRoot,
      timeout: 30000,
      maxBuffer: 1024 * 1024,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
      },
    });
    const payload = JSON.parse(stdout);
    return NextResponse.json(payload, { status: payload.ok ? 200 : 400 });
  } catch (error) {
    const execError = error as { stdout?: string; stderr?: string; code?: number };

    if (execError.stdout) {
      try {
        const payload = JSON.parse(execError.stdout);
        return NextResponse.json(payload, { status: 400 });
      } catch {
        return jsonError("Paper portfolio command returned invalid JSON.", 500, "command_parse_error");
      }
    }

    return jsonError(
      execError.stderr || "Paper portfolio command failed.",
      500,
      "command_failed"
    );
  }
}
