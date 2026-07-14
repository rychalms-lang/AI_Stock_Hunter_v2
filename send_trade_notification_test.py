from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from trade_notification_service import build_html_body, build_subject, build_text_body, notify_trade_event, sample_event


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render or send one synthetic paper-trade notification email.")
    parser.add_argument("--type", choices=["opened", "closed"], default="opened")
    parser.add_argument("--send", action="store_true", help="Actually send the test email using configured SMTP credentials.")
    parser.add_argument("--output-html", type=Path, help="Write the rendered HTML preview to this path.")
    parser.add_argument("--output-text", type=Path, help="Write the rendered plain-text preview to this path.")
    parser.add_argument("--state-dir", type=Path, default=Path("data/paper_trading/state"))
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    event = sample_event(args.type)
    subject = build_subject(event, test=True)
    text = build_text_body(event, test=True)
    html = build_html_body(event, test=True)

    if args.output_html:
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(html, encoding="utf-8")
    if args.output_text:
        args.output_text.parent.mkdir(parents=True, exist_ok=True)
        args.output_text.write_text(text, encoding="utf-8")

    result = notify_trade_event(
        event,
        state_dir=args.state_dir,
        dry_run=not args.send,
        test=True,
    )
    if not args.send:
        print("Rendered TEST trade notification. No email was sent.")
        print(json.dumps({
            "status": result["status"],
            "subject": subject,
            "html_output": str(args.output_html) if args.output_html else None,
            "text_output": str(args.output_text) if args.output_text else None,
            "text_preview": text[:1000],
        }, indent=2))
    else:
        print(json.dumps({
            "status": result["status"],
            "ok": result["ok"],
            "notification": result.get("notification", {}),
        }, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
