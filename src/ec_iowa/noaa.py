"""NOAA CDO daily temps for Cedar Rapids (USW00014990) + GDD50 computation.

Daily GDD50 = max(0, (max(min(TMAX, 86), 50) + max(min(TMIN, 86), 50)) / 2 - 50)
Cumulative from May 1. See handoff §6.1.2.

Implementation pending.
"""
from __future__ import annotations
