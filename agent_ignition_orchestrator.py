#!/usr/bin/env python3
"""
Master Ignition — full TryHard Forge loop.

ingestion → Chroma seed → regret bridge → timeframe profile → agent call
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STEPS = (
    "build_ingested_memory",
    "seed_memory",
    "live_regret_loop",
    "timeframe_context_builder",
    "assemble_and_call",
    "verify_stack",
)


def run_step(script: str, extra_args: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(ROOT / f"{script}.py")] + (extra_args or [])
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
    parser = argparse.ArgumentParser(description="TryHard Forge master ignition")
    parser.add_argument(
        "--context",
        default="BTC testing 63120 blue support; ribbon +2 reclaim; post-dump base.",
    )
    parser.add_argument("--live", action="store_true", help="Live LLM call (else dry-run)")
    parser.add_argument(
        "--skip-regret",
        action="store_true",
        help="Skip regret loop when live_fills.csv absent",
    )
    parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "grok", "ollama"],
    )
    args = parser.parse_args()

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if args.live else "dry_run",
        "steps": [],
    }

    print("=== TryHard Forge Master Ignition ===")

    for step in ("build_ingested_memory", "seed_memory"):
        result = run_step(step)
        report["steps"].append(result)
        if result["returncode"] != 0:
            print(f"ABORT: {step} failed")
            _write_report(report)
            return 1

    fills = ROOT / "live_fills.csv"
    if fills.exists() and not args.skip_regret:
        result = run_step("live_regret_loop")
        report["steps"].append(result)
    else:
        msg = "SKIP live_regret_loop (no live_fills.csv)"
        print(msg)
        report["steps"].append({"script": "live_regret_loop", "skipped": msg})

    result = run_step("timeframe_context_builder")
    report["steps"].append(result)

    asm_args = ["--context", args.context, "--provider", args.provider]
    if args.live:
        asm_args.append("--live")
    else:
        asm_args.append("--dry-run")
    result = run_step("assemble_and_call", asm_args)
    report["steps"].append(result)

    result = run_step("verify_stack")
    report["steps"].append(result)

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["success"] = all(
        s.get("returncode", 0) == 0 or s.get("skipped") for s in report["steps"]
    )
    _write_report(report)

    print("\n===", "IGNITION COMPLETE" if report["success"] else "IGNITION FAILED", "===")
    return 0 if report["success"] else 1


def _write_report(report: dict) -> None:
    path = ROOT / "last_ignition_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {path}")


if __name__ == "__main__":
    raise SystemExit(main())