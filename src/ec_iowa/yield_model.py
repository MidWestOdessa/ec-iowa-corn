"""Yield model — prediction and the peak-July input it depends on.

    Yield (bu/ac) = intercept + year_coef x Year + substress_coef x SubStress_Jul

`SubStress_Jul` is peak-July **subsoil** (Very Short + Short) %, **on the NASS
scale**. Since 2026 the observation comes from CASMA satellite data, which
reads systematically lower than the NASS survey the model was trained on, so it
must be translated first via `casma.casma_to_nass_substress`. `forecast()` does
this for you — skipping it silently biases the result.

Report the LOOCV MAE (8.52 bu/ac), not the in-sample MAE, as the expected error.

Public API:
    predict(year, substress_nass)     -> float
    peak_july_substress(wb=None)      -> PeakStress
    forecast(year, wb=None)           -> Forecast
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ec_iowa import casma, config, workbook as wbio

# Crop-CASMA archive layout (see MODEL_HANDOFF.md §3.2)
_ARCHIVE_FIRST_ROW, _ARCHIVE_LAST_ROW = 96, 131
_COL_DATE, _COL_SUB_VS, _COL_SUB_S = 1, 7, 8


@dataclass(frozen=True)
class PeakStress:
    """Peak-July subsoil stress, both as observed and as model input."""
    raw_casma: float           # VS+S straight from CASMA
    nass_equivalent: float     # after calibration — what the model expects
    week_ending: date | None
    weeks_observed: int

    @property
    def is_complete(self) -> bool:
        """July has ~4-5 reportable weeks; fewer means CASMA is still landing."""
        return self.weeks_observed >= 4


@dataclass(frozen=True)
class Forecast:
    year: int
    yield_bu_ac: float
    low_95: float
    high_95: float
    substress: PeakStress
    district_bushels: float

    def summary(self) -> str:
        return (f"{self.year}: {self.yield_bu_ac:.1f} bu/ac "
                f"[{self.low_95:.1f}, {self.high_95:.1f}]  "
                f"~{self.district_bushels / 1e6:.1f}M bu")


def predict(year: int, substress_nass: float) -> float:
    """Point prediction. `substress_nass` must already be on the NASS scale."""
    m = config.YIELD_MODEL
    return (float(m["intercept"])
            + float(m["year"]) * year
            + float(m["substress_jul"]) * substress_nass)


def peak_july_substress(wb=None) -> PeakStress:
    """Peak subsoil stress across July, read from the Crop-CASMA archive.

    Reads the archive's literal values rather than the Crop Progress formula
    cells, which may hold stale caches (MODEL_HANDOFF.md P2).

    A week counts as July if its Monday falls in July, or is Jun 29-30 (that
    week lands mostly in July).
    """
    wb = wb if wb is not None else wbio.load(data_only=True)
    ws = wb[config.SHEET_CASMA]

    peak, peak_week, seen = None, None, 0
    for r in range(_ARCHIVE_FIRST_ROW, _ARCHIVE_LAST_ROW + 1):
        d = ws.cell(r, _COL_DATE).value
        if isinstance(d, datetime):
            d = d.date()
        if not isinstance(d, date):
            continue
        if not (d.month == 7 or (d.month == 6 and d.day >= 29)):
            continue
        vs, s = ws.cell(r, _COL_SUB_VS).value, ws.cell(r, _COL_SUB_S).value
        if not (isinstance(vs, (int, float)) and isinstance(s, (int, float))):
            continue
        seen += 1
        stress = float(vs) + float(s)
        if peak is None or stress > peak:
            peak, peak_week = stress, d

    if peak is None:
        raise ValueError("no July subsoil observations in the Crop-CASMA archive")

    return PeakStress(
        raw_casma=peak,
        nass_equivalent=casma.casma_to_nass_substress(peak),
        week_ending=peak_week,
        weeks_observed=seen,
    )


def forecast(year: int, wb=None) -> Forecast:
    """Full forecast for `year`, including the 95% band and district bushels."""
    stress = peak_july_substress(wb)
    yhat = predict(year, stress.nass_equivalent)
    band = 2 * float(config.YIELD_MODEL["loocv_mae"])
    return Forecast(
        year=year,
        yield_bu_ac=round(yhat, 1),
        low_95=round(yhat - band, 1),
        high_95=round(yhat + band, 1),
        substress=stress,
        district_bushels=yhat * config.TOTAL_CORN_ACRES,
    )
