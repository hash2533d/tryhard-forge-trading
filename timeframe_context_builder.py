#!/usr/bin/env python3
"""Backward-compatible wrapper — delegates to handoff_timeframe."""

from handoff_timeframe import (
    DAYTRADE_PROFILE,
    SCALPER_PROFILE,
    SWING_LONG_PROFILE,
    get_active_profile,
    get_regret_pivot_threshold,
)

# Legacy aliases
SWING_PROFILE = SWING_LONG_PROFILE

if __name__ == "__main__":
    name, block = get_active_profile()
    print(f"Active profile: {name}")
    print(block)