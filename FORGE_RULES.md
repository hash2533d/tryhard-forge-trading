# TryHard Forge — Agent OS Rules

Portable rules for the GFLBS multi-timeframe trading orchestration loop.

## Pipeline order

1. **Ingest** (`build_ingested_memory.py`) — GFLBS training + Janus SetupExamples → `ingested_agent_memory.json`
2. **Seed** (`seed_memory.py`) — Chroma `trading_memory` collection with Hebbian base weights
3. **Regret** (`live_regret_loop.py`) — NT8 fills → weight nudges on nearest memory vectors
4. **Timeframe** (`timeframe_context_builder.py`) — Scalper / Day / Swing profile injection by clock
5. **Ignite** (`assemble_and_call.py`) — Grok primary, Ollama (`phi4:latest`) fallback

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