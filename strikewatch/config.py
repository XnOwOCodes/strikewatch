"""Runtime settings. Env-overridable so tests stay isolated."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from strikewatch.clock import parse_iso

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ("SPY", "QQQ", "IWM", "AAPL")


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    market_path: Path
    chain_dir: Path
    data_dir: Path
    session_id: str = "desk"
    universe: tuple[str, ...] = UNIVERSE
    now: datetime | None = None
    kill: bool = False
    kill_path: Path | None = None
    paper_trade: bool = True
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    max_contracts_per_name: int = 2
    max_notional: float = 20_000.0
    max_daily_loss: float = 500.0
    max_open_positions: int = 4
    iv_rank_min: float = 60.0
    iv_minus_rv_min: float = 0.08
    starting_equity: float = 100_000.0
    force_mock: bool = False
    extra: dict = field(default_factory=dict)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def last_decision_path(self) -> Path:
        return self.data_dir / "last_decision.json"

    @property
    def session_path(self) -> Path:
        return self.data_dir / "session.json"

    @property
    def account_path(self) -> Path:
        return self.data_dir / "mock_account.json"

    @property
    def has_alpaca_keys(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_secret_key)

    def kill_active(self) -> bool:
        if self.kill:
            return True
        path = self.kill_path
        return bool(path and path.exists())

    @classmethod
    def from_env(cls, **overrides: object) -> "Settings":
        root = Path(os.environ.get("STRIKEWATCH_ROOT", str(ROOT)))
        kill_path = Path(os.environ.get("STRIKEWATCH_KILL_FILE", str(root / "data" / "KILL")))
        values: dict = {
            "market_path": Path(
                os.environ.get(
                    "STRIKEWATCH_MARKET",
                    str(root / "fixtures" / "market.json"),
                )
            ),
            "chain_dir": Path(
                os.environ.get("STRIKEWATCH_CHAINS", str(root / "fixtures" / "chains"))
            ),
            "data_dir": Path(os.environ.get("STRIKEWATCH_DATA", str(root / "data"))),
            "session_id": os.environ.get("STRIKEWATCH_SESSION_ID", "desk"),
            "now": parse_iso(os.environ.get("STRIKEWATCH_NOW")),
            "kill": _truthy(os.environ.get("STRIKEWATCH_KILL"), default=False),
            "kill_path": kill_path,
            "paper_trade": _truthy(os.environ.get("ALPACA_PAPER_TRADE"), default=True),
            "alpaca_api_key": os.environ.get("ALPACA_API_KEY", "").strip(),
            "alpaca_secret_key": os.environ.get("ALPACA_SECRET_KEY", "").strip(),
            "max_contracts_per_name": int(os.environ.get("STRIKEWATCH_MAX_CONTRACTS", "2")),
            "max_notional": float(os.environ.get("STRIKEWATCH_MAX_NOTIONAL", "20000")),
            "max_daily_loss": float(os.environ.get("STRIKEWATCH_MAX_DAILY_LOSS", "500")),
            "max_open_positions": int(os.environ.get("STRIKEWATCH_MAX_OPEN", "4")),
            "iv_rank_min": float(os.environ.get("STRIKEWATCH_IV_RANK_MIN", "60")),
            "iv_minus_rv_min": float(os.environ.get("STRIKEWATCH_IV_RV_MIN", "0.08")),
            "starting_equity": float(os.environ.get("STRIKEWATCH_EQUITY", "100000")),
            "force_mock": _truthy(os.environ.get("STRIKEWATCH_FORCE_MOCK"), default=False),
        }
        values.update(overrides)
        settings = cls(**values)  # type: ignore[arg-type]
        settings.ensure_dirs()
        return settings
