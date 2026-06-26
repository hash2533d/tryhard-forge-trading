#!/usr/bin/env python3
"""
Master 5-Step Trading Forge Loop

Discover → Hand off → Verify → Persist → Schedule
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(script: str, args: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(ROOT / script)] + (args or [])
    print(f"\n>> {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="5-step trading forge master runner")
    parser.add_argument(
        "--context",
        default="Current BTC 1-min action at 63120 blue; ribbon +2 reclaim.",
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--provider", default="auto", choices=["auto", "grok", "ollama"])
    args = parser.parse_args()

    report = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": []}
    print("=== TryHard 5-Step Trading Forge ===")

    if not args.skip_ingest:
        r = run("build_ingested_memory.py")
        report["steps"].append({"step": 0, "ingest": r})
        if r["returncode"] != 0:
            return 1

    # 1 Discover + Persist
    r = run("discover_persist.py", ["--reset"])
    report["steps"].append({"step": 1, "discover_persist": r})
    if r["returncode"] != 0:
        return 1

    # 2 Hand off
    r = run("handoff_timeframe.py")
    report["steps"].append({"step": 2, "handoff": r})

    # 3 Verify + Regret (batch if fills present)
    if not args.skip_verify:
        fills = ROOT / "live_fills.csv"
        if fills.exists():
            r = run("verify_regret_loop.py", ["--once", "--fills", str(fills)])
            report["steps"].append({"step": 3, "verify_regret": r})
        else:
            msg = "SKIP verify_regret_loop (no live_fills.csv)"
            print(msg)
            report["steps"].append({"step": 3, "verify_regret": {"skipped": msg}})

    # 4 Schedule + agent call
    sched_args = ["--context", args.context, "--provider", args.provider]
    sched_args.append("--live" if args.live else "--dry-run")
    r = run("schedule_agent_call.py", sched_args)
    report["steps"].append({"step": 4, "schedule": r})

    # 5 Persist report + verify
    r = run("forge_verify.py")
    report["steps"].append({"step": 5, "verify_forge": r})

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["success"] = all(
        s.get("returncode", 0) == 0
        for block in report["steps"]
        for s in block.values()
        if isinstance(s, dict) and "returncode" in s
    )
    out = ROOT / "last_forge_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {out}")
    print("=== FORGE COMPLETE ===" if report["success"] else "=== FORGE FAILED ===")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())