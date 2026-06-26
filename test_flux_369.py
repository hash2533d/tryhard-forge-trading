#!/usr/bin/env python3
"""Smoke test for 369 flux weighting."""

from datetime import datetime

from flux_369 import compute_flux_369_weight, digital_root, mod9_lock


def main() -> int:
    now = datetime.now()
    samples = [
        (63120.0, 1.0, 0.0),
        (7536.5, 3.0, 412.5),
        (30410.0, 3.0, 1692.0),
    ]
    print("=== 369 Flux Weighting ===\n")
    for price, qty, profit in samples:
        w = compute_flux_369_weight(price, now, qty=qty, profit=profit)
        print(
            f"price={price} mod9={w.mod9} dr={w.digital_root} "
            f"material={w.on_material_track} lock={w.is_369_lock} ×{w.multiplier}"
        )
    print(f"\ndigital_root(27000)={digital_root(27000)}")
    print(f"mod9_lock(63120)={mod9_lock(63120.0, now)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())