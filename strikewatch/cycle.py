"""One watch cycle: snapshot, policy, gates, maybe one paper order."""

from __future__ import annotations

from typing import Any

from strikewatch.broker import Broker, make_broker
from strikewatch.clock import iso, now_et
from strikewatch.config import Settings
from strikewatch.dataio import (
    load_chains,
    load_market,
    load_session,
    save_last_decision,
    save_session,
)
from strikewatch.gates import GateContext, all_passed, evaluate_gates, fired
from strikewatch.mcp_adapter import cli_cycle_commands
from strikewatch.policy import choose_proposal, scoreboard


def run_cycle(
    settings: Settings | None = None,
    broker: Broker | None = None,
) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    settings.ensure_dirs()
    ts = now_et(settings.now)
    chains = load_chains(settings)
    snapshots = load_market(settings.market_path)

    if broker is None:
        broker = make_broker(settings, chains)

    account = broker.get_account()
    positions = broker.list_positions()
    session = load_session(settings)
    seen = set(session.get("seen_signals") or [])

    merged = dict(chains)
    for symbol in settings.universe:
        live = broker.list_option_contracts(symbol)
        if live:
            merged[symbol] = live

    proposal = choose_proposal(
        snapshots, merged, settings, as_of=ts, cash=account.cash
    )
    ctx = GateContext(
        settings=settings,
        now=ts,
        account=account,
        positions=positions,
        seen_signals=seen,
        proposal=proposal,
    )
    gates = evaluate_gates(ctx)
    gates_fired = fired(gates)

    reasons: list[str] = []
    order = None
    decision = "quiet"
    notified = False

    if proposal is None:
        reasons.append(
            "no options-alpha signal (IV rank / realized-vs-implied below thresholds)."
        )
        reasons.extend(g.reason for g in gates if not g.passed)
    elif not all_passed(gates):
        reasons.append("signal present but a risk gate fired.")
        reasons.extend(g.reason for g in gates if not g.passed)
    else:
        payload = proposal.alpaca_payload()
        order = broker.submit_order(payload).as_dict()
        seen.add(proposal.signal_key)
        session["seen_signals"] = sorted(seen)
        save_session(settings, session)
        account = broker.get_account()
        positions = broker.list_positions()
        decision = "alert"
        notified = True
        reasons = list(proposal.reasons)
        reasons.append(f"submitted {proposal.structure} via {broker.name}")

    body: dict[str, Any] = {
        "decision": decision,
        "reasons": reasons,
        "gates": [g.as_dict() for g in gates],
        "gates_fired": gates_fired,
        "signal": None
        if proposal is None
        else {
            "underlying": proposal.underlying,
            "structure": proposal.structure,
            "iv_rank": round(proposal.iv_rank, 2),
            "iv_minus_rv": round(proposal.iv_minus_rv, 4),
            "signal_key": proposal.signal_key,
        },
        "proposal": None if proposal is None else proposal.as_dict(),
        "order": order,
        "account": account.as_dict(),
        "open_legs": [p.as_dict() for p in positions],
        "universe": scoreboard(snapshots, settings),
        "cycle_at": iso(ts),
        "broker": broker.name,
        "notified": notified,
        "cli_equivalents": cli_cycle_commands(
            proposal.underlying if proposal else "SPY",
            proposal.alpaca_payload() if proposal and notified else None,
        ),
    }
    save_last_decision(settings, body)
    return body
