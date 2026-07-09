import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Metric from "@/components/ui/Metric";
import { AIRecommendation } from "@/lib/webSnapshot";

function formatPercent(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function badgeTone(action: string) {
  if (action === "BUY") return "green";
  if (action === "WATCH") return "amber";
  if (action === "AVOID") return "red";
  return "black";
}

export default function PortfolioPositionCard({
  recommendation,
}: {
  recommendation: AIRecommendation;
}) {
  return (
    <Card className="p-8">
      <div className="flex flex-col justify-between gap-8 xl:flex-row xl:items-start">
        <div>
          <div className="text-sm text-neutral-500">
            {recommendation.sector}
          </div>

          <div className="mt-1 text-6xl font-black tracking-[-0.09em]">
            {recommendation.ticker}
          </div>

          <div className="mt-5">
            <Badge tone={badgeTone(recommendation.action)}>
              {recommendation.action}
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-8 xl:text-right">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.22em] text-neutral-500">
              Expected Return
            </div>

            <div
              className={`mt-2 text-4xl font-black tracking-[-0.08em] ${
                recommendation.expected_return >= 0
                  ? "text-emerald-600"
                  : "text-red-600"
              }`}
            >
              {formatPercent(recommendation.expected_return)}
            </div>
          </div>

          <div>
            <div className="text-xs font-black uppercase tracking-[0.22em] text-neutral-500">
              Confidence
            </div>

            <div className="mt-2 text-4xl font-black tracking-[-0.08em]">
              {recommendation.confidence.toFixed(0)}%
            </div>
          </div>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-2 border-y border-neutral-200 md:grid-cols-4">
        <Metric
          label="Score"
          value={recommendation.score.toFixed(2)}
          className="border-r border-neutral-200"
        />
        <Metric
          label="Matches"
          value={recommendation.historical_matches.toLocaleString()}
          className="border-r border-neutral-200"
        />
        <Metric
          label="Best Hold"
          value={`${recommendation.best_hold_period_days}D`}
          className="border-r border-neutral-200"
        />
        <Metric label="Risk" value={recommendation.risk} />
      </div>

      <p className="mt-7 max-w-4xl text-base leading-7 text-neutral-600">
        {recommendation.reason}
      </p>

      <div className="mt-7 flex flex-wrap gap-3">
        <Button>Open Research</Button>
        <Button variant="secondary">Add to Portfolio</Button>
      </div>
    </Card>
  );
}