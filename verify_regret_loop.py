#!/usr/bin/env python3
"""Step 3 Verify + Live Regret: second agent with pivot detection."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

import chromadb
import pandas as pd

from flux_369 import apply_flux_delta, compute_flux_369_weight
from handoff_timeframe import get_active_profile, get_regret_pivot_threshold

ROOT = Path(__file__).resolve().parent
CHROMA_PATH = ROOT / "agent_longterm_memory"
DEFAULT_FILLS = ROOT / "live_fills.csv"
STATE_FILE = ROOT / "verify_agent_state.json"
PIVOT_LOG = ROOT / "novel_overflow_pivots.jsonl"


class VerifyRegretAgent:
    def __init__(
        self,
        fill_log_path: Path = DEFAULT_FILLS,
        fail_limit: int = 3,
    ) -> None:
        self.fill_log_path = fill_log_path
        self.fail_limit = fail_limit
        self.consecutive_high_regret = 0
        self.processed: set[str] = set()
        self._load_state()

        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.hebbian = client.get_or_create_collection(name="hebbian_edges")
        try:
            embed_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            from chromadb.utils import embedding_functions

            embed = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self.trading_mem = embed_client.get_or_create_collection(
                name="trading_memory",
                embedding_function=embed,
            )
        except Exception:
            self.trading_mem = None

        _, _ = get_active_profile()
        self.profile_name, _ = get_active_profile()
        self.pivot_threshold = get_regret_pivot_threshold(self.profile_name)

    def _load_state(self) -> None:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.processed = set(data.get("processed", []))
            self.consecutive_high_regret = int(data.get("consecutive_high_regret", 0))

    def _save_state(self) -> None:
        STATE_FILE.write_text(
            json.dumps(
                {
                    "processed": sorted(self.processed),
                    "consecutive_high_regret": self.consecutive_high_regret,
                    "updated_at": datetime.now().isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def parse_new_fills(self) -> list[dict]:
        if not self.fill_log_path.exists():
            return []

        with self.fill_log_path.open(encoding="utf-8", newline="") as f:
            sample = f.read(2048)
            f.seek(0)
            if "SignalId" in sample or "Timestamp" in sample and "Side" in sample:
                return self._parse_signal_csv(f)
            return self._parse_nt8_csv()

    def _parse_signal_csv(self, f) -> list[dict]:
        reader = csv.DictReader(f)
        new = []
        for row in reader:
            sid = row.get("SignalId") or row.get("OrderId")
            if not sid or sid in self.processed:
                continue
            ts = row.get("Timestamp", datetime.now().isoformat())
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now()
            new.append(
                {
                    "signal_id": str(sid),
                    "timestamp": timestamp,
                    "side": row.get("Side", "buy").lower(),
                    "price": float(row.get("Price", 0)),
                    "qty": float(row.get("Qty", 1)),
                    "profit": float(row.get("Profit", 0) or 0),
                }
            )
            self.processed.add(str(sid))
        return new

    def _parse_nt8_csv(self) -> list[dict]:
        df = pd.read_csv(self.fill_log_path)
        rename = {
            "Trade number": "trade_number",
            "Market pos": "side",
            "Entry price": "price",
            "Profit": "profit",
            "Entry time": "entry_time",
        }
        for old, new in rename.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        new = []
        for _, row in df.iterrows():
            sid = str(row.get("trade_number", row.name))
            if sid in self.processed:
                continue
            side_raw = str(row.get("side", "Long")).lower()
            side = "buy" if "long" in side_raw else "sell"
            profit = float(row.get("profit", 0) or 0)
            new.append(
                {
                    "signal_id": sid,
                    "timestamp": datetime.now(),
                    "side": side,
                    "price": float(row.get("price", 0)),
                    "qty": 1.0,
                    "profit": profit,
                }
            )
            self.processed.add(sid)
        return new

    def verify_and_compute_regret(self, fill: dict) -> float:
        """Verify fill output; compute regret vs optimal (profit-based proxy)."""
        profit = float(fill.get("profit", 0))
        if profit >= 0:
            return 0.0
        mfe_proxy = max(abs(profit), 1.0)
        return min(1.0, abs(profit) / mfe_proxy)

    def update_hebbian(self, signal_id: str, regret: float, fill: dict) -> float:
        edge_id = f"fill_{signal_id}"
        existing = self.hebbian.get(ids=[edge_id], include=["metadatas"])
        metas = existing.get("metadatas") or []
        weight = float(metas[0].get("weight", 1.0)) if metas else 1.0

        flux = compute_flux_369_weight(
            float(fill.get("price", 0)),
            fill.get("timestamp", datetime.now()),
            qty=float(fill.get("qty", 1.0)),
            profit=float(fill.get("profit", 0)),
        )

        if regret <= 0.0001:
            delta = apply_flux_delta(0.15, flux)
        else:
            delta = apply_flux_delta(-regret * 0.5, flux)

        weight = round(max(0.1, min(2.0, weight + delta)), 3)
        edge_meta = {
            "weight": weight,
            "signal_id": signal_id,
            "regret": regret,
            **flux.to_metadata(),
        }

        if weight < 0.2:
            try:
                self.hebbian.delete(ids=[edge_id])
            except Exception:
                pass
            print(
                f"[VERIFY PRUNE] {signal_id} removed (weight {weight}, "
                f"flux×{flux.multiplier})"
            )
        else:
            self.hebbian.upsert(
                ids=[edge_id],
                documents=[
                    f"fill edge {signal_id} regret={regret:.4f} mod9={flux.mod9} dr={flux.digital_root}"
                ],
                metadatas=[edge_meta],
            )
            lock = "369-LOCK" if flux.is_369_lock else "off-res"
            print(
                f"[VERIFY] {signal_id} weight={weight:.3f} regret={regret:.4f} "
                f"flux×{flux.multiplier} mod9={flux.mod9} [{lock}]"
            )

        if self.trading_mem is not None:
            mem_delta = apply_flux_delta(0.05 if regret <= 0.0001 else -0.15 * regret, flux)
            hits = self.trading_mem.query(
                query_texts=[f"fill {signal_id} profit={fill.get('profit', 0)}"],
                n_results=1,
            )
            ids = hits.get("ids", [[]])[0]
            metas2 = hits.get("metadatas", [[]])[0]
            if ids and metas2:
                meta = metas2[0]
                meta["hebbian_weight"] = round(
                    max(0.1, min(2.0, float(meta.get("hebbian_weight", 1.0)) + mem_delta)),
                    3,
                )
                meta.update(flux.to_metadata())
                self.trading_mem.update(ids=[ids[0]], metadatas=[meta])

        return weight

    def check_pivot(self, regret: float) -> bool:
        if regret > self.pivot_threshold:
            self.consecutive_high_regret += 1
        else:
            self.consecutive_high_regret = 0

        if self.consecutive_high_regret >= self.fail_limit:
            msg = (
                "[!!! NOVEL OVERFLOW PIVOT !!!] High regret detected — "
                "switching to capital protection / long-term mode"
            )
            print(msg)
            record = {
                "ts": datetime.now().isoformat(),
                "profile": self.profile_name,
                "threshold": self.pivot_threshold,
                "consecutive": self.consecutive_high_regret,
            }
            with PIVOT_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            self.consecutive_high_regret = 0
            return True
        return False

    def process_batch(self) -> int:
        n = 0
        for fill in self.parse_new_fills():
            regret = self.verify_and_compute_regret(fill)
            self.update_hebbian(fill["signal_id"], regret, fill)
            self.check_pivot(regret)
            n += 1
        self._save_state()
        return n

    def run(self, interval: float = 1.0) -> None:
        print(
            f"Verify + Regret Agent running (profile={self.profile_name}, "
            f"pivot_threshold={self.pivot_threshold})..."
        )
        while True:
            count = self.process_batch()
            if count:
                print(f"Processed {count} new fill(s)")
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify + Regret loop agent")
    parser.add_argument("--fills", type=Path, default=DEFAULT_FILLS)
    parser.add_argument("--once", action="store_true", help="Process batch and exit")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--fail-limit", type=int, default=3)
    args = parser.parse_args()

    if not CHROMA_PATH.exists():
        raise SystemExit("Chroma missing. Run discover_persist.py first.")

    agent = VerifyRegretAgent(fill_log_path=args.fills, fail_limit=args.fail_limit)

    if args.once:
        if not args.fills.exists():
            print("SKIP: no live_fills.csv")
            return 0
        n = agent.process_batch()
        print(f"Verify batch complete. {n} fill(s) processed.")
        return 0

    if not args.fills.exists():
        raise SystemExit(f"Fills file required for daemon mode: {args.fills}")
    agent.run(interval=args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())