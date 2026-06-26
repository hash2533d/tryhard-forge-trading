#!/usr/bin/env python3
"""
Grok production research + backtest context engine.

Injects ATM execution matrix (MES/ES Safe Adjust pyramid) into every alpha
generation call so live sessions reference exact bracket configurations.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from atm_rules import format_atm_context, load_atm_execution_bounds
from tryhard_quant_lsystem import TryHardQuantLSystemEngine, TryHardStrategySchema

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "last_research_report.json"


class ResearchAndBacktestEngine(TryHardQuantLSystemEngine):
    """Quant L-System engine with ATM matrix awareness for prop-firm-safe execution."""

    def __init__(self, atm_path: Path | str | None = None) -> None:
        super().__init__()
        self.atm_path = Path(atm_path) if atm_path else None

    def load_atm_execution_bounds(self) -> dict[str, Any]:
        return load_atm_execution_bounds(self.atm_path)

    def execute_alpha_generation(
        self,
        raw_intuition: str,
        regime_metrics: dict[str, Any],
        *,
        base_watermark: str = "algocurator",
    ) -> TryHardStrategySchema:
        """Generate strategy with ATM matrix + regime context injected for Grok."""
        evolved_wm = self.watermark_engine.evolve(base_watermark)
        self.agent_state.watermark_evolved = evolved_wm
        self.update_agent_state("aureostellarc")

        atm_rules = self.load_atm_execution_bounds()
        user_payload = (
            f"RAW INTUITION: {raw_intuition}\n"
            f"REGIME METRICS: {json.dumps(regime_metrics, indent=2)}\n"
            f"EVOLVED WATERMARK: {evolved_wm}\n"
            f"AGENT STATE: {json.dumps(asdict(self.agent_state))}\n"
            f"{format_atm_context(atm_rules)}"
            "Align stop/target ticks with ACTIVE ATM templates when instrument is MES or ES. "
            "Prefer automated trail steps (15/25/2) over manual broker adjustments — "
            "Intentional Friction Minimization for prop evaluation environments.\n"
        )

        if not self.api_key:
            strategy = self._offline_fallback(regime_metrics, evolved_wm)
            self._apply_atm_ticks(strategy, atm_rules, regime_metrics)
            return strategy

        try:
            parsed = self._call_grok(user_payload)
            parsed.setdefault("evolved_watermark", evolved_wm)
            parsed.setdefault("agent_state", self.agent_state.aureostellarc)
            strategy = TryHardStrategySchema.model_validate(parsed)
            self._apply_atm_ticks(strategy, atm_rules, regime_metrics)
            return strategy
        except Exception as exc:
            print(f"[GROK FALLBACK] {exc}")
            strategy = self._offline_fallback(regime_metrics, evolved_wm)
            self._apply_atm_ticks(strategy, atm_rules, regime_metrics)
            return strategy

    @staticmethod
    def _apply_atm_ticks(
        strategy: TryHardStrategySchema,
        atm_rules: dict[str, Any],
        regime_metrics: dict[str, Any],
    ) -> None:
        """Bias offline/fallback ticks toward MES Safe Adjust baseline when present."""
        templates = (atm_rules or {}).get("atm_templates") or {}
        instrument = str(regime_metrics.get("instrument", "MES")).upper()
        key = "MES_Safe_Adjust" if instrument in ("MES", "MNQ") else "ES_Scale_Safe"
        tmpl = templates.get(key) or templates.get("MES_Safe_Adjust") or {}
        if tmpl.get("baseline_stop_loss_ticks"):
            strategy.stop_loss_ticks = int(tmpl["baseline_stop_loss_ticks"])
        if tmpl.get("baseline_profit_target_ticks"):
            strategy.take_profit_ticks = int(tmpl["baseline_profit_target_ticks"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Research + backtest alpha generation")
    parser.add_argument(
        "--context",
        default="MES pyramid: wide 40/100 baseline, tighten stop to +2 at +10 ticks.",
    )
    parser.add_argument("--instrument", default="MES")
    parser.add_argument("--watermark", default="algocurator")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from handoff_timeframe import get_active_profile

    profile_name, profile_block = get_active_profile()
    regime_metrics = {
        "trend": profile_name,
        "instrument": args.instrument,
        "timeframe_profile": profile_name,
        "session_context": profile_block.splitlines()[0],
        "market_context": args.context,
    }

    engine = ResearchAndBacktestEngine()
    strategy = engine.execute_alpha_generation(
        args.context,
        regime_metrics,
        base_watermark=args.watermark,
    )

    report = {
        "strategy": strategy.model_dump(),
        "atm_loaded": bool(engine.load_atm_execution_bounds()),
        "matrix_group": engine.load_atm_execution_bounds()
        .get("matrix_meta", {})
        .get("strategy_group"),
        "backend": "grok" if engine.api_key else "offline_fallback",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(json.dumps(strategy.model_dump(), indent=2, ensure_ascii=True))
        print(f"\nWrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
