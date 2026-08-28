from __future__ import annotations

import pytest

from strikewatch.broker import AlpacaBroker, MissingKeysError, MockBroker, PaperOnlyError, make_broker
from strikewatch.dataio import load_chains
from strikewatch.policy import choose_proposal


def test_make_broker_without_keys_is_mock(tmp_settings):
    tmp_settings.alpaca_api_key = ""
    tmp_settings.alpaca_secret_key = ""
    tmp_settings.force_mock = False
    broker = make_broker(tmp_settings, load_chains(tmp_settings))
    assert isinstance(broker, MockBroker)


def test_alpaca_broker_refuses_missing_keys():
    with pytest.raises(MissingKeysError):
        AlpacaBroker(api_key="", secret_key="secret", paper_trade=True)


def test_alpaca_broker_refuses_live():
    with pytest.raises(PaperOnlyError):
        AlpacaBroker(api_key="PK", secret_key="SK", paper_trade=False)


def test_alpaca_broker_uses_paper_host():
    broker = AlpacaBroker(api_key="PK", secret_key="SK", paper_trade=True)
    assert broker.base == "https://paper-api.alpaca.markets"
    assert broker.name == "alpaca-paper"


def test_mock_equity_and_fill(tmp_settings, fat_settings):
    chains = load_chains(tmp_settings)
    broker = MockBroker(tmp_settings, chains)
    acct = broker.get_account()
    assert acct.equity == 100_000
    from strikewatch.clock import now_et

    proposal = choose_proposal(
        __import__("strikewatch.dataio", fromlist=["load_market"]).load_market(
            fat_settings.market_path
        ),
        chains,
        fat_settings,
        as_of=now_et(fat_settings.now),
        cash=acct.cash,
    )
    assert proposal is not None
    payload = proposal.alpaca_payload()
    assert payload.get("order_class") == "mleg"
    assert payload["legs"]
    for leg in payload["legs"]:
        assert {"symbol", "side", "ratio_qty"} <= set(leg)
    result = broker.submit_order(payload)
    assert result.status == "filled"
    assert result.filled_avg_price is not None
    after = broker.get_account()
    assert after.equity > 100_000
    assert broker.list_positions()
