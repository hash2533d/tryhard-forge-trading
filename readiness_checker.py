#!/usr/bin/env python3
"""Quantitative readiness gate for 2-month → live MES micro transition."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
CHROMA_PATH = ROOT / "agent_longterm_memory"
FILLS_PATH = ROOT / "live_fills.csv"
CURATED_LOG = ROOT / "curated_setups.jsonl"
TANK_STORE = ROOT / "memory_tanks.json"
REPORT_PATH = ROOT / "readiness_report.json"

# Phase 2 micro-ignition gates (FORGE_RULES)
MIN_WIN_RATE = 0.60
MIN_PROFIT_FACTOR = 1.30
MIN_TRADES_FOR_LIVE = 30
MIN_CURATED_SETUPS = 10
MIN_TANKS = 3  # ~3 × 18-day cycles in 2 months


class ForgeReadinessChecker:
    def __init__(self, fills_path: Path = FILLS_PATH):
        self.fills_path = fills_path

    def load_fills(self) -> pd.DataFrame:
        if not self.fills_path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.fills_path)
        if "Profit" in df.columns:
            df["profit"] = pd.to_numeric(df["Profit"], errors="coerce").fillna(0.0)
        elif "profit" in df.columns:
            df["profit"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0.0)
        else:
            df["profit"] = 0.0
        return df

    def count_curated_setups(self) -> int:
        if not CURATED_LOG.exists():
            return 0
        return sum(1 for line in CURATED_LOG.read_text(encoding="utf-8").splitlines() if line.strip())

    def count_memory_tanks(self) -> int:
        if not TANK_STORE.exists():
            return 0
        data = json.loads(TANK_STORE.read_text(encoding="utf-8"))
        return len(data) if isinstance(data, dict) else 0

    def count_chroma_curated(self) -> int:
        try:
            import chromadb

            if not CHROMA_PATH.exists():
                return 0
            client = chromadb.PersistentClient(str(CHROMA_PATH))
            col = client.get_collection("trading_memory")
            # Sample query — count human curated via get if small, else estimate from log
            return self.count_curated_setups()
        except Exception:
            return 0

    def compute_trade_metrics(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {
                "total_trades": 0,
                "win_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "net_pnl": 0.0,
            }

        profits = df["profit"].astype(float)
        wins = profits[profits > 0]
        losses = profits[profits < 0]
        total = len(profits)
        win_count = len(wins)
        gross_profit = float(wins.sum()) if len(wins) else 0.0
        gross_loss = float(abs(losses.sum())) if len(losses) else 0.0

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        return {
            "total_trades": int(total),
            "win_trades": int(win_count),
            "win_rate_pct": round((win_count / total) * 100, 2) if total else 0.0,
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_pnl": round(float(profits.sum()), 2),
        }

    def analyze_tank_metrics(
        self,
        *,
        min_win_rate: float = MIN_WIN_RATE,
        min_profit_factor: float = MIN_PROFIT_FACTOR,
        min_trades: int = MIN_TRADES_FOR_LIVE,
    ) -> dict:
        print("[CHECKER] Evaluating 18-day tank metrics for live-ignition readiness...")

        fills = self.load_fills()
        trade_metrics = self.compute_trade_metrics(fills)
        curated_count = self.count_curated_setups()
        tank_count = self.count_memory_tanks()

        win_rate = trade_metrics["win_rate_pct"] / 100.0
        pf = trade_metrics["profit_factor"]
        if pf >= 999:
            pf_ok = True
        else:
            pf_ok = pf >= min_profit_factor

        metrics_pass = win_rate >= min_win_rate and pf_ok
        sample_ok = trade_metrics["total_trades"] >= min_trades
        curation_ok = curated_count >= MIN_CURATED_SETUPS
        tanks_ok = tank_count >= MIN_TANKS

        ready_for_live_micros = metrics_pass and sample_ok and curation_ok

        ignition_status = "APPROVED_FOR_MICRO_LIVE" if ready_for_live_micros else "RETAIN_IN_SIMULATION"

        blockers = []
        if not metrics_pass:
            blockers.append(
                f"win_rate={trade_metrics['win_rate_pct']}% (need ≥{min_win_rate*100:.0f}%) "
                f"or PF={trade_metrics['profit_factor']} (need ≥{min_profit_factor})"
            )
        if not sample_ok:
            blockers.append(
                f"sample_size={trade_metrics['total_trades']} trades (need ≥{min_trades})"
            )
        if not curation_ok:
            blockers.append(
                f"curated_setups={curated_count} (need ≥{MIN_CURATED_SETUPS})"
            )
        if not tanks_ok:
            blockers.append(f"memory_tanks={tank_count} (need ≥{MIN_TANKS} for 2-month gate)")

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_period_note": "Target: 2 months ≈ 3 × 18-day Mercury tanks",
            "trade_metrics": trade_metrics,
            "curation": {
                "curated_setups_logged": curated_count,
                "memory_tanks": tank_count,
                "fills_source": str(self.fills_path),
                "fills_present": self.fills_path.exists(),
            },
            "thresholds": {
                "min_win_rate_pct": min_win_rate * 100,
                "min_profit_factor": min_profit_factor,
                "min_trades": min_trades,
                "min_curated_setups": MIN_CURATED_SETUPS,
                "min_tanks": MIN_TANKS,
            },
            "gates": {
                "metrics_pass": metrics_pass,
                "sample_size_pass": sample_ok,
                "curation_pass": curation_ok,
                "tanks_pass": tanks_ok,
            },
            "ignition_status": ignition_status,
            "phase_recommendation": (
                "PHASE_2_MICRO_IGNITION"
                if ready_for_live_micros
                else "PHASE_1_CURATED_SIM"
            ),
            "blockers": blockers,
            "risk_note": (
                "Live = 1 MES contract max; 12-tick stop ≈ $15 structural risk per trade."
            ),
        }
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Forge live-readiness diagnostic")
    parser.add_argument("--fills", type=Path, default=FILLS_PATH)
    parser.add_argument("--min-trades", type=int, default=MIN_TRADES_FOR_LIVE)
    args = parser.parse_args()

    checker = ForgeReadinessChecker(fills_path=args.fills)
    report = checker.analyze_tank_metrics(min_trades=args.min_trades)

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n=== SYSTEM DIAGNOSTIC REPORT ===")
    print(json.dumps(report, indent=2))
    print("================================")
    print(f"Report saved: {REPORT_PATH}")
    return 0 if report["ignition_status"] == "APPROVED_FOR_MICRO_LIVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())