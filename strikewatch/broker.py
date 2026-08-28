"""Broker protocol, instant mock, and Alpaca paper REST.

Missing keys never touch the network. Live trading is refused in code.
"""

from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from typing import Any, Protocol

from strikewatch.config import Settings
from strikewatch.models import (
    AccountSnapshot,
    OptionContract,
    OrderResult,
    Position,
    Proposal,
)



def occ_root(symbol: str) -> str:
    letters = []
    for ch in symbol:
        if ch.isalpha():
            letters.append(ch)
        else:
            break
    return "".join(letters)

class MissingKeysError(RuntimeError):
    pass


class PaperOnlyError(RuntimeError):
    pass


class Broker(Protocol):
    name: str

    def get_account(self) -> AccountSnapshot: ...

    def list_positions(self) -> list[Position]: ...

    def list_option_contracts(self, underlying: str) -> list[OptionContract]: ...

    def submit_order(self, payload: dict[str, Any]) -> OrderResult: ...


class MockBroker:
    """$100k paper desk. Contracts come from fixtures. Fills immediately. No network."""

    name = "mock"

    def __init__(
        self,
        settings: Settings,
        chains: dict[str, list[OptionContract]] | None = None,
    ) -> None:
        self.settings = settings
        self.chains = chains or {}
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        path = self.settings.account_path
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        equity = float(self.settings.starting_equity)
        return {
            "equity": equity,
            "cash": equity,
            "buying_power": equity,
            "daily_pnl": 0.0,
            "start_equity": equity,
            "orders": [],
            "positions": [],
        }

    def _save(self) -> None:
        self.settings.account_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.account_path.write_text(
            json.dumps(self._state, indent=2) + "\n", encoding="utf-8"
        )

    def get_account(self) -> AccountSnapshot:
        s = self._state
        return AccountSnapshot(
            equity=float(s["equity"]),
            cash=float(s["cash"]),
            buying_power=float(s["buying_power"]),
            daily_pnl=float(s["daily_pnl"]),
            source="mock",
        )

    def list_positions(self) -> list[Position]:
        out: list[Position] = []
        for row in self._state["positions"]:
            out.append(
                Position(
                    symbol=row["symbol"],
                    qty=float(row["qty"]),
                    side=row["side"],
                    avg_entry=float(row["avg_entry"]),
                    market_value=float(row["market_value"]),
                    unrealized_pl=float(row["unrealized_pl"]),
                    underlying=row["underlying"],
                    asset_class=row.get("asset_class", "us_option"),
                )
            )
        return out

    def list_option_contracts(self, underlying: str) -> list[OptionContract]:
        return list(self.chains.get(underlying.upper(), []))

    def submit_order(self, payload: dict[str, Any]) -> OrderResult:
        order_id = "mock-" + uuid.uuid4().hex[:12]
        fill = float(payload.get("limit_price") or 0.0)
        qty = int(float(payload.get("qty") or 1))
        credit = fill * 100 * qty
        self._state["cash"] = float(self._state["cash"]) + credit
        self._state["equity"] = float(self._state["equity"]) + credit
        self._state["buying_power"] = float(self._state["cash"])
        self._state["daily_pnl"] = float(self._state["equity"]) - float(
            self._state["start_equity"]
        )
        legs = payload.get("legs") or []
        if not legs and payload.get("symbol"):
            legs = [
                {
                    "symbol": payload["symbol"],
                    "side": payload.get("side", "sell"),
                    "ratio_qty": "1",
                }
            ]
        for leg in legs:
            signed = qty * int(float(leg.get("ratio_qty") or 1))
            if leg.get("side") == "sell":
                pos_qty = -signed
                side = "short"
            else:
                pos_qty = signed
                side = "long"
            root = str(leg["symbol"])
            underlying = occ_root(root)
            self._state["positions"].append(
                {
                    "symbol": leg["symbol"],
                    "qty": pos_qty,
                    "side": side,
                    "avg_entry": fill,
                    "market_value": -credit if side == "short" else credit,
                    "unrealized_pl": 0.0,
                    "underlying": underlying,
                    "asset_class": "us_option",
                }
            )
        record = {
            "id": order_id,
            "status": "filled",
            "filled_avg_price": fill,
            "payload": payload,
        }
        self._state["orders"].append(record)
        self._save()
        return OrderResult(
            id=order_id,
            status="filled",
            payload=payload,
            filled_avg_price=fill,
            broker=self.name,
        )


class AlpacaBroker:
    """Official paper REST at https://paper-api.alpaca.markets. Never live."""

    PAPER_BASE = "https://paper-api.alpaca.markets"
    name = "alpaca-paper"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper_trade: bool = True,
        timeout: float = 10.0,
    ) -> None:
        if not paper_trade:
            raise PaperOnlyError(
                "StrikeWatch is paper-only. Refusing AlpacaBroker when paper_trade is false."
            )
        if not api_key or not secret_key:
            raise MissingKeysError(
                "AlpacaBroker needs ALPACA_API_KEY and ALPACA_SECRET_KEY. "
                "Missing keys must use MockBroker (no network)."
            )
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self.base = self.PAPER_BASE

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if not self.api_key or not self.secret_key:
            raise MissingKeysError("refusing network: missing Alpaca keys")
        url = self.base + path
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("APCA-API-KEY-ID", self.api_key)
        req.add_header("APCA-API-SECRET-KEY", self.secret_key)
        req.add_header("accept", "application/json")
        if body is not None:
            req.add_header("content-type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alpaca {method} {path} failed: {exc.code} {detail}") from exc
        return json.loads(raw) if raw else {}

    def get_account(self) -> AccountSnapshot:
        raw = self._request("GET", "/v2/account")
        equity = float(raw.get("equity") or 0.0)
        last_equity = float(raw.get("last_equity") or equity)
        return AccountSnapshot(
            equity=equity,
            cash=float(raw.get("cash") or 0.0),
            buying_power=float(raw.get("options_buying_power") or raw.get("buying_power") or 0.0),
            daily_pnl=equity - last_equity,
            status=str(raw.get("status") or "ACTIVE"),
            pattern_day_trader=bool(raw.get("pattern_day_trader")),
            source="alpaca-paper",
        )

    def list_positions(self) -> list[Position]:
        raw = self._request("GET", "/v2/positions")
        rows = raw if isinstance(raw, list) else raw.get("positions") or []
        out: list[Position] = []
        for row in rows:
            symbol = str(row.get("symbol") or "")
            underlying = str(row.get("underlying_symbol") or "")
            if not underlying:
                underlying = occ_root(symbol)
            asset = str(row.get("asset_class") or "us_equity")
            out.append(
                Position(
                    symbol=symbol,
                    qty=float(row.get("qty") or 0.0),
                    side=str(row.get("side") or "long"),
                    avg_entry=float(row.get("avg_entry_price") or 0.0),
                    market_value=float(row.get("market_value") or 0.0),
                    unrealized_pl=float(row.get("unrealized_pl") or 0.0),
                    underlying=underlying,
                    asset_class=asset,
                )
            )
        return out

    def list_option_contracts(self, underlying: str) -> list[OptionContract]:
        path = f"/v2/options/contracts?underlying_symbols={underlying}&limit=1000"
        raw = self._request("GET", path)
        rows = raw.get("option_contracts") or []
        return [OptionContract.from_alpaca(row) for row in rows]

    def submit_order(self, payload: dict[str, Any]) -> OrderResult:
        raw = self._request("POST", "/v2/orders", body=payload)
        fill = raw.get("filled_avg_price")
        return OrderResult(
            id=str(raw.get("id") or ""),
            status=str(raw.get("status") or "accepted"),
            payload=payload,
            filled_avg_price=float(fill) if fill not in (None, "", "0") else None,
            broker=self.name,
        )


def make_broker(
    settings: Settings,
    chains: dict[str, list[OptionContract]] | None = None,
) -> Broker:
    """Keys + paper → Alpaca paper REST. Anything else → mock, no network."""
    if (
        not settings.force_mock
        and settings.has_alpaca_keys
        and settings.paper_trade
    ):
        return AlpacaBroker(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper_trade=True,
        )
    return MockBroker(settings, chains)
