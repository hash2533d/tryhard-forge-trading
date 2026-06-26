#!/usr/bin/env python3
"""Verify MES/MNQ datafeed sources and ensure forge data-collection folders exist."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "datafeed" / "manifest.json"
REPORT_PATH = ROOT / "mes_mnq_datafeed_report.json"

NT8_ROOT = Path.home() / "Documents" / "NinjaTrader 8"


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {
        "instruments": ["MES", "MNQ"],
        "forge_drop_zones": {
            "ticks": "datafeed/mes_mnq/ticks",
            "bars": "datafeed/mes_mnq/bars",
            "session_exports": "datafeed/mes_mnq/session_exports",
            "seismograph": "datafeed/mes_mnq/seismograph",
        },
    }


def ensure_datafeed_folders(manifest: dict | None = None) -> dict[str, str]:
    """Create MES/MNQ collection tree under tryhard-forge-trading/datafeed/."""
    manifest = manifest or _load_manifest()
    created: dict[str, str] = {}

    manifest_path = ROOT / "datafeed" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    created["manifest"] = str(manifest_path)

    zones = manifest.get("forge_drop_zones", {})
    for name, rel_path in zones.items():
        path = ROOT / rel_path
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
        created[name] = str(path)

    return created


def _scan_nt8_instrument_dirs(base: Path, roots: tuple[str, ...] = ("MES", "MNQ")) -> dict:
    if not base.exists():
        return {"exists": False, "path": str(base), "contracts": {}}

    contracts: dict[str, list[str]] = {r: [] for r in roots}
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        for root in roots:
            if entry.name.upper().startswith(root + " "):
                contracts[root].append(entry.name)

    return {
        "exists": True,
        "path": str(base),
        "contracts": contracts,
        "ready": all(len(contracts[r]) > 0 for r in roots),
    }


def _read_janus_feed_confirm() -> dict:
    path = NT8_ROOT / "JanusEngine" / "Telemetry" / "janus_feed_confirm.json"
    if not path.exists():
        return {"exists": False, "path": str(path), "mes_mnq_live": False}

    data = json.loads(path.read_text(encoding="utf-8"))
    syms = [s.upper() for s in data.get("nt8_syms", [])]
    roots = data.get("roots", {})
    mes_in_roots = "MES" in roots
    mnq_in_roots = "MNQ" in roots
    mes_in_syms = any(s.startswith("MES") for s in syms)
    mnq_in_syms = any(s.startswith("MNQ") for s in syms)

    return {
        "exists": True,
        "path": str(path),
        "confirmed": data.get("confirmed", False),
        "nt8_feed_ok": data.get("nt8_feed_ok", False),
        "nt8_syms": data.get("nt8_syms", []),
        "roots_tracked": list(roots.keys()),
        "mes_mnq_live": mes_in_roots or mnq_in_roots or mes_in_syms or mnq_in_syms,
        "mes_live": mes_in_roots or mes_in_syms,
        "mnq_live": mnq_in_roots or mnq_in_syms,
        "note": (
            "MES/MNQ on live TCP feed"
            if (mes_in_roots or mnq_in_roots)
            else "NT8 db has MES/MNQ history; live feed confirm still ES/NQ only — open MES+MNQ charts on my_ninjatrader"
        ),
    }


def _count_forge_files(zones: dict[str, str]) -> dict[str, int]:
    counts = {}
    for name, rel in zones.items():
        path = ROOT / rel
        if not path.exists():
            counts[name] = 0
            continue
        counts[name] = sum(
            1 for f in path.iterdir() if f.is_file() and f.name != ".gitkeep"
        )
    return counts


def run_check(*, create_folders: bool = True) -> dict:
    manifest = _load_manifest()
    folders = ensure_datafeed_folders(manifest) if create_folders else {}

    tick_scan = _scan_nt8_instrument_dirs(NT8_ROOT / "db" / "tick")
    minute_scan = _scan_nt8_instrument_dirs(NT8_ROOT / "db" / "minute")
    feed = _read_janus_feed_confirm()
    zones = manifest.get("forge_drop_zones", {})
    file_counts = _count_forge_files(zones)

    # Micro roots often land in minute DB first; tick DB may be ES/NQ-only until tick recording enabled
    nt8_minute_ready = minute_scan.get("ready", False)
    nt8_tick_ready = tick_scan.get("ready", False)
    nt8_db_ready = nt8_minute_ready
    forge_ready = all(p.exists() for p in (ROOT / z for z in zones.values()))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instruments": manifest.get("instruments", ["MES", "MNQ"]),
        "cycle_tank_id": manifest.get("cycle_tank_id", "TANK_02_MERCURY"),
        "folders": folders,
        "forge_file_counts": file_counts,
        "nt8_tick_db": tick_scan,
        "nt8_minute_db": minute_scan,
        "janus_feed_confirm": feed,
        "status": {
            "nt8_minute_ready": nt8_minute_ready,
            "nt8_tick_ready": nt8_tick_ready,
            "nt8_db_ready": nt8_db_ready,
            "forge_folders_ready": forge_ready,
            "live_feed_mes_mnq": feed.get("mes_mnq_live", False),
            "collection_ready": nt8_db_ready and forge_ready,
        },
        "next_actions": [],
    }

    if not feed.get("mes_mnq_live"):
        report["next_actions"].append(
            "NT8: open MES 09-26 + MNQ 09-26 charts on my_ninjatrader connection; confirm price feed connected"
        )
    if sum(file_counts.values()) == 0:
        report["next_actions"].append(
            "Export session ticks/bars or analyzer trades into datafeed/mes_mnq/* drop zones"
        )
    if not report["next_actions"]:
        report["next_actions"].append("Datafeed OK — continue TANK_02 curation")

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="MES/MNQ datafeed folder check + NT8 source scan")
    parser.add_argument("--no-create", action="store_true", help="Check only; do not mkdir")
    args = parser.parse_args()

    report = run_check(create_folders=not args.no_create)
    print("=== MES/MNQ Datafeed Check ===")
    print(f"NT8 minute DB: {report['nt8_minute_db'].get('contracts')}")
    print(f"NT8 tick DB:   {report['nt8_tick_db'].get('contracts')} (optional for micro)")
    print(f"Live MES/MNQ:  {report['janus_feed_confirm'].get('mes_mnq_live')}")
    print(f"Forge folders: {report['status']['forge_folders_ready']}")
    print(f"Collection OK: {report['status']['collection_ready']}")
    for action in report["next_actions"]:
        print(f"  -> {action}")
    print(f"Report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())