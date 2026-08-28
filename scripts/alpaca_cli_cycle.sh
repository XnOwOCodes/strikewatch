#!/usr/bin/env bash
# CLI equivalent of one StrikeWatch cycle. Paper only.
# Does not submit unless STRIKEWATCH_CLI_SUBMIT=1.
set -euo pipefail

# Pin paper. Never live.
export ALPACA_PAPER_TRADE=true
unset ALPACA_LIVE_TRADE || true

UNDERLYING="${1:-SPY}"

echo "# account"
alpaca account get

echo "# contracts"
alpaca option contracts --underlying-symbol "${UNDERLYING}"

echo "# clock (regular hours gate)"
alpaca clock

echo "# positions"
alpaca position list

PAYLOAD='{
  "order_class": "mleg",
  "qty": "1",
  "type": "limit",
  "limit_price": "0.70",
  "time_in_force": "day",
  "legs": [
    {"symbol": "SPY260918P00530000", "ratio_qty": "1", "side": "sell", "position_intent": "sell_to_open"},
    {"symbol": "SPY260918P00520000", "ratio_qty": "1", "side": "buy", "position_intent": "buy_to_open"}
  ]
}'

echo "# defined-risk mleg payload (bull put credit)"
echo "${PAYLOAD}"

if [[ "${STRIKEWATCH_CLI_SUBMIT:-0}" == "1" ]]; then
  echo "# submit paper mleg"
  printf '%s' "${PAYLOAD}" | alpaca api POST /v2/orders
else
  echo "# not submitting. export STRIKEWATCH_CLI_SUBMIT=1 to POST against paper."
  echo "# preview helper: alpaca order submit --symbol SPY --side buy --qty 1 --type market --dry-run"
fi
