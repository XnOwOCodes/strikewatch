from __future__ import annotations

from datetime import datetime

from strikewatch.clock import ET
from strikewatch.gates import (
    GateContext,
    defined_risk,
    duplicate_signal,
    evaluate_gates,
    fired,
    kill_switch,
    max_contracts_per_name,
    max_daily_loss,
    max_notional,
    max_open_positions,
    paper_only,
    us_regular_hours,
)
from strikewatch.models import AccountSnapshot, Leg, Position, Proposal


def _spread() -> Proposal:
    legs = [
        Leg("SPY260918P00530000", "sell", 1, "put", 530.0, "2026-09-18", "SPY"),
        Leg("SPY260918P00520000", "buy", 1, "put", 520.0, "2026-09-18", "SPY"),
    ]
    return Proposal(
        structure="bull_put_credit",
        underlying="SPY",
        qty=1,
        limit_price=0.70,
        legs=legs,
        max_loss=930.0,
        credit=0.70,
        signal_key="SPY:bull_put_credit:2026-09-18:530",
        iv_rank=82.0,
        iv_minus_rv=0.16,
        expiry="2026-09-18",
    )


def test_paper_only_passes_when_paper(tmp_settings):
    assert paper_only(tmp_settings).passed is True


def test_paper_only_blocks_when_not_paper(tmp_settings):
    tmp_settings.paper_trade = False
    result = paper_only(tmp_settings)
    assert result.passed is False
    assert "paper" in result.reason.lower()


def test_kill_switch_env(tmp_settings):
    tmp_settings.kill = True
    assert kill_switch(tmp_settings).passed is False


def test_kill_switch_file(tmp_settings):
    path = tmp_settings.data_dir / "KILL"
    path.write_text("1\n")
    tmp_settings.kill_path = path
    assert kill_switch(tmp_settings).passed is False


def test_hours_rth_friday():
    assert us_regular_hours(datetime(2026, 8, 28, 10, 30, tzinfo=ET)).passed is True


def test_hours_weekend():
    assert us_regular_hours(datetime(2026, 8, 29, 10, 30, tzinfo=ET)).passed is False


def test_hours_after_close():
    assert us_regular_hours(datetime(2026, 8, 28, 16, 0, tzinfo=ET)).passed is False


def test_defined_risk_spread_ok():
    assert defined_risk(_spread()).passed is True


def test_defined_risk_rejects_naked_short():
    legs = [Leg("SPY260918C00600000", "sell", 1, "call", 600.0, "2026-09-18", "SPY")]
    proposal = _spread()
    proposal.structure = "naked_short_call"
    proposal.legs = legs
    assert defined_risk(proposal).passed is False


def test_defined_risk_rejects_two_short_puts():
    proposal = _spread()
    proposal.legs = [
        Leg("SPY260918P00530000", "sell", 1, "put", 530.0, "2026-09-18", "SPY"),
        Leg("SPY260918P00520000", "sell", 1, "put", 520.0, "2026-09-18", "SPY"),
    ]
    assert defined_risk(proposal).passed is False


def test_defined_risk_csp_needs_cash():
    proposal = _spread()
    proposal.structure = "cash_secured_put"
    proposal.legs = [Leg("SPY260918P00530000", "sell", 1, "put", 530.0, "2026-09-18", "SPY")]
    proposal.cash_reserved = 0.0
    assert defined_risk(proposal).passed is False
    proposal.cash_reserved = 53000.0
    assert defined_risk(proposal).passed is True


def test_max_contracts():
    pos = [Position("SPY260918P00540000", -2, "short", 1.0, -200, 0, "SPY")]
    assert max_contracts_per_name(_spread(), pos, limit=2).passed is False
    assert max_contracts_per_name(_spread(), [], limit=2).passed is True


def test_max_notional():
    p = _spread()
    p.max_loss = 50_000
    assert max_notional(p, 20_000).passed is False
    p.max_loss = 900
    assert max_notional(p, 20_000).passed is True


def test_max_daily_loss():
    acct = AccountSnapshot(99_000, 99_000, 99_000, daily_pnl=-500)
    assert max_daily_loss(acct, 500).passed is False
    acct.daily_pnl = -20
    assert max_daily_loss(acct, 500).passed is True


def test_max_open_positions():
    positions = [
        Position("QQQ1", -1, "short", 1, 0, 0, "QQQ"),
        Position("IWM1", -1, "short", 1, 0, 0, "IWM"),
        Position("AAPL1", -1, "short", 1, 0, 0, "AAPL"),
        Position("MSFT1", -1, "short", 1, 0, 0, "MSFT"),
    ]
    assert max_open_positions(positions, _spread(), limit=4).passed is False
    assert max_open_positions([], _spread(), limit=4).passed is True


def test_duplicate_signal():
    p = _spread()
    assert duplicate_signal(p, set()).passed is True
    assert duplicate_signal(p, {p.signal_key}).passed is False


def test_evaluate_all_pass_on_clean_desk(tmp_settings):
    ctx = GateContext(
        settings=tmp_settings,
        now=datetime(2026, 8, 28, 10, 30, tzinfo=ET),
        account=AccountSnapshot(100_000, 100_000, 100_000, 0.0),
        positions=[],
        seen_signals=set(),
        proposal=_spread(),
    )
    results = evaluate_gates(ctx)
    assert fired(results) == []
