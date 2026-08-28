# Alpaca MCP + CLI (paper only)

StrikeWatch talks to Alpaca through:

1. **Python REST** — `AlpacaBroker` posts to `https://paper-api.alpaca.markets` when paper keys are set.
2. **Official MCP** — `uvx alpaca-mcp-server` ([alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server)).
3. **Official CLI** — `alpaca` ([docs](https://docs.alpaca.markets/us/docs/alpacas-cli)). A scripted cycle lives in `scripts/alpaca_cli_cycle.sh`.

## Paper-only MCP env

Never set `ALPACA_PAPER_TRADE` to false. Never set `ALPACA_LIVE_TRADE` to true.

```json
{
  "mcpServers": {
    "alpaca": {
      "command": "uvx",
      "args": ["alpaca-mcp-server"],
      "env": {
        "ALPACA_API_KEY": "<paper-key>",
        "ALPACA_SECRET_KEY": "<paper-secret>",
        "ALPACA_PAPER_TRADE": "true"
      }
    }
  }
}
```

Install the runner with `uv` / `uvx`. Paper is the server default; StrikeWatch still pins `ALPACA_PAPER_TRADE=true` so a client config cannot silently flip live.

## CLI equivalents of one cycle

```bash
export ALPACA_PAPER_TRADE=true
alpaca account get
alpaca option contracts --underlying-symbol SPY
alpaca clock
alpaca position list
```

Defined-risk multi-leg body (bull put credit / bear call credit) uses the Orders API `legs` array (`symbol`, `side`, `ratio_qty`, `position_intent`) with `order_class=mleg`. The CLI posts that JSON:

```bash
printf '%s' "$PAYLOAD" | alpaca api POST /v2/orders
```

Single-leg cash-secured put:

```bash
alpaca order submit --symbol SPY260918P00530000 --side sell --qty 1 \
  --type limit --limit-price 2.10 --dry-run
```

`--dry-run` previews. Drop it only against a dedicated paper account.

See `scripts/alpaca_cli_cycle.sh`.
