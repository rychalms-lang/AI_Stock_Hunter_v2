export type GovernanceMode = "ai_managed" | "ai_assisted" | "user_managed";

export type PortfolioGovernance = {
  schema_version: string;
  mode: GovernanceMode;
  updated_at: string | null;
  updated_by: string;
  effective_from: string | null;
  previous_mode: GovernanceMode | null;
  mode_version: number;
  pending_transition: unknown | null;
};

export type PortfolioProposal = {
  proposal_id: string;
  created_at: string;
  expires_at: string;
  action_type: "open_position" | "close_position";
  ticker: string;
  source_pick_id: string;
  scanner_action: string;
  research_rating: string;
  proposed_amount: number;
  proposed_quantity: number;
  estimated_price: number;
  quote_status: string;
  rationale: string;
  confidence: number;
  expected_return: number;
  risk: string;
  hold_period: number;
  stop_loss: number | null;
  take_profit: number | null;
  status: "pending" | "approved" | "rejected" | "expired" | "cancelled" | "executed" | "failed";
  user_decision: string | null;
  decided_at: string | null;
};

export type GovernanceData = {
  governance: PortfolioGovernance;
  proposals: PortfolioProposal[];
};

export const MODE_LABELS: Record<GovernanceMode, string> = {
  ai_managed: "AI Managed",
  ai_assisted: "AI Assisted",
  user_managed: "User Managed",
};

export function modeCapabilities(mode: GovernanceMode) {
  if (mode === "ai_managed") {
    return {
      authority: "V8",
      entries: "Automatic V8 entries enabled",
      exits: "V8 lifecycle exits enabled",
      approval: "Approval not required",
      manual: "Manual add disabled",
      automation: "V8 automation enabled",
      message: "V8 is managing this paper portfolio.",
    };
  }

  if (mode === "user_managed") {
    return {
      authority: "User",
      entries: "Manual entries enabled",
      exits: "Manual lifecycle for new user positions",
      approval: "Approval not required",
      manual: "Manual add enabled",
      automation: "V8 automation disabled",
      message: "You control this paper portfolio.",
    };
  }

  return {
    authority: "User-approved V8",
    entries: "V8 proposals require approval",
    exits: "Assisted exits deferred; no silent automatic assisted exits",
    approval: "Approval required",
    manual: "Manual add enabled",
    automation: "V8 proposal generation enabled",
    message: "V8 proposes. You decide.",
  };
}
