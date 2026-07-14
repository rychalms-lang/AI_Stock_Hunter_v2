import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

from market_data_service import MarketDataService
from paper_trading_engine import SCHEMA_VERSION, atomic_write_json


DEFAULT_PAPER_DIR = Path("data/paper_trading")
DEFAULT_STATE_DIR = DEFAULT_PAPER_DIR / "state"
DEFAULT_OUTPUT = Path("data/market_snapshot.json")
DEFAULT_BENCHMARKS = ("SPY", "QQQ", "IWM")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def valuation_batch_id(generated_at: str) -> str:
    return "valuation_" + generated_at.replace(":", "").replace("-", "").replace("+", "_").replace(".", "_")


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open() as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def normalize_tickers(values: Iterable[Any]) -> Set[str]:
    tickers: Set[str] = set()
    for value in values:
        ticker = str(value or "").strip().upper()
        if ticker:
            tickers.add(ticker)
    return tickers


def collect_tickers(
    paper_dir: Path = DEFAULT_PAPER_DIR,
    state_dir: Path = DEFAULT_STATE_DIR,
    include_benchmarks: bool = True,
) -> Set[str]:
    tickers: Set[str] = set()

    open_positions = read_json(paper_dir / "open_positions.json") or {}
    tickers.update(normalize_tickers(position.get("ticker") for position in open_positions.get("positions", [])))

    daily_picks = read_json(paper_dir / "daily_picks.json") or {}
    tickers.update(normalize_tickers(pick.get("ticker") for pick in daily_picks.get("picks", [])))

    proposals = read_json(state_dir / "pending_proposals.json") or {}
    tickers.update(
        normalize_tickers(
            proposal.get("ticker")
            for proposal in proposals.get("proposals", [])
            if proposal.get("status") == "pending"
        )
    )

    if include_benchmarks:
        tickers.update(DEFAULT_BENCHMARKS)

    return tickers


def overall_quote_status(quotes: Dict[str, Dict[str, Any]], market_state: str) -> str:
    if not quotes:
        return "UNAVAILABLE"

    statuses = {str(quote.get("price_status", "UNAVAILABLE")).upper() for quote in quotes.values()}
    if statuses == {"LIVE"}:
        return "LIVE"
    if statuses <= {"LIVE", "DELAYED"}:
        return "DELAYED"
    if market_state == "CLOSED" and statuses <= {"MARKET_CLOSED", "DELAYED", "LIVE"}:
        return "MARKET_CLOSED"
    if "STALE" in statuses:
        return "STALE"
    return "UNAVAILABLE" if statuses == {"UNAVAILABLE"} else "STALE"


def build_market_snapshot(
    market_data_service: Optional[MarketDataService] = None,
    paper_dir: Path = DEFAULT_PAPER_DIR,
    state_dir: Path = DEFAULT_STATE_DIR,
    include_benchmarks: bool = True,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    generated_at = generated_at or now_iso()
    service = market_data_service or MarketDataService()
    tickers = sorted(collect_tickers(paper_dir, state_dir, include_benchmarks))
    quotes = service.get_quotes(tickers)
    errors = [
        {
            "ticker": ticker,
            "error": str(quote.get("error")),
            "price_status": quote.get("price_status", "UNAVAILABLE"),
        }
        for ticker, quote in quotes.items()
        if quote.get("error")
    ]
    market_state = service.get_market_state()

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "valuation_generated_at": generated_at,
        "valuation_batch_id": valuation_batch_id(generated_at),
        "refresh_cadence_seconds": 300,
        "market_state": market_state,
        "provider": getattr(service.provider, "name", "unknown"),
        "quote_status": overall_quote_status(quotes, market_state),
        "tickers_requested": tickers,
        "tickers_updated": len([
            quote for quote in quotes.values()
            if str(quote.get("price_status")).upper() in {"LIVE", "DELAYED", "MARKET_CLOSED"}
        ]),
        "tickers_stale": len([
            quote for quote in quotes.values()
            if str(quote.get("price_status")).upper() not in {"LIVE", "DELAYED", "MARKET_CLOSED"}
        ]),
        "quotes": quotes,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh intraday market quotes for frontend display without rerunning the scanner."
    )
    parser.add_argument("--paper-dir", type=Path, default=DEFAULT_PAPER_DIR)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-benchmarks", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = build_market_snapshot(
            paper_dir=args.paper_dir,
            state_dir=args.state_dir,
            include_benchmarks=not args.no_benchmarks,
        )
        if not args.dry_run:
            atomic_write_json(args.output, payload)
        print(json.dumps({
            "status": "success",
            "dry_run": args.dry_run,
            "market_state": payload["market_state"],
            "quote_status": payload["quote_status"],
            "tickers_requested": len(payload["tickers_requested"]),
            "tickers_updated": payload["tickers_updated"],
            "errors": len(payload["errors"]),
            "output": str(args.output),
        }, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
