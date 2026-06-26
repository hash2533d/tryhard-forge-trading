#!/usr/bin/env python3
"""
Master Ignition — extended loop on top of 5-step forge.

ingest → discover/persist → verify/regret → handoff → schedule → quant → verify
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-quant", action="store_true")
    parser.add_argument("--require-coherence", action="store_true")
    parser.add_argument("--watermark", default="gflbsdragon")
    parser.add_argument("--provider", default="auto", choices=["auto", "grok", "ollama"])
    args = parser.parse_args()

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if args.live else "dry_run",
        "steps": [],
    }

    print("=== TryHard Forge Master Ignition ===")

    result = run_step("build_ingested_memory")
    report["steps"].append(result)
    if result["returncode"] != 0:
        _write_report(report)
        return 1

    result = run_step("discover_persist")
    report["steps"].append(result)
    if result["returncode"] != 0:
        _write_report(report)
        return 1

    fills = ROOT / "live_fills.csv"
    if fills.exists() and not args.skip_verify:
        result = run_step("verify_regret_loop", ["--once"])
        report["steps"].append(result)
    else:
        msg = "SKIP verify_regret_loop (no live_fills.csv)"
        print(msg)
        report["steps"].append({"script": "verify_regret_loop", "skipped": msg})

    result = run_step("handoff_timeframe")
    report["steps"].append(result)

    sched_args = ["--context", args.context, "--provider", args.provider]
    sched_args.append("--live" if args.live else "--dry-run")
    result = run_step("schedule_agent_call", sched_args)
    report["steps"].append(result)

    if not args.skip_quant:
        quant_args = ["--context", args.context, "--watermark", args.watermark, "--ignition"]
        if args.require_coherence:
            quant_args.append("--require-coherence")
        result = run_step("run_quant_strategy", quant_args)
        report["steps"].append(result)
        if result["returncode"] != 0:
            _write_report(report)
            return 1

    result = run_step("forge_verify")
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