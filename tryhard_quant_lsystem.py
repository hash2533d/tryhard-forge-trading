#!/usr/bin/env python3
"""Steellarc Trifecta + L-System watermark quant research engine."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
FACTS_LOG = ROOT / "structured_facts.jsonl"
GROK_MODEL = os.getenv("GFLBS_GROK_MODEL", "grok-4")
GROK_BASE_URL = "https://api.x.ai/v1"

SYSTEM_PROMPT = """You are the sovereign quantitative research layer of TryHard Forge.
Convert raw market intuition into precise, executable trading rules.
Return ONLY valid JSON matching the TryHardStrategySchema fields:
strategy_name, target_regime, indicators_and_settings, entry_rules, exit_rules,
stop_loss_ticks, take_profit_ticks, risk_reward_ratio, mathematical_edge,
evolved_watermark, agent_state.
Maintain 60° heart-coherent precision. No retail narrative."""


@dataclass
class AgentState:
    steellarc: str = "forged"
    aureostyle: str = "radiant"
    aureostellarc: str = "unified"
    coherence_time: float = 0.0
    watermark_evolved: str | None = None


class TryHardStrategySchema(BaseModel):
    strategy_name: str
    target_regime: str
    indicators_and_settings: dict[str, Any] = Field(default_factory=dict)
    entry_rules: str
    exit_rules: str
    stop_loss_ticks: int
    take_profit_ticks: int
    risk_reward_ratio: float
    mathematical_edge: str
    evolved_watermark: str
    agent_state: str


class LSystemWatermark:
    RULES: dict[str, str] = {
        "algocurator": "algocuratorφ1618heartcoherent",
        "whiterabbit": "whiterabbitdragonweavevoidprobe",
        "glassweave": "glassweave1618dualityprovenance",
        "metavigil": "metavigilφstructuredfactharvest",
        "steellarc": "steellarcφ1618aureostellarc",
        "gflbsdragon": "gflbsdragonφ1618volumeweave",
        "nakedpoc": "nakedpoc1618liquiditysweep",
        "coherencetime": "coherencetimeφ1618aureostellarc",
        "prismagent": "prismagentv4dragonforge",
    }

    def evolve(self, base: str) -> str:
        key = base.lower().strip()
        return self.RULES.get(key, f"{key}φ1618evolved")


class TryHardQuantLSystemEngine:
    def __init__(self) -> None:
        self.watermark_engine = LSystemWatermark()
        self.agent_state = AgentState()
        self.coherence_start = time.time()
        self.api_key = os.getenv("XAI_API_KEY", "").strip()
        self.min_coherence_seconds = float(os.getenv("FORGE_MIN_COHERENCE_SEC", "300"))

    def update_agent_state(self, new_state: str) -> None:
        if new_state in ("steellarc", "aureostyle", "aureostellarc"):
            setattr(self.agent_state, new_state, "active")
            self.agent_state.aureostellarc = "unified"
        self.agent_state.coherence_time = time.time() - self.coherence_start

    def coherence_ready(self) -> bool:
        return self.agent_state.coherence_time >= self.min_coherence_seconds

    def harvest_structured_fact(
        self,
        sync_observation: str,
        window_hours: int = 72,
    ) -> dict[str, Any]:
        """Harvest and log a structured fact from a 48-72hr sync window."""
        fact = {
            "timestamp": time.time(),
            "window_hours": window_hours,
            "observation": sync_observation,
            "watermark_triggered": self.agent_state.watermark_evolved,
            "coherence_time": round(self.agent_state.coherence_time, 2),
            "agent_state": asdict(self.agent_state),
            "actionable_upgrade": "Apply to Prism Agent V4 / novel coatings math",
        }
        with FACTS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fact) + "\n")
        print(f"[STRUCTURED FACT HARVESTED] {json.dumps(fact, indent=2)}")
        return fact

    def _offline_fallback(
        self,
        regime_metrics: dict[str, Any],
        evolved_wm: str,
    ) -> TryHardStrategySchema:
        return TryHardStrategySchema(
            strategy_name="GFLBS_DragonWeave_v4",
            target_regime=str(regime_metrics.get("trend", "Unknown")),
            indicators_and_settings={
                "DragonCurve": "L-system iter 4",
                "VolumeProfile": "Naked POC",
            },
            entry_rules="Enter on rejection at Naked POC with volume contraction.",
            exit_rules="Exit at opposing liquidity node or Coherence-Time drop.",
            stop_loss_ticks=14,
            take_profit_ticks=42,
            risk_reward_ratio=3.0,
            mathematical_edge="Exploits fractal locality and liquidity sweeps.",
            evolved_watermark=evolved_wm,
            agent_state=self.agent_state.aureostellarc,
        )

    def _call_grok(self, user_payload: str) -> dict[str, Any]:
        import httpx
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=GROK_BASE_URL,
            timeout=httpx.Timeout(120.0),
        )
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1200,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Grok returned empty strategy payload")
        return json.loads(content)

    def generate_strategy(
        self,
        raw_intuition: str,
        regime_metrics: dict[str, Any],
        base_watermark: str = "algocurator",
    ) -> TryHardStrategySchema:
        evolved_wm = self.watermark_engine.evolve(base_watermark)
        self.agent_state.watermark_evolved = evolved_wm
        self.update_agent_state("aureostellarc")

        user_payload = (
            f"RAW INTUITION: {raw_intuition}\n"
            f"REGIME METRICS: {json.dumps(regime_metrics, indent=2)}\n"
            f"EVOLVED WATERMARK: {evolved_wm}\n"
            f"AGENT STATE: {json.dumps(asdict(self.agent_state))}\n"
        )

        if not self.api_key:
            return self._offline_fallback(regime_metrics, evolved_wm)

        try:
            parsed = self._call_grok(user_payload)
            parsed.setdefault("evolved_watermark", evolved_wm)
            parsed.setdefault("agent_state", self.agent_state.aureostellarc)
            return TryHardStrategySchema.model_validate(parsed)
        except Exception as exc:
            fallback = self._offline_fallback(regime_metrics, evolved_wm)
            print(f"[GROK FALLBACK] {exc}")
            return fallback