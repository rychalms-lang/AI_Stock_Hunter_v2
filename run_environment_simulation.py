from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from strategy_lab_exporter import export_strategy_lab_foundation, run_strategy_lab_request


def _load_request(args: argparse.Namespace) -> Dict[str, Any]:
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        return json.loads(config_path.read_text(encoding="utf-8"))

    request: Dict[str, Any] = {
        "mode": args.mode,
        "strategy": args.strategy,
        "preset_id": args.preset,
    }
    if args.compare:
        request["mode"] = "environment_comparison"
        request["preset_ids"] = args.compare
    if args.sensitivity_parameter:
        request["mode"] = "sensitivity_analysis"
        request["parameter"] = args.sensitivity_parameter
        request["values"] = args.sensitivity_values or []
    return request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Trading Environment Simulator.")
    parser.add_argument("--config", help="Path to a JSON request file.")
    parser.add_argument("--mode", default="historical_replay", choices=["historical_replay", "environment_comparison", "sensitivity_analysis"])
    parser.add_argument("--preset", default="personal_cash_account")
    parser.add_argument("--strategy", default="V8", choices=["V8", "V8_CHAMPION", "V9", "V9_DEFENSIVE"])
    parser.add_argument("--compare", nargs="*", help="Preset ids to compare.")
    parser.add_argument("--sensitivity-parameter")
    parser.add_argument("--sensitivity-values", nargs="*", type=float)
    parser.add_argument("--dry-run", action="store_true", help="Do not persist runtime simulation output.")
    parser.add_argument("--export-foundation", action="store_true", help="Write built-in preset data for the frontend.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.export_foundation:
            print(json.dumps({"status": "ok", **export_strategy_lab_foundation()}, sort_keys=True))
            return 0
        payload = run_strategy_lab_request(_load_request(args), persist=not args.dry_run)
        print(json.dumps({"status": "ok", "result": payload}, sort_keys=True))
        return 0
    except Exception as exc:  # CLI boundary: keep machine-readable failure.
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
