#!/usr/bin/env python3
"""Step 1 Discover + Persist: seed trading_memory and hebbian_edges context graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent
MEMORY_PATH = ROOT / "ingested_agent_memory.json"
CHROMA_PATH = ROOT / "agent_longterm_memory"
TRADING_COLLECTION = "trading_memory"
HEBBIAN_COLLECTION = "hebbian_edges"


def get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def seed_from_history(json_path: Path, reset: bool = False) -> dict[str, int]:
    if not json_path.exists():
        raise FileNotFoundError(
            f"{json_path} missing — run build_ingested_memory.py first."
        )

    client = get_client()
    embed = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    if reset:
        for name in (TRADING_COLLECTION, HEBBIAN_COLLECTION):
            try:
                client.delete_collection(name)
            except Exception:
                pass

    trading_mem = client.get_or_create_collection(
        name=TRADING_COLLECTION,
        embedding_function=embed,
    )
    hebbian = client.get_or_create_collection(name=HEBBIAN_COLLECTION)

    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("memory_nodes", [])
    if not nodes:
        raise ValueError("No memory_nodes in ingested file")

    batch_size = 64
    edge_ids: list[str] = []
    edge_docs: list[str] = []
    edge_metas: list[dict] = []

    for start in range(0, len(nodes), batch_size):
        chunk = nodes[start : start + batch_size]
        trading_mem.upsert(
            documents=[n["payload"].get("raw_notes", "") for n in chunk],
            metadatas=[
                {
                    "timestamp": str(n.get("timestamp", "")),
                    "timeframe": str(n.get("target_timeframe", "swing")),
                    "hebbian_weight": float(
                        n.get("hebbian_meta", {}).get("base_weight", 1.0)
                    ),
                    "source": str(n.get("source", "")),
                    "node_id": str(n.get("id", "")),
                }
                for n in chunk
            ],
            ids=[f"mem_{start + i}" for i in range(len(chunk))],
        )

        for n in chunk:
            nid = str(n.get("id", f"edge_{start}"))
            edge_ids.append(f"edge_{nid}")
            edge_docs.append(n["payload"].get("raw_notes", "")[:512])
            edge_metas.append(
                {
                    "node_id": nid,
                    "weight": float(n.get("hebbian_meta", {}).get("base_weight", 1.0)),
                    "timeframe": str(n.get("target_timeframe", "swing")),
                }
            )

    if edge_ids:
        hebbian.upsert(ids=edge_ids, documents=edge_docs, metadatas=edge_metas)

    counts = {
        "trading_memory": trading_mem.count(),
        "hebbian_edges": hebbian.count(),
    }
    print(
        f"Discover + Persist complete. "
        f"{counts['trading_memory']} memories, {counts['hebbian_edges']} hebbian edges."
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover + Persist memory seeding")
    parser.add_argument(
        "--json-path",
        type=Path,
        default=MEMORY_PATH,
    )
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild collections")
    args = parser.parse_args()
    seed_from_history(args.json_path, reset=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())