"""Dry-run: quiet, then alert with a mock defined-risk order, then quiet.

No API keys. No network. Exit 0 only if that sequence holds.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime

from strikewatch.broker import MockBroker
from strikewatch.clock import ET
from strikewatch.config import ROOT, Settings
from strikewatch.cycle import run_cycle
from strikewatch.dataio import load_chains


FROZEN = datetime(2026, 8, 28, 10, 30, tzinfo=ET)


def _print_cycle(title: str, payload: dict) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)
    print(f"decision : {payload['decision'].upper()}")
    print(f"broker   : {payload.get('broker')}")
    print(f"notified : {payload['notified']}")
    print(f"gates    : {payload.get('gates_fired') or '(all passed or n/a)'}")
    print("reasons  :")
    for reason in payload.get("reasons") or ["(none)"]:
        print(f"  - {reason}")
    order = payload.get("order")
    if order:
        body = order.get("payload") or {}
        print(f"order    : {order.get('id')} {order.get('status')} via {order.get('broker')}")
        print(f"  class  : {body.get('order_class', 'single')}")
        print(f"  limit  : {body.get('limit_price')}")
        for leg in body.get("legs") or []:
            print(f"  leg    : {leg}")
        if body.get("symbol") and not body.get("legs"):
            print(f"  symbol : {body.get('symbol')} {body.get('side')} x{body.get('qty')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="StrikeWatch dry-run (no API keys)")
    parser.add_argument("--keep", action="store_true", help="keep the dry-run data dir")
    args = parser.parse_args(argv)

    work = ROOT / "data" / "dry-run"
    if not args.keep and work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        market_path=ROOT / "fixtures" / "scenarios" / "quiet" / "market.json",
        chain_dir=ROOT / "fixtures" / "chains",
        data_dir=work,
        session_id="dry-run",
        now=FROZEN,
        paper_trade=True,
        force_mock=True,
    )
    settings.ensure_dirs()
    chains = load_chains(settings)
    broker = MockBroker(settings, chains)

    quiet = run_cycle(settings, broker=broker)
    _print_cycle("Cycle 1 — quiet tape (IV rank / RV-IV asleep)", quiet)

    settings.market_path = ROOT / "fixtures" / "scenarios" / "fat-iv" / "market.json"
    alert = run_cycle(settings, broker=broker)
    _print_cycle("Cycle 2 — fat IV rank, defined-risk structure", alert)

    again = run_cycle(settings, broker=broker)
    _print_cycle("Cycle 3 — same signal, same session (must stay quiet)", again)

    summary = {
        "quiet": quiet["decision"],
        "alert": alert["decision"],
        "no_realert": again["decision"],
        "alert_order": None if not alert.get("order") else alert["order"].get("id"),
        "alert_structure": None
        if not alert.get("proposal")
        else alert["proposal"].get("structure"),
        "last_decision_path": str(settings.last_decision_path),
    }
    print()
    print("SUMMARY", json.dumps(summary, indent=2))
    expected = ("quiet", "alert", "quiet")
    got = (quiet["decision"], alert["decision"], again["decision"])
    has_order = bool(alert.get("order") and (alert["order"].get("payload") or {}).get("legs"))
    structure = (alert.get("proposal") or {}).get("structure")
    defined = structure in {"bull_put_credit", "bear_call_credit", "cash_secured_put"}
    if got != expected or not has_order or not defined:
        print(
            f"unexpected: got {got}, expected {expected}, order={has_order}, structure={structure}"
        )
        return 1
    print("dry-run ok: QUIET → ALERT → QUIET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
