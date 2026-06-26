#!/usr/bin/env python3
"""
Prediction training loop — resolves forecasts vs realized tank outcomes,
replays leave-one-out on real tanks, and auto-tunes ensemble weights.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from eighteen_day_memory_tank import (
    PREDICTION_LOG,
    PREDICTOR_STATE,
    TANK_STORE,
    EighteenDayMemoryTankSystem,
    PredictionEngine,
    _cosine_similarity,
    _feature_vector,
    _normalize_outcomes,
)

ROOT = Path(__file__).resolve().parent
TRAINING_REPORT = ROOT / "prediction_training_report.json"

DEFAULT_STATE = {
    "top_n": 5,
    "anomaly_threshold": 0.82,
    "action_confidence": 0.75,
    "tune_history": [],
}


class PredictionTrainingLoop:
    def __init__(
        self,
        tank_system: EighteenDayMemoryTankSystem | None = None,
        *,
        log_path: Path = PREDICTION_LOG,
        state_path: Path = PREDICTOR_STATE,
        report_path: Path = TRAINING_REPORT,
    ):
        self.tank_system = tank_system or EighteenDayMemoryTankSystem()
        self.tank_system.load()
        self.log_path = log_path
        self.state_path = state_path
        self.report_path = report_path
        self.predictor = PredictionEngine(self.tank_system, log_path=log_path)

    def _read_log(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        rows = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def _write_log(self, rows: list[dict]) -> None:
        if not rows:
            return
        self.log_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def _feature_similarity(self, features_a: dict, features_b: dict) -> float:
        wf_a = features_a.get("waveform_stats", {})
        tas_a = features_a.get("tas_distribution", {})
        wf_b = features_b.get("waveform_stats", {})
        tas_b = features_b.get("tas_distribution", {})
        vec_a = _feature_vector(wf_a, tas_a)
        vec_b = _feature_vector(wf_b, tas_b)
        return _cosine_similarity(vec_a, vec_b)

    def resolve_by_tank_id(self, tank_id: str, outcomes: dict) -> int:
        """Resolve open predictions tagged with cycle_tank_id."""
        rows = self._read_log()
        norm = _normalize_outcomes(outcomes)
        resolved = 0

        for row in rows:
            if row.get("actual") is not None:
                continue
            if row.get("cycle_tank_id") != tank_id:
                continue
            row["actual"] = norm
            row["resolved_at"] = datetime.now(timezone.utc).isoformat()
            row["resolved_via"] = "cycle_tank_id"
            row["correct_1d"] = row["predicted"]["direction_1d"] == norm["direction_1d"]
            row["correct_2d"] = row["predicted"]["direction_2d"] == norm["direction_2d"]
            resolved += 1

        if resolved:
            self._write_log(rows)
        return resolved

    def resolve_by_feature_match(
        self,
        waveform_stats: dict,
        tas_distribution: dict,
        outcomes: dict,
        *,
        min_similarity: float = 0.97,
    ) -> int:
        """Resolve the single best orphan prediction matching a completed tank."""
        rows = self._read_log()
        norm = _normalize_outcomes(outcomes)
        target = {
            "waveform_stats": waveform_stats,
            "tas_distribution": tas_distribution,
        }

        best_idx: int | None = None
        best_sim = 0.0
        for i, row in enumerate(rows):
            if row.get("actual") is not None:
                continue
            sim = self._feature_similarity(row.get("features", {}), target)
            if sim >= min_similarity and sim > best_sim:
                best_sim = sim
                best_idx = i

        if best_idx is None:
            return 0

        row = rows[best_idx]
        row["actual"] = norm
        row["resolved_at"] = datetime.now(timezone.utc).isoformat()
        row["resolved_via"] = "feature_match"
        row["feature_match_similarity"] = round(best_sim, 4)
        row["correct_1d"] = row["predicted"]["direction_1d"] == norm["direction_1d"]
        row["correct_2d"] = row["predicted"]["direction_2d"] == norm["direction_2d"]
        self._write_log(rows)
        return 1

    def replay_on_real_tanks(self) -> dict:
        """Chronological leave-one-out on memory_tanks.json (no synthetic data)."""
        tanks = sorted(
            self.tank_system.tanks.items(),
            key=lambda kv: kv[1].get("timestamp", ""),
        )
        if len(tanks) < 2:
            return {
                "mode": "real_tank_replay",
                "tank_count": len(tanks),
                "folds": 0,
                "accuracy_1d": None,
                "accuracy_2d": None,
                "note": "Need ≥2 completed tanks for replay.",
            }

        folds: list[dict] = []
        for holdout_id, holdout in tanks:
            train_system = EighteenDayMemoryTankSystem(max_tanks=self.tank_system.max_tanks)
            for tid, tank in tanks:
                if tid == holdout_id:
                    continue
                train_system.create_tank_from_seismograph(
                    tank_id=tid,
                    waveform_stats=tank["meta"]["waveform_stats"],
                    tas_distribution=tank["meta"]["tas_distribution"],
                    crr_paths=tank.get("crr_paths", []),
                    outcomes=tank["outcomes"],
                    quiet=True,
                )

            engine = PredictionEngine(train_system)
            meta = holdout["meta"]
            pred = engine.predict_1_to_2_days_ahead(
                meta["waveform_stats"],
                meta["tas_distribution"],
                holdout.get("crr_paths"),
                log=False,
            )
            actual = _normalize_outcomes(holdout["outcomes"])
            folds.append({
                "holdout_tank": holdout_id,
                "predicted_1d": pred["direction_1d"],
                "predicted_2d": pred["direction_2d"],
                "actual_1d": actual["direction_1d"],
                "actual_2d": actual["direction_2d"],
                "confidence_1d": pred["confidence_1d"],
                "correct_1d": pred["direction_1d"] == actual["direction_1d"],
                "correct_2d": pred["direction_2d"] == actual["direction_2d"],
            })

        n = len(folds)
        acc_1d = sum(1 for f in folds if f["correct_1d"]) / n
        acc_2d = sum(1 for f in folds if f["correct_2d"]) / n
        return {
            "mode": "real_tank_replay",
            "tank_count": len(tanks),
            "folds": n,
            "accuracy_1d": round(acc_1d, 4),
            "accuracy_2d": round(acc_2d, 4),
            "fold_details": folds,
        }

    def maybe_tune_weights(self, accuracy_report: dict) -> dict:
        """Simple auto-tune: expand top_n when accuracy lags, hold when strong."""
        state = DEFAULT_STATE.copy()
        if self.state_path.exists():
            state.update(json.loads(self.state_path.read_text(encoding="utf-8")))

        resolved = accuracy_report.get("resolved", 0)
        acc_1d = accuracy_report.get("accuracy_1d")
        changed = False
        tune_note = "no_change"

        if resolved >= 5 and acc_1d is not None:
            if acc_1d < 0.55 and state["top_n"] < 8:
                state["top_n"] += 1
                tune_note = "increased_top_n_low_accuracy"
                changed = True
            elif acc_1d >= 0.80 and state["top_n"] > 3:
                state["top_n"] -= 1
                tune_note = "decreased_top_n_high_accuracy"
                changed = True

        state["last_accuracy_1d"] = acc_1d
        state["last_resolved"] = resolved
        state["last_tuned_at"] = datetime.now(timezone.utc).isoformat()
        state["tune_history"] = (state.get("tune_history") or [])[-19:] + [{
            "at": state["last_tuned_at"],
            "note": tune_note,
            "top_n": state["top_n"],
            "accuracy_1d": acc_1d,
            "resolved": resolved,
        }]

        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        if changed:
            self.predictor._load_state()

        return {"changed": changed, "note": tune_note, "state": state}

    def on_tank_completed(
        self,
        tank_id: str,
        waveform_stats: dict,
        tas_distribution: dict,
        crr_paths: list,
        outcomes: dict,
    ) -> dict:
        """Training tick when a new 18-day tank is sealed."""
        by_id = self.resolve_by_tank_id(tank_id, outcomes)
        by_feat = self.resolve_by_feature_match(waveform_stats, tas_distribution, outcomes)
        log_accuracy = self.predictor.training_accuracy_report()
        replay = self.replay_on_real_tanks()
        tune = self.maybe_tune_weights(log_accuracy)

        return {
            "tank_id": tank_id,
            "resolved_by_tank_id": by_id,
            "resolved_by_feature_match": by_feat,
            "log_accuracy": log_accuracy,
            "real_tank_replay": replay,
            "tune": tune,
        }

    def run(self) -> dict:
        """Full training sync for cursor_training_loop."""
        log_accuracy = self.predictor.training_accuracy_report()
        replay = self.replay_on_real_tanks()
        tune = self.maybe_tune_weights(log_accuracy)
        pending = sum(1 for r in self._read_log() if r.get("actual") is None)

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tank_count": len(self.tank_system.tanks),
            "pending_predictions": pending,
            "log_accuracy": log_accuracy,
            "real_tank_replay": replay,
            "predictor_state": tune["state"],
            "last_tune": tune,
            "univac_ready": (
                log_accuracy.get("accuracy_1d") is not None
                and log_accuracy["accuracy_1d"] >= 0.75
                and log_accuracy.get("resolved", 0) >= 5
            ),
        }
        self.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prediction training loop")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()

    trainer = PredictionTrainingLoop()

    if args.replay_only:
        report = trainer.replay_on_real_tanks()
    elif args.resolve_only:
        pending = trainer._read_log()
        resolved = sum(1 for r in pending if r.get("actual") is not None)
        report = {"pending_before": len(pending) - resolved, "note": "Use finalize_tank_cycle.py to resolve"}
    else:
        report = trainer.run()

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())