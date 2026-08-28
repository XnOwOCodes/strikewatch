"""CLI: python -m strikewatch [dry-run|cycle|dashboard]."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="strikewatch",
        description="StrikeWatch — page only when a defined-risk structure clears every gate.",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("dry-run", help="Quiet, alert (mock order), then no-re-alert. No keys.")
    sub.add_parser("cycle", help="Run one watch cycle against fixtures / paper broker")
    dash = sub.add_parser("dashboard", help="Serve the last-decision board (not a chat)")
    dash.add_argument("--host", default="127.0.0.1")
    dash.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    cmd = args.cmd or "dry-run"

    if cmd == "dry-run":
        from strikewatch.dry_run import main as dry_main

        return dry_main([])

    if cmd == "cycle":
        from strikewatch.cycle import run_cycle

        payload = run_cycle()
        print(json.dumps(payload, indent=2))
        return 0

    if cmd == "dashboard":
        import uvicorn

        uvicorn.run("strikewatch.dashboard:app", host=args.host, port=args.port, reload=False)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
