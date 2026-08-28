"""Fixture and artifact I/O. No network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strikewatch.config import Settings
from strikewatch.models import OptionContract, Snapshot


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_market(path: Path) -> list[Snapshot]:
    raw = load_json(path)
    names = raw["names"] if isinstance(raw, dict) else raw
    out: list[Snapshot] = []
    for row in names:
        out.append(
            Snapshot(
                symbol=str(row["symbol"]).upper(),
                spot=float(row["spot"]),
                iv=float(row["iv"]),
                iv_52w_low=float(row["iv_52w_low"]),
                iv_52w_high=float(row["iv_52w_high"]),
                realized_vol_20d=float(row["realized_vol_20d"]),
                bias=str(row.get("bias") or "neutral"),
            )
        )
    return out


def load_chain_file(path: Path) -> list[OptionContract]:
    raw = load_json(path)
    rows = raw["option_contracts"] if isinstance(raw, dict) else raw
    return [OptionContract.from_alpaca(row) for row in rows]


def load_chains(settings: Settings) -> dict[str, list[OptionContract]]:
    chains: dict[str, list[OptionContract]] = {}
    for symbol in settings.universe:
        path = settings.chain_dir / f"{symbol}.json"
        if path.exists():
            chains[symbol] = load_chain_file(path)
    return chains


def load_session(settings: Settings) -> dict[str, Any]:
    if not settings.session_path.exists():
        return {"session_id": settings.session_id, "seen_signals": []}
    data = load_json(settings.session_path)
    data.setdefault("seen_signals", [])
    return data


def save_session(settings: Settings, payload: dict[str, Any]) -> None:
    payload["session_id"] = settings.session_id
    dump_json(settings.session_path, payload)


def load_last_decision(settings: Settings) -> dict[str, Any]:
    if not settings.last_decision_path.exists():
        return {
            "decision": "none",
            "reasons": ["No cycle yet."],
            "gates": [],
            "gates_fired": [],
            "order": None,
            "account": None,
        }
    return load_json(settings.last_decision_path)


def save_last_decision(settings: Settings, payload: dict[str, Any]) -> None:
    dump_json(settings.last_decision_path, payload)
