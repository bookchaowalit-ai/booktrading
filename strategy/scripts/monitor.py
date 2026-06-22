#!/usr/bin/env python3
"""
Polymarket Paper Bot — Daily Monitoring Report
Run: docker compose exec strategy python /app/scripts/monitor.py
"""
import json
import redis
import os
from datetime import datetime, timezone

def main():
    r = redis.Redis(host='redis', port=6379, password=os.getenv('REDIS_PASSWORD',''), decode_responses=True)
    state = json.loads(r.get('poly_paper:state') or '{}')

    positions = state.get('positions', {})
    resolved = [p for p in positions.values() if p.get('status') in ('resolved', 'closed')]
    # Legacy positions have no status field — treat as active if not resolved
    active = [p for p in positions.values() if p.get('status') not in ('resolved', 'closed')]

    bankroll = state.get('bankroll', 100.0)
    initial = 100.0
    pnl = bankroll - initial
    dd_pct = ((initial - bankroll) / initial) * 100 if bankroll < initial else 0

    ks = state.get('kill_switch_active', False)
    reason = state.get('kill_reason', '')
    consec = state.get('consecutive_losses', 0)
    daily_pnl = state.get('daily_pnl', 0.0)

    # Per-signal PnL from resolved
    signal_pnl = {}
    signal_count = {}
    for p in resolved:
        sig = p.get('signal_type', 'unknown')
        size = p.get('size', 5.0)
        outcome = p.get('outcome', '')
        if outcome == 'win':
            entry = p.get('entry_price', 0.5)
            profit = size * (1 - entry) / entry if entry > 0 else 0
        else:
            profit = -size
        signal_pnl[sig] = signal_pnl.get(sig, 0) + profit
        signal_count[sig] = signal_count.get(sig, 0) + 1

    # Report
    print("=" * 55)
    print("  Polymarket Paper Bot — Daily Monitor")
    print("=" * 55)
    print(f"Date:              {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Active positions:  {len(active)}")
    print(f"Resolved trades:   {len(resolved)}")
    print(f"Bankroll:          ${bankroll:.2f}")
    print(f"Total PnL:         ${pnl:+.2f}")
    print(f"Drawdown:          {dd_pct:.1f}%")
    print(f"Kill switch:       {'ACTIVE — ' + reason if ks else 'OFF (normal)'}")
    print(f"Consec losses:     {consec}")
    print(f"Daily PnL:         ${daily_pnl:+.2f}")
    print()

    if signal_pnl:
        print("Per-signal PnL (resolved):")
        for sig, pnl_s in sorted(signal_pnl.items(), key=lambda x: x[1]):
            cnt = signal_count.get(sig, 0)
            flag = "  ⚠ DISABLE" if pnl_s < -5 else ""
            print(f"  {sig:25s}  ${pnl_s:+6.2f}  ({cnt} trades){flag}")
    else:
        print("Per-signal PnL:    (no resolved trades yet)")

    print()
    print("-" * 55)

    # Decision logic
    if ks:
        print("Decision: WAIT — kill switch active, legacy exposure resolving")
    elif len(active) > 8:
        print(f"Decision: WAIT — {len(active)} active positions still above limit (8)")
    elif len(resolved) < 50:
        print(f"Decision: WAIT — only {len(resolved)} resolved trades (need 50-100 for review)")
    else:
        print("Decision: EVALUATE — review per-signal PnL, consider disabling losers")

    print("=" * 55)

if __name__ == '__main__':
    main()
