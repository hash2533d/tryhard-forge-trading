#!/usr/bin/env python3
"""Dynamic prompt assembly + agent call (Grok primary, Ollama fallback)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Literal

import chromadb
from chromadb.utils import embedding_functions

from handoff_timeframe import get_active_profile

ROOT = Path(__file__).resolve().parent
CHROMA_PATH = ROOT / "agent_longterm_memory"
COLLECTION = "trading_memory"
SYSTEM_PROMPT_PATH = (
    Path.home()
    / "Documents"
    / "NinjaTrader 8"
    / "JanusEngine"
    / "GFLBS"
    / "AGENT_SYSTEM_PROMPT.md"
)

GROK_MODEL = os.environ.get("GFLBS_GROK_MODEL", "grok-4")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4:latest")
GROK_BASE_URL = "https://api.x.ai/v1"

GFLBS_JSON_SCHEMA = """{
  "signal": "LONG" | "SHORT" | "WAIT",
  "confidence": 0,
  "nearest_node": 0,
  "deviation_pct": 0.0,
  "reasoning": "short explanation referencing the level and context",
  "entry": null,
  "stop": 0,
  "target_1": 0,
  "target_2": null,
  "risk_reward": 0.0,
  "cycle_phase": ["tag1", "tag2"]
}"""

Provider = Literal["auto", "grok", "ollama"]


def extract_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            chunk = part.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{"):
                return json.loads(chunk)
    return json.loads(text)


def load_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embed = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    return client.get_or_create_collection(name=COLLECTION, embedding_function=embed)


def retrieve_memories(collection, query: str, timeframe: str, k: int = 5) -> list[dict]:
    result = collection.query(
        query_texts=[query],
        n_results=k,
        where={"timeframe": timeframe},
    )
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    return [
        {"text": d, "weight": float(m.get("hebbian_weight", 1.0)), "source": m.get("source", "")}
        for d, m in zip(docs, metas)
    ]


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return "You are GFLBS Trading Agent v2. Output strict JSON only."


def build_messages(market_context: str) -> tuple[str, list[dict[str, str]]]:
    profile_name, profile_block = get_active_profile()
    collection = load_collection()
    memories = retrieve_memories(collection, market_context, profile_name)

    memory_block = "\n".join(
        f"- (w={m['weight']:.2f}) {m['text'][:220]}" for m in memories
    ) or "- No matching memories; use GFLBS grid rules only."

    system_prompt = (
        f"{load_system_prompt()}\n\n"
        f"Return ONLY a single JSON object matching this schema (no markdown fences):\n"
        f"{GFLBS_JSON_SCHEMA}\n\n"
        f"STRICT OUTPUT: raw JSON only. No prose before or after. "
        f"No markdown code fences. risk_reward must be a numeric float, never an expression."
    )
    user_prompt = (
        f"{profile_block}\n\n"
        f"Relevant Memories ({profile_name}):\n{memory_block}\n\n"
        f"Market Context:\n{market_context}\n\n"
        f"Act as GFLBS Trading Agent with regret awareness."
    )
    return profile_name, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def resolve_provider(requested: Provider) -> Provider:
    if requested != "auto":
        return requested
    if os.getenv("XAI_API_KEY", "").strip():
        return "grok"
    return "ollama"


def call_grok(messages: list[dict[str, str]], model: str) -> str:
    import httpx
    import openai

    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("XAI_API_KEY not set. Get one at https://console.x.ai/")

    client = openai.OpenAI(
        api_key=api_key,
        base_url=GROK_BASE_URL,
        timeout=httpx.Timeout(120.0),
    )
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=800,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Grok returned empty response")
    return content


def call_ollama(messages: list[dict[str, str]], model: str) -> str:
    import ollama

    response = ollama.chat(model=model, messages=messages)
    content = response["message"]["content"]
    if not content:
        raise ValueError("Ollama returned empty response")
    return content


def call_agent(
    messages: list[dict[str, str]],
    *,
    provider: Provider,
    grok_model: str,
    ollama_model: str,
    dry_run: bool,
) -> str:
    if dry_run:
        user_text = next(m["content"] for m in messages if m["role"] == "user")
        return json.dumps(
            {
                "mode": "dry_run",
                "provider": resolve_provider(provider),
                "grok_model": grok_model,
                "ollama_model": ollama_model,
                "prompt_chars": sum(len(m["content"]) for m in messages),
                "preview": user_text[:400] + "...",
            },
            indent=2,
        )

    chosen = resolve_provider(provider)
    errors: list[str] = []

    if chosen in ("grok", "auto") or provider == "grok":
        try:
            out = call_grok(messages, grok_model)
            return json.dumps(
                {"backend": "grok", "model": grok_model, "response": json.loads(out)},
                indent=2,
            )
        except Exception as exc:
            errors.append(f"grok: {exc}")
            if provider == "grok":
                return json.dumps({"error": str(exc), "backend": "grok"}, indent=2)

    try:
        out = call_ollama(messages, ollama_model)
        try:
            parsed = extract_json(out)
            payload = {"backend": "ollama", "model": ollama_model, "response": parsed}
        except json.JSONDecodeError:
            payload = {"backend": "ollama", "model": ollama_model, "response_raw": out}
        if errors:
            payload["fallback_from"] = errors
        return json.dumps(payload, indent=2)
    except Exception as exc:
        errors.append(f"ollama: {exc}")
        return json.dumps({"error": "; ".join(errors)}, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="GFLBS agent: Grok primary, Ollama fallback")
    parser.add_argument(
        "--context",
        default="BTC testing 63120 blue support; ribbon +2 reclaim; post-dump base.",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "grok", "ollama"],
        default=os.environ.get("GFLBS_PROVIDER", "auto"),
        help="auto = Grok if XAI_API_KEY set, else Ollama",
    )
    parser.add_argument("--grok-model", default=GROK_MODEL)
    parser.add_argument("--ollama-model", default=OLLAMA_MODEL)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true", help="Call Grok and/or Ollama")
    args = parser.parse_args()

    _, messages = build_messages(args.context)
    out = call_agent(
        messages,
        provider=args.provider,
        grok_model=args.grok_model,
        ollama_model=args.ollama_model,
        dry_run=not args.live,
    )
    print(out)


if __name__ == "__main__":
    main()