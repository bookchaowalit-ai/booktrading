#!/usr/bin/env bash
# Trading Bot Health Check — run anytime to get full status
# Usage: ./monitor.sh [--watch]  (pass --watch for 30s auto-refresh)

set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE_DIR="$(pwd)"
BACKEND="http://localhost:8080"

watch_mode=false
[[ "${1:-}" == "--watch" ]] && watch_mode=true

render() {
  clear 2>/dev/null || true
  echo "═══════════════════════════════════════════════════════════"
  echo "  TRADING BOT STATUS — $(date '+%Y-%m-%d %H:%M:%S')"
  echo "═══════════════════════════════════════════════════════════"

  # ── 1. Real Grid Bot (from logs) ──
  echo ""
  echo "── Real Grid Bot ──"
  local real_logs
  real_logs=$(docker logs trading-bot-strategy --since 2m 2>&1 | grep "RealGrid" | tail -5)
  if [[ -n "$real_logs" ]]; then
    echo "$real_logs" | sed 's/.*INFO - //'
  else
    echo "  (no recent logs — may be idle)"
  fi

  # ── 2. Real Open Orders ──
  echo ""
  echo "── Live Open Orders (Binance TH) ──"
  local total_orders=0
  for sym in BTCTHB ETHTHB BNBTHB SOLTHB XRPTHB; do
    local count
    count=$(curl -sf "${BACKEND}/api/trade/open-orders?symbol=$sym" 2>/dev/null \
      | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('orders',[])))" 2>/dev/null || echo "0")
    printf "  %-10s %s orders\n" "$sym" "$count"
    total_orders=$((total_orders + count))
  done
  echo "  TOTAL: $total_orders live orders"

  # ── 3. Paper Grid Bot ──
  echo ""
  echo "── Paper Grid Bot ──"
  local paper_logs
  paper_logs=$(docker logs trading-bot-strategy --since 2m 2>&1 | grep "paper_grid_bot.*Grid.*THB\|paper_grid_bot.*Grid.*USDT" | tail -5)
  if [[ -n "$paper_logs" ]]; then
    echo "$paper_logs" | sed 's/.*INFO - //'
  else
    echo "  (no recent activity)"
  fi

  # ── 4. Polymarket Paper Bot ──
  echo ""
  echo "── Polymarket Paper Bot ──"
  local poly_status
  poly_status=$(docker logs trading-bot-strategy --since 2m 2>&1 | grep "poly_bot" | tail -3)
  if echo "$poly_status" | grep -q "KILL SWITCH"; then
    echo "  ⚠ KILL SWITCH ACTIVE"
    echo "$poly_status" | grep "KILL SWITCH" | tail -1 | sed 's/.*WARNING - //'
  else
    echo "  ✅ Operational"
    local scan_line
    scan_line=$(docker logs trading-bot-strategy --since 5m 2>&1 | grep "Alpha scan #" | tail -1)
    [[ -n "$scan_line" ]] && echo "  $scan_line" | sed 's/.*INFO - //'
  fi

  # ── 5. Error Rate ──
  echo ""
  echo "── Error Rate (last 5 min) ──"
  local count_429
  count_429=$(docker logs trading-bot-strategy --since 5m 2>&1 | grep -c "429" || true)
  local err_count
  err_count=$(docker logs trading-bot-strategy --since 5m 2>&1 | grep -c "ERROR" || true)
  echo "  429 rate limits: $count_429"
  echo "  Total errors:    $err_count"

  # ── 6. Recent Fills ──
  echo ""
  echo "── Recent Fills (last 30 min) ──"
  local fills
  fills=$(docker logs trading-bot-strategy --since 30m 2>&1 | grep -i "FILLED\|fill.*real\|RealGrid.*fill\|order.*filled" | tail -5)
  if [[ -n "$fills" ]]; then
    echo "$fills" | sed 's/.*INFO - //'
  else
    echo "  (no fills in last 30 min)"
  fi

  # ── 7. Container Health ──
  echo ""
  echo "── Containers ──"
  docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep "trading-bot" || echo "  (docker not available)"

  echo ""
  echo "═══════════════════════════════════════════════════════════"
}

if $watch_mode; then
  while true; do
    render
    sleep 30
  done
else
  render
fi
