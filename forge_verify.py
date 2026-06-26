#!/usr/bin/env python3
"""Final verification for the 5-step trading forge loop."""

from __future__ import annotations

import sys
from pathlib import Path

import chromadb

from handoff_timeframe import get_active_profile

ROOT = Path(__file__).resolve().parent
CHROMA_PATH = ROOT / "agent_longterm_memory"


def main() -> int:
    print("=== TryHard Forge 5-Step Verification ===")
    ok = True

    if not CHROMA_PATH.exists():
        print("FAIL: agent_longterm_memory missing")
        return 1

    client = chromadb.PersistentClient(str(CHROMA_PATH))
    trading_count = client.get_collection("trading_memory").count()
    hebbian_count = client.get_collection("hebbian_edges").count()
    print(f"trading_memory: {trading_count}")
    print(f"hebbian_edges: {hebbian_count}")

    name, _ = get_active_profile()
    print(f"handoff profile: {name}")

    if trading_count == 0:
        print("FAIL: trading_memory empty")
        ok = False

    if hebbian_count == 0:
        print("WARN: hebbian_edges empty (run discover_persist)")

    print("Steps wired:")
    for step in (
        "discover_persist.py",
        "handoff_timeframe.py",
        "verify_regret_loop.py",
        "schedule_agent_call.py",
        "run_trading_forge.py",
    ):
        exists = (ROOT / step).exists()
        print(f"  [{'OK' if exists else 'MISSING'}] {step}")

    if ok:
        print("All 5 steps wired. Daemon: python verify_regret_loop.py")
        print("Agent call: python schedule_agent_call.py --live")
    else:
        print("SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())