# StrikeWatch architecture

Pager, not a chatbot. One cycle, then a board.

```
┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│  Universe    │     │  Policy     │     │  Risk gates │
│  SPY QQQ     │────▶│  IV rank    │────▶│  paper      │
│  IWM AAPL    │     │  IV − RV    │     │  kill       │
│  fixtures or │     │  defined-   │     │  hours      │
│  paper chain │     │  risk only  │     │  size caps  │
└──────────────┘     └─────────────┘     │  duplicate  │
                                         └──────┬──────┘
                                                │
                         all pass & signal      │ miss / no signal
                                ▼               ▼
                         ALERT + order        QUIET
                         MockBroker or        board still updates
                         Alpaca paper REST
                                │
                                ▼
                      FastAPI last-decision board
                      (why, gates, P&L, open legs)
```

## Brokers

| Class | When | Network |
| --- | --- | --- |
| `MockBroker` | keys missing, `force_mock`, or dry-run | never |
| `AlpacaBroker` | `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` and paper is true | `https://paper-api.alpaca.markets` only |

`AlpacaBroker` refuses construction when paper is false or keys are missing.

## Official extras

- MCP: `uvx alpaca-mcp-server` with `ALPACA_PAPER_TRADE=true` — [strikewatch/mcp.md](../strikewatch/mcp.md)
- CLI: `scripts/alpaca_cli_cycle.sh` wraps `alpaca account get`, `alpaca option contracts`, `alpaca api POST /v2/orders`

## Session memory

`data/session.json` stores `seen_signals`. The same structure + expiry + short strike will not re-alert in the same session.
