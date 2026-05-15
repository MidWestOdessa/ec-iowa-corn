"""Generate web/data.json from the canonical workbook + config.

Run weekly (or after a weekly-update) to refresh what the dashboard shows.
Usage:  uv run python -m web.snapshot
"""
from __future__ import annotations
import json, sys, warnings
from datetime import date, datetime
from pathlib import Path
from statistics import median

import openpyxl

sys.stdout.reconfigure(encoding="utf-8")
from ec_iowa import config

OUT = Path(__file__).parent / "data.json"


def _date_safe(v):
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def main() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(config.WORKBOOK_PATH, data_only=True)
    ws_y = wb[config.SHEET_YIELD_MODEL]
    ws_cp = wb[config.SHEET_CROP_PROGRESS]
    ws_ca = wb[config.SHEET_CASMA]

    # ---- 1. Yield model history (training table rows 30-45) ----
    history = []
    for r in range(30, 46):
        yr = ws_y.cell(r, 1).value
        if not isinstance(yr, int):
            continue
        actual_raw = ws_y.cell(r, 2).value
        substr = ws_y.cell(r, 3).value
        ge = ws_y.cell(r, 4).value
        gdd = ws_y.cell(r, 5).value
        predicted = ws_y.cell(r, 7).value
        residual = ws_y.cell(r, 8).value
        note = ws_y.cell(r, 9).value
        actual = float(actual_raw) if isinstance(actual_raw, (int, float)) else None
        excluded = yr in config.YIELD_MODEL["training_excluded_years"]
        history.append({
            "year": yr,
            "actual": actual,
            "predicted": float(predicted) if isinstance(predicted, (int, float)) else None,
            "residual": float(residual) if isinstance(residual, (int, float)) else None,
            "substress_jul": float(substr) if isinstance(substr, (int, float)) else None,
            "excluded": excluded,
            "note": note,
        })

    # ---- 2. Indicative 2026 forecast ----
    # We don't have peak-July SubStress for 2026 yet. Use median of training years
    # as a placeholder, with uncertainty showing the trader the spread.
    train_substr = [
        h["substress_jul"] for h in history
        if h["substress_jul"] is not None and not h["excluded"] and h["year"] >= 2010 and h["year"] <= 2024
    ]
    median_substr = float(median(train_substr)) if train_substr else 20.0
    ym = config.YIELD_MODEL
    forecast_year = 2026
    indicative = (
        float(ym["intercept"])
        + float(ym["year"]) * forecast_year
        + float(ym["substress_jul"]) * median_substr
    )
    loocv_mae = float(ym["loocv_mae"])
    # ~95% band ≈ ±2σ; use 2*LOOCV_MAE as a practical envelope (conservative)
    forecast = {
        "year": forecast_year,
        "indicative_bu_ac": round(indicative, 1),
        "band_low_95":  round(indicative - 2 * loocv_mae, 1),
        "band_high_95": round(indicative + 2 * loocv_mae, 1),
        "loocv_mae":    round(loocv_mae, 2),
        "method":       "Year + SubStress_Jul (NASS-equivalent scale)",
        "inputs": {
            "year": forecast_year,
            "substress_jul_used": round(median_substr, 1),
            "substress_jul_source": (
                f"Median of 2010-2024 training SubStress_Jul ({len(train_substr)} years). "
                "Real 2026 peak-July value not yet observed — forecast firms up late July."
            ),
        },
        "calibration_note": (
            "When peak-July 2026 CASMA data lands, apply "
            "casma.casma_to_nass_substress() before plugging in here."
        ),
        "fit_stats": {
            "r_squared":  ym["r_squared"],
            "mae":        ym["mae"],
            "loocv_mae":  ym["loocv_mae"],
            "training_years": "2010-2024 excluding 2020, 2025",
            "excluded": ym["training_excluded_years"],
        },
    }

    # ---- 3. Current conditions snapshot ----
    # Latest CASMA archive row that's not empty
    latest_casma = None
    for r in range(131, 95, -1):
        if any(ws_ca.cell(r, c).value is not None for c in (3, 4, 5, 6, 7, 8, 9, 10)):
            latest_casma = {
                "monday":   _date_safe(ws_ca.cell(r, 1).value),
                "iso_week": ws_ca.cell(r, 2).value,
                "top": {
                    "vs": ws_ca.cell(r, 3).value, "s": ws_ca.cell(r, 4).value,
                    "a":  ws_ca.cell(r, 5).value, "su": ws_ca.cell(r, 6).value,
                },
                "sub": {
                    "vs": ws_ca.cell(r, 7).value, "s": ws_ca.cell(r, 8).value,
                    "a":  ws_ca.cell(r, 9).value, "su": ws_ca.cell(r, 10).value,
                },
            }
            break

    # 2026 GDD progression
    gdd_series = []
    dates_row = config.CROP_PROGRESS_YEAR_BLOCKS[2026]["dates"]
    gdd_row = config.CROP_PROGRESS_YEAR_BLOCKS[2026]["gdd"]
    for c in range(2, 38):
        d = ws_cp.cell(dates_row, c).value
        if d is None:
            continue
        g = ws_cp.cell(gdd_row, c).value
        if isinstance(g, (int, float)):
            gdd_series.append({"monday": _date_safe(d), "gdd": float(g)})

    # Crop progress (most recent non-zero values per stage)
    stages = ["planted", "emerged", "silking", "doughing", "dented", "corn_mature", "corn_harvested"]
    crop_progress = {}
    for stage in stages:
        row = dates_row + config.DATA_ROW_OFFSETS[stage]
        latest_val = latest_date = latest_wk = None
        for c in range(2, 38):
            d = ws_cp.cell(dates_row, c).value
            v = ws_cp.cell(row, c).value
            if isinstance(v, (int, float)) and v > 0 and d is not None:
                latest_val = float(v)
                latest_date = _date_safe(d)
                # compute ISO week from date
                if isinstance(d, datetime):
                    d = d.date()
                latest_wk = d.isocalendar()[1] if hasattr(d, "isocalendar") else None
        crop_progress[stage] = {
            "latest_pct": latest_val,
            "latest_monday": latest_date,
            "latest_iso_week": latest_wk,
        }

    conditions = {
        "latest_casma": latest_casma,
        "gdd_series": gdd_series,
        "crop_progress": crop_progress,
    }

    # ---- Assemble + write ----
    snapshot = {
        "as_of": date.today().isoformat(),
        "district": "EC Iowa (NASS District 60)",
        "counties": [n for fips, (n, _) in config.EC_IOWA_COUNTIES.items()],
        "total_corn_acres": config.TOTAL_CORN_ACRES,
        "forecast": forecast,
        "history": history,
        "conditions": conditions,
        "model": {
            "yield": dict(ym),
            "casma_to_nass": config.CASMA_NASS_SUBSTRESS_CALIBRATION,
        },
    }

    OUT.write_text(json.dumps(snapshot, indent=2, default=str))
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")
    print(f"  as_of: {snapshot['as_of']}")
    print(f"  history entries: {len(history)}")
    print(f"  indicative 2026 forecast: {forecast['indicative_bu_ac']} bu/ac "
          f"[{forecast['band_low_95']}, {forecast['band_high_95']}]")
    if latest_casma:
        print(f"  latest CASMA: wk{latest_casma['iso_week']} ({latest_casma['monday']})")


if __name__ == "__main__":
    main()
