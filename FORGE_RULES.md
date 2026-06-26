# TryHard Forge — Agent OS Rules

Portable rules for the GFLBS multi-timeframe trading orchestration loop.

## Pipeline order

1. **Ingest** (`build_ingested_memory.py`) — GFLBS training + Janus SetupExamples → `ingested_agent_memory.json`
2. **Seed** (`seed_memory.py`) — Chroma `trading_memory` collection with Hebbian base weights
3. **Regret** (`live_regret_loop.py`) — NT8 fills → weight nudges on nearest memory vectors
4. **Timeframe** (`timeframe_context_builder.py`) — Scalper / Day / Swing profile injection by clock
5. **Ignite** (`assemble_and_call.py`) — Grok primary, Ollama (`phi4:latest`) fallback
6. **Quant L-System** (`run_quant_strategy.py`) — Steellarc Trifecta strategy + fact harvest
7. **Verify** (`verify_stack.py`) — health check

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