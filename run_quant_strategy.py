#!/usr/bin/env python3
"""Step 6: L-System quant strategy generation + optional structured fact harvest."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from handoff_timeframe import get_active_profile
from tryhard_quant_lsystem import TryHardQuantLSystemEngine

ROOT = Path(__file__).resolve().parent
STRATEGY_OUTPUT = ROOT / "last_quant_strategy.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="TryHard quant L-System strategy step")
    parser.add_argument(
        "--context",
        default="BTC testing 63120 blue support; ribbon +2 reclaim; post-dump base.",
        help="Raw market intuition passed to Grok / offline fallback",
    )
    parser.add_argument("--watermark", default="gflbsdragon")
    parser.add_argument("--instrument", default="BTC")
    parser.add_argument(
        "--harvest-fact",
        default="",
        help="Optional 48-72hr sync observation to log via harvest_structured_fact",
    )
    parser.add_argument(
        "--ignition",
        action="store_true",
        help="Orchestrator mode: satisfy coherence gate for pipeline smoke tests",
    )
    parser.add_argument(
        "--require-coherence",
        action="store_true",
        help="Fail if coherence-time < FORGE_MIN_COHERENCE_SEC (production deploy)",
    )
    args = parser.parse_args()

    profile_name, profile_block = get_active_profile()
    regime_metrics = {
        "trend": profile_name,
        "instrument": args.instrument,
        "timeframe_profile": profile_name,
        "session_context": profile_block.splitlines()[0],
        "market_context": args.context,
    }

    engine = TryHardQuantLSystemEngine()
    if args.ignition:
        engine.coherence_start = time.time() - 301

    if args.require_coherence and not engine.coherence_ready():
        print(
            f"ABORT: coherence_time={engine.agent_state.coherence_time:.0f}s "
            f"< {engine.min_coherence_seconds}s required"
        )
        return 1

    print("=== Step 6: Quant L-System Strategy ===")
    print(f"Profile: {profile_name} | Watermark base: {args.watermark}")

    strategy = engine.generate_strategy(
        raw_intuition=args.context,
        regime_metrics=regime_metrics,
        base_watermark=args.watermark,
    )

    payload = {
        "strategy": strategy.model_dump(),
        "coherence_ready": engine.coherence_ready(),
        "coherence_time_sec": round(engine.agent_state.coherence_time, 2),
        "evolved_watermark": engine.agent_state.watermark_evolved,
        "agent_state": {
            "steellarc": engine.agent_state.steellarc,
            "aureostyle": engine.agent_state.aureostyle,
            "aureostellarc": engine.agent_state.aureostellarc,
        },
        "backend": "grok" if engine.api_key else "offline_fallback",
    }

    if args.harvest_fact:
        payload["harvested_fact"] = engine.harvest_structured_fact(
            args.harvest_fact,
            window_hours=72,
        )
    elif args.ignition:
        payload["harvested_fact"] = engine.harvest_structured_fact(
            f"Ignition sync: {args.context[:120]}",
            window_hours=72,
        )

    STRATEGY_OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(strategy.model_dump_json(indent=2))
    print(f"\nWrote {STRATEGY_OUTPUT}")
    print(f"Coherence ready: {payload['coherence_ready']} | Backend: {payload['backend']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())