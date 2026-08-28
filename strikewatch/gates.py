"""Risk gates. Every candidate order has to pass all of them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from strikewatch.clock import is_us_regular_hours, now_et
from strikewatch.config import Settings
from strikewatch.models import (
    ALLOWED_STRUCTURES,
    AccountSnapshot,
    GateResult,
    Position,
    Proposal,
)


def paper_only(settings: Settings) -> GateResult:
    if settings.paper_trade:
        return GateResult("paper_only", True, "ALPACA_PAPER_TRADE is true; live is refused.")
    return GateResult(
        "paper_only",
        False,
        "paper-only gate: ALPACA_PAPER_TRADE is not true. StrikeWatch will not send orders.",
    )


def kill_switch(settings: Settings) -> GateResult:
    if settings.kill_active():
        return GateResult(
            "kill_switch",
            False,
            "STRIKEWATCH_KILL is on (env or kill file). All orders blocked.",
        )
    return GateResult("kill_switch", True, "kill switch is off.")


def us_regular_hours(ts: datetime) -> GateResult:
    if is_us_regular_hours(ts):
        return GateResult("us_regular_hours", True, "inside US regular hours (09:30–16:00 ET).")
    local = now_et(ts)
    return GateResult(
        "us_regular_hours",
        False,
        f"outside US regular hours ({local.strftime('%A %H:%M %Z')}).",
    )


def defined_risk(proposal: Proposal) -> GateResult:
    if proposal.structure not in ALLOWED_STRUCTURES:
        return GateResult(
            "defined_risk",
            False,
            f"structure {proposal.structure!r} is not a defined-risk structure.",
        )
    if proposal.qty <= 0:
        return GateResult("defined_risk", False, "qty must be a positive whole number.")

    shorts = [leg for leg in proposal.legs if leg.side == "sell"]
    longs = [leg for leg in proposal.legs if leg.side == "buy"]
    if not shorts:
        return GateResult("defined_risk", False, "no short option; nothing to sell.")

    if proposal.structure == "cash_secured_put":
        if len(proposal.legs) != 1 or len(shorts) != 1:
            return GateResult("defined_risk", False, "cash-secured put must be a single short put.")
        short = shorts[0]
        if short.option_type != "put":
            return GateResult("defined_risk", False, "cash-secured put must be a put.")
        needed = short.strike * 100 * proposal.qty
        if proposal.cash_reserved + 1e-9 < needed:
            return GateResult(
                "defined_risk",
                False,
                f"CSP cash cover {proposal.cash_reserved:.0f} < {needed:.0f}.",
            )
        return GateResult("defined_risk", True, "cash-secured put is fully cash-covered.")

    if len(proposal.legs) != 2 or len(shorts) != 1 or len(longs) != 1:
        return GateResult(
            "defined_risk",
            False,
            "credit spread must be one short leg and one long wing (no naked short).",
        )
    short, long = shorts[0], longs[0]
    if short.expiration_date != long.expiration_date:
        return GateResult("defined_risk", False, "spread wings must share an expiry.")
    if short.underlying_symbol != long.underlying_symbol:
        return GateResult("defined_risk", False, "spread wings must share an underlying.")
    if short.ratio_qty != long.ratio_qty != 1:
        return GateResult("defined_risk", False, "spread ratios must be 1:1.")

    if proposal.structure == "bull_put_credit":
        if short.option_type != "put" or long.option_type != "put":
            return GateResult("defined_risk", False, "bull put credit needs two puts.")
        if long.strike >= short.strike:
            return GateResult(
                "defined_risk",
                False,
                "bull put credit needs long strike below the short strike.",
            )
        return GateResult("defined_risk", True, "bull put credit spread is defined-risk.")

    if proposal.structure == "bear_call_credit":
        if short.option_type != "call" or long.option_type != "call":
            return GateResult("defined_risk", False, "bear call credit needs two calls.")
        if long.strike <= short.strike:
            return GateResult(
                "defined_risk",
                False,
                "bear call credit needs long strike above the short strike.",
            )
        return GateResult("defined_risk", True, "bear call credit spread is defined-risk.")

    return GateResult("defined_risk", False, "unrecognized structure.")


def max_contracts_per_name(
    proposal: Proposal, positions: list[Position], limit: int
) -> GateResult:
    existing = sum(
        abs(pos.qty)
        for pos in positions
        if pos.underlying == proposal.underlying
        and pos.asset_class == "us_option"
        and pos.qty < 0
    )
    # count short contracts on the name, not the long wing
    planned = existing + proposal.qty
    if planned > limit:
        return GateResult(
            "max_contracts_per_name",
            False,
            f"{proposal.underlying} would be {planned} short contracts vs cap {limit}.",
        )
    return GateResult(
        "max_contracts_per_name",
        True,
        f"{proposal.underlying} short qty {planned} within cap {limit}.",
    )


def max_notional(proposal: Proposal, limit: float) -> GateResult:
    if proposal.max_loss > limit:
        return GateResult(
            "max_notional",
            False,
            f"max loss {proposal.max_loss:.0f} exceeds notional cap {limit:.0f}.",
        )
    return GateResult(
        "max_notional",
        True,
        f"max loss {proposal.max_loss:.0f} within notional cap {limit:.0f}.",
    )


def max_daily_loss(account: AccountSnapshot, limit: float) -> GateResult:
    if account.daily_pnl <= -abs(limit):
        return GateResult(
            "max_daily_loss",
            False,
            f"daily P&L {account.daily_pnl:.2f} hit loss cap {limit:.0f}.",
        )
    return GateResult(
        "max_daily_loss",
        True,
        f"daily P&L {account.daily_pnl:.2f} inside loss cap {limit:.0f}.",
    )


def max_open_positions(
    positions: list[Position], proposal: Proposal, limit: int
) -> GateResult:
    # count distinct underlyings with open option legs, plus this name if new
    names = {pos.underlying for pos in positions if pos.asset_class == "us_option"}
    names.add(proposal.underlying)
    if len(names) > limit and proposal.underlying not in {
        pos.underlying for pos in positions if pos.asset_class == "us_option"
    }:
        return GateResult(
            "max_open_positions",
            False,
            f"open names {sorted(names)} would exceed cap {limit}.",
        )
    if len({pos.symbol for pos in positions}) + len(proposal.legs) > limit * 4:
        # hard ceiling on raw legs in case one name is packed
        pass
    open_count = len({pos.symbol for pos in positions})
    if open_count >= limit and proposal.underlying not in {
        pos.underlying for pos in positions
    }:
        return GateResult(
            "max_open_positions",
            False,
            f"{open_count} open option symbols already at cap {limit}.",
        )
    # simpler: number of underlyings with positions, after this trade
    after = len({pos.underlying for pos in positions} | {proposal.underlying})
    # also cap raw open option lines
    lines_after = len({pos.symbol for pos in positions} | {leg.symbol for leg in proposal.legs})
    if after > limit:
        return GateResult(
            "max_open_positions",
            False,
            f"{after} open underlyings would exceed cap {limit}.",
        )
    return GateResult(
        "max_open_positions",
        True,
        f"{after} open underlyings / {lines_after} legs within cap {limit}.",
    )


def duplicate_signal(proposal: Proposal, seen: set[str]) -> GateResult:
    if proposal.signal_key in seen:
        return GateResult(
            "duplicate_signal",
            False,
            f"signal {proposal.signal_key} already acted on this session.",
        )
    return GateResult("duplicate_signal", True, "new signal for this session.")


@dataclass
class GateContext:
    settings: Settings
    now: datetime
    account: AccountSnapshot
    positions: list[Position]
    seen_signals: set[str]
    proposal: Proposal | None


def evaluate_gates(ctx: GateContext) -> list[GateResult]:
    results = [
        paper_only(ctx.settings),
        kill_switch(ctx.settings),
        us_regular_hours(ctx.now),
    ]
    proposal = ctx.proposal
    if proposal is None:
        return results
    results.extend(
        [
            defined_risk(proposal),
            max_contracts_per_name(
                proposal, ctx.positions, ctx.settings.max_contracts_per_name
            ),
            max_notional(proposal, ctx.settings.max_notional),
            max_daily_loss(ctx.account, ctx.settings.max_daily_loss),
            max_open_positions(ctx.positions, proposal, ctx.settings.max_open_positions),
            duplicate_signal(proposal, ctx.seen_signals),
        ]
    )
    return results


def fired(results: list[GateResult]) -> list[str]:
    return [item.name for item in results if not item.passed]


def all_passed(results: list[GateResult]) -> bool:
    return all(item.passed for item in results)
