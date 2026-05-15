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

web/              # Trader-facing dashboard (side project)
  snapshot.py     # Extracts data.json from canonical workbook
  app.py          # Streamlit app
  data.json       # Last weekly snapshot (regenerated from snapshot.py)
```

The canonical workbook is read/written in place at the OneDrive path configured in `config.WORKBOOK_PATH`. The local `workbooks/` directory is for one-off copies during testing — do not commit them.

## Dashboard (side project)

A Streamlit dashboard surfaces the current forecast + history + conditions for a trader-style consumer.

```powershell
# One-time
uv sync --extra web

# Each refresh (e.g., after a weekly-update)
uv run python -m web.snapshot

# Launch the dashboard
uv run streamlit run web/app.py
# -> opens at http://localhost:8501
```

Refresh cadence: re-run `python -m web.snapshot` whenever the canonical workbook has new data (typically after each weekly update). The dashboard reads only from `web/data.json` — no live workbook access — so it stays cheap and portable.

### Deploying publicly (Streamlit Community Cloud)

The repo is set up for one-click deploy to [share.streamlit.io](https://share.streamlit.io):

1. **Push the repo to GitHub** (public or private — both work on the free tier).
2. **Go to share.streamlit.io**, sign in with GitHub, click **New app**.
3. **Pick this repo**, set the entry point to `web/app.py`, branch to `main`.
4. Click Deploy. Streamlit Cloud reads `requirements.txt` + `runtime.txt` and serves the dashboard at a public `*.streamlit.app` URL within ~2 minutes.

The cloud instance only sees `web/data.json` — your canonical workbook stays on your local machine. To refresh the live site after a weekly snapshot:

```powershell
uv run python -m web.snapshot
git add web/data.json
git commit -m "Snapshot YYYY-MM-DD"
git push
```

Streamlit Cloud auto-redeploys on push. **Note:** `web/data.json` is committed publicly — it contains district-level yields, forecasts, and soil-moisture readings, all derived from public NASS / NOAA sources, so this is fine for the kind of side project this is.
