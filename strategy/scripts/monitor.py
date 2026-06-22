#!/usr/bin/env python3
"""
Polymarket Paper Bot — Daily Monitoring Report
Run: docker compose exec strategy python /app/scripts/monitor.py

Output matches strategy/RUNBOOK.md decision tree.
"""
import json
import redis
import os
import time
from datetime import datetime, timezone

MAX_POSITIONS = 8
MIN_RESOLVED_FOR_REVIEW = 10


def compute_signal_pnl(resolved):
    """Compute per-signal PnL from resolved positions. Pure function."""
    signal_pnl = {}
    signal_count = {}
    signal_wins = {}
    for p in resolved:
        sig = p.get('signal_type', p.get('signals', ['unknown'])[0] if p.get('signals') else 'unknown')
        size = p.get('size_usdc', p.get('size', 5.0))
        outcome = p.get('outcome', '')
        if outcome == 'win':
            entry = p.get('entry_price', 0.5)
            profit = size * (1 - entry) / entry if entry > 0 else 0
            signal_wins[sig] = signal_wins.get(sig, 0) + 1
        else:
            profit = -size
        signal_pnl[sig] = signal_pnl.get(sig, 0) + profit
        signal_count[sig] = signal_count.get(sig, 0) + 1
    return signal_pnl, signal_count, signal_wins


def compute_decision(state):
    """
    Compute the daily monitor decision from Redis state.
    Pure function — no I/O, no Redis, no print.

    Returns: (decision, reason, next_trigger)
    """
    positions = state.get('positions', {})
    active = [p for p in positions.values() if p.get('status') not in ('resolved', 'closed')]
    resolved = [p for p in positions.values() if p.get('status') in ('resolved', 'closed')]

    ks_active = state.get('kill_switch_active', False)
    ks_reason = state.get('kill_reason', '')

    signal_pnl, _, _ = compute_signal_pnl(resolved)

    if ks_active:
        return ('WAIT',
                f'kill switch active — {ks_reason}',
                'Reset kill switch only after: positions ≤ 8 + per-signal PnL reviewed')
    elif len(active) > MAX_POSITIONS:
        return ('WAIT',
                f'active positions {len(active)} > {MAX_POSITIONS} limit',
                f'Active positions drop below {MAX_POSITIONS}')
    elif len(resolved) < MIN_RESOLVED_FOR_REVIEW:
        return ('WAIT',
                f'only {len(resolved)} resolved trades (need {MIN_RESOLVED_FOR_REVIEW}+ for signal review)',
                f'{MIN_RESOLVED_FOR_REVIEW - len(resolved)} more resolutions needed')
    elif signal_pnl:
        worst_sig = min(signal_pnl, key=signal_pnl.get)
        worst_pnl = signal_pnl[worst_sig]
        if worst_pnl < -5:
            return ('REVIEW_SIGNALS',
                    f'worst signal "{worst_sig}" at ${worst_pnl:+.2f} — consider disabling',
                    'Disable losing signal, then re-evaluate')
        else:
            return ('ENABLE_DRY_RUN',
                    'signal PnL acceptable — ready for dry-run validation',
                    'Set POLY_DRY_RUN=true, run 2-4 weeks')
    else:
        return ('EVALUATE',
                'resolved trades available but no PnL data — inspect manually',
                'Review resolved positions in Redis')


def main():
    r = redis.Redis(
        host='redis', port=6379,
        password=os.getenv('REDIS_PASSWORD', ''),
        decode_responses=True,
    )
    state = json.loads(r.get('poly_paper:state') or '{}')

    positions = state.get('positions', {})
    # Legacy positions have no status field — treat as active if not resolved/closed
    active = [p for p in positions.values() if p.get('status') not in ('resolved', 'closed')]
    resolved = [p for p in positions.values() if p.get('status') in ('resolved', 'closed')]

    bankroll = state.get('bankroll', 100.0)
    peak = state.get('peak_bankroll', 100.0)
    initial = 100.0
    pnl = bankroll - initial
    dd_pct = ((peak - bankroll) / peak) * 100 if peak > 0 else 0

    ks_active = state.get('kill_switch_active', False)
    ks_reason = state.get('kill_reason', '')
    consec = state.get('_consecutive_losses', state.get('consecutive_losses', 0))
    daily_pnl = state.get('_daily_pnl', state.get('daily_pnl', 0.0))

    # Oldest active position age
    now = time.time()
    oldest_age_days = 0
    oldest_question = ''
    for p in active:
        entry = p.get('entry_time', 0)
        if entry:
            age = (now - entry) / 86400
            if age > oldest_age_days:
                oldest_age_days = age
                oldest_question = p.get('question', '?')[:50]

    signal_pnl, signal_count, signal_wins = compute_signal_pnl(resolved)

    decision, reason, next_trigger = compute_decision(state)

    # ── Report ──────────────────────────────────────────────────────────────────
    print()
    print('┌─────────────────────────────────────────────────────────────┐')
    print('│   Polymarket Paper Bot — Daily Monitor                      │')
    print('└─────────────────────────────────────────────────────────────┘')
    print(f'  Date:              {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}')
    print()

    # Decision block
    print(f'  Decision:          {decision}')
    print(f'  Reason:            {reason}')
    print(f'  Next trigger:      {next_trigger}')
    print()
    print('  ── Portfolio ──────────────────────────────────────────────')
    print(f'  Active positions:  {len(active)}')
    print(f'  Resolved trades:   {len(resolved)}')
    print(f'  Bankroll:          ${bankroll:.2f}')
    print(f'  Total PnL:         ${pnl:+.2f}  (from $100 initial)')
    print(f'  Drawdown:          {dd_pct:.1f}%')
    print()

    # Kill switch
    ks_display = f'ACTIVE — {ks_reason}' if ks_active else 'OFF'
    print('  ── Safety ────────────────────────────────────────────────')
    print(f'  Kill switch:       {ks_display}')
    print(f'  Consec losses:     {consec}')
    print(f'  Daily PnL:         ${daily_pnl:+.2f}')
    print()

    # Oldest position
    if active:
        print('  ── Oldest Open Position ─────────────────────────────────')
        print(f'  Age:               {oldest_age_days:.1f} days')
        print(f'  Question:          {oldest_question}')
        print()

    # Per-signal PnL
    print('  ── Per-Signal PnL (resolved) ─────────────────────────────')
    if signal_pnl:
        for sig, pnl_s in sorted(signal_pnl.items(), key=lambda x: x[1]):
            cnt = signal_count.get(sig, 0)
            wins = signal_wins.get(sig, 0)
            wr = (wins / cnt * 100) if cnt > 0 else 0
            flag = '  ← DISABLE' if pnl_s < -5 else ''
            print(f'    {sig:22s}  ${pnl_s:+7.2f}  ({cnt} trades, {wr:.0f}% WR){flag}')
    else:
        print('    (no resolved trades yet)')
    print()
    print('  ───────────────────────────────────────────────────────────')
    print(f'  See strategy/RUNBOOK.md for full decision tree')
    print('  ───────────────────────────────────────────────────────────')
    print()


if __name__ == '__main__':
    main()
