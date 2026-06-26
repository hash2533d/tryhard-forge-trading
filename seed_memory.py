#!/usr/bin/env python3
"""Legacy alias — delegates to discover_persist."""

from __future__ import annotations

from pathlib import Path

from discover_persist import seed_from_history

ROOT = Path(__file__).resolve().parent
MEMORY_PATH = ROOT / "ingested_agent_memory.json"


def main() -> None:
    seed_from_history(MEMORY_PATH)


if __name__ == "__main__":
    main()