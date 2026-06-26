#!/usr/bin/env python3
"""18-day Mercury recirculating memory tank — delay-line resonance matching."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np

ROOT = Path(__file__).resolve().parent
TANK_STORE = ROOT / "memory_tanks.json"
PREDICTION_LOG = ROOT / "prediction_log.jsonl"
PREDICTOR_STATE = ROOT / "predictor_state.json"

Direction = Literal["UP", "DOWN", "FLAT"]


def _feature_vector(waveform_stats: dict, tas_distribution: dict) -> np.ndarray:
    return np.array(
        [
            waveform_stats.get("mean_force", 0.0),
            waveform_stats.get("max_amplitude", 0.0),
            waveform_stats.get("resonance_score", 0.0),
            tas_distribution.get("exploration_pct", 0.0),
            tas_distribution.get("reinforcement_pct", 0.0),
            tas_distribution.get("stabilization_pct", 0.0),
        ],
        dtype=np.float64,
    )


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot_prod = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_prod / (norm_a * norm_b)


def _crr_up_ratio(crr_paths: list | None) -> float:
    if not crr_paths:
        return 0.5
    vals = [float(x) for x in crr_paths]
    return sum(vals) / len(vals) if vals else 0.5


def _prob_to_direction(prob: float, *, up_thresh: float = 0.55, down_thresh: float = 0.45) -> Direction:
    if prob >= up_thresh:
        return "UP"
    if prob <= down_thresh:
        return "DOWN"
    return "FLAT"


def _normalize_outcomes(outcomes: dict) -> dict:
    """Unify legacy next_candle_up_probability with explicit 1d/2d labels."""
    p1 = outcomes.get("actual_1d_up_prob")
    if p1 is None:
        p1 = outcomes.get("next_candle_up_probability", 0.5)
    p2 = outcomes.get("actual_2d_up_prob")
    if p2 is None:
        p2 = float(p1) * 0.85 + 0.075

    d1 = outcomes.get("direction_1d") or _prob_to_direction(float(p1))
    d2 = outcomes.get("direction_2d") or _prob_to_direction(float(p2), up_thresh=0.52, down_thresh=0.48)
    mag1 = outcomes.get("magnitude_1d_pct")
    if mag1 is None:
        mag1 = abs(float(p1) - 0.5) * 2.0
    mag2 = outcomes.get("magnitude_2d_pct")
    if mag2 is None:
        mag2 = abs(float(p2) - 0.5) * 1.8

    return {
        "up_probability_1d": round(float(p1), 4),
        "up_probability_2d": round(float(p2), 4),
        "direction_1d": d1,
        "direction_2d": d2,
        "magnitude_1d_pct": round(float(mag1), 4),
        "magnitude_2d_pct": round(float(mag2), 4),
    }


class PredictionEngine:
    """UNIVAC-style ensemble predictor over 18-day memory tanks."""

    def __init__(
        self,
        tank_system: "EighteenDayMemoryTankSystem",
        *,
        top_n: int = 5,
        anomaly_threshold: float = 0.82,
        action_confidence: float = 0.75,
        log_path: Path = PREDICTION_LOG,
    ):
        self.tank_system = tank_system
        self.top_n = top_n
        self.anomaly_threshold = anomaly_threshold
        self.action_confidence = action_confidence
        self.log_path = log_path
        self._load_state()

    def _load_state(self) -> None:
        if PREDICTOR_STATE.exists():
            state = json.loads(PREDICTOR_STATE.read_text(encoding="utf-8"))
            self.top_n = int(state.get("top_n", self.top_n))
            self.anomaly_threshold = float(state.get("anomaly_threshold", self.anomaly_threshold))
            self.action_confidence = float(state.get("action_confidence", self.action_confidence))

    def predict_at_cycle_open(
        self,
        cycle_tank_id: str,
        current_waveform_stats: dict,
        current_tas_dist: dict | None = None,
        current_crr_paths: list | None = None,
    ) -> dict:
        """Log a cycle-open forecast linked to a tank ID for later training resolution."""
        result = self.predict_1_to_2_days_ahead(
            current_waveform_stats, current_tas_dist, current_crr_paths
        )
        if result.get("prediction_id") and self.log_path.exists():
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
            if lines:
                row = json.loads(lines[-1])
                if row.get("prediction_id") == result["prediction_id"]:
                    row["cycle_tank_id"] = cycle_tank_id
                    row["cycle_phase"] = "open"
                    lines[-1] = json.dumps(row)
                    self.log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return result

    def _weighted_ensemble(
        self,
        similar: list[tuple[str, float, dict, dict]],
        horizon: Literal["1d", "2d"],
        current_crr: list | None,
    ) -> dict:
        prob_key = f"up_probability_{horizon}"
        mag_key = f"magnitude_{horizon}_pct"
        dir_key = f"direction_{horizon}"

        weighted_prob = 0.0
        weighted_mag = 0.0
        weight_total = 0.0
        direction_votes: dict[Direction, float] = {"UP": 0.0, "DOWN": 0.0, "FLAT": 0.0}

        current_crr_ratio = _crr_up_ratio(current_crr)

        for _tid, similarity, outcomes, tank_meta in similar:
            norm = _normalize_outcomes(outcomes)
            base_weight = max(similarity, 0.0001) ** 2

            tank_crr = tank_meta.get("crr_paths")
            crr_align = 1.0 - abs(current_crr_ratio - _crr_up_ratio(tank_crr))
            crr_boost = 1.0 + (0.25 * crr_align) if current_crr else 1.0

            tas = tank_meta.get("tas_distribution") or {}
            stab = float(tas.get("stabilization_pct", 0.33))
            tas_boost = 1.0 + (0.15 * stab)

            weight = base_weight * crr_boost * tas_boost
            prob = norm[prob_key]
            direction = norm[dir_key]

            weighted_prob += prob * weight
            weighted_mag += norm[mag_key] * weight
            direction_votes[direction] += weight
            weight_total += weight

        if weight_total <= 0:
            return {
                "up_probability": 0.5,
                "direction": "FLAT",
                "magnitude_pct": 0.0,
                "confidence": 0.0,
            }

        up_prob = weighted_prob / weight_total
        magnitude = weighted_mag / weight_total
        vote_total = sum(direction_votes.values())
        direction = max(direction_votes, key=direction_votes.get)
        vote_share = direction_votes[direction] / vote_total if vote_total else 0.0

        if vote_share < 0.45:
            direction = _prob_to_direction(up_prob)
        elif direction == "FLAT":
            direction = _prob_to_direction(up_prob)

        top_sim = similar[0][1] if similar else 0.0
        agreement = direction_votes[direction] / weight_total
        confidence = min(1.0, top_sim * (0.55 + 0.45 * agreement))

        return {
            "up_probability": round(up_prob, 4),
            "direction": direction,
            "magnitude_pct": round(magnitude, 4),
            "confidence": round(confidence, 4),
        }

    def predict_1_to_2_days_ahead(
        self,
        current_waveform_stats: dict,
        current_tas_dist: dict | None = None,
        current_crr_paths: list | None = None,
        *,
        log: bool = True,
    ) -> dict:
        """
        Ensemble 1–2 day directional bias from resonant ancestor tanks.

        Agents act when confidence > 0.75 and direction is not FLAT.
        """
        tas = current_tas_dist or {
            "exploration_pct": 0.33,
            "reinforcement_pct": 0.34,
            "stabilization_pct": 0.33,
        }

        if not self.tank_system.tanks:
            return {
                "prediction_id": None,
                "direction": "FLAT",
                "direction_1d": "FLAT",
                "direction_2d": "FLAT",
                "confidence": 0.0,
                "confidence_1d": 0.0,
                "confidence_2d": 0.0,
                "up_probability_1d": 0.5,
                "up_probability_2d": 0.5,
                "magnitude_1d_pct": 0.0,
                "magnitude_2d_pct": 0.0,
                "resonance": 0.0,
                "ancestor_tanks": [],
                "anomaly": {"anomaly_detected": False, "reason": "No tanks — learning phase."},
                "crr_alignment": 0.0,
                "action_threshold_met": False,
                "engine": "ensemble_v1",
            }

        raw_matches = self.tank_system.find_similar_tanks(
            current_waveform_stats, tas, top_n=self.top_n
        )
        similar = [
            (tid, sim, outcomes, self.tank_system.tanks[tid])
            for tid, sim, outcomes in raw_matches
        ]

        anomaly = self.tank_system.detect_anomaly(
            current_waveform_stats, tas, anomaly_threshold=self.anomaly_threshold
        )
        h1 = self._weighted_ensemble(similar, "1d", current_crr_paths)
        h2 = self._weighted_ensemble(similar, "2d", current_crr_paths)

        if anomaly.get("anomaly_detected"):
            h1["confidence"] = round(h1["confidence"] * 0.55, 4)
            h2["confidence"] = round(h2["confidence"] * 0.55, 4)

        top_resonance = similar[0][1] if similar else 0.0
        crr_alignment = 0.0
        if current_crr_paths and similar:
            crr_alignment = round(
                1.0 - abs(_crr_up_ratio(current_crr_paths) - _crr_up_ratio(similar[0][3].get("crr_paths"))),
                4,
            )

        primary_conf = h1["confidence"]
        action_met = (
            primary_conf >= self.action_confidence
            and h1["direction"] != "FLAT"
            and not anomaly.get("anomaly_detected", False)
        )

        prediction_id = str(uuid.uuid4())
        result = {
            "prediction_id": prediction_id,
            "direction": h1["direction"],
            "direction_1d": h1["direction"],
            "direction_2d": h2["direction"],
            "confidence": primary_conf,
            "confidence_1d": h1["confidence"],
            "confidence_2d": h2["confidence"],
            "up_probability_1d": h1["up_probability"],
            "up_probability_2d": h2["up_probability"],
            "magnitude_1d_pct": h1["magnitude_pct"],
            "magnitude_2d_pct": h2["magnitude_pct"],
            "resonance": round(top_resonance, 4),
            "ancestor_tanks": [
                {"tank_id": tid, "resonance": round(sim, 4)} for tid, sim, _, _ in similar
            ],
            "anomaly": anomaly,
            "crr_alignment": crr_alignment,
            "action_threshold_met": action_met,
            "engine": "ensemble_v1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if log:
            self._log_prediction(result, current_waveform_stats, tas, current_crr_paths)
        return result

    def _log_prediction(
        self,
        prediction: dict,
        waveform_stats: dict,
        tas_dist: dict,
        crr_paths: list | None,
    ) -> None:
        entry = {
            "prediction_id": prediction["prediction_id"],
            "timestamp": prediction["timestamp"],
            "predicted": {
                "direction_1d": prediction["direction_1d"],
                "direction_2d": prediction["direction_2d"],
                "confidence_1d": prediction["confidence_1d"],
                "confidence_2d": prediction["confidence_2d"],
            },
            "features": {
                "waveform_stats": waveform_stats,
                "tas_distribution": tas_dist,
                "crr_paths": crr_paths,
            },
            "actual": None,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def record_actual_outcome(self, prediction_id: str, actual_outcomes: dict) -> bool:
        """Attach realized 1d/2d outcomes to a logged prediction for training feedback."""
        if not self.log_path.exists():
            return False

        norm_actual = _normalize_outcomes(actual_outcomes)
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        updated = False
        out_lines: list[str] = []

        for line in lines:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("prediction_id") == prediction_id:
                row["actual"] = norm_actual
                row["resolved_at"] = datetime.now(timezone.utc).isoformat()
                row["correct_1d"] = row["predicted"]["direction_1d"] == norm_actual["direction_1d"]
                row["correct_2d"] = row["predicted"]["direction_2d"] == norm_actual["direction_2d"]
                updated = True
            out_lines.append(json.dumps(row))

        if updated:
            self.log_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        return updated

    def training_accuracy_report(self) -> dict:
        """Rolling accuracy from resolved predictions in prediction_log.jsonl."""
        if not self.log_path.exists():
            return {"resolved": 0, "accuracy_1d": None, "accuracy_2d": None}

        resolved = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("actual") is not None:
                resolved.append(row)

        if not resolved:
            return {"resolved": 0, "accuracy_1d": None, "accuracy_2d": None}

        acc_1d = sum(1 for r in resolved if r.get("correct_1d")) / len(resolved)
        acc_2d = sum(1 for r in resolved if r.get("correct_2d")) / len(resolved)
        high_conf = [r for r in resolved if r["predicted"]["confidence_1d"] >= self.action_confidence]
        high_conf_acc = None
        if high_conf:
            high_conf_acc = sum(1 for r in high_conf if r.get("correct_1d")) / len(high_conf)

        return {
            "resolved": len(resolved),
            "accuracy_1d": round(acc_1d, 4),
            "accuracy_2d": round(acc_2d, 4),
            "high_confidence_count": len(high_conf),
            "high_confidence_accuracy_1d": (
                round(high_conf_acc, 4) if high_conf_acc is not None else None
            ),
        }


class EighteenDayMemoryTankSystem:
    def __init__(self, max_tanks: int = 20, cycle_days: int = 18):
        self.max_tanks = max_tanks
        self.cycle_days = cycle_days
        self.tanks: dict[str, dict] = {}
        self._predictor: PredictionEngine | None = None

    @property
    def predictor(self) -> PredictionEngine:
        if self._predictor is None:
            self._predictor = PredictionEngine(self)
        return self._predictor

    def create_tank_from_seismograph(
        self,
        tank_id: str,
        waveform_stats: dict,
        tas_distribution: dict,
        crr_paths: list,
        outcomes: dict,
        *,
        quiet: bool = False,
        train_on_complete: bool = False,
    ) -> dict:
        """Ingest a completed 18-day market cycle into the recirculating memory cavity."""
        feature_vector = _feature_vector(waveform_stats, tas_distribution)

        tank_node = {
            "tank_id": tank_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_vector": feature_vector.tolist(),
            "crr_paths": crr_paths,
            "outcomes": outcomes,
            "meta": {
                "waveform_stats": waveform_stats,
                "tas_distribution": tas_distribution,
            },
        }

        if len(self.tanks) >= self.max_tanks:
            oldest_key = min(self.tanks.keys(), key=lambda k: self.tanks[k]["timestamp"])
            del self.tanks[oldest_key]
            if not quiet:
                print(f"[RECIRCULATION] Max tank limit reached. Pruned oldest cavity: {oldest_key}")

        self.tanks[tank_id] = tank_node
        if not quiet:
            print(f"[TANK ENGINE] Composed 18-Day Memory Tank '{tank_id}' into active lattice.")

        if train_on_complete:
            from prediction_training_loop import PredictionTrainingLoop

            trainer = PredictionTrainingLoop(self)
            training_report = trainer.on_tank_completed(
                tank_id=tank_id,
                waveform_stats=waveform_stats,
                tas_distribution=tas_distribution,
                crr_paths=crr_paths,
                outcomes=outcomes,
            )
            tank_node["training_report"] = training_report

        return tank_node

    def find_similar_tanks(
        self,
        current_waveform_stats: dict,
        current_tas_dist: dict,
        top_n: int = 3,
    ) -> list[tuple[str, float, dict]]:
        """Resonance matching via normalized cosine similarity."""
        if not self.tanks:
            return []

        target_vector = _feature_vector(current_waveform_stats, current_tas_dist)
        rankings: list[tuple[str, float, dict]] = []

        for tank_id, tank in self.tanks.items():
            tank_vector = np.array(tank["feature_vector"], dtype=np.float64)
            similarity = _cosine_similarity(target_vector, tank_vector)
            # Penalize opposite signed mean_force — prevents bull/bear cross-resonance
            if target_vector[0] * tank_vector[0] < 0:
                if abs(target_vector[0]) > 2.0 and abs(tank_vector[0]) > 2.0:
                    similarity *= 0.30
            rankings.append((tank_id, similarity, tank["outcomes"]))

        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings[:top_n]

    def detect_anomaly(
        self,
        current_waveform_stats: dict,
        current_tas_dist: dict,
        anomaly_threshold: float = 0.82,
    ) -> dict:
        """Flag novel regimes when signature matching falls below threshold."""
        matches = self.find_similar_tanks(current_waveform_stats, current_tas_dist, top_n=1)
        if not matches:
            return {
                "anomaly_detected": False,
                "confidence": 1.0,
                "reason": "System learning phase initialized.",
            }

        highest_resonance = matches[0][1]
        is_anomaly = highest_resonance < anomaly_threshold

        return {
            "anomaly_detected": is_anomaly,
            "highest_historical_resonance": round(highest_resonance, 4),
            "closest_ancestor_tank": matches[0][0],
            "action_posture": (
                "CAUTIOUS_CAPITAL_PROTECTION" if is_anomaly else "NORMAL_EXECUTION"
            ),
        }

    def get_long_horizon_prediction(
        self,
        current_waveform_stats: dict,
        current_tas_dist: dict,
    ) -> float:
        """Weighted ensemble prediction from historical ancestor outcomes."""
        similar_tanks = self.find_similar_tanks(current_waveform_stats, current_tas_dist, top_n=3)
        if not similar_tanks:
            return 0.5

        weighted_p_sum = 0.0
        weight_total = 0.0

        for _tank_id, similarity, outcomes in similar_tanks:
            weight = max(similarity, 0.0001)
            next_candle_probability = outcomes.get("next_candle_up_probability", 0.5)
            weighted_p_sum += next_candle_probability * weight
            weight_total += weight

        return round(weighted_p_sum / weight_total, 4) if weight_total > 0 else 0.5

    def predict_1_to_2_days_ahead(
        self,
        current_waveform_stats: dict,
        current_tas_dist: dict | None = None,
        current_crr_paths: list | None = None,
        *,
        log: bool = True,
    ) -> dict:
        """Delegate to PredictionEngine — primary agent-facing forecast API."""
        return self.predictor.predict_1_to_2_days_ahead(
            current_waveform_stats,
            current_tas_dist,
            current_crr_paths,
            log=log,
        )

    def save(self, path: Path = TANK_STORE) -> None:
        path.write_text(json.dumps(self.tanks, indent=2), encoding="utf-8")

    def load(self, path: Path = TANK_STORE) -> int:
        if not path.exists():
            return 0
        self.tanks = json.loads(path.read_text(encoding="utf-8"))
        return len(self.tanks)

    def query_context(
        self,
        current_waveform_stats: dict,
        current_tas_dist: dict,
    ) -> dict:
        """Single-call bundle for orchestrator / agent injection."""
        matches = self.find_similar_tanks(current_waveform_stats, current_tas_dist)
        anomaly = self.detect_anomaly(current_waveform_stats, current_tas_dist)
        ensemble_p = self.get_long_horizon_prediction(current_waveform_stats, current_tas_dist)
        forecast = self.predict_1_to_2_days_ahead(current_waveform_stats, current_tas_dist)
        return {
            "tank_count": len(self.tanks),
            "top_matches": [
                {"tank_id": tid, "resonance": round(sim, 4)} for tid, sim, _ in matches
            ],
            "anomaly": anomaly,
            "ensemble_up_probability": ensemble_p,
            "forecast_1_2d": forecast,
            "training_accuracy": self.predictor.training_accuracy_report(),
        }


if __name__ == "__main__":
    print("[INIT] Verifying 18-Day Delay-Line Tank Infrastructure...")
    system = EighteenDayMemoryTankSystem()

    system.create_tank_from_seismograph(
        tank_id="TANK_01_BULL_STABILIZED",
        waveform_stats={"mean_force": 12.4, "max_amplitude": 45.2, "resonance_score": 0.88},
        tas_distribution={
            "exploration_pct": 0.20,
            "reinforcement_pct": 0.30,
            "stabilization_pct": 0.50,
        },
        crr_paths=[1, 1, 0, 1],
        outcomes={"next_candle_up_probability": 0.68},
    )

    current_metrics = {
        "mean_force": 11.9,
        "max_amplitude": 42.1,
        "resonance_score": 0.85,
    }
    current_tas = {
        "exploration_pct": 0.22,
        "reinforcement_pct": 0.28,
        "stabilization_pct": 0.50,
    }

    resonance = system.find_similar_tanks(current_metrics, current_tas)
    anomaly_status = system.detect_anomaly(current_metrics, current_tas)
    ensemble_p = system.get_long_horizon_prediction(current_metrics, current_tas)
    prediction = system.predict_1_to_2_days_ahead(
        current_metrics,
        current_tas,
        current_crr_paths=[1, 1, 0, 1, 1],
    )

    print(f"\n[METRICS] Best Resonance Match: {resonance[0][0]} with coefficient {resonance[0][1]:.4f}")
    print(f"[METRICS] Anomaly Diagnostics: {json.dumps(anomaly_status)}")
    print(f"[METRICS] Multi-Tank Ensemble Up-Probability: {ensemble_p * 100:.1f}%")
    print(f"[UNIVAC] 1-2 Day Forecast: {json.dumps(prediction, indent=2)}")