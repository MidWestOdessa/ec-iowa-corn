"""Tests for GDD computation and the yield model — pure logic, no network."""
from __future__ import annotations

from datetime import date

import pytest

from ec_iowa import casma, config, noaa, yield_model


# ── daily GDD50 ────────────────────────────────────────────────────────────

def test_gdd_basic_case():
    # 2026-05-01, Cedar Rapids: 55/35 -> min capped up to 50 -> (55+50)/2-50
    assert noaa.compute_gdd50_daily(55, 35) == pytest.approx(2.5)


def test_gdd_caps_high_temp_at_86():
    """Heat above 86F adds nothing — corn stops gaining."""
    assert noaa.compute_gdd50_daily(95, 70) == noaa.compute_gdd50_daily(86, 70)


def test_gdd_floors_low_temp_at_50():
    assert noaa.compute_gdd50_daily(60, 40) == noaa.compute_gdd50_daily(60, 50)


def test_gdd_never_negative():
    assert noaa.compute_gdd50_daily(30, 10) == 0.0


# ── cumulative GDD ─────────────────────────────────────────────────────────

def _temps(pairs):
    return {d: {"TMAX": hi, "TMIN": lo} for d, hi, lo in pairs}


def test_cumulative_accumulates_from_start():
    temps = _temps([
        (date(2026, 5, 1), 55, 35),   # 2.5
        (date(2026, 5, 2), 60, 32),   # 5.0
    ])
    cum = noaa.cumulative_gdd(temps, date(2026, 5, 1), date(2026, 12, 31))
    assert cum[date(2026, 5, 1)] == pytest.approx(2.5)
    assert cum[date(2026, 5, 2)] == pytest.approx(7.5)


def test_cumulative_stops_at_last_observed_day():
    """Must not extrapolate flat past available data.

    It once filled through last_day regardless, so today's running total got
    written into every future week's slot.
    """
    temps = _temps([(date(2026, 5, 1), 55, 35), (date(2026, 5, 2), 60, 32)])
    cum = noaa.cumulative_gdd(temps, date(2026, 5, 1), date(2026, 12, 31))
    assert max(cum) == date(2026, 5, 2)
    assert date(2026, 6, 1) not in cum


def test_cumulative_passes_through_gaps():
    """A missing day contributes 0 but does not break the running total."""
    temps = _temps([(date(2026, 5, 1), 55, 35), (date(2026, 5, 3), 60, 32)])
    cum = noaa.cumulative_gdd(temps, date(2026, 5, 1), date(2026, 5, 3))
    assert cum[date(2026, 5, 2)] == pytest.approx(2.5)   # unchanged
    assert cum[date(2026, 5, 3)] == pytest.approx(7.5)


def test_cumulative_of_nothing_is_empty():
    assert noaa.cumulative_gdd({}, date(2026, 5, 1), date(2026, 12, 31)) == {}


# ── CASMA -> NASS calibration ──────────────────────────────────────────────

def test_calibration_matches_published_coefficients():
    cal = config.CASMA_NASS_SUBSTRESS_CALIBRATION
    assert casma.casma_to_nass_substress(0) == pytest.approx(cal["intercept"])
    expected = cal["intercept"] + cal["slope"] * 30
    assert casma.casma_to_nass_substress(30) == pytest.approx(expected)


def test_calibration_raises_casma_values():
    """CASMA reads lower than the NASS survey the model was trained on."""
    for raw in (0, 5, 20, 50):
        assert casma.casma_to_nass_substress(raw) > raw


# ── yield model ────────────────────────────────────────────────────────────

def test_predict_matches_published_2026_forecast():
    # Peak-July subsoil 0.44% raw -> 10.87% NASS-equivalent -> 247.0 bu/ac
    nass_equiv = casma.casma_to_nass_substress(0.44)
    assert yield_model.predict(2026, nass_equiv) == pytest.approx(247.0, abs=0.1)


def test_drought_lowers_yield():
    wet = yield_model.predict(2026, 10)
    dry = yield_model.predict(2026, 60)
    assert dry < wet
    # -0.44 bu per stress point
    assert wet - dry == pytest.approx(0.44 * 50, abs=0.01)


def test_trend_raises_yield_year_over_year():
    delta = yield_model.predict(2027, 20) - yield_model.predict(2026, 20)
    assert delta == pytest.approx(config.YIELD_MODEL["year"], abs=0.01)
