"""Tests for the GDD stage model — pure logic, no network."""
from __future__ import annotations

import math

import pytest

from ec_iowa import config, gdd_stage


def test_stage_order_is_monotonic():
    """GDD50 must increase across the phenological sequence.

    A hand-tuned shift once pushed doughing above dented, which would have
    predicted dent before dough.
    """
    assert gdd_stage.check_ordering() == []


def test_no_growth_before_season_starts():
    for stage in gdd_stage.STAGE_ORDER:
        assert gdd_stage.stage_pct(stage, 0) == 0.0
        assert gdd_stage.stage_pct(stage, -50) == 0.0


def test_fifty_percent_at_gdd50():
    """By construction the logistic passes through 50% at its GDD50."""
    for stage in gdd_stage.STAGE_ORDER:
        g50 = float(config.GDD_STAGE_PARAMS[stage]["GDD50"])
        assert gdd_stage.stage_pct(stage, g50) == pytest.approx(50.0, abs=1e-6)


def test_display_floor_suppresses_the_early_tail():
    """The logistic never reaches 0; the floor is what keeps June clean.

    Silking at GDD 961 (late June 2026) computes ~4.4% raw — reported as 0.
    """
    raw = 100 / (1 + math.exp(-0.00723 * (961 - 1388.0)))
    assert 0 < raw < gdd_stage.DISPLAY_FLOOR_PCT
    assert gdd_stage.stage_pct("silking", 961) == 0.0


def test_values_above_the_floor_pass_through():
    # GDD 1525 (week ending Jul 19 2026) -> ~73%, validated against Iowa's 72%.
    assert gdd_stage.stage_pct("silking", 1525) == pytest.approx(72.9, abs=0.5)


def test_monotonic_in_gdd_and_bounded():
    prev = -1.0
    for gdd in range(0, 4000, 100):
        v = gdd_stage.stage_pct("silking", gdd)
        assert 0.0 <= v <= 100.0
        assert v >= prev
        prev = v


def test_all_stages_covers_every_stage_in_order():
    out = gdd_stage.all_stages(1500)
    assert list(out) == gdd_stage.STAGE_ORDER
    # Early stages complete before later ones at any given GDD.
    assert out["silking"] > out["doughing"] >= out["dented"]


def test_unknown_stage_rejected():
    with pytest.raises(KeyError):
        gdd_stage.stage_pct("tasseled", 1500)
