#!/usr/bin/env python3
"""Step 4 Schedule + Full Agent Call (Grok primary, Ollama fallback)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEDULE_LOG = ROOT / "agent_schedule.jsonl"

# Reuse production agent assembly from step 5 legacy path
from assemble_and_call import build_messages, call_agent, resolve_provider


def log_schedule(profile: str, provider: str, context: str) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "provider": provider,
        "context_preview": context[:160],
    }
    with SCHEDULE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule + agent call")
    parser.add_argument(
        "--context",
        default="Current BTC 1-min action at 63120 blue; ribbon +2 reclaim.",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("GFLBS_PROVIDER", "auto"),
        choices=["auto", "grok", "ollama"],
    )
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    profile_name, messages = build_messages(args.context)
    provider = resolve_provider(args.provider)  # type: ignore[arg-type]
    log_schedule(profile_name, provider, args.context)

    out = call_agent(
        messages,
        provider=args.provider,  # type: ignore[arg-type]
        grok_model=os.environ.get("GFLBS_GROK_MODEL", "grok-4"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "phi4:latest"),
        dry_run=not args.live,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())