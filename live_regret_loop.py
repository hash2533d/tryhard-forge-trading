#!/usr/bin/env python3
"""Live regret bridge: process fills, compute regret, update Hebbian weights in Chroma."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent
CHROMA_PATH = ROOT / "agent_longterm_memory"
COLLECTION = "trading_memory"
DEFAULT_FILLS = ROOT / "live_fills.csv"
REGRET_LOG = ROOT / "regret_updates.jsonl"


def load_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embed = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    return client.get_or_create_collection(name=COLLECTION, embedding_function=embed)


def parse_fills(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    rename = {
        "Profit": "profit",
        "Entry price": "entry_price",
        "Exit price": "exit_price",
        "Market pos": "side",
        "Instrument": "instrument",
        "Entry time": "entry_time",
        "Exit time": "exit_time",
        "Strategy": "strategy",
    }
    for old, new in rename.items():
        if old in df.columns:
            df = df.rename(columns={old: new})
    if "profit" not in df.columns and "Profit" in df.columns:
        df["profit"] = df["Profit"]
    df["profit"] = pd.to_numeric(df.get("profit", 0), errors="coerce").fillna(0.0)
    return df


def regret_score(row: pd.Series) -> float:
    """Higher regret when trade lost despite favorable excursion proxy."""
    profit = float(row.get("profit", 0))
    mfe = float(row.get("MFE", row.get("mfe", abs(profit))))
    if profit >= 0:
        return 0.0
    return min(1.0, abs(profit) / max(mfe, 1.0))


def timeframe_from_fill(row: pd.Series) -> str:
    try:
        entry = pd.to_datetime(row.get("entry_time"))
        exit_t = pd.to_datetime(row.get("exit_time"))
        minutes = (exit_t - entry).total_seconds() / 60.0
    except Exception:
        minutes = 999
    if minutes <= 20:
        return "scalper"
    if minutes <= 240:
        return "daytrade"
    return "swing"


def update_weights(collection, fills: pd.DataFrame, dry_run: bool = False) -> int:
    updated = 0
    for _, row in fills.iterrows():
        tf = timeframe_from_fill(row)
        regret = regret_score(row)
        delta = -0.15 * regret if regret > 0 else 0.05

        query = (
            f"{row.get('instrument', '')} {row.get('side', '')} "
            f"profit={row.get('profit', 0)} strategy={row.get('strategy', '')}"
        )
        hits = collection.query(
            query_texts=[query],
            n_results=3,
            where={"timeframe": tf} if tf else None,
        )
        ids = hits.get("ids", [[]])[0]
        metas = hits.get("metadatas", [[]])[0]

        for mem_id, meta in zip(ids, metas):
            old_w = float(meta.get("hebbian_weight", 1.0))
            new_w = round(max(0.1, min(2.0, old_w + delta)), 3)
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "fill_instrument": str(row.get("instrument", "")),
                "fill_profit": float(row.get("profit", 0)),
                "regret": regret,
                "memory_id": mem_id,
                "old_weight": old_w,
                "new_weight": new_w,
            }
            if not dry_run:
                meta["hebbian_weight"] = new_w
                meta["last_regret_update"] = record["ts"]
                collection.update(ids=[mem_id], metadatas=[meta])
            REGRET_LOG.open("a", encoding="utf-8").write(json.dumps(record) + "\n")
            updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Live regret bridge for TryHard Forge")
    parser.add_argument("--fills", type=Path, default=DEFAULT_FILLS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.fills.exists():
        raise SystemExit(f"Fills file not found: {args.fills}")

    if not CHROMA_PATH.exists():
        raise SystemExit("Chroma store missing. Run seed_memory.py first.")

    fills = parse_fills(args.fills)
    collection = load_collection()
    n = update_weights(collection, fills, dry_run=args.dry_run)
    print(f"Processed {len(fills)} fills, updated {n} memory weights.")
    print(f"Regret log: {REGRET_LOG}")


if __name__ == "__main__":
    main()