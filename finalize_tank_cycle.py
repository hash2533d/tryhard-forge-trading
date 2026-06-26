#!/usr/bin/env python3
"""
Seal a completed 18-day Mercury tank and run prediction training feedback.

Use at end of each 18-day cycle when waveform + TAS + CRR + realized outcomes are known.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eighteen_day_memory_tank import EighteenDayMemoryTankSystem, TANK_STORE

ROOT = Path(__file__).resolve().parent


def load_spec(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finalize(spec: dict, *, quiet: bool = False) -> dict:
    required = ("tank_id", "waveform_stats", "tas_distribution", "outcomes")
    missing = [k for k in required if k not in spec]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    system = EighteenDayMemoryTankSystem()
    system.load()

    tank_node = system.create_tank_from_seismograph(
        tank_id=spec["tank_id"],
        waveform_stats=spec["waveform_stats"],
        tas_distribution=spec["tas_distribution"],
        crr_paths=spec.get("crr_paths", []),
        outcomes=spec["outcomes"],
        quiet=quiet,
        train_on_complete=True,
    )
    system.save(TANK_STORE)

    return {
        "tank_id": spec["tank_id"],
        "tank_count": len(system.tanks),
        "training_report": tank_node.get("training_report", {}),
        "saved_to": str(TANK_STORE),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize 18-day tank + train predictor")
    parser.add_argument("--spec", type=Path, help="JSON spec file (see regime_library/tank_completion.example.json)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not args.spec:
        print("Usage: python finalize_tank_cycle.py --spec regime_library/tank_completion.example.json")
        return 1

    if not args.spec.exists():
        print(f"Spec not found: {args.spec}", file=sys.stderr)
        return 1

    result = finalize(load_spec(args.spec), quiet=args.quiet)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())