#!/usr/bin/env python3
"""369 flux weighting — Mod-9 phase lock + digital-root resonance for Hebbian edges."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


RESONANCE_MOD9 = frozenset({0, 3, 6})
RESONANCE_DIGITAL_ROOTS = frozenset({3, 6, 9})
DAMPEN_MOD9 = frozenset({4, 5})
MATERIAL_FLUX_ANCHORS = (3000, 9000, 27000)


@dataclass(frozen=True)
class Flux369Weight:
    mod9: int
    digital_root: int
    on_material_track: bool
    is_369_lock: bool
    multiplier: float

    def to_metadata(self) -> dict[str, Any]:
        return {
            "flux_mod9": self.mod9,
            "flux_digital_root": self.digital_root,
            "flux_material_track": self.on_material_track,
            "flux_369_lock": self.is_369_lock,
            "flux_multiplier": round(self.multiplier, 4),
        }


def digital_root(n: int) -> int:
    """Repeated digit sum; maps 0 → 9 (Gann convention)."""
    n = abs(int(n))
    if n == 0:
        return 9
    r = n % 9
    return 9 if r == 0 else r


def mod9_lock(price: float, timestamp: datetime, qty: float = 1.0, tick_size: float = 0.25) -> int:
    """(price_ticks + epoch_sec + qty_cent) mod 9 — aligns with Genesis 3-6-9 gate."""
    price_ticks = int(round(price / tick_size)) if tick_size > 0 else int(price)
    ts_seed = int(timestamp.timestamp()) % 9
    qty_seed = int(round(qty * 100)) % 9
    return (price_ticks + ts_seed + qty_seed) % 9


def on_material_flux_track(flux_value: int, tolerance: float = 0.02) -> bool:
    """True when flux is near V_c anchors (3000 / 9000 / 27000)."""
    flux_value = abs(int(flux_value))
    for anchor in MATERIAL_FLUX_ANCHORS:
        if anchor == 0:
            continue
        if abs(flux_value - anchor) / anchor <= tolerance:
            return True
        if flux_value > 0 and flux_value % anchor == 0:
            return True
    return False


def compute_flux_369_weight(
    price: float,
    timestamp: datetime,
    *,
    qty: float = 1.0,
    profit: float = 0.0,
    tick_size: float = 0.25,
) -> Flux369Weight:
    """
    Compute Hebbian weight multiplier from 369 flux resonance.

    - mod9 in {0,3,6} → boost (phase-locked)
    - digital root in {3,6,9} → additional boost
    - material track (3k/9k/27k flux) → boost
    - mod9 in {4,5} → dampen (off-resonance / tritone band)
    """
    m9 = mod9_lock(price, timestamp, qty=qty, tick_size=tick_size)
    flux_raw = int(abs(price * qty * 100) + abs(profit * 100))
    dr = digital_root(flux_raw)
    material = on_material_flux_track(flux_raw)

    multiplier = 1.0

    if m9 in RESONANCE_MOD9:
        multiplier += 0.15 if m9 == 0 else 0.10
    elif m9 in DAMPEN_MOD9:
        multiplier -= 0.12

    if dr in RESONANCE_DIGITAL_ROOTS:
        multiplier += 0.08

    if material:
        multiplier += 0.06

    multiplier = round(max(0.5, min(2.0, multiplier)), 4)
    return Flux369Weight(
        mod9=m9,
        digital_root=dr,
        on_material_track=material,
        is_369_lock=m9 in RESONANCE_MOD9,
        multiplier=multiplier,
    )


def apply_flux_delta(base_delta: float, flux: Flux369Weight) -> float:
    """Scale a Hebbian delta by the 369 flux multiplier."""
    return round(base_delta * flux.multiplier, 4)