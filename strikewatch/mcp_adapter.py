"""Official Alpaca MCP / CLI surface for one StrikeWatch cycle.

Does not spawn a server. Maps desk actions onto:
  uvx alpaca-mcp-server   (alpacahq/alpaca-mcp-server)
  alpaca CLI              (alpacahq/cli)

Paper only. ALPACA_PAPER_TRADE must be true. Never set ALPACA_LIVE_TRADE.
"""

from __future__ import annotations

from typing import Any

PAPER_MCP_ENV = {
    "ALPACA_API_KEY": "<paper-key>",
    "ALPACA_SECRET_KEY": "<paper-secret>",
    "ALPACA_PAPER_TRADE": "true",
}

MCP_LAUNCH = {
    "command": "uvx",
    "args": ["alpaca-mcp-server"],
    "env": dict(PAPER_MCP_ENV),
}


def cli_cycle_commands(
    underlying: str = "SPY",
    order_payload: dict[str, Any] | None = None,
) -> list[str]:
    """CLI equivalents of one watch cycle. Paper is the alpaca CLI default."""
    cmds = [
        "alpaca account get",
        f"alpaca option contracts --underlying-symbol {underlying}",
        "alpaca clock",
        "alpaca position list",
    ]
    if order_payload:
        cmds.append(
            "printf '%s' \"$PAYLOAD\" | alpaca api POST /v2/orders"
        )
        cmds.append("# preview without sending: alpaca order submit ... --dry-run")
    return cmds


class McpAdapter:
    """Thin wrapper documenting the official paper-only MCP/CLI surface."""

    def __init__(self, paper_trade: bool = True) -> None:
        if not paper_trade:
            raise RuntimeError("McpAdapter is paper-only.")
        self.paper_trade = True

    def launch_spec(self) -> dict[str, Any]:
        return dict(MCP_LAUNCH)

    def env(self) -> dict[str, str]:
        return dict(PAPER_MCP_ENV)

    def cycle_commands(
        self, underlying: str = "SPY", order_payload: dict[str, Any] | None = None
    ) -> list[str]:
        return cli_cycle_commands(underlying, order_payload)
