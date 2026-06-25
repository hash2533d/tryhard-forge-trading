#!/usr/bin/env python3
"""Inject scalper / swing / long-term profile context by session clock."""

from __future__ import annotations

from datetime import datetime, time

SCALPER_PROFILE = """[Scalper Profile Context]
ATM: Matrix_Scalper | V_c=3000 | Target 4-8 ticks | Stop 12 ticks | Trail 4/1
Stopwatch: 15s hard purge on unfilled queue.
Rules: Micro-delta filter, tight spreads, active RTH windows only.
GFLBS: Only trade within 1.5% of node. Bank partials at first node touch.
Ribbon +2/-2 at node boosts confidence +10-15. Never chase impulse bars.
Novel Overflow: Fast reaction, regret-weighted memory recall, sub-minute exits."""

SWING_PROFILE = """[Swing Profile Context]
ATM: Matrix_Swing | V_c=27000 | Target 60-100 ticks | Stop 80 ticks | BE at +30
Stopwatch: No time veto — infinite boundary lock for multi-day holds.
Rules: Wider targets, VA/ribbon reversal for exits, persistence engine for regime.
GFLBS: Structural nodes on 4H/Daily. Wait for exact node + cycle phase alignment.
Novel Overflow: Slow accumulation, high Hebbian-weight memories, trend-tier A entries only."""

DAYTRADE_PROFILE = """[Day Trader Profile Context]
ATM: Matrix_Day_Trader | V_c=9000 | Target 16-24 ticks | Stop 32 ticks | Trail 12/2
Stopwatch: 180s stagnation auto-veto.
Rules: Intraday ribbon reclaim, premarket 6AM entries preferred over NY-open chase.
GFLBS node banks + ribbon touch exits. Rule #1: bank into strength at resistance."""

LONGTERM_PROFILE = """[Long-Term Profile Context]
Janus shadow ledger + D007/Enoch regime awareness.
Rules: Evaluate directional hits on compressed state hashes.
Use for position sizing bias and macro cycle phase — not scalp execution."""


def get_active_profile(now: datetime | None = None) -> tuple[str, str]:
    """Return (profile_name, context_block) for current clock."""
    now = now or datetime.now()
    t = now.time()

    # RTH scalper windows (ET approximated on local clock)
    if time(9, 30) <= t <= time(11, 30) or time(14, 30) <= t <= time(16, 0):
        return "scalper", SCALPER_PROFILE
    if time(6, 0) <= t <= time(9, 0) or time(11, 30) < t < time(14, 30):
        return "daytrade", DAYTRADE_PROFILE
    if now.weekday() >= 5:
        return "swing", SWING_PROFILE
    return "swing", SWING_PROFILE


if __name__ == "__main__":
    name, block = get_active_profile()
    print(f"Active profile: {name}")
    print(block)