export type AIRecommendation = {
  ticker: string;
  sector: string;
  score: number;
  confidence: number;
  expected_return: number;
  best_hold_period_days: number;
  historical_matches: number;
  risk: string;
  action: string;
  reason: string;
};

export type TodayAction = {
  ticker: string;
  action: string;
  badge: string;
  tone: "green" | "amber" | "red" | "black";
  confidence: number;
  reason: string;
};

export type WebSnapshot = {
  generated_at: string;
  source_file: string;
  market_regime: {
    label: string;
    score: number;
  };
  top_opportunity: AIRecommendation;
  portfolio_summary: {
    status: string;
    health_label: string;
    total_value: number;
    total_return: number;
    cash_percent: number;
    positions: number;
    expected_10_day_return: number;
    ai_confidence: number;
    summary: string;
  };
  today_actions: TodayAction[];
  ranked_candidates: AIRecommendation[];
};

export async function getWebSnapshot(): Promise<WebSnapshot> {
  const response = await fetch("/web_snapshot.json", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to load web snapshot.");
  }

  return response.json();
}