#!/usr/bin/env python3
"""18-day Mercury recirculating memory tank — delay-line resonance matching."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
TANK_STORE = ROOT / "memory_tanks.json"


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


class EighteenDayMemoryTankSystem:
    def __init__(self, max_tanks: int = 20, cycle_days: int = 18):
        self.max_tanks = max_tanks
        self.cycle_days = cycle_days
        self.tanks: dict[str, dict] = {}

    def create_tank_from_seismograph(
        self,
        tank_id: str,
        waveform_stats: dict,
        tas_distribution: dict,
        crr_paths: list,
        outcomes: dict,
    ) -> None:
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
            print(f"[RECIRCULATION] Max tank limit reached. Pruned oldest cavity: {oldest_key}")

        self.tanks[tank_id] = tank_node
        print(f"[TANK ENGINE] Composed 18-Day Memory Tank '{tank_id}' into active lattice.")

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
        return {
            "tank_count": len(self.tanks),
            "top_matches": [
                {"tank_id": tid, "resonance": round(sim, 4)} for tid, sim, _ in matches
            ],
            "anomaly": anomaly,
            "ensemble_up_probability": ensemble_p,
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

    print(f"\n[METRICS] Best Resonance Match: {resonance[0][0]} with coefficient {resonance[0][1]:.4f}")
    print(f"[METRICS] Anomaly Diagnostics: {json.dumps(anomaly_status)}")
    print(f"[METRICS] Multi-Tank Ensemble Up-Probability: {ensemble_p * 100:.1f}%")