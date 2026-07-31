"""GDD Stage Model — district crop stages from accumulated heat.

    pct = 100 / (1 + exp(-k * (GDD - GDD50)))

with GDD = cumulative GDD50 from May 1. This is the **only district-level
source for crop stages** now that NASS cut the district breakdown, so it is
load-bearing. State progress numbers are a cross-check, never a substitute
(MODEL_HANDOFF.md C3).

Two behaviours that mirror the workbook formulas exactly:

  * **5% display floor.** The logistic never reaches zero, so far below a
    stage's threshold it emits a small false tail (silking read 4.4% in June).
    Values under the floor are reported as 0. Fix tails with the floor, never
    by sliding GDD50 — moving the centre breaks the correct mid-range.
  * **GDD <= 0 means the season hasn't started**, so every stage is 0.

Public API:
    stage_pct(stage, gdd)   -> float
    all_stages(gdd)         -> dict[str, float]
    check_ordering()        -> list[str]   (empty == healthy)
"""
from __future__ import annotations

import math

from ec_iowa import config

DISPLAY_FLOOR_PCT = 5.0

#: Phenological order. GDD50 must increase along this sequence — a hand-tuned
#: shift once pushed doughing above dented, which would have predicted dent
#: before dough. `check_ordering()` guards against a repeat.
STAGE_ORDER = ["planted", "emerged", "silking", "doughing",
               "dented", "corn_mature", "corn_harvested"]


def stage_pct(stage: str, gdd: float, floor: float = DISPLAY_FLOOR_PCT) -> float:
    """Predicted % of acres at or past `stage` for the given cumulative GDD."""
    if stage not in config.GDD_STAGE_PARAMS:
        raise KeyError(f"unknown stage {stage!r}; expected one of {STAGE_ORDER}")
    if gdd <= 0:
        return 0.0
    p = config.GDD_STAGE_PARAMS[stage]
    raw = 100.0 / (1.0 + math.exp(-float(p["k"]) * (gdd - float(p["GDD50"]))))
    if raw < floor:
        return 0.0
    return min(100.0, max(0.0, raw))


def all_stages(gdd: float, floor: float = DISPLAY_FLOOR_PCT) -> dict[str, float]:
    """Every stage at one GDD level, in phenological order."""
    return {s: stage_pct(s, gdd, floor) for s in STAGE_ORDER}


def check_ordering() -> list[str]:
    """Stages whose GDD50 falls below the preceding stage. Empty == healthy."""
    broken, prev = [], None
    for s in STAGE_ORDER:
        g = float(config.GDD_STAGE_PARAMS[s]["GDD50"])
        if prev is not None and g < prev:
            broken.append(s)
        prev = g
    return broken
