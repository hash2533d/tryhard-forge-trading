#!/usr/bin/env python3
"""Build ingested_agent_memory.json from GFLBS training + Janus SetupExamples."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
JANUS = Path.home() / "Documents" / "NinjaTrader 8" / "JanusEngine"

GFLBS_PATHS = [
    JANUS / "GFLBS" / "Training" / "gflbs_training.jsonl",
    JANUS / "GFLBS" / "Training" / "gflbs_training_merged.jsonl",
]
SETUP_EXAMPLES = JANUS / "SetupExamples" / "index.jsonl"
LEDGER = JANUS / "Telemetry" / "janus_shadow_ledger.jsonl"
OUTPUT = ROOT / "ingested_agent_memory.json"


def infer_timeframe(record: dict[str, Any], source: str) -> str:
    tags = {t.lower() for t in record.get("tags", [])}
    tf = str(record.get("timeframe", "")).lower()
    trade_style = str(record.get("input", {}).get("trade_style", "")).lower()

    if "scalp" in tags or "1m_intraday" in tags or tf == "1m":
        return "scalper"
    if "swing" in tags or trade_style == "swing" or tf in {"4h", "1d", "daily"}:
        return "swing"
    if "day_trade" in tags or trade_style == "daytrade" or tf in {"15m", "5m"}:
        return "daytrade"
    if source == "ledger":
        return "longterm"
    return "swing"


def gflbs_to_node(row: dict[str, Any]) -> dict[str, Any]:
    out = row.get("output", {})
    inp = row.get("input", {})
    tags = row.get("tags", [])
    cycle = out.get("cycle_phase") or row.get("cycle_phase", [])
    notes = (
        f"[{row.get('instrument', 'UNK')}] {out.get('signal', 'WAIT')} @ node {out.get('nearest_node')} "
        f"({out.get('deviation_pct', 0):.2f}% dev). {out.get('reasoning', '')} "
        f"Context: {inp.get('recent_action', '')} | phases: {', '.join(cycle)} | tags: {', '.join(tags)}"
    )
    confidence = float(out.get("confidence", 50)) / 100.0
    return {
        "id": row.get("id", f"gflbs_{hash(notes) & 0xFFFFFFFF:08x}"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_timeframe": infer_timeframe(row, "gflbs"),
        "source": "gflbs_training",
        "payload": {
            "raw_notes": notes,
            "instrument": row.get("instrument"),
            "signal": out.get("signal"),
            "nearest_node": out.get("nearest_node"),
            "confidence": out.get("confidence"),
            "ribbon_signal": out.get("ribbon_signal") or row.get("ribbon_signal"),
        },
        "hebbian_meta": {"base_weight": round(0.8 + confidence * 0.4, 3)},
    }


def setup_to_node(row: dict[str, Any]) -> dict[str, Any]:
    notes = (
        f"[{row.get('instrument')}] {row.get('signal_type')} ({row.get('engine')}) "
        f"verdict={row.get('user_verdict')} outcome={row.get('outcome')}. "
        f"{row.get('notes', '')} level={row.get('price_level')} session={row.get('session_time_hint')}"
    )
    weight = 1.2 if row.get("outcome") == "confirmed" else 0.9
    return {
        "id": row.get("id", f"setup_{hash(notes) & 0xFFFFFFFF:08x}"),
        "timestamp": row.get("created_at", datetime.now(timezone.utc).isoformat()),
        "target_timeframe": infer_timeframe(row, "setup"),
        "source": "setup_examples",
        "payload": {
            "raw_notes": notes,
            "instrument": row.get("instrument"),
            "signal_type": row.get("signal_type"),
            "outcome": row.get("outcome"),
            "price_level": row.get("price_level"),
        },
        "hebbian_meta": {"base_weight": weight},
    }


def ledger_to_node(row: dict[str, Any], idx: int) -> dict[str, Any] | None:
    if not row.get("is_evaluated"):
        return None
    notes = (
        f"[{row.get('ticker')}] shadow prediction return={row.get('predicted_return'):.4f} "
        f"actual={row.get('actual_realized_return')} hit={row.get('directional_hit')}"
    )
    hit = row.get("directional_hit")
    weight = 1.1 if hit else 0.7
    return {
        "id": f"ledger_{idx}",
        "timestamp": row.get("prediction_timestamp", datetime.now(timezone.utc).isoformat()),
        "target_timeframe": "longterm",
        "source": "janus_shadow_ledger",
        "payload": {"raw_notes": notes, "ticker": row.get("ticker")},
        "hebbian_meta": {"base_weight": weight},
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    seen_ids: set[str] = set()
    nodes: list[dict[str, Any]] = []

    for path in GFLBS_PATHS:
        for row in load_jsonl(path):
            node = gflbs_to_node(row)
            if node["id"] not in seen_ids:
                seen_ids.add(node["id"])
                nodes.append(node)

    for row in load_jsonl(SETUP_EXAMPLES):
        node = setup_to_node(row)
        if node["id"] not in seen_ids:
            seen_ids.add(node["id"])
            nodes.append(node)

    for idx, row in enumerate(load_jsonl(LEDGER)):
        node = ledger_to_node(row, idx)
        if node and node["id"] not in seen_ids:
            seen_ids.add(node["id"])
            nodes.append(node)

    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "sources": [str(p) for p in GFLBS_PATHS] + [str(SETUP_EXAMPLES), str(LEDGER)],
        "memory_nodes": nodes,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(nodes)} memory nodes -> {OUTPUT}")


if __name__ == "__main__":
    main()