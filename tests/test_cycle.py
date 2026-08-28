from __future__ import annotations

from strikewatch.broker import MockBroker
from strikewatch.cycle import run_cycle
from strikewatch.dataio import load_chains, load_last_decision


def test_quiet_cycle_does_not_page(tmp_settings):
    payload = run_cycle(tmp_settings)
    assert payload["decision"] == "quiet"
    assert payload["notified"] is False
    assert payload["order"] is None
    assert payload["broker"] == "mock"


def test_fat_cycle_alerts_once(fat_settings):
    broker = MockBroker(fat_settings, load_chains(fat_settings))
    payload = run_cycle(fat_settings, broker=broker)
    assert payload["decision"] == "alert"
    assert payload["notified"] is True
    assert payload["order"] is not None
    body = payload["order"]["payload"]
    assert body.get("order_class") == "mleg"
    assert body.get("legs")
    second = run_cycle(fat_settings, broker=broker)
    assert second["decision"] == "quiet"
    assert "duplicate" in " ".join(second["reasons"]).lower() or "already" in " ".join(
        second["reasons"]
    ).lower()
    assert "duplicate_signal" in second["gates_fired"]


def test_kill_blocks_alert(fat_settings):
    fat_settings.kill = True
    payload = run_cycle(fat_settings)
    assert payload["decision"] == "quiet"
    assert "kill_switch" in payload["gates_fired"]
    assert payload["order"] is None


def test_cycle_writes_last_decision(tmp_settings):
    run_cycle(tmp_settings)
    last = load_last_decision(tmp_settings)
    assert last["decision"] == "quiet"
