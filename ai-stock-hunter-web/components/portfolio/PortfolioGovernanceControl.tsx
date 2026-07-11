"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import {
  GovernanceData,
  GovernanceMode,
  MODE_LABELS,
  PortfolioProposal,
  modeCapabilities,
} from "@/lib/governanceDisplay";

const modes: GovernanceMode[] = ["ai_managed", "ai_assisted", "user_managed"];

function requestId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `governance-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function money(value: number | null | undefined) {
  if (typeof value !== "number") return "Unavailable";
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function pct(value: number | null | undefined) {
  if (typeof value !== "number") return "Insufficient data";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export default function PortfolioGovernanceControl({ data }: { data: GovernanceData }) {
  const router = useRouter();
  const [pendingMode, setPendingMode] = useState<GovernanceMode | null>(null);
  const [showModeChooser, setShowModeChooser] = useState(false);
  const [showProposals, setShowProposals] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const currentMode = data.governance.mode;
  const capabilities = modeCapabilities(currentMode);
  const pendingProposals = data.proposals.filter((proposal) => proposal.status === "pending");

  function submit(payload: Record<string, unknown>) {
    setMessage(null);
    startTransition(async () => {
      const response = await fetch("/api/portfolio-governance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requestId: requestId(), ...payload }),
      });
      const result = (await response.json()) as { ok?: boolean; message?: string };
      if (!result.ok) {
        setMessage(result.message ?? "Governance action failed.");
        return;
      }
      setPendingMode(null);
      router.refresh();
    });
  }

  return (
    <section className="border-y border-[#e8e8e3] bg-white py-5">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
              Governance
            </div>
            <span className="h-1.5 w-1.5 rounded-full bg-[#7fb000]" />
            <div className="text-xs font-bold text-black/45">
              {MODE_LABELS[currentMode]}
            </div>
          </div>
          <h2 className="mt-2 text-2xl font-black tracking-[-0.055em] text-black md:text-3xl">
            {capabilities.message}
          </h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-black/50">
            Decision authority is simulated only. Paper trades remain research
            software, never brokerage instructions.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {pendingProposals.length > 0 ? (
            <button
              type="button"
              onClick={() => setShowProposals((value) => !value)}
              className="border border-[#e8e8e3] bg-white px-4 py-2 text-sm font-bold text-black transition duration-200 hover:border-black/30"
            >
              {pendingProposals.length} proposal{pendingProposals.length === 1 ? "" : "s"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setShowModeChooser((value) => !value)}
            className="border border-black bg-black px-4 py-2 text-sm font-bold text-white transition duration-200 hover:-translate-y-0.5 hover:bg-black/86"
          >
            {showModeChooser ? "Hide modes" : "Change mode"}
          </button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-x-7 gap-y-4 md:grid-cols-4">
        <Mini label="Decision Authority" value={capabilities.authority} />
        <Mini label="Entries" value={capabilities.entries} />
        <Mini label="Manual Control" value={capabilities.manual} />
        <Mini label="Pending Approvals" value={`${pendingProposals.length}`} />
      </div>

      {showModeChooser ? (
        <div className="mt-6 grid grid-cols-1 gap-3 xl:grid-cols-3">
          {modes.map((mode) => {
            const selected = mode === currentMode;
            const modeInfo = modeCapabilities(mode);
            return (
              <button
                key={mode}
                type="button"
                onClick={() => mode !== currentMode && setPendingMode(mode)}
                className={`min-h-[150px] border p-5 text-left transition duration-200 hover:-translate-y-0.5 ${
                  selected
                    ? "border-black bg-[#fafafa]"
                    : "border-[#e8e8e3] bg-white hover:border-black/25"
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="text-xl font-black tracking-[-0.045em] text-black">
                    {MODE_LABELS[mode]}
                  </div>
                  {selected ? (
                    <span className="text-xs font-black uppercase tracking-[0.16em] text-[#5f8600]">
                      Active
                    </span>
                  ) : null}
                </div>
                <p className="mt-3 text-sm leading-6 text-black/55">
                  {modeInfo.entries}
                </p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <Mini label="Authority" value={modeInfo.authority} />
                  <Mini label="Approval" value={modeInfo.approval} />
                </div>
              </button>
            );
          })}
        </div>
      ) : null}

      {message ? (
        <div className="mt-5 border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          {message}
        </div>
      ) : null}

      {showProposals && pendingProposals.length > 0 ? (
        <ProposalList
          proposals={pendingProposals}
          disabled={isPending}
          onApprove={(proposalId) => submit({ action: "approve_proposal", proposalId })}
          onReject={(proposalId) => submit({ action: "reject_proposal", proposalId })}
        />
      ) : null}

      {pendingMode ? (
        <ModeConfirmation
          currentMode={currentMode}
          requestedMode={pendingMode}
          isPending={isPending}
          onCancel={() => setPendingMode(null)}
          onConfirm={() => submit({ action: "set_mode", mode: pendingMode })}
        />
      ) : null}
    </section>
  );
}

function ProposalList({
  proposals,
  disabled,
  onApprove,
  onReject,
}: {
  proposals: PortfolioProposal[];
  disabled: boolean;
  onApprove: (proposalId: string) => void;
  onReject: (proposalId: string) => void;
}) {
  return (
    <div className="mt-8">
      <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
        AI Assisted Proposals
      </div>
      {proposals.length === 0 ? (
        <div className="mt-4 border border-[#e8e8e3] bg-[#fafafa] p-5 text-sm text-black/50">
          No pending AI proposals.
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {proposals.map((proposal) => (
            <div key={proposal.proposal_id} className="border border-[#e8e8e3] p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-3xl font-black tracking-[-0.06em] text-black">
                    {proposal.ticker}
                  </div>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-black/55">
                    {proposal.rationale}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onApprove(proposal.proposal_id)}
                    className="border border-black bg-black px-4 py-2 text-sm font-bold text-white disabled:opacity-40"
                  >
                    Approve simulated action
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onReject(proposal.proposal_id)}
                    className="border border-[#e8e8e3] bg-white px-4 py-2 text-sm font-bold text-black disabled:opacity-40"
                  >
                    Reject proposal
                  </button>
                </div>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-6">
                <Mini label="Amount" value={money(proposal.proposed_amount)} />
                <Mini label="Qty" value={`${proposal.proposed_quantity}`} />
                <Mini label="Quote" value={proposal.quote_status} />
                <Mini label="Confidence" value={`${proposal.confidence.toFixed(0)}%`} />
                <Mini label="Expected" value={pct(proposal.expected_return)} />
                <Mini label="Risk" value={proposal.risk} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ModeConfirmation({
  currentMode,
  requestedMode,
  isPending,
  onCancel,
  onConfirm,
}: {
  currentMode: GovernanceMode;
  requestedMode: GovernanceMode;
  isPending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const requested = modeCapabilities(requestedMode);

  useEffect(() => {
    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    cancelButtonRef.current?.focus();

    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }

      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );

      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [onCancel]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[10000] grid place-items-center bg-black/55 px-4 backdrop-blur-md">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        className="w-full max-w-2xl border border-[#e8e8e3] bg-white p-7 shadow-[0_30px_100px_rgba(0,0,0,0.28)]"
      >
        <div className="text-xs font-black uppercase tracking-[0.25em] text-black/40">
          Confirm Mode Change
        </div>
        <h3 className="mt-3 text-4xl font-black tracking-[-0.07em] text-black">
          Activate {MODE_LABELS[requestedMode]}.
        </h3>
        <div className="mt-5 space-y-3 text-sm leading-6 text-black/58">
          <p>Current mode: {MODE_LABELS[currentMode]}.</p>
          <p>Requested mode: {MODE_LABELS[requestedMode]}.</p>
          <p>{requested.entries}</p>
          <p>Existing open positions keep their original origin and lifecycle metadata.</p>
          <p>Pending proposals will not silently execute during this transition.</p>
          {requestedMode === "ai_managed" ? (
            <p className="font-bold text-black">
              I understand that V8 will control future simulated portfolio decisions according to the existing paper-trading rules.
            </p>
          ) : null}
          <p>Paper trading simulation only. No real trades are placed. This is research and decision support, not investment advice.</p>
        </div>
        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            ref={cancelButtonRef}
            type="button"
            onClick={onCancel}
            className="border border-[#e8e8e3] bg-white px-5 py-3 text-sm font-bold text-black"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={onConfirm}
            className="border border-black bg-black px-5 py-3 text-sm font-bold text-white disabled:opacity-40"
          >
            Activate {MODE_LABELS[requestedMode]}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-[0.16em] text-black/35">{label}</div>
      <div className="mt-1 break-words text-sm font-bold text-black/70">{value}</div>
    </div>
  );
}
