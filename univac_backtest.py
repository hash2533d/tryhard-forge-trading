#!/usr/bin/env python3
"""
Simulated UNIVAC first-run backtest — leave-one-out over synthetic memory tanks.

Seeds 10–15 labeled 18-day tanks, predicts each from the remaining corpus,
and reports 1d/2d directional accuracy + high-confidence hit rate.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from eighteen_day_memory_tank import EighteenDayMemoryTankSystem, PredictionEngine

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "univac_backtest_report.json"


def _synthetic_tank_specs(seed: int = 369) -> list[dict]:
    """Curated synthetic regimes — waveform clusters with known 1d/2d outcomes."""
    rng = random.Random(seed)
    regimes = [
        ("BULL_STABILIZED", {"mean_force": 12.0, "max_amplitude": 44.0, "resonance_score": 0.88},
         {"exploration_pct": 0.18, "reinforcement_pct": 0.30, "stabilization_pct": 0.52},
         "UP", "UP", 0.72, 0.68),
        ("BULL_REINFORCING", {"mean_force": 11.5, "max_amplitude": 40.0, "resonance_score": 0.84},
         {"exploration_pct": 0.22, "reinforcement_pct": 0.45, "stabilization_pct": 0.33},
         "UP", "UP", 0.65, 0.60),
        ("BEAR_STABILIZED", {"mean_force": -8.2, "max_amplitude": 38.0, "resonance_score": 0.86},
         {"exploration_pct": 0.20, "reinforcement_pct": 0.28, "stabilization_pct": 0.52},
         "DOWN", "DOWN", 0.28, 0.32),
        ("BEAR_EXPLORATION", {"mean_force": -6.5, "max_amplitude": 35.0, "resonance_score": 0.79},
         {"exploration_pct": 0.55, "reinforcement_pct": 0.25, "stabilization_pct": 0.20},
         "DOWN", "FLAT", 0.38, 0.48),
        ("RANGE_CHOP", {"mean_force": 1.2, "max_amplitude": 18.0, "resonance_score": 0.62},
         {"exploration_pct": 0.40, "reinforcement_pct": 0.35, "stabilization_pct": 0.25},
         "FLAT", "FLAT", 0.51, 0.50),
        ("VOL_EXPANSION_UP", {"mean_force": 15.8, "max_amplitude": 62.0, "resonance_score": 0.91},
         {"exploration_pct": 0.35, "reinforcement_pct": 0.40, "stabilization_pct": 0.25},
         "UP", "UP", 0.78, 0.74),
        ("VOL_EXPANSION_DOWN", {"mean_force": -14.1, "max_amplitude": 58.0, "resonance_score": 0.90},
         {"exploration_pct": 0.38, "reinforcement_pct": 0.37, "stabilization_pct": 0.25},
         "DOWN", "DOWN", 0.22, 0.26),
        ("LATE_CYCLE_TOP", {"mean_force": 9.0, "max_amplitude": 48.0, "resonance_score": 0.75},
         {"exploration_pct": 0.30, "reinforcement_pct": 0.35, "stabilization_pct": 0.35},
         "UP", "UP", 0.62, 0.58),
        ("LATE_CYCLE_BOTTOM", {"mean_force": -9.5, "max_amplitude": 46.0, "resonance_score": 0.77},
         {"exploration_pct": 0.28, "reinforcement_pct": 0.37, "stabilization_pct": 0.35},
         "DOWN", "DOWN", 0.38, 0.42),
        ("MERCURY_RETEST", {"mean_force": 5.5, "max_amplitude": 28.0, "resonance_score": 0.81},
         {"exploration_pct": 0.25, "reinforcement_pct": 0.35, "stabilization_pct": 0.40},
         "UP", "FLAT", 0.57, 0.52),
        ("FLUX_369_LOCK", {"mean_force": 13.2, "max_amplitude": 41.5, "resonance_score": 0.93},
         {"exploration_pct": 0.15, "reinforcement_pct": 0.33, "stabilization_pct": 0.52},
         "UP", "UP", 0.81, 0.76),
        ("TRITONE_ANOMALY", {"mean_force": 3.0, "max_amplitude": 55.0, "resonance_score": 0.55},
         {"exploration_pct": 0.50, "reinforcement_pct": 0.30, "stabilization_pct": 0.20},
         "FLAT", "DOWN", 0.49, 0.41),
        ("SWING_CONTINUATION", {"mean_force": 10.8, "max_amplitude": 36.0, "resonance_score": 0.83},
         {"exploration_pct": 0.20, "reinforcement_pct": 0.42, "stabilization_pct": 0.38},
         "UP", "UP", 0.70, 0.66),
        ("SWING_REVERSAL", {"mean_force": -7.8, "max_amplitude": 34.0, "resonance_score": 0.80},
         {"exploration_pct": 0.32, "reinforcement_pct": 0.38, "stabilization_pct": 0.30},
         "DOWN", "DOWN", 0.35, 0.38),
        ("SESSION_GAP_FILL", {"mean_force": 2.5, "max_amplitude": 22.0, "resonance_score": 0.70},
         {"exploration_pct": 0.45, "reinforcement_pct": 0.30, "stabilization_pct": 0.25},
         "FLAT", "FLAT", 0.51, 0.50),
    ]

    specs: list[dict] = []
    for idx, (name, wf, tas, d1, d2, p1, p2) in enumerate(regimes):
        wf_n = {
            k: round(
                v + rng.uniform(-0.25, 0.25) if k == "mean_force" else (
                    v + rng.uniform(-0.02, 0.02) if k == "resonance_score" else v + rng.uniform(-0.5, 0.5)
                ),
                2,
            )
            for k, v in wf.items()
        }
        tas_n = {k: round(max(0.05, v + rng.uniform(-0.04, 0.04)), 2) for k, v in tas.items()}
        total = sum(tas_n.values())
        tas_n = {k: round(v / total, 2) for k, v in tas_n.items()}

        crr_len = rng.randint(4, 8)
        crr_paths = [1 if rng.random() < p1 else 0 for _ in range(crr_len)]

        specs.append({
            "tank_id": f"TANK_SYN_{idx:02d}_{name}",
            "waveform_stats": wf_n,
            "tas_distribution": tas_n,
            "crr_paths": crr_paths,
            "outcomes": {
                "direction_1d": d1,
                "direction_2d": d2,
                "actual_1d_up_prob": p1,
                "actual_2d_up_prob": p2,
                "magnitude_1d_pct": abs(p1 - 0.5) * 2,
                "magnitude_2d_pct": abs(p2 - 0.5) * 1.8,
            },
        })
    return specs


def _seed_system(specs: list[dict]) -> EighteenDayMemoryTankSystem:
    system = EighteenDayMemoryTankSystem(max_tanks=25)
    for spec in specs:
        system.create_tank_from_seismograph(
            tank_id=spec["tank_id"],
            waveform_stats=spec["waveform_stats"],
            tas_distribution=spec["tas_distribution"],
            crr_paths=spec["crr_paths"],
            outcomes=spec["outcomes"],
            quiet=True,
        )
    return system


def run_leave_one_out(specs: list[dict], *, action_confidence: float = 0.75) -> dict:
    folds: list[dict] = []

    for holdout in specs:
        train_specs = [s for s in specs if s["tank_id"] != holdout["tank_id"]]
        system = _seed_system(train_specs)
        engine = PredictionEngine(system, action_confidence=action_confidence)

        pred = engine.predict_1_to_2_days_ahead(
            holdout["waveform_stats"],
            holdout["tas_distribution"],
            holdout["crr_paths"],
        )

        actual = holdout["outcomes"]
        folds.append({
            "holdout_tank": holdout["tank_id"],
            "predicted_1d": pred["direction_1d"],
            "predicted_2d": pred["direction_2d"],
            "actual_1d": actual["direction_1d"],
            "actual_2d": actual["direction_2d"],
            "confidence_1d": pred["confidence_1d"],
            "confidence_2d": pred["confidence_2d"],
            "resonance": pred["resonance"],
            "correct_1d": pred["direction_1d"] == actual["direction_1d"],
            "correct_2d": pred["direction_2d"] == actual["direction_2d"],
            "action_threshold_met": pred["action_threshold_met"],
        })

    n = len(folds)
    acc_1d = sum(1 for f in folds if f["correct_1d"]) / n
    acc_2d = sum(1 for f in folds if f["correct_2d"]) / n

    major_moves = [f for f in folds if f["actual_1d"] in ("UP", "DOWN")]
    major_acc = (
        sum(1 for f in major_moves if f["correct_1d"]) / len(major_moves) if major_moves else None
    )

    high_conf = [f for f in folds if f["confidence_1d"] >= action_confidence]
    high_conf_acc = (
        sum(1 for f in high_conf if f["correct_1d"]) / len(high_conf) if high_conf else None
    )

    univac_grade = "LEARNING_PHASE"
    if acc_1d >= 0.80 and (major_acc or 0) >= 0.85:
        univac_grade = "UNIVAC_FIRST_RUN"
    elif acc_1d >= 0.65:
        univac_grade = "APPROACHING_UNIVAC"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "leave_one_out_synthetic",
        "tank_count": n,
        "accuracy_1d": round(acc_1d, 4),
        "accuracy_2d": round(acc_2d, 4),
        "major_move_accuracy_1d": round(major_acc, 4) if major_acc is not None else None,
        "high_confidence_calls": len(high_conf),
        "high_confidence_accuracy_1d": (
            round(high_conf_acc, 4) if high_conf_acc is not None else None
        ),
        "univac_grade": univac_grade,
        "action_confidence_threshold": action_confidence,
        "folds": folds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="UNIVAC-style synthetic tank backtest")
    parser.add_argument("--seed", type=int, default=369)
    parser.add_argument("--confidence", type=float, default=0.75)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    specs = _synthetic_tank_specs(seed=args.seed)
    report = run_leave_one_out(specs, action_confidence=args.confidence)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== UNIVAC Synthetic Backtest (Leave-One-Out) ===")
    print(f"Tanks:           {report['tank_count']}")
    print(f"1d Accuracy:     {report['accuracy_1d'] * 100:.1f}%")
    print(f"2d Accuracy:     {report['accuracy_2d'] * 100:.1f}%")
    if report["major_move_accuracy_1d"] is not None:
        print(f"Major Moves 1d:  {report['major_move_accuracy_1d'] * 100:.1f}%")
    print(f"High-Conf Calls: {report['high_confidence_calls']}")
    if report["high_confidence_accuracy_1d"] is not None:
        print(f"High-Conf Acc:   {report['high_confidence_accuracy_1d'] * 100:.1f}%")
    print(f"Grade:           {report['univac_grade']}")
    print(f"Report:          {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())