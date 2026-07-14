"use client";

import { useMemo, useState } from "react";
import {
  StrategyLabApiResponse,
  StrategyLabPreset,
  StrategyLabResult,
  runStrategyLabSimulation,
} from "@/lib/strategyLab";
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  formatResultStatus,
  formatRuleName,
  formatTradeStream,
  resultTone,
} from "@/lib/strategyLabDisplay";

type Props = {
  presets: StrategyLabPreset[];
};

type BuilderState = {
  startingCapital: number;
  cashReserve: number;
  maxPositions: number;
  maxPositionAllocation: number;
  dailyLossLimit: number;
  overallDrawdown: number;
  trailingDrawdown: number;
  profitTarget: number;
  overnightAllowed: boolean;
  weekendAllowed: boolean;
  slippage: number;
  takeProfit: number;
  stopLoss: number;
};

const defaultBuilder: BuilderState = {
  startingCapital: 25000,
  cashReserve: 10,
  maxPositions: 7,
  maxPositionAllocation: 15,
  dailyLossLimit: 4,
  overallDrawdown: 12,
  trailingDrawdown: 12,
  profitTarget: 10,
  overnightAllowed: true,
  weekendAllowed: true,
  slippage: 0.1,
  takeProfit: 0,
  stopLoss: 0,
};

function isSimulationResult(value: StrategyLabApiResponse | null): value is { status: "ok"; result: StrategyLabResult } {
  return Boolean(value && value.status === "ok" && "metrics" in value.result);
}

function metricLabel(key: string): string {
  const labels: Record<string, string> = {
    ending_equity: "Ending equity",
    total_return_pct: "Total return",
    max_drawdown_pct: "Max drawdown",
    win_rate_pct: "Win rate",
    trades_taken: "Trades taken",
    missed_opportunities: "Missed",
    profit_factor: "Profit factor",
    target_progress_pct: "Target progress",
  };
  return labels[key] ?? "Metric";
}

function buildEnvironment(state: BuilderState) {
  return {
    account_rules: {
      starting_capital: state.startingCapital,
      minimum_cash_reserve_pct: state.cashReserve,
      maximum_open_positions: state.maxPositions,
      maximum_position_allocation_pct: state.maxPositionAllocation,
      slippage_pct: state.slippage,
    },
    risk_limits: {
      daily_loss_limit_pct: state.dailyLossLimit,
      overall_max_drawdown_pct: state.overallDrawdown,
      trailing_drawdown_pct: state.trailingDrawdown,
    },
    trading_restrictions: {
      overnight_holding_allowed: state.overnightAllowed,
      weekend_holding_allowed: state.weekendAllowed,
      forced_end_of_day_liquidation: false,
    },
    targets: {
      profit_target_pct: state.profitTarget,
      profit_target_dollars: state.startingCapital * (state.profitTarget / 100),
    },
    execution_overrides: {
      take_profit_override_pct: state.takeProfit > 0 ? state.takeProfit : null,
      stop_loss_override_pct: state.stopLoss > 0 ? state.stopLoss : null,
    },
  };
}

function NumberControl({
  label,
  value,
  min,
  max,
  step = 1,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block border-t border-[#e8e8e3] py-5">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-semibold text-black">{label}</span>
        <span className="font-mono text-sm text-black/50">
          {value}
          {suffix}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-[1fr_96px] gap-4">
        <input
          className="accent-[#7fb000]"
          max={max}
          min={min}
          onChange={(event) => onChange(Number(event.target.value))}
          step={step}
          type="range"
          value={value}
        />
        <input
          className="h-10 border border-[#deded8] bg-white px-3 text-right font-mono text-sm outline-none transition focus:border-black"
          max={max}
          min={min}
          onChange={(event) => onChange(Number(event.target.value))}
          step={step}
          type="number"
          value={value}
        />
      </div>
    </label>
  );
}

function PresetPicker({
  presets,
  selected,
  onSelect,
}: {
  presets: StrategyLabPreset[];
  selected: string;
  onSelect: (preset: StrategyLabPreset) => void;
}) {
  return (
    <div className="grid gap-px overflow-hidden border border-[#e8e8e3] bg-[#e8e8e3] md:grid-cols-2 xl:grid-cols-3">
      {presets.map((preset) => (
        <button
          className={`bg-white p-5 text-left transition hover:bg-[#f7f7f4] ${
            selected === preset.environment_id ? "shadow-[inset_3px_0_0_#7fb000]" : ""
          }`}
          key={preset.environment_id}
          onClick={() => onSelect(preset)}
          type="button"
        >
          <div className="text-xs font-black uppercase tracking-[0.22em] text-black/35">
            {preset.preset_source === "custom_local" ? "Custom" : "Built in"}
          </div>
          <div className="mt-3 text-lg font-semibold tracking-[-0.03em] text-black">
            {preset.name}
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3 text-xs text-black/50">
            <span>{formatCurrency(Number(preset.account_rules.starting_capital))}</span>
            <span>{Number(preset.account_rules.maximum_open_positions)} max pos.</span>
            <span>{Number(preset.targets.profit_target_pct)}% target</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function ResultSummary({ result }: { result: StrategyLabResult }) {
  const metrics = result.metrics;
  const chart = result.equity_curve.slice(-80);
  const min = Math.min(...chart.map((point) => point.equity));
  const max = Math.max(...chart.map((point) => point.equity));
  const path = chart
    .map((point, index) => {
      const x = chart.length <= 1 ? 0 : (index / (chart.length - 1)) * 100;
      const y = max === min ? 50 : 88 - ((point.equity - min) / (max - min)) * 76;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <section className="mt-12 border-t border-[#e8e8e3] pt-10">
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.28em] text-black/35">
            Replay Result
          </div>
          <h2 className="mt-3 text-4xl font-semibold tracking-[-0.06em] text-black md:text-6xl">
            {formatResultStatus(result.pass_fail)}
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-black/52">
            {formatTradeStream(result.trade_stream.path)} replayed through {result.environment.name}.
            V8/V9 logic was not modified.
          </p>
        </div>
        <div className="font-mono text-xs text-black/42">{result.simulation_id}</div>
      </div>

      <div className="mt-10 grid gap-px overflow-hidden border border-[#e8e8e3] bg-[#e8e8e3] md:grid-cols-4">
        {["ending_equity", "total_return_pct", "max_drawdown_pct", "win_rate_pct"].map((key) => (
          <div className="bg-white p-6" key={key}>
            <div className="text-xs font-black uppercase tracking-[0.22em] text-black/35">
              {metricLabel(key)}
            </div>
            <div className="mt-3 text-3xl font-semibold tracking-[-0.05em]">
              {key === "ending_equity"
                ? formatCurrency(metrics[key])
                : key.includes("pct")
                  ? formatPercent(metrics[key])
                  : formatNumber(metrics[key])}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 grid gap-10 xl:grid-cols-[1.35fr_0.65fr]">
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xl font-semibold tracking-[-0.04em]">Equity path</h3>
            <span className="text-xs text-black/42">Event-based replay</span>
          </div>
          <svg className="h-72 w-full overflow-visible border-y border-[#e8e8e3] py-6" viewBox="0 0 100 100" preserveAspectRatio="none">
            <path d={path} fill="none" stroke="#111" strokeLinecap="round" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
          </svg>
        </div>
        <div>
          <h3 className="text-xl font-semibold tracking-[-0.04em]">Rule checks</h3>
          <div className="mt-4 divide-y divide-[#e8e8e3] border-y border-[#e8e8e3]">
            {result.rule_results.map((rule) => (
              <div className="flex items-center justify-between py-4" key={rule.rule}>
                <span className="text-sm text-black/62">{formatRuleName(rule.rule)}</span>
                <span className={`text-sm font-semibold ${resultTone(rule.status)}`}>
                  {formatResultStatus(rule.status)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-10 grid gap-10 lg:grid-cols-2">
        <div>
          <h3 className="text-xl font-semibold tracking-[-0.04em]">Failure timeline</h3>
          <div className="mt-4 divide-y divide-[#e8e8e3] border-y border-[#e8e8e3]">
            {(result.violations.length ? result.violations : [{ date: "None", rule: "passed", severity: "info", message: "No hard rule failures in this replay." }]).slice(0, 8).map((event, index) => (
              <div className="grid grid-cols-[110px_1fr] gap-4 py-4 text-sm" key={`${event.rule}-${index}`}>
                <span className="font-mono text-black/42">{event.date}</span>
                <span>{event.message}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3 className="text-xl font-semibold tracking-[-0.04em]">Missed opportunities</h3>
          <div className="mt-4 divide-y divide-[#e8e8e3] border-y border-[#e8e8e3]">
            {(result.missed_opportunities.length ? result.missed_opportunities : [{ ticker: "None", reason: "none", detail: "No opportunities were skipped by the selected environment." }]).slice(0, 8).map((miss, index) => (
              <div className="grid grid-cols-[80px_1fr] gap-4 py-4 text-sm" key={`${miss.ticker}-${index}`}>
                <span className="font-mono font-semibold">{String(miss.ticker)}</span>
                <span className="text-black/58">{String(miss.detail)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function StrategyLabWorkbench({ presets }: Props) {
  const [selectedPreset, setSelectedPreset] = useState(presets[0]?.environment_id ?? "personal_cash_account");
  const [strategy, setStrategy] = useState("V8");
  const [state, setState] = useState(defaultBuilder);
  const [response, setResponse] = useState<StrategyLabApiResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"historical_replay" | "environment_comparison" | "sensitivity_analysis">("historical_replay");
  const activePreset = useMemo(
    () => presets.find((preset) => preset.environment_id === selectedPreset) ?? presets[0],
    [presets, selectedPreset],
  );

  async function submit(nextMode = mode) {
    setLoading(true);
    setResponse(null);
    const request =
      nextMode === "environment_comparison"
        ? {
            mode: nextMode,
            strategy,
            preset_ids: ["personal_cash_account", selectedPreset, "strict_funded_style_account"].filter((value, index, list) => list.indexOf(value) === index).slice(0, 4),
          }
        : nextMode === "sensitivity_analysis"
          ? {
              mode: nextMode,
              strategy,
              parameter: "risk_limits.daily_loss_limit_pct",
              values: [1, 2, 3, 4, 5],
              environment: buildEnvironment(state),
            }
          : {
              mode: nextMode,
              strategy,
              preset_id: selectedPreset,
              environment: buildEnvironment(state),
            };
    const result = await runStrategyLabSimulation(request);
    setResponse(result);
    setLoading(false);
  }

  return (
    <div className="space-y-14">
      <section className="grid gap-10 xl:grid-cols-[0.92fr_1.08fr]">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.28em] text-black/35">
            Environment Builder
          </div>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-0.06em] md:text-6xl">
            Replay V8 inside different account realities.
          </h2>
          <p className="mt-6 max-w-xl text-base leading-7 text-black/56">
            Configure constraints around the existing trade stream. The simulator changes cash,
            position sizing, restrictions, and pass/fail rules; it does not change the strategy.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {["V8", "V9"].map((item) => (
              <button
                className={`border px-4 py-2 text-sm font-semibold transition ${
                  strategy === item ? "border-black bg-black text-white" : "border-[#deded8] bg-white text-black/58 hover:text-black"
                }`}
                key={item}
                onClick={() => setStrategy(item)}
                type="button"
              >
                {item === "V8" ? "V8 Active" : "V9 Experimental"}
              </button>
            ))}
          </div>
        </div>

        <div className="border-y border-[#e8e8e3]">
          <NumberControl label="Starting capital" min={1000} max={250000} step={1000} value={state.startingCapital} onChange={(value) => setState({ ...state, startingCapital: value })} />
          <NumberControl label="Cash reserve" min={0} max={50} suffix="%" value={state.cashReserve} onChange={(value) => setState({ ...state, cashReserve: value })} />
          <NumberControl label="Max open positions" min={1} max={20} value={state.maxPositions} onChange={(value) => setState({ ...state, maxPositions: value })} />
          <NumberControl label="Position allocation" min={1} max={50} suffix="%" value={state.maxPositionAllocation} onChange={(value) => setState({ ...state, maxPositionAllocation: value })} />
          <details className="border-t border-[#e8e8e3] py-5">
            <summary className="cursor-pointer text-sm font-semibold text-black">Advanced constraints</summary>
            <div className="mt-2">
              <NumberControl label="Daily loss limit" min={0.5} max={10} step={0.5} suffix="%" value={state.dailyLossLimit} onChange={(value) => setState({ ...state, dailyLossLimit: value })} />
              <NumberControl label="Overall drawdown" min={2} max={35} suffix="%" value={state.overallDrawdown} onChange={(value) => setState({ ...state, overallDrawdown: value })} />
              <NumberControl label="Profit target" min={1} max={40} suffix="%" value={state.profitTarget} onChange={(value) => setState({ ...state, profitTarget: value })} />
              <NumberControl label="Slippage" min={0} max={2} step={0.05} suffix="%" value={state.slippage} onChange={(value) => setState({ ...state, slippage: value })} />
            </div>
          </details>
          <div className="flex flex-wrap gap-3 border-t border-[#e8e8e3] py-5">
            <label className="flex items-center gap-2 text-sm text-black/62">
              <input checked={state.overnightAllowed} className="accent-[#7fb000]" onChange={(event) => setState({ ...state, overnightAllowed: event.target.checked })} type="checkbox" />
              Overnight holdings
            </label>
            <label className="flex items-center gap-2 text-sm text-black/62">
              <input checked={state.weekendAllowed} className="accent-[#7fb000]" onChange={(event) => setState({ ...state, weekendAllowed: event.target.checked })} type="checkbox" />
              Weekend holdings
            </label>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-5 flex items-end justify-between gap-5">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.28em] text-black/35">
              Presets
            </div>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.05em]">Choose a trading environment.</h2>
          </div>
          <div className="hidden text-right text-sm text-black/45 md:block">
            Active preset: {activePreset?.name}
          </div>
        </div>
        <PresetPicker presets={presets} selected={selectedPreset} onSelect={(preset) => setSelectedPreset(preset.environment_id)} />
      </section>

      <section className="flex flex-col gap-4 border-y border-[#e8e8e3] py-6 md:flex-row md:items-center md:justify-between">
        <div className="text-sm leading-6 text-black/52">
          Modes: historical replay, environment comparison, and sensitivity analysis. Results are paper research artifacts only.
        </div>
        <div className="flex flex-wrap gap-3">
          {[
            ["historical_replay", "Run Replay"],
            ["environment_comparison", "Compare"],
            ["sensitivity_analysis", "Sensitivity"],
          ].map(([nextMode, label]) => (
            <button
              className="border border-black bg-black px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#2a2a2a] disabled:cursor-wait disabled:opacity-50"
              disabled={loading}
              key={nextMode}
              onClick={() => {
                setMode(nextMode as typeof mode);
                void submit(nextMode as typeof mode);
              }}
              type="button"
            >
              {loading ? "Running..." : label}
            </button>
          ))}
        </div>
      </section>

      {response?.status === "error" ? (
        <div className="border border-red-200 bg-red-50 p-6 text-sm text-red-800">
          {response.error}
        </div>
      ) : null}

      {isSimulationResult(response) ? <ResultSummary result={response.result} /> : null}

      {response?.status === "ok" && !isSimulationResult(response) ? (
        <pre className="max-h-[540px] overflow-auto border border-[#e8e8e3] bg-white p-6 text-xs text-black/70">
          {JSON.stringify(response.result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
