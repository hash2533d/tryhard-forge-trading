#!/usr/bin/env python3
"""Seed Chroma long-term memory from ingested_agent_memory.json."""

from __future__ import annotations

import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent
MEMORY_PATH = ROOT / "ingested_agent_memory.json"
CHROMA_PATH = ROOT / "agent_longterm_memory"
COLLECTION = "trading_memory"


def main() -> None:
    if not MEMORY_PATH.exists():
        raise SystemExit(f"Missing {MEMORY_PATH}. Run build_ingested_memory.py first.")

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embed = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(name=COLLECTION, embedding_function=embed)

    with MEMORY_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("memory_nodes", [])
    if not nodes:
        raise SystemExit("No memory_nodes found in ingested file.")

    batch_size = 64
    for start in range(0, len(nodes), batch_size):
        chunk = nodes[start : start + batch_size]
        collection.add(
            documents=[n["payload"].get("raw_notes", "") for n in chunk],
            metadatas=[
                {
                    "timestamp": str(n.get("timestamp", "")),
                    "timeframe": str(n.get("target_timeframe", "swing")),
                    "hebbian_weight": float(n.get("hebbian_meta", {}).get("base_weight", 1.0)),
                    "source": str(n.get("source", "")),
                    "node_id": str(n.get("id", "")),
                }
                for n in chunk
            ],
            ids=[f"mem_{start + i}" for i in range(len(chunk))],
        )

    print(f"Seeded {collection.count()} long-term memory vectors.")


if __name__ == "__main__":
    main()