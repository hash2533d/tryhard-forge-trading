#!/usr/bin/env python3
"""
Cursor training loop — daily sync for Forge + readiness handoff.

Run after curation sessions so Cursor Agent has fresh state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HANDOFF_PATH = ROOT / "cursor_handoff.json"
MANIFEST = ROOT / "regime_library" / "daily_manifest.jsonl"


def run(script: str, args: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(ROOT / script)] + (args or [])
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-2000:] if proc.stdout else "",
        "stderr": proc.stderr[-1000:] if proc.stderr else "",
    }


def manifest_has_entries() -> bool:
    if not MANIFEST.exists():
        return False
    return any(line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines())


def main() -> int:
    parser = argparse.ArgumentParser(description="Cursor daily forge training sync")
    parser.add_argument("--skip-ingest-if-empty", action="store_true")
    parser.add_argument("--full-forge", action="store_true", help="Also run run_trading_forge.py")
    args = parser.parse_args()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cursor_training": True,
        "steps": [],
    }

    print("=== Cursor Training Loop ===")

    if manifest_has_entries():
        ingest_step = run("data_ingestion_patch.py", ["--manifest", str(MANIFEST)])
        report["steps"].append(ingest_step)
        if ingest_step.get("returncode", 0) == 0:
            MANIFEST.write_text("", encoding="utf-8")
            report["manifest_cleared"] = True
            print("Cleared daily_manifest.jsonl after successful ingest.")
    elif not args.skip_ingest_if_empty:
        print("SKIP ingest: empty daily_manifest.jsonl")

    report["steps"].append(run("build_ingested_memory.py"))
    report["steps"].append(run("discover_persist.py"))
    report["steps"].append(run("readiness_checker.py"))
    report["steps"].append(run("prediction_training_loop.py"))
    report["steps"].append(run("univac_backtest.py"))

    if args.full_forge:
        report["steps"].append(run("run_trading_forge.py", ["--skip-ingest"]))

    # Load readiness summary if present
    readiness_path = ROOT / "readiness_report.json"
    if readiness_path.exists():
        report["readiness"] = json.loads(readiness_path.read_text(encoding="utf-8"))

    training_path = ROOT / "prediction_training_report.json"
    if training_path.exists():
        report["prediction_training"] = json.loads(training_path.read_text(encoding="utf-8"))

    univac_path = ROOT / "univac_backtest_report.json"
    if univac_path.exists():
        report["univac_backtest"] = json.loads(univac_path.read_text(encoding="utf-8"))

    def step_ok(step: dict) -> bool:
        if step.get("returncode", 0) == 0:
            return True
        # readiness_checker exits 1 when not live-ready — expected in Phase 1
        if step.get("script") == "readiness_checker.py":
            return True
        return False

    report["success"] = all(step_ok(s) for s in report["steps"] if "returncode" in s)
    pt = report.get("prediction_training", {})
    univac = report.get("univac_backtest", {})
    report["cursor_chat_opener"] = (
        "@CURSOR_TRAINING.md @cursor_handoff.json @prediction_training_report.json — "
        "Forge training sync complete. "
        f"Readiness: {report.get('readiness', {}).get('ignition_status', 'unknown')}. "
        f"Predictor: {pt.get('log_accuracy', {}).get('resolved', 0)} resolved, "
        f"1d acc={pt.get('log_accuracy', {}).get('accuracy_1d')}. "
        f"UNIVAC sim grade: {univac.get('univac_grade', 'n/a')}."
    )

    HANDOFF_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nHandoff: {HANDOFF_PATH}")
    print(report["cursor_chat_opener"])
    print("=== TRAINING LOOP COMPLETE ===" if report["success"] else "=== TRAINING LOOP PARTIAL ===")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())