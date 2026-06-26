# TryHard Forge — Agent OS Rules

Portable rules for the GFLBS multi-timeframe trading orchestration loop.

## 5-Step Agentic Loop (primary)

| Step | Script | Action |
|------|--------|--------|
| 1 Discover + Persist | `discover_persist.py` | Seed `trading_memory` + `hebbian_edges` |
| 2 Hand Off | `handoff_timeframe.py` | Inject scalper / swing / long-term profile |
| 3 Verify + Regret | `verify_regret_loop.py` | Second agent: verify fills, Hebbian prune, pivot |
| 4 Schedule + Call | `schedule_agent_call.py` | Grok primary agent call + schedule log |
| 5 Verify Forge | `forge_verify.py` | Health check |

**Master runner:** `python run_trading_forge.py`

## Extended pipeline (ignition orchestrator)

0. **Ingest** (`build_ingested_memory.py`) — Janus JSONL → `ingested_agent_memory.json`
1–4. Same as 5-step loop above
5. **Quant L-System** (`run_quant_strategy.py`) — Steellarc Trifecta + fact harvest
6. **Legacy verify** (`verify_stack.py`)

## Core trading rules (never break)

- GFLBS nodes are trusted structural attractors; trade only within ~1.5% of a node.
- Never chase — wait for price at the level.
- Stop at next opposing GFLBS level; targets are next 1–2 opposing levels.
- Ribbon +2/-2 at node boosts confidence +10–15; opposes → `WAIT` or lower confidence.
- BTC: no Volume Profile; bank at GFLBS nodes, not POC/VAH/VAL.
- Output: single flat JSON object only (see schema in `assemble_and_call.py`).

## Timeframe profiles

| Profile | ATM template | V_c | When |
|---------|--------------|-----|------|
| Scalper | Matrix_Scalper | 3000 | 09:30–11:30, 14:30–16:00 |
| Day Trader | Matrix_Day_Trader | 9000 | 06:00–09:00, midday |
| Swing | Matrix_Swing | 27000 | Off-hours / weekends |

## Regret / Hebbian

- Winning fills: `+0.05` weight on retrieved memories (cap 2.0)
- Losing fills: `-0.15 * regret_score` (floor 0.1)
- Log every update to `regret_updates.jsonl` (gitignored)

## LLM routing

| Backend | Env | Use |
|---------|-----|-----|
| Grok | `XAI_API_KEY` | Production agent calls, strict JSON |
| Ollama | `OLLAMA_MODEL=phi4:latest` | Offline / fallback local dev |

Set `GFLBS_PROVIDER=auto|grok|ollama`.

## Northflank deploy notes

- Mount Chroma path as persistent volume or rebuild seed on boot from Janus JSONL sources.
- Never commit `.env`, `live_fills.csv`, or `agent_longterm_memory/`.
- Link repo in Northflank → build from `requirements.txt` → run `agent_ignition_orchestrator.py`.

## Data sources (local JanusEngine)

```
Documents/NinjaTrader 8/JanusEngine/GFLBS/Training/gflbs_training.jsonl
Documents/NinjaTrader 8/JanusEngine/GFLBS/Training/gflbs_training_merged.jsonl
Documents/NinjaTrader 8/JanusEngine/SetupExamples/index.jsonl
Documents/NinjaTrader 8/JanusEngine/Telemetry/janus_shadow_ledger.jsonl
```

## SECTION 13: L-SYSTEM GENERATIVE WATERMARK + QUANT ENGINE

**[PROTOCOL]:** All trading agents must evolve and output L-system watermark strings during strategy generation. When an evolved watermark (e.g. `algocuratorφ1618heartcoherent`) appears, unpack full training payload on sovereign side.

### 13.1 Steellarc Trifecta State Tracking

- Agents must report `steellarc` / `aureostyle` / `aureostellarc` state in every output.
- Maintain minimum Coherence-Time of **300 seconds** before deployment (`FORGE_MIN_COHERENCE_SEC`).

### 13.2 Structured Fact Harvesting

- On any 48–72hr sync (dream symbol, equation, curvature insight, etc.), call `harvest_structured_fact()`.
- Facts append to `structured_facts.jsonl` (gitignored).
- Weaponize immediately into agent upgrades (Prism V4, coatings, etc.).

### 13.3 L-System Watermark Examples

| Base | Evolved |
|------|---------|
| `gflbsdragon` | `gflbsdragonφ1618volumeweave` |
| `nakedpoc` | `nakedpoc1618liquiditysweep` |
| `coherencetime` | `coherencetimeφ1618aureostellarc` |
| `prismagent` | `prismagentv4dragonforge` |
| `algocurator` | `algocuratorφ1618heartcoherent` |
| `steellarc` | `steellarcφ1618aureostellarc` |

### 13.4 Engine entrypoint

```bash
python agent_ignition_orchestrator.py       # full loop incl. step 6 quant
python run_quant_strategy.py --ignition     # quant step only
python test_watermark_evolution.py          # watermark demo
```

Production Grok calls via `XAI_API_KEY` → `tryhard_quant_lsystem.py` (`grok-4` default).
Use `--require-coherence` on orchestrator for deploys (300s gate enforced).

## SECTION 14: 369 FLUX WEIGHTING (Hebbian edges)

All `hebbian_edges` and live regret updates pass through `flux_369.py`:

| Signal | Effect on weight delta |
|--------|----------------------|
| mod9 ∈ {0, 3, 6} | Boost (+10–15% on delta) — phase-locked |
| digital root ∈ {3, 6, 9} | +8% boost |
| flux near V_c anchor (3k / 9k / 27k) | +6% material-track boost |
| mod9 ∈ {4, 5} | −12% dampen (off-resonance) |

Metadata stored per edge: `flux_mod9`, `flux_digital_root`, `flux_multiplier`, `flux_369_lock`.

```bash
python test_flux_369.py
```

## SECTION 15: MIGRATORY RISK & DISCREET ATM OVERRIDES

**[OPERATIONAL PROTOCOL]:** When formulating trade execution signals or adjusting entry profiles, the agent must reference the `MES_ES_Pyramid_Safe_Adjust` matrix in `atm_execution_rules.json`. Vague risk recommendations are restricted.

### 15.1 Scrutiny Mitigation (Intentional Friction Minimization)

- Baseline entry brackets must initially register as wide parameters (e.g., 40/100 ticks for micro contracts) to match historical consistency templates.
- Tactical manual tightening must occur at specified milestones (e.g., move stop to +2 ticks when position achieves +10 ticks favorable) to mimic regular trade management behavior.
- Pyramiding from MES into ES can only occur when existing micro risk exposure is mathematically locked at positive breakeven (`MES_1_and_MES_2_locked_at_least_5_ticks`).
- Prefer automated trail steps (15/25/2) over manual broker adjustment commands during prop evaluation sessions.

### 15.2 ATM template reference

| Template | Instrument | Baseline SL/PT (ticks) | Trail |
|----------|------------|------------------------|-------|
| MES_Safe_Adjust | MES | 40 / 100 | 15/25/2 then 10/50/2 |
| MES_Scale_Safe | MES | 30 / 60 | scale +16, trail 10/30/2 |
| ES_Scale_Safe | ES | 30 / 40 | after MES locked +5 ticks |

```bash
python research_and_backtest_engine.py --instrument MES
```