import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from paper_trading_engine import PaperTradingStateError, refresh_paper_trading


DEFAULT_OUTPUT_DIR = Path("data/paper_trading")
DEFAULT_STATE_DIR = DEFAULT_OUTPUT_DIR / "state"
DEFAULT_DAILY_PICKS_FILE = DEFAULT_OUTPUT_DIR / "daily_picks.json"


def load_daily_picks(path: Path) -> Optional[dict]:
    if not path.exists():
        return None

    with path.open() as f:
        return json.load(f)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh paper-trading ledger prices and lifecycle outputs without rerunning the scanner."
    )
    parser.add_argument("--dry-run", action="store_true", help="Run refresh calculations without writing state or output files.")
    parser.add_argument("--verbose", action="store_true", help="Include paths and mode details in the JSON status output.")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Paper-trading state directory.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Paper-trading JSON output directory.")
    parser.add_argument("--daily-picks", default=str(DEFAULT_DAILY_PICKS_FILE), help="Existing daily_picks.json file used only for metadata.")
    return parser


def status_payload(result: dict, verbose: bool = False) -> dict:
    payload = {
        "status": "success",
        "dry_run": result["dry_run"],
        "positions_updated": result["positions_updated"],
        "positions_stale": result["positions_stale"],
        "positions_closed": result["positions_closed"],
        "cash": result["cash"],
        "total_equity": result["total_equity"],
        "realized_pnl": result["realized_pnl"],
        "unrealized_pnl": result["unrealized_pnl"],
        "market_state": result["market_state"],
        "timestamp": result["last_market_update"],
        "price_data_status": result["price_data_status"],
    }

    if verbose:
        payload.update({
            "state_dir": result["state_dir"],
            "output_dir": result["output_dir"],
            "as_of_date": result["as_of_date"],
            "open_positions": result["open_positions"],
            "closed_trades": result["closed_trades"],
            "live_prices": result["live_prices"],
            "stale_positions": result["stale_positions"],
            "paths": result["paths"],
        })

    return payload


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        daily_picks = load_daily_picks(Path(args.daily_picks))
        result = refresh_paper_trading(
            output_dir=Path(args.output_dir),
            state_dir=Path(args.state_dir),
            daily_picks=daily_picks,
            dry_run=args.dry_run,
        )
        print(json.dumps(status_payload(result, verbose=args.verbose), sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, PaperTradingStateError, ValueError) as exc:
        print(
            json.dumps({
                "status": "error",
                "error": str(exc),
            }, sort_keys=True),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
