from __future__ import annotations

from strikewatch.clock import now_et
from strikewatch.dataio import load_chains, load_market
from strikewatch.models import Snapshot
from strikewatch.policy import build_bear_call_credit, choose_proposal, signal_hits


def test_quiet_has_no_proposal(tmp_settings):
    snaps = load_market(tmp_settings.market_path)
    assert all(not signal_hits(s, tmp_settings) for s in snaps)
    proposal = choose_proposal(
        snaps,
        load_chains(tmp_settings),
        tmp_settings,
        as_of=now_et(tmp_settings.now),
        cash=100_000,
    )
    assert proposal is None


def test_fat_iv_builds_defined_risk(fat_settings):
    snaps = load_market(fat_settings.market_path)
    proposal = choose_proposal(
        snaps,
        load_chains(fat_settings),
        fat_settings,
        as_of=now_et(fat_settings.now),
        cash=100_000,
    )
    assert proposal is not None
    assert proposal.structure == "bull_put_credit"
    payload = proposal.alpaca_payload()
    assert payload["order_class"] == "mleg"
    sides = {leg["side"] for leg in payload["legs"]}
    assert sides == {"buy", "sell"}


def test_bear_bias_uses_call_spread(fat_settings):
    snap = Snapshot(
        symbol="SPY",
        spot=560.0,
        iv=0.28,
        iv_52w_low=0.10,
        iv_52w_high=0.32,
        realized_vol_20d=0.12,
        bias="bear",
    )
    chain = load_chains(fat_settings)["SPY"]
    proposal = build_bear_call_credit(snap, chain, qty=1, as_of=now_et(fat_settings.now).date())
    assert proposal is not None
    assert proposal.structure == "bear_call_credit"
    types = {leg.option_type for leg in proposal.legs}
    assert types == {"call"}
