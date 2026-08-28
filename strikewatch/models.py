"""Small value objects shared by policy, gates, and brokers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    symbol: str
    spot: float
    iv: float
    iv_52w_low: float
    iv_52w_high: float
    realized_vol_20d: float
    bias: str = "neutral"

    @property
    def iv_rank(self) -> float:
        span = self.iv_52w_high - self.iv_52w_low
        if span <= 0:
            return 0.0
        rank = 100.0 * (self.iv - self.iv_52w_low) / span
        return max(0.0, min(100.0, rank))

    @property
    def iv_minus_rv(self) -> float:
        return self.iv - self.realized_vol_20d

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["iv_rank"] = round(self.iv_rank, 2)
        payload["iv_minus_rv"] = round(self.iv_minus_rv, 4)
        return payload


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    underlying_symbol: str
    expiration_date: str
    option_type: str
    strike: float
    bid: float
    ask: float
    size: int = 100
    tradable: bool = True
    status: str = "active"

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return round((self.bid + self.ask) / 2.0, 4)
        return round(float(self.ask or self.bid or 0.0), 4)

    @classmethod
    def from_alpaca(cls, raw: dict[str, Any]) -> "OptionContract":
        bid = float(raw.get("bid") or 0.0)
        ask = float(raw.get("ask") or 0.0)
        close = float(raw.get("close_price") or 0.0)
        if bid <= 0 and ask <= 0 and close > 0:
            bid, ask = round(close * 0.98, 4), round(close * 1.02, 4)
        return cls(
            symbol=str(raw["symbol"]),
            underlying_symbol=str(raw.get("underlying_symbol") or raw.get("root_symbol") or ""),
            expiration_date=str(raw["expiration_date"]),
            option_type=str(raw.get("type") or raw.get("option_type") or "").lower(),
            strike=float(raw["strike_price"]),
            bid=bid,
            ask=ask,
            size=int(float(raw.get("size") or 100)),
            tradable=bool(raw.get("tradable", True)),
            status=str(raw.get("status") or "active"),
        )


@dataclass(frozen=True)
class Leg:
    symbol: str
    side: str
    ratio_qty: int
    option_type: str
    strike: float
    expiration_date: str
    underlying_symbol: str

    def alpaca_leg(self) -> dict[str, str]:
        intent = "sell_to_open" if self.side == "sell" else "buy_to_open"
        return {
            "symbol": self.symbol,
            "side": self.side,
            "ratio_qty": str(self.ratio_qty),
            "position_intent": intent,
        }


ALLOWED_STRUCTURES = frozenset(
    {"bull_put_credit", "bear_call_credit", "cash_secured_put"}
)


@dataclass
class Proposal:
    structure: str
    underlying: str
    qty: int
    limit_price: float
    legs: list[Leg]
    max_loss: float
    credit: float
    signal_key: str
    iv_rank: float
    iv_minus_rv: float
    expiry: str
    cash_reserved: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def alpaca_payload(self) -> dict[str, Any]:
        """Orders API body. Multi-leg uses order_class=mleg and a legs array."""
        if self.structure == "cash_secured_put":
            leg = self.legs[0]
            return {
                "symbol": leg.symbol,
                "qty": str(self.qty),
                "side": "sell",
                "type": "limit",
                "time_in_force": "day",
                "limit_price": f"{self.limit_price:.2f}",
                "position_intent": "sell_to_open",
            }
        return {
            "order_class": "mleg",
            "qty": str(self.qty),
            "type": "limit",
            "limit_price": f"{self.limit_price:.2f}",
            "time_in_force": "day",
            "legs": [leg.alpaca_leg() for leg in self.legs],
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "structure": self.structure,
            "underlying": self.underlying,
            "qty": self.qty,
            "limit_price": self.limit_price,
            "max_loss": self.max_loss,
            "credit": self.credit,
            "signal_key": self.signal_key,
            "iv_rank": self.iv_rank,
            "iv_minus_rv": self.iv_minus_rv,
            "expiry": self.expiry,
            "cash_reserved": self.cash_reserved,
            "reasons": self.reasons,
            "legs": [leg.alpaca_leg() for leg in self.legs],
            "alpaca_order": self.alpaca_payload(),
        }


@dataclass
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float
    daily_pnl: float
    status: str = "ACTIVE"
    pattern_day_trader: bool = False
    source: str = "mock"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Position:
    symbol: str
    qty: float
    side: str
    avg_entry: float
    market_value: float
    unrealized_pl: float
    underlying: str
    asset_class: str = "us_option"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrderResult:
    id: str
    status: str
    payload: dict[str, Any]
    filled_avg_price: float | None = None
    broker: str = "mock"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "filled_avg_price": self.filled_avg_price,
            "broker": self.broker,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "reason": self.reason}
