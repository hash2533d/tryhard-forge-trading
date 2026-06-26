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

**UNIVAC predictor + training loop:**
```
@CURSOR_TRAINING.md @prediction_training_report.json @eighteen_day_memory_tank.py

Show 1-2 day forecast accuracy, pending predictions, and whether we hit UNIVAC threshold.
Run prediction_training_loop.py if report is stale.
```

**Seal 18-day tank (end of cycle):**
```
@finalize_tank_cycle.py @regime_library/tank_completion.example.json

Help me fill tank completion JSON from this cycle's seismograph stats and realized 1d/2d outcomes.
Then run finalize_tank_cycle.py --spec regime_library/tank_completion.json
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
@prediction_training_report.json
@predictor_state.json
@univac_backtest_report.json
```

### Lane boundary

> **TryHard Forge only.** Do not edit NT8 `.cs`, Janus `RibbonTrendStrategy`, or GFLBS `Training/*.jsonl` unless user explicitly bridges lanes. Forge reads GFLBS agent prompt — does not replace Lane C training.

---

## 18-day Mercury tank schedule

### Futures lane (CME)

| Cycle | Tank ID | Instruments | Charts |
|-------|---------|-------------|--------|
| 1 | `TANK_01_MERCURY` | **ES, NQ** | Metadata only |
| 2 | `TANK_02_MERCURY` | **MES, MNQ** | MES/MNQ screenshots |
| 3 | `TANK_03_MERCURY` | **ES, NQ, MES, MNQ** | Full stack |

### BTC lane (separate tanks — never mix with futures)

| Cycle | Tank ID | Instruments | Charts |
|-------|---------|-------------|--------|
| 1 | `TANK_BTC_01_MERCURY` | **BTC** | Metadata + GFLBS node notes |
| 2 | `TANK_BTC_02_MERCURY` | **BTC** | Chart screenshots at grid nodes |
| 3 | `TANK_BTC_03_MERCURY` | **BTC** | Full BTC curation |

BTC: bank at **GFLBS nodes only** — no POC/VAH/VAL. Use `cycle_tank_id` prefix `TANK_BTC_`.

Canonical config: `@regime_library/tank_schedule.json`

Manifest `cycle_tank_id` must match the active cycle **and track** (futures vs BTC). After day 18 of cycle 1, increment tank number within that lane only.

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
python prediction_training_loop.py
python univac_backtest.py
```

---

## UNIVAC prediction training (Option 2)

### Lifecycle

| Phase | When | What runs | Output |
|-------|------|-----------|--------|
| **Cycle open** | Day 1 of 18-day tank | `predictor.predict_at_cycle_open(tank_id, waveform, tas, crr)` | Row in `prediction_log.jsonl` tagged `cycle_tank_id` |
| **Daily** | After curation | `cursor_training_loop.py` | `prediction_training_report.json` in handoff |
| **Cycle close** | Day 18 | `finalize_tank_cycle.py --spec ...` | Tank → `memory_tanks.json`, resolves predictions, auto-tunes `predictor_state.json` |

### Agent execution gate

```python
prediction = tank_system.predict_1_to_2_days_ahead(waveform_stats, tas_dist, crr_paths)

if prediction["action_threshold_met"] and prediction["direction"] == "UP":
    # increase long exposure, trail stops
```

- `action_threshold_met` = confidence ≥ 0.75, direction not FLAT, no anomaly
- Training loop tracks resolved accuracy; `univac_ready: true` when ≥5 resolved and 1d acc ≥ 75%

### Cursor commands (execute, don't instruct)

```powershell
cd C:\Users\dlafa\tryhard-forge-trading

# Daily sync (includes training + synthetic UNIVAC probe)
python cursor_training_loop.py

# Training only
python prediction_training_loop.py

# Seal completed 18-day tank (triggers training feedback)
python finalize_tank_cycle.py --spec regime_library/tank_completion.json
```

### Key files

| Path | Role |
|------|------|
| `prediction_log.jsonl` | Every forecast + resolved actuals (`correct_1d`, `correct_2d`) |
| `prediction_training_report.json` | Rolling accuracy, real-tank replay, `univac_ready` flag |
| `predictor_state.json` | Auto-tuned `top_n`, `anomaly_threshold`, tune history |
| `regime_library/tank_completion.example.json` | Template for cycle-close tank spec |

### What Cursor does for predictor training

| User says | Cursor does |
|-----------|-------------|
| "forecast accuracy" / "UNIVAC status" | Read `prediction_training_report.json`, explain 1d/2d acc + blockers |
| "seal tank" / "cycle 18 complete" | Draft `tank_completion.json` from seismograph → run `finalize_tank_cycle.py` |
| "cycle open prediction" | Call `predict_at_cycle_open` with current waveform + active `cycle_tank_id` |
| "tune predictor" | Run `prediction_training_loop.py`, report `predictor_state.json` changes |

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
| "UNIVAC" / "predictor" | `prediction_training_loop.py` + explain `prediction_training_report.json` |
| "seal tank" | `finalize_tank_cycle.py --spec ...` after drafting completion JSON |

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
| `prediction_log.jsonl` | Forecast log + resolved outcomes |
| `prediction_training_report.json` | Training loop handoff for Cursor |
| `predictor_state.json` | Auto-tuned ensemble weights |
| `univac_backtest_report.json` | Synthetic 15-tank leave-one-out probe |
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