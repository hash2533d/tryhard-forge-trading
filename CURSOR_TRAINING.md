# TryHard Forge — Cursor Training Pack

Full setup for Cursor Agent on the Hebbian Persona Forge stack. Last updated: 2026-06-26.

---

## Quick start

1. Open workspace: `C:\Users\dlafa\tryhard-forge-trading`
2. Cursor loads `.cursor/rules/tryhard-forge*.mdc` automatically.
3. New chat openers:

**Daily curation (Months 1–2):**
```
@CURSOR_TRAINING.md @FORGE_RULES.md @regime_library/daily_manifest.jsonl

Forge curation mode. Help me grade today's MES sim session, append manifest row, run ingest + readiness.
```

**Live agent call (shadow or dry-run):**
```
@CURSOR_TRAINING.md @assemble_and_call.py @handoff_timeframe.py

Run forge stack dry-run for current market context. GFLBS JSON only. Grok if XAI_API_KEY set.
```

**Readiness gate (2-month live check):**
```
@readiness_checker.py @FORGE_RULES.md

Run readiness diagnostic. Tell me blockers before MES micro live.
```

---

## Cursor setup

### Project rules (installed)

| Rule | Purpose |
|------|---------|
| `tryhard-forge.mdc` | Core forge agent — 5-step loop, tanks, regret, GFLBS |
| `tryhard-forge-curation.mdc` | **Curation mode** — manifest, screenshots, HUMAN_CURATED ingest |

Rules also copied to `%USERPROFILE%\.cursor\rules\` when workspace root is `C:\Users\dlafa`.

Curation rule auto-applies when editing `regime_library/**`, `data_ingestion_patch.py`, or user says **curate** / **grade session** / **manifest**.

### @-mention context (per chat)

```
@CURSOR_TRAINING.md
@FORGE_RULES.md
@atm_execution_rules.json
@Documents/NinjaTrader 8/JanusEngine/GFLBS/AGENT_SYSTEM_PROMPT.md
@regime_library/daily_manifest.jsonl
@readiness_report.json
```

### Lane boundary

> **TryHard Forge only.** Do not edit NT8 `.cs`, Janus `RibbonTrendStrategy`, or GFLBS `Training/*.jsonl` unless user explicitly bridges lanes. Forge reads GFLBS agent prompt — does not replace Lane C training.

---

## Daily training loop (run yourself)

Cursor must execute these — never only tell the user:

```powershell
cd C:\Users\dlafa\tryhard-forge-trading

# Full daily cursor training sync
python cursor_training_loop.py

# Or step-by-step:
python data_ingestion_patch.py --manifest regime_library/daily_manifest.jsonl
python build_ingested_memory.py
python discover_persist.py
python readiness_checker.py
```

---

## Phase 1 curation workflow (what Cursor does)

| User says | Cursor does |
|-----------|-------------|
| "curate today" / "grade session" | Draft manifest JSONL row + notes from chart |
| "ingest" | Run `data_ingestion_patch.py --manifest ...` |
| "readiness" / "ready for live?" | Run `readiness_checker.py`, explain blockers |
| "run forge" | `python run_trading_forge.py` or `agent_ignition_orchestrator.py` |
| "simulate ATM" | `python atm_simulator.py` |
| "shadow mode" | Run regret loop `--once` on `live_fills.csv`, no live orders |

Every curated row must include:
- `verification_status: HUMAN_CURATED` (set by ingestor)
- `cycle_tank_id` (e.g. `TANK_01_MERCURY`)
- Chart path under `Desktop\TradingScreenshots\` or `regime_library/charts\`

---

## GFLBS output schema (agent calls)

Same as Lane C — see `AGENT_SYSTEM_PROMPT.md`. Forge adds tank + regret context in `assemble_and_call.py`.

```json
{
  "signal": "LONG" | "SHORT" | "WAIT",
  "confidence": 0,
  "nearest_node": 0,
  "deviation_pct": 0.0,
  "reasoning": "...",
  "entry": null,
  "stop": 0,
  "target_1": 0,
  "target_2": null,
  "risk_reward": 0.0,
  "cycle_phase": ["tag1"]
}
```

---

## Key paths

| Path | Role |
|------|------|
| `regime_library/daily_manifest.jsonl` | Daily curated setup queue |
| `Desktop/TradingScreenshots/` | Chart drop zone |
| `curated_setups.jsonl` | Ingest audit log |
| `readiness_report.json` | Live gate diagnostic |
| `memory_tanks.json` | 18-day Mercury tanks |
| `agent_longterm_memory/` | Chroma DB (gitignored) |

---

## Environment

| Variable | Use |
|----------|-----|
| `XAI_API_KEY` | Grok production calls |
| `GFLBS_PROVIDER` | `auto` / `grok` / `ollama` |
| `OLLAMA_MODEL` | Default `phi4:latest` |
| `FORGE_MIN_COHERENCE_SEC` | Quant L-System gate (300) |

---

## Northflank / GitHub

Repo: https://github.com/hash2533d/tryhard-forge-trading

Push after forge changes; Northflank pulls for container deploy.