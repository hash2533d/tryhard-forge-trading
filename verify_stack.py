#!/usr/bin/env python3
"""Quick full-stack verification (playbook step 6)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import chromadb

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ok = True

    memory_file = ROOT / "ingested_agent_memory.json"
    chroma_path = ROOT / "agent_longterm_memory"

    print("=== TryHard Forge Stack Verification ===")

    if memory_file.exists():
        import json

        data = json.loads(memory_file.read_text(encoding="utf-8"))
        print(f"ingested_agent_memory.json: {len(data.get('memory_nodes', []))} nodes")
    else:
        print("FAIL: ingested_agent_memory.json missing")
        ok = False

    if chroma_path.exists():
        client = chromadb.PersistentClient(str(chroma_path))
        col = client.get_collection("trading_memory")
        print(f"Chroma trading_memory count: {col.count()}")
    else:
        print("FAIL: agent_longterm_memory Chroma store missing")
        ok = False

    print("Regret bridge: live_regret_loop.py ready (run after placing live_fills.csv)")

    tf = subprocess.run(
        [sys.executable, str(ROOT / "timeframe_context_builder.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    if tf.returncode == 0:
        first_line = tf.stdout.strip().splitlines()[0] if tf.stdout else "(empty)"
        print(f"Timeframe test: {first_line}")
    else:
        print(f"FAIL timeframe_context_builder: {tf.stderr}")
        ok = False

    asm = subprocess.run(
        [sys.executable, str(ROOT / "assemble_and_call.py"), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    if asm.returncode == 0:
        print("assemble_and_call.py: OK (dry-run)")
    else:
        print(f"FAIL assemble_and_call: {asm.stderr}")
        ok = False

    print("===", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())