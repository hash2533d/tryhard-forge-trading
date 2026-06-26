#!/usr/bin/env python3
"""Demonstrate L-system watermark evolution + structured fact harvest."""

from __future__ import annotations

import os
import time

from tryhard_quant_lsystem import LSystemWatermark, TryHardQuantLSystemEngine

EXAMPLES = [
    "gflbsdragon",
    "nakedpoc",
    "coherencetime",
    "prismagent",
    "algocurator",
]


def main() -> int:
    print("=== TryHard L-System Watermark Evolution ===\n")

    wm = LSystemWatermark()
    for base in EXAMPLES:
        print(f"  {base:16} -> {wm.evolve(base)}")

    engine = TryHardQuantLSystemEngine()
    # Simulate 301s coherence (production gate: FORGE_MIN_COHERENCE_SEC=300)
    engine.coherence_start = time.time() - 301

    regime = {
        "trend": "corrective_bounce",
        "instrument": "BTC",
        "nearest_gflbs_node": 63120,
        "ribbon_signal": "+2",
        "session": "ny_scalp",
    }
    intuition = (
        "Price basing at 63120 blue with ribbon +2 reclaim after dump; "
        "scalp long toward 64540 with stop under 62353 cluster."
    )

    strategy = engine.generate_strategy(
        raw_intuition=intuition,
        regime_metrics=regime,
        base_watermark="gflbsdragon",
    )

    print("\n=== Generated Strategy ===")
    print(strategy.model_dump_json(indent=2))

    fact = engine.harvest_structured_fact(
        "Jun 25 sync: curvature equation maps to POC rejection entry refinement",
        window_hours=72,
    )

    backend = "grok" if os.getenv("XAI_API_KEY") else "offline_fallback"
    print(f"\nBackend used: {backend}")
    print(f"Coherence ready: {engine.coherence_ready()}")
    print(f"Fact logged: {fact['observation'][:60]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())