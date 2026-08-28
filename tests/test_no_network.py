from __future__ import annotations

import urllib.request

from strikewatch.broker import make_broker
from strikewatch.cycle import run_cycle
from strikewatch.dry_run import main


def test_cycle_does_not_call_urlopen(tmp_settings, monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    payload = run_cycle(tmp_settings)
    assert payload["broker"] == "mock"


def test_missing_keys_factory_is_mock(tmp_settings, monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    tmp_settings.alpaca_api_key = ""
    tmp_settings.alpaca_secret_key = ""
    tmp_settings.force_mock = False
    broker = make_broker(tmp_settings, {})
    assert broker.name == "mock"


def test_dry_run_no_urlopen(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert main([]) == 0
