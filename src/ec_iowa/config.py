"""Project-wide constants.

All FIPS codes, county acres, workbook layout offsets, model coefficients,
and external API base URLs live here so there's one source of truth.
"""
from __future__ import annotations

from pathlib import Path

# ---- File paths --------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "cache"

# Canonical workbook lives in OneDrive for cross-device backup (handoff §10).
WORKBOOK_PATH = Path(
    r"C:\Users\artur\OneDrive\Рабочий стол\Yield model"
) / "Corn Progress EC Iowa 2021 2025 v5.xlsx"

# ---- Geography: USDA NASS District 60 (East-Central Iowa) --------------
# Source: handoff §1. Tama (FIPS 19171) is District 50 — DO NOT include.

EC_IOWA_COUNTIES: dict[str, tuple[str, int]] = {
    "19011": ("Benton",    250_000),
    "19031": ("Cedar",     190_000),
    "19045": ("Clinton",   210_000),
    "19095": ("Iowa",      170_000),
    "19103": ("Johnson",   130_000),
    "19105": ("Jones",     170_000),
    "19113": ("Linn",      165_000),
    "19139": ("Muscatine", 115_000),
    "19163": ("Scott",     130_000),
}
TOTAL_CORN_ACRES = sum(acres for _, acres in EC_IOWA_COUNTIES.values())  # 1_530_000

# ---- Crop Progress sheet layout (handoff §3.1) -------------------------
# Year blocks (1-indexed Excel rows). dates row + offsets below = data rows.

CROP_PROGRESS_YEAR_BLOCKS: dict[int, dict[str, int]] = {
    2026: {"title":   1, "dates":   2, "last":  25, "gdd":  25},
    2025: {"title":  27, "dates":  28, "last":  51, "gdd":  51},
    2024: {"title":  53, "dates":  54, "last":  77, "gdd":  77},
    2023: {"title":  79, "dates":  80, "last": 103, "gdd": 103},
    2022: {"title": 105, "dates": 106, "last": 129, "gdd": 129},
    2021: {"title": 131, "dates": 132, "last": 155, "gdd": 155},
}

# Row offsets from the dates row within each year block.
DATA_ROW_OFFSETS: dict[str, int] = {
    "planted":         1,
    "emerged":         2,
    "silking":         3,
    "doughing":        4,
    "dented":          5,
    "corn_mature":     6,
    "corn_harvested":  7,
    "pf_state":        8,   # Poor/Fair (state-level)
    "ge_state":        9,   # Good/Excellent (state-level)
    "topsoil_vs":     12,
    "topsoil_s":      13,
    "topsoil_stress": 14,   # = VS + S, computed
    "topsoil_a":      15,
    "topsoil_su":     16,
    "subsoil_vs":     18,
    "subsoil_s":      19,
    "subsoil_stress": 20,   # = VS + S, computed
    "subsoil_a":      21,
    "subsoil_su":     22,
    "gdd50_cum":      23,   # cumulative GDD50 from May 1
}

# ---- Yield Model coefficients (handoff §3.2) ---------------------------
# Refit 2026-05-01 on Year + SubStress_Jul only. The original 3-feature
# model included GE_Silking (NASS state-level Good+Excellent rating at
# silking week), but NASS Crop Progress publication was cut as of
# 2026-05-01. Dropping the feature cost 0.016 R² and 0.6 bu/ac LOOCV MAE.
# Training set unchanged: 2010-2024 excluding 2020 (derecho), 14 years.

YIELD_MODEL: dict[str, float | list[int]] = {
    "intercept":      -10086.87,
    "year":                5.103,
    "substress_jul":      -0.440,
    # ge_silking removed — see header comment
    "r_squared":           0.886,
    "mae":                 6.63,
    "loocv_mae":           8.52,
    # 2020 = derecho exogenous shock; 2025 = Southern Rust disease pressure
    # exogenous shock (residual -25.9 bu/ac vs prediction; Benton imputed)
    "training_excluded_years": [2020, 2025],
}

# ---- CASMA → NASS subsoil-stress calibration --------------------------
# Calibrated 2026-05-05 against PublicHISTORIC_Moisture.xlsx Dist Subsoil
# 2010-current, EC column, peak-July weeks of 2015-2024 (10 overlap years).
#
# Yield model was trained on NASS-source SubStress_Jul values (1990s-2024
# crowd-rated soil moisture). 2026+ pipeline uses CASMA satellite-derived
# values, which read systematically lower (slope < 1, positive intercept).
# Use casma_to_nass_substress(x) to translate before feeding to yield model.

CASMA_NASS_SUBSTRESS_CALIBRATION = {
    "intercept": 10.33,
    "slope":      1.2226,
    "r_squared":  0.845,
    "mae_pp":     7.54,
    "pearson":    0.919,
    "n_years":    10,
    "training_years": list(range(2015, 2025)),
}

# ---- GDD Stage Model parameters (handoff §3.3) -------------------------
# Logistic: pct = 100 / (1 + exp(-k * (GDD - GDD50)))
# Refit 2026-05-05 on 2010-2025 NASS district stage observations from
# IEM PublicHISTORIC_CORN.xlsx, paired with NOAA-standard cumulative GDD
# from Cedar Rapids airport (USW00014990).
#
# Window choice: an era-split diagnostic (2026-05-05) showed that adding
# pre-2010 data degrades fit quality due to genetic drift (1970s/80s
# hybrids develop on a different GDD schedule than modern hybrids). The
# previous 2021-2025-only fit had higher in-sample R² but parameters that
# were outliers vs the long-term consensus, suggesting it overfit to
# unusually cool springs in 2021-2025. The 2010-2025 window is the sweet
# spot: enough modern-era observations (n=88-129 per stage) without
# pre-genetic-drift contamination, and parameters align with the
# 31/51-year long-term consensus.
#
# Don't refit casually.

GDD_STAGE_PARAMS: dict[str, dict[str, float]] = {
    "planted":        {"GDD50":   56.6, "k": 0.02243, "r_squared": 0.765, "n": 103},
    "emerged":        {"GDD50":  199.9, "k": 0.01053, "r_squared": 0.843, "n":  99},
    # GDD50 manually shifted 1387.8->1550 (2026-07-06) ->1600 (2026-07-14):
    # the 16-yr-refit curve ran early on silking ONSET vs EC Iowa field reads.
    # 1600 gives ~4% at GDD 1159 (wk ending Jul 5, matching the user's read).
    # k and old-fit r_squared unchanged — onset adjustment, not a refit.
    "silking":        {"GDD50": 1600.0, "k": 0.00723, "r_squared": 0.917, "n":  88},
    # GDD50 manually shifted 1843.8->2250 (2026-07-14): 16-yr curve ran early
    # on doughing too (showed ~4% mid-July; EC Iowa soft dough is ~mid-late
    # Aug). 2250 keeps dough ~0 through July, 50% ~Aug 22 (~4wk after 50%
    # silking). Onset adjustment for the delayed 2026 season, not a refit.
    "doughing":       {"GDD50": 2250.0, "k": 0.00476, "r_squared": 0.824, "n": 108},
    "dented":         {"GDD50": 2221.2, "k": 0.00562, "r_squared": 0.915, "n": 115},
    "corn_mature":    {"GDD50": 2619.1, "k": 0.00799, "r_squared": 0.792, "n": 102},
    "corn_harvested": {"GDD50": 2952.5, "k": 0.00456, "r_squared": 0.367, "n": 129},
}

# ---- Weather (handoff §4.1, §6.1.2) -----------------------------------

NOAA_STATION_ID = "USW00014990"  # Cedar Rapids Airport
GDD_BASE_F = 50
GDD_CAP_HIGH_F = 86
GDD_ACCUM_START_MONTH = 5  # accumulate from May 1
GDD_ACCUM_START_DAY = 1

# ---- External API base URLs (handoff §5) ------------------------------

NASS_PROGRESS_PDF_BASE = (
    "https://www.nass.usda.gov/Statistics_by_State/Iowa/"
    "Publications/Crop_Progress_&_Condition/"
)
NASS_QUICKSTATS_BASE = "https://quickstats.nass.usda.gov/api/"
NOAA_CDO_BASE = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
USDM_BASE = "https://usdmdataservices.unl.edu/api/CountyStatistics/"
CASMA_WPS_BASE = "https://nassgeo.csiss.gmu.edu/smap_service"
CASMA_CACHE_BASE = "https://nassgeo.csiss.gmu.edu/smap_cache/byFips/"

# ---- Sheet names (verify against workbook before relying on these) ----

SHEET_CROP_PROGRESS = "Crop Progress"
SHEET_YIELD_MODEL = "Yield Model"
SHEET_GDD_STAGE = "GDD Stage Model"
SHEET_DROUGHT_MONITOR = "Drought Monitor"
SHEET_CASMA = "Crop-CASMA"
