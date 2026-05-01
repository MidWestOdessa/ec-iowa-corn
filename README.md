# EC Iowa Corn Progress

Weekly data pipeline and yield forecast for USDA NASS District 60 (East-Central Iowa, 9 counties, ~1.53M corn acres). Pulls satellite soil moisture (NASA SMAP via Crop-CASMA), weather (NOAA CDO), drought (USDM), and NASS crop progress; writes results into the canonical Excel workbook.

The full project spec is in `CLAUDE CODE HANDOFF.pdf` (kept in the OneDrive `Yield model` folder).

## Quickstart

Prereqs: Windows + [uv](https://docs.astral.sh/uv/) (`winget install astral-sh.uv`) + git.

```powershell
# Clone / cd into this directory, then:
uv python install 3.12
uv sync --extra dev

# Configure tokens
copy .env.example .env
# Edit .env: paste NOAA_TOKEN from https://www.ncdc.noaa.gov/cdo-web/token

# Run CLI (entry points are stubs until Phase 4)
uv run ec-iowa --help

# Run tests
uv run pytest
```

## Layout

```
src/ec_iowa/
  config.py       # FIPS, county acres, sheet offsets, model coefficients
  workbook.py     # openpyxl helpers, formula-safe row/col inserts
  casma.py        # CASMA WPS + cached-CSV client (NASA SMAP soil moisture)
  noaa.py         # NOAA CDO daily temps + GDD50 computation
  nass.py         # NASS Quick Stats API client
  usdm.py         # U.S. Drought Monitor REST client
  yield_model.py  # Regression fit + prediction
  gdd_stage.py    # Logistic crop-stage estimator
  cli.py          # weekly-update / backfill / verify / forecast
```

The canonical workbook is read/written in place at the OneDrive path configured in `config.WORKBOOK_PATH`. The local `workbooks/` directory is for one-off copies during testing — do not commit them.
