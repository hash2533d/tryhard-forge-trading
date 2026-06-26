#!/usr/bin/env python3
"""Manual training ingestor — maps chart screenshots + notes to 18-day tanks."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from eighteen_day_memory_tank import EighteenDayMemoryTankSystem

ROOT = Path(__file__).resolve().parent
CHROMA_PATH = ROOT / "agent_longterm_memory"
CURATED_LOG = ROOT / "curated_setups.jsonl"
REGIME_LIBRARY = ROOT / "regime_library"
CHARTS_DIR = REGIME_LIBRARY / "charts"
NOTES_DIR = REGIME_LIBRARY / "notes"
DEFAULT_SCREENSHOTS = Path.home() / "Desktop" / "TradingScreenshots"

VALID_TIMEFRAMES = {
    "scalping": "scalper",
    "scalper": "scalper",
    "daytrade": "daytrade",
    "day trader": "daytrade",
    "swing": "swing",
    "long-term": "swing",
    "longterm": "swing",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MIN_NOTE_CHARS = 20
RESONANCE_GATE = 0.85


class ManualTrainingIngestor:
    def __init__(self, db_path: Path | str = CHROMA_PATH):
        self.client = chromadb.PersistentClient(path=str(db_path))
        embed = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.memory_collection = self.client.get_or_create_collection(
            name="trading_memory",
            embedding_function=embed,
        )
        self.tank_system = EighteenDayMemoryTankSystem()
        self.tank_system.load()

    @staticmethod
    def normalize_timeframe(timeframe: str) -> str:
        key = timeframe.strip().lower()
        return VALID_TIMEFRAMES.get(key, "swing")

    def verify_setup(
        self,
        notes: str,
        associated_image_path: str | Path,
        *,
        strict_image: bool = False,
    ) -> dict:
        """Pre-flight checks before curated ingest."""
        image_path = Path(associated_image_path)
        checks = {
            "notes_ok": len(notes.strip()) >= MIN_NOTE_CHARS,
            "image_exists": image_path.exists(),
            "image_ext_ok": image_path.suffix.lower() in IMAGE_EXTENSIONS,
            "image_readable": False,
        }
        if checks["image_exists"]:
            checks["image_readable"] = os.access(image_path, os.R_OK)

        passed = checks["notes_ok"] and (
            (checks["image_exists"] and checks["image_ext_ok"] and checks["image_readable"])
            or not strict_image
        )
        if strict_image and not checks["image_exists"]:
            passed = False

        return {"passed": passed, "checks": checks, "image_path": str(image_path)}

    def ingest_curated_setup(
        self,
        date_str: str,
        notes: str,
        associated_image_path: str | Path,
        timeframe: str,
        cycle_tank_id: str,
        *,
        strict_image: bool = False,
        indicator_snapshot: dict | None = None,
    ) -> dict:
        """Inject a human-curated trade setup with image + tank correlation."""
        print(f"[CURATOR] Ingesting hand-trained setup for {date_str} into {cycle_tank_id}...")

        verification = self.verify_setup(notes, associated_image_path, strict_image=strict_image)
        if not verification["passed"]:
            raise ValueError(f"Verification failed: {verification['checks']}")

        if not verification["checks"]["image_exists"]:
            print(f"[WARNING] Chart screenshot not found at: {associated_image_path}. Metadata only.")

        tf_norm = self.normalize_timeframe(timeframe)
        mem_id = f"curated_{date_str}_{tf_norm}"

        metadata = {
            "timestamp": date_str,
            "target_timeframe": tf_norm,
            "associated_tank": cycle_tank_id,
            "image_path": str(Path(associated_image_path)),
            "verification_status": "HUMAN_CURATED",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "source": "manual_curation",
            "resonance_gate": RESONANCE_GATE,
            "hebbian_weight": 1.25,
        }
        if indicator_snapshot:
            metadata["indicators"] = json.dumps(indicator_snapshot)

        self.memory_collection.upsert(
            documents=[notes.strip()],
            metadatas=[metadata],
            ids=[mem_id],
        )

        record = {
            "mem_id": mem_id,
            "date": date_str,
            "timeframe": tf_norm,
            "tank_id": cycle_tank_id,
            "image_path": metadata["image_path"],
            "ingested_at": metadata["ingested_at"],
            "checks": verification["checks"],
        }
        with CURATED_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        print("[SUCCESS] Curated memory node locked with image link metadata.")
        return record

    def ingest_from_manifest(self, manifest_path: Path) -> int:
        """Batch ingest from regime_library/daily_manifest.jsonl."""
        count = 0
        if not manifest_path.exists():
            raise FileNotFoundError(manifest_path)
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            self.ingest_curated_setup(
                date_str=row["date_str"],
                notes=row["notes"],
                associated_image_path=row["image_path"],
                timeframe=row.get("timeframe", "scalping"),
                cycle_tank_id=row.get("cycle_tank_id", "TANK_01_MERCURY"),
                strict_image=row.get("strict_image", False),
                indicator_snapshot=row.get("indicators"),
            )
            count += 1
        return count


def ensure_regime_folders() -> dict[str, str]:
    """Create local curation folder layout for months 1–6."""
    for path in (REGIME_LIBRARY, CHARTS_DIR, NOTES_DIR, DEFAULT_SCREENSHOTS):
        path.mkdir(parents=True, exist_ok=True)
    manifest = REGIME_LIBRARY / "daily_manifest.jsonl"
    if not manifest.exists():
        manifest.write_text("", encoding="utf-8")
    return {
        "regime_library": str(REGIME_LIBRARY),
        "charts": str(CHARTS_DIR),
        "notes": str(NOTES_DIR),
        "desktop_screenshots": str(DEFAULT_SCREENSHOTS),
        "manifest": str(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual curated setup ingestion")
    parser.add_argument("--init-folders", action="store_true", help="Create regime library dirs")
    parser.add_argument("--manifest", type=Path, help="Batch ingest from JSONL manifest")
    parser.add_argument("--strict-image", action="store_true")
    args = parser.parse_args()

    if args.init_folders:
        paths = ensure_regime_folders()
        print(json.dumps(paths, indent=2))
        return 0

    curator = ManualTrainingIngestor()

    if args.manifest:
        n = curator.ingest_from_manifest(args.manifest)
        print(f"[CURATOR] Batch complete: {n} setups ingested.")
        return 0

    # Example daily workflow
    folders = ensure_regime_folders()
    example_image = Path(folders["desktop_screenshots"]) / "nq_breakout_20260626.jpg"
    curator.ingest_curated_setup(
        date_str="2026-06-26",
        notes=(
            "GFLBS short setup. Swept session high volume node before a clean rejection. "
            "Order flow delta flipped deep red."
        ),
        associated_image_path=example_image,
        timeframe="Scalping",
        cycle_tank_id="TANK_01_MERCURY",
        strict_image=args.strict_image,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())