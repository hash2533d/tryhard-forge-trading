#!/usr/bin/env python3
"""Step 2 Hand Off: timeframe profile injection for scalper / swing / long-term."""

from __future__ import annotations

from datetime import datetime, time

SCALPER_PROFILE = """[Scalper Profile Context]
Current Bar Interval = 1-Minute. Max Holding Time = 5 minutes.
Max Drawdown Trigger = 5 ticks. Edge evaluation window = 5 minutes.
Only use GFLBS Grid and Order Flow micro-structures.
Regret threshold for pivot = 0.05
ATM: Matrix_Scalper | V_c=3000 | Target 4-8 ticks | Stop 12 ticks"""

SWING_LONG_PROFILE = """[Swing / Long-term Profile Context]
Current Bar Interval = 4-Hour / Daily. Focus Node = Naked Point of Control (nPOC).
Use Volume Profile macro structures. Low accumulated regret priority.
Regret threshold for pivot = 0.03
ATM: Matrix_Swing | V_c=27000 | Target 60-100 ticks | Stop 80 ticks"""

DAYTRADE_PROFILE = """[Day Trader Profile Context]
Current Bar Interval = 5-15 Minute. Max Holding Time = 180 minutes.
Ribbon reclaim entries preferred. Regret threshold for pivot = 0.04
ATM: Matrix_Day_Trader | V_c=9000 | Target 16-24 ticks | Stop 32 ticks"""


def get_active_profile(now: datetime | None = None) -> tuple[str, str]:
    """Return (profile_name, context_block)."""
    now = now or datetime.now()
    t = now.time()

    if time(9, 30) <= t <= time(11, 30) or time(14, 30) <= t <= time(16, 0):
        return "scalper", SCALPER_PROFILE
    if time(6, 0) <= t <= time(9, 0) or time(11, 30) < t < time(14, 30):
        return "daytrade", DAYTRADE_PROFILE
    return "swing", SWING_LONG_PROFILE


def get_regret_pivot_threshold(profile_name: str) -> float:
    thresholds = {"scalper": 0.05, "daytrade": 0.04, "swing": 0.03}
    return thresholds.get(profile_name, 0.04)


if __name__ == "__main__":
    name, block = get_active_profile()
    print(f"Active profile: {name}")
    print(block)