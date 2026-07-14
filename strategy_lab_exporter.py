from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from environment_simulator import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TRADE_STREAM,
    run_comparison,
    run_environment_simulation,
    run_sensitivity,
    save_simulation_result,
)
from strategy_lab_presets import write_builtin_presets
from trading_environment import environment_from_overrides


ALLOWED_TRADE_STREAMS = {
    "balanced": DEFAULT_TRADE_STREAM,
}


def _safe_trade_stream(key: str | None) -> Path:
    if not key:
        return DEFAULT_TRADE_STREAM
    if key not in ALLOWED_TRADE_STREAMS:
        raise ValueError("Unsupported trade stream.")
    return ALLOWED_TRADE_STREAMS[key]


def run_strategy_lab_request(request: Dict[str, Any], *, persist: bool = True) -> Dict[str, Any]:
    mode = request.get("mode", "historical_replay")
    strategy = request.get("strategy", "V8")
    stream_path = _safe_trade_stream(request.get("trade_stream"))

    if mode == "historical_replay":
        result = run_environment_simulation(
            environment=request.get("environment"),
            preset_id=request.get("preset_id"),
            strategy=strategy,
            trade_stream_path=stream_path,
        )
        if persist:
            result["saved_to"] = str(save_simulation_result(result, DEFAULT_OUTPUT_DIR))
        return result

    if mode == "environment_comparison":
        preset_ids = request.get("preset_ids") or []
        if not isinstance(preset_ids, list) or not 2 <= len(preset_ids) <= 4:
            raise ValueError("Environment comparison requires 2 to 4 preset ids.")
        return run_comparison([str(item) for item in preset_ids], strategy=strategy, trade_stream_path=stream_path)

    if mode == "sensitivity_analysis":
        values = request.get("values") or []
        parameter = request.get("parameter")
        if not parameter or not isinstance(values, list) or len(values) < 2 or len(values) > 9:
            raise ValueError("Sensitivity analysis requires a parameter and 2 to 9 values.")
        base_environment = environment_from_overrides(request.get("environment"))
        return run_sensitivity(
            base_environment,
            str(parameter),
            [float(value) for value in values],
            strategy=strategy,
            trade_stream_path=stream_path,
        )

    raise ValueError(f"Unsupported simulation mode: {mode}")


def export_strategy_lab_foundation() -> Dict[str, Any]:
    presets_path = write_builtin_presets()
    return {
        "presets": str(presets_path),
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "trade_stream": str(DEFAULT_TRADE_STREAM),
    }


def write_json_payload(payload: Dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(output_path)
    return output_path
