"""Load ATM execution matrix for Grok / backtest context injection."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_ATM_PATH = ROOT / "atm_execution_rules.json"


def load_atm_execution_bounds(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path or os.getenv("FORGE_ATM_RULES", DEFAULT_ATM_PATH))
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def format_atm_context(rules: dict[str, Any] | None = None) -> str:
    data = rules if rules is not None else load_atm_execution_bounds()
    if not data:
        return ""
    return f"\n### ACTIVE ATM EXECUTION RULES MATRIX:\n{json.dumps(data, indent=2)}\n"
