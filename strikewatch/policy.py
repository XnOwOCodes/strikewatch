"""Deterministic local policy. No LLM keys."""

from __future__ import annotations

from datetime import date, datetime

from strikewatch.config import Settings
from strikewatch.models import Leg, OptionContract, Proposal, Snapshot


def occ_symbol(root: str, expiry: str, right: str, strike: float) -> str:
    ymd = expiry.replace("-", "")[2:]
    kind = "C" if right.lower().startswith("c") else "P"
    return f"{root}{ymd}{kind}{int(round(strike * 1000)):08d}"


def _expiry_ok(expiry: str, as_of: date, min_dte: int = 14, max_dte: int = 45) -> bool:
    try:
        exp = date.fromisoformat(expiry)
    except ValueError:
        return False
    dte = (exp - as_of).days
    return min_dte <= dte <= max_dte


def _pick_expiry(chain: list[OptionContract], as_of: date) -> str | None:
    expiries = sorted({c.expiration_date for c in chain if c.tradable})
    ranked = [exp for exp in expiries if _expiry_ok(exp, as_of)]
    if ranked:
        return ranked[0]
    return expiries[0] if expiries else None


def _by_strike(chain: list[OptionContract], expiry: str, option_type: str) -> list[OptionContract]:
    rows = [
        c
        for c in chain
        if c.expiration_date == expiry
        and c.option_type == option_type
        and c.tradable
        and c.mid > 0
    ]
    return sorted(rows, key=lambda c: c.strike)


def _net(short: OptionContract, long: OptionContract) -> float:
    return round(short.mid - long.mid, 2)


def signal_hits(snap: Snapshot, settings: Settings) -> bool:
    return snap.iv_rank >= settings.iv_rank_min and snap.iv_minus_rv >= settings.iv_minus_rv_min


def build_bull_put_credit(
    snap: Snapshot, chain: list[OptionContract], qty: int, as_of: date
) -> Proposal | None:
    expiry = _pick_expiry(chain, as_of)
    if not expiry:
        return None
    puts = _by_strike(chain, expiry, "put")
    target = snap.spot * 0.95
    shorts = [c for c in puts if c.strike <= target]
    if not shorts:
        return None
    short = shorts[-1]
    longs = [c for c in puts if c.strike < short.strike]
    if not longs:
        return None
    long = longs[-1]
    credit = _net(short, long)
    if credit < 0.15:
        return None
    width = short.strike - long.strike
    max_loss = round((width - credit) * 100 * qty, 2)
    legs = [
        Leg(short.symbol, "sell", 1, "put", short.strike, expiry, snap.symbol),
        Leg(long.symbol, "buy", 1, "put", long.strike, expiry, snap.symbol),
    ]
    return Proposal(
        structure="bull_put_credit",
        underlying=snap.symbol,
        qty=qty,
        limit_price=credit,
        legs=legs,
        max_loss=max_loss,
        credit=credit,
        signal_key=f"{snap.symbol}:bull_put_credit:{expiry}:{short.strike:g}",
        iv_rank=snap.iv_rank,
        iv_minus_rv=snap.iv_minus_rv,
        expiry=expiry,
        reasons=[
            f"{snap.symbol} IV rank {snap.iv_rank:.0f}",
            f"IV-RV {snap.iv_minus_rv:.2f}",
            f"bull put credit {short.strike:g}/{long.strike:g} {expiry} net {credit:.2f}",
        ],
    )


def build_bear_call_credit(
    snap: Snapshot, chain: list[OptionContract], qty: int, as_of: date
) -> Proposal | None:
    expiry = _pick_expiry(chain, as_of)
    if not expiry:
        return None
    calls = _by_strike(chain, expiry, "call")
    target = snap.spot * 1.05
    shorts = [c for c in calls if c.strike >= target]
    if not shorts:
        return None
    short = shorts[0]
    longs = [c for c in calls if c.strike > short.strike]
    if not longs:
        return None
    long = longs[0]
    credit = _net(short, long)
    if credit < 0.15:
        return None
    width = long.strike - short.strike
    max_loss = round((width - credit) * 100 * qty, 2)
    legs = [
        Leg(short.symbol, "sell", 1, "call", short.strike, expiry, snap.symbol),
        Leg(long.symbol, "buy", 1, "call", long.strike, expiry, snap.symbol),
    ]
    return Proposal(
        structure="bear_call_credit",
        underlying=snap.symbol,
        qty=qty,
        limit_price=credit,
        legs=legs,
        max_loss=max_loss,
        credit=credit,
        signal_key=f"{snap.symbol}:bear_call_credit:{expiry}:{short.strike:g}",
        iv_rank=snap.iv_rank,
        iv_minus_rv=snap.iv_minus_rv,
        expiry=expiry,
        reasons=[
            f"{snap.symbol} IV rank {snap.iv_rank:.0f}",
            f"IV-RV {snap.iv_minus_rv:.2f}",
            f"bear call credit {short.strike:g}/{long.strike:g} {expiry} net {credit:.2f}",
        ],
    )


def build_cash_secured_put(
    snap: Snapshot, chain: list[OptionContract], qty: int, as_of: date, cash: float
) -> Proposal | None:
    expiry = _pick_expiry(chain, as_of)
    if not expiry:
        return None
    puts = _by_strike(chain, expiry, "put")
    target = snap.spot * 0.95
    shorts = [c for c in puts if c.strike <= target]
    if not shorts:
        return None
    short = shorts[-1]
    credit = round(short.mid, 2)
    if credit < 0.15:
        return None
    reserved = short.strike * 100 * qty
    if cash < reserved:
        return None
    max_loss = round(reserved - credit * 100 * qty, 2)
    legs = [Leg(short.symbol, "sell", 1, "put", short.strike, expiry, snap.symbol)]
    return Proposal(
        structure="cash_secured_put",
        underlying=snap.symbol,
        qty=qty,
        limit_price=credit,
        legs=legs,
        max_loss=max_loss,
        credit=credit,
        signal_key=f"{snap.symbol}:cash_secured_put:{expiry}:{short.strike:g}",
        iv_rank=snap.iv_rank,
        iv_minus_rv=snap.iv_minus_rv,
        expiry=expiry,
        cash_reserved=reserved,
        reasons=[
            f"{snap.symbol} IV rank {snap.iv_rank:.0f}",
            f"cash-secured put {short.strike:g} {expiry} net {credit:.2f}",
        ],
    )


def build_proposal(
    snap: Snapshot,
    chain: list[OptionContract],
    settings: Settings,
    as_of: datetime,
    cash: float,
) -> Proposal | None:
    if not signal_hits(snap, settings):
        return None
    day = as_of.date()
    bias = (snap.bias or "neutral").lower()
    if bias == "bear":
        proposal = build_bear_call_credit(snap, chain, qty=1, as_of=day)
        if proposal:
            return proposal
    proposal = build_bull_put_credit(snap, chain, qty=1, as_of=day)
    if proposal:
        return proposal
    return build_cash_secured_put(snap, chain, qty=1, as_of=day, cash=cash)


def choose_proposal(
    snapshots: list[Snapshot],
    chains: dict[str, list[OptionContract]],
    settings: Settings,
    as_of: datetime,
    cash: float,
) -> Proposal | None:
    ranked = sorted(
        (snap for snap in snapshots if snap.symbol in settings.universe),
        key=lambda s: s.iv_rank,
        reverse=True,
    )
    for snap in ranked:
        chain = chains.get(snap.symbol) or []
        proposal = build_proposal(snap, chain, settings, as_of, cash)
        if proposal:
            return proposal
    return None


def scoreboard(snapshots: list[Snapshot], settings: Settings) -> list[dict]:
    return [{**snap.as_dict(), "signal": signal_hits(snap, settings)} for snap in snapshots]
