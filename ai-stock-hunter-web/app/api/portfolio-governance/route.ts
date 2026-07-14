import { execFile } from "child_process";
import { existsSync } from "fs";
import path from "path";
import { promisify } from "util";
import { NextRequest, NextResponse } from "next/server";

const execFileAsync = promisify(execFile);

export const runtime = "nodejs";

const REQUEST_ID_RE = /^[A-Za-z0-9_.:-]{8,80}$/;
const VALID_MODES = new Set(["ai_managed", "ai_assisted", "user_managed"]);

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function pythonPath(projectRoot: string) {
  const venvPython = path.join(projectRoot, "venv", "bin", "python");
  return existsSync(venvPython) ? venvPython : "python3";
}

function jsonError(message: string, status = 400, code = "invalid_request") {
  return NextResponse.json({ ok: false, code, message }, { status });
}

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return jsonError("Request body must be valid JSON.");
  }

  const action = text(body.action);
  const requestId = text(body.requestId);
  if (!REQUEST_ID_RE.test(requestId)) {
    return jsonError("Request ID is invalid.", 400, "invalid_request_id");
  }

  const projectRoot = path.resolve(process.cwd(), "..");
  const args = [path.join(projectRoot, "manage_portfolio_governance.py")];

  if (action === "set_mode") {
    const mode = text(body.mode);
    if (!VALID_MODES.has(mode)) {
      return jsonError("Portfolio control mode is invalid.", 400, "invalid_mode");
    }
    args.push("set-mode", "--mode", mode, "--request-id", requestId);
  } else if (action === "approve_proposal") {
    const proposalId = text(body.proposalId);
    if (!proposalId) return jsonError("Proposal ID is required.", 400, "invalid_proposal_id");
    args.push("approve-proposal", "--proposal-id", proposalId, "--request-id", requestId);
  } else if (action === "reject_proposal") {
    const proposalId = text(body.proposalId);
    if (!proposalId) return jsonError("Proposal ID is required.", 400, "invalid_proposal_id");
    args.push("reject-proposal", "--proposal-id", proposalId, "--request-id", requestId);
  } else {
    return jsonError("Portfolio control action is invalid.", 400, "invalid_action");
  }

  try {
    const { stdout } = await execFileAsync(pythonPath(projectRoot), args, {
      cwd: projectRoot,
      timeout: 30000,
      maxBuffer: 1024 * 1024,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
    const payload = JSON.parse(stdout);
    return NextResponse.json(payload, { status: payload.ok ? 200 : 400 });
  } catch (error) {
    const execError = error as { stdout?: string; stderr?: string };
    if (execError.stdout) {
      try {
        return NextResponse.json(JSON.parse(execError.stdout), { status: 400 });
      } catch {
        return jsonError("Portfolio control command returned invalid JSON.", 500, "command_parse_error");
      }
    }
    return jsonError(execError.stderr || "Portfolio control command failed.", 500, "command_failed");
  }
}
