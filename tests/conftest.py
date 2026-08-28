from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from strikewatch.clock import ET
from strikewatch.config import ROOT, Settings
from strikewatch.dataio import load_chains

RTH = datetime(2026, 8, 28, 10, 30, tzinfo=ET)


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        market_path=ROOT / "fixtures" / "scenarios" / "quiet" / "market.json",
        chain_dir=ROOT / "fixtures" / "chains",
        data_dir=tmp_path / "data",
        session_id="test",
        now=RTH,
        paper_trade=True,
        force_mock=True,
    )
    settings.ensure_dirs()
    return settings


@pytest.fixture
def fat_settings(tmp_settings: Settings) -> Settings:
    tmp_settings.market_path = ROOT / "fixtures" / "scenarios" / "fat-iv" / "market.json"
    return tmp_settings


@pytest.fixture
def chains(tmp_settings: Settings):
    return load_chains(tmp_settings)
