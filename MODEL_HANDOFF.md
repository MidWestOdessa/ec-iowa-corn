# EC Iowa Corn Yield Model — Technical Handoff

**Purpose:** everything an engineer (or coding agent) needs to run, maintain, and extend this
project without prior context. Written 2026-07-31, reflecting the state at the end of the
2026 pre-harvest season.

This supersedes `CLAUDE CODE HANDOFF.pdf` (the original spec, written before the project moved
to a PC). Where the two disagree, **this document is current** — the original predates the NASS
data cuts, the model refits, and the dashboard.

---

## 1. What this project is

A weekly-updated **Excel workbook** that ingests public agricultural data and produces a
pre-harvest corn yield forecast for **USDA NASS District 60** (East-Central Iowa, 9 counties,
1,530,000 corn acres).

Three artifacts exist:

| Artifact | Role | Location |
|---|---|---|
| **The workbook** | The deliverable. Source of truth for all data. | OneDrive (see §3) |
| **Python package** | Fetches data and writes into the workbook | `src/ec_iowa/` |
| **Streamlit dashboard** | Read-only view for a trader audience | `web/`, deployed publicly |

**Design constraint the owner has repeatedly affirmed:** Excel remains the deliverable. Do not
propose migrating to a database. The dashboard is a read-only mirror, not a replacement.

### Why it exists
USDA NASS announced survey cuts in Aug 2025. As of ~May 2026 the **district-level** crop
progress breakdown is gone. The workbook replicates that lost data from satellite and weather
sources so the owner retains continuity. This is the central fact that shapes the architecture:
**where NASS used to supply district numbers, we now model them.**

---

## 2. Geography — get this right

District 60 is exactly these nine counties:

| County | FIPS | Corn acres |
|---|---|---:|
| Benton | 19011 | 250,000 |
| Cedar | 19031 | 190,000 |
| Clinton | 19045 | 210,000 |
| Iowa | 19095 | 170,000 |
| Johnson | 19103 | 130,000 |
| Jones | 19105 | 170,000 |
| Linn | 19113 | 165,000 |
| Muscatine | 19139 | 115,000 |
| Scott | 19163 | 130,000 |
| **Total** | | **1,530,000** |

**Tama County (19171) is NOT in District 60** — it is District 50. Never include it in rollups.
All district aggregation is **corn-acre-weighted** using the acres above.

Canonical source: `config.EC_IOWA_COUNTIES`.

---

## 3. The workbook — structure in detail

**Path** (hard-coded in `config.WORKBOOK_PATH`; note the Cyrillic "Рабочий стол" = Desktop):

```
C:\Users\artur\OneDrive\Рабочий стол\Yield model\Corn Progress EC Iowa 2021 2025 v5.xlsx
```

Five sheets. All row/column references below are 1-indexed Excel coordinates.

### 3.1 `Crop Progress`
Year blocks stacked vertically, newest at top. Each block is 26 rows.

| Year | Title row | Dates row | GDD row |
|---|---|---|---|
| 2026 | 1 | 2 | 25 |
| 2025 | 27 | 28 | 51 |
| 2024 | 53 | 54 | 77 |
| 2023 | 79 | 80 | 103 |
| 2022 | 105 | 106 | 129 |
| 2021 | 131 | 132 | 155 |

Within a block, data rows are **offsets from the dates row** (`config.DATA_ROW_OFFSETS`):

| Offset | Content | 2026 row |
|---:|---|---:|
| +1 | Planted % | 3 |
| +2 | Emerged % | 4 |
| +3 | Silking % | 5 |
| +4 | Doughing % | 6 |
| +5 | Dented % | 7 |
| +6 | Corn mature % | 8 |
| +7 | Corn harvested % | 9 |
| +8 | Poor+Fair % (**state**-level) | 10 |
| +9 | Good+Excellent % (**state**-level) | 11 |
| +12..+16 | Topsoil VS / S / **Stress** / A / Surplus | 14–18 |
| +18..+22 | Subsoil VS / S / **Stress** / A / Surplus | 20–24 |
| +23 | GDD50 cumulative from May 1 | 25 |

- **Stress rows (16, 22)** are same-sheet formulas `=VS+S`, not fetched.
- **Columns:** B = Mon Mar 30 2026, then weekly Mondays through AK (36 weeks, ends Nov 30).
  The Mar-30 column exists because 2026 ISO week 14 starts Mar 30, a week before the usual
  April start. **All columns from B rightward shifted by one when it was inserted** — see
  Pitfall P1.
- **2021–2025 blocks are hardcoded historical values.** Treat as immutable.
- **2026 block:** stage rows 3–9 and soil rows 14–24 are `INDEX/MATCH` formulas (see below);
  Planted (row 3) and the state condition rows (10, 11) are manually entered.

### 3.2 `Crop-CASMA` — satellite soil moisture archive
- Rows 1–94: description, county config, 2025 historical.
- **Row 95: header.** Row 96–131: the 2026 weekly archive (36 Mondays, Mar 30 → Nov 30).
- Columns: **A** = Monday date, **B** = ISO week, **C–F** = Top VS/S/A/Surplus %,
  **G–J** = Sub VS/S/A/Surplus %.
- Written by `casma.write_to_archive()`. This sheet holds **literal values** — it is the
  source the Crop Progress soil formulas read from.

### 3.3 `GDD Stage Model`
- **Rows 13–19: the calibrated parameter table.** Columns: A = stage name, B = `GDD50`,
  C = `k`, D = R², E = n obs, F = notes.
  Row order: 13 Planted, 14 Emerged, 15 Silking, 16 Doughing, 17 Dented, 18 Mature, 19 Harvested.
- **Rows 27–62: 2026 weekly predictions.** Columns: A = Monday, B = ISO week,
  C = GDD pulled from Crop Progress, **D–J** = predicted % for the seven stages
  (D=Planted … J=Harvested).
- Column C formula pulls the **prior** Monday's GDD — see Convention C2.
- Stage formula shape (all 252 cells in D27:J62 are identical modulo references):

```excel
=IFERROR(IF(C{r}<=0, 0,
   IF(100/(1+EXP(-C${p}*(C{r}-B${p})))<5, 0,
      MIN(100, MAX(0, 100/(1+EXP(-C${p}*(C{r}-B${p}))))))), 0)
```

where `{r}` is the row and `{p}` is the parameter row (13 for col D … 19 for col J).
The `<5` term is the **5% display floor** — see Pitfall P4.

### 3.4 `Yield Model`
- Rows 7–10: coefficients (β₀ intercept, β₁ Year, β₂ SubStress_Jul; row 10 is the retired
  GE_Silking slot, labelled REMOVED).
- Rows 14–16: fit statistics (R², in-sample MAE, LOOCV MAE).
- Row 17: excluded-years note.
- **Rows 20–26: predictions table** (header row 20; 2021–2026 in rows 21–26).
  Columns: A Year, B SubStress_Jul, C GE at silking, D Predicted, E Actual, F Error.
- **Rows 29–46: full training/validation table** (header 29; 2010–2026 in rows 30–46).
  Columns: A Year, B Yield, C SubStress_Jul, D GE@Silking, E GDD Jul 31, F Planted by May 15,
  G Predicted, H Residual, I Note.

### 3.5 `Drought Monitor`
USDM-based backup for soil moisture. **Currently unused** — `usdm.py` is a stub. Left in place
as a fallback if CASMA ever goes away.

---

## 4. The three models

### 4.1 Yield model (the headline output)

```
Yield (bu/ac) = -10086.87 + 5.103 × Year − 0.440 × SubStress_Jul
```

| Statistic | Value |
|---|---|
| R² | 0.886 |
| In-sample MAE | 6.63 bu/ac |
| **LOOCV MAE** | **8.52 bu/ac** ← the honest error figure |
| Training set | 2010–2024, **excluding 2020** = 14 years |
| Also excluded from future refits | **2025** |

- `SubStress_Jul` = peak-July **subsoil** (Very Short + Short) %, **on the NASS scale**.
- **Year** carries the genetics/agronomy trend (~5.1 bu/ac/yr). It dominates; treat the model
  as "trend, adjusted for July drought."
- **Exclusions are exogenous shocks the model structurally cannot see:** 2020 = derecho,
  2025 = Southern Rust (actual 217.9 vs predicted 243.8, residual −25.9).
- **GE_Silking was dropped** (2026-05-01) when NASS cut district data. Cost: R² 0.902→0.886,
  LOOCV 7.93→8.52. NASS **state** condition ratings later resumed — re-adding a GE feature is
  an open question (§8).
- Constants: `config.YIELD_MODEL`.

**2026 forecast: 247.0 bu/ac** (95% band 230–264), from peak-July subsoil stress of
0.44% raw CASMA → 10.9% calibrated. Written to Yield Model rows 26 and 46.

### 4.2 CASMA → NASS calibration (required glue)

The yield model was trained on **NASS** soil-moisture ratings. From 2026 the input comes from
**CASMA satellite** data, which reads systematically lower. You must translate before feeding
the yield model:

```
NASS_SubStress = 10.33 + 1.2226 × CASMA_SubStress
```

R² 0.845, MAE 7.54 pp, Pearson 0.919, fit on peak-July weeks of 2015–2024 (10 overlap years).
Helper: `casma.casma_to_nass_substress(x)`. Constants: `config.CASMA_NASS_SUBSTRESS_CALIBRATION`.

**Skipping this step silently biases the forecast.**

### 4.3 GDD Stage Model (replaces lost district stage data)

Logistic per stage: `pct = 100 / (1 + exp(−k × (GDD − GDD50)))`, where GDD is cumulative GDD50
from May 1.

| Stage | GDD50 | k | R² | n |
|---|---:|---:|---:|---:|
| Planted | 56.6 | 0.02243 | 0.765 | 103 |
| Emerged | 199.9 | 0.01053 | 0.843 | 99 |
| Silking | 1388.0 | 0.00723 | 0.917 | 88 |
| Doughing | **2250.0** ⚠ | 0.00476 | 0.824 | 108 |
| Dented | 2221.2 | 0.00562 | 0.915 | 115 |
| Corn mature | 2619.1 | 0.00799 | 0.792 | 102 |
| Corn harvested | 2952.5 | 0.00456 | **0.367** ⚠ | 129 |

- Fit on **2010–2025** district observations from `PublicHISTORIC_CORN.xlsx` paired with
  NOAA-standard GDD. An era-split test showed pre-2010 data *degrades* the fit (genetic drift:
  1970s–80s hybrids develop on a different GDD schedule).
- ⚠ **Doughing GDD50 = 2250 is a hand-tuned onset adjustment, not a refit** (2026-07-14). The
  fitted 1843.8 showed ~4% dough in mid-July, which is agronomically wrong for EC Iowa
  (soft dough is mid-to-late August). **Note it is now higher than Dented (2221.2)** — the two
  are out of biological order. This has not mattered yet because neither has activated, but
  **it must be reconciled before the dough/dent window** (§8).
- ⚠ **Harvested R² = 0.367** — GDD is a weak predictor of harvest timing (weather windows and
  logistics dominate). Don't trust it much.
- Constants: `config.GDD_STAGE_PARAMS`. **Keep the workbook's parameter table (rows 13–19) and
  `config.py` in sync — nothing enforces this automatically.**

---

## 5. Data sources

### 5.1 NOAA CDO — temperature → GDD
- **Endpoint:** `https://www.ncdc.noaa.gov/cdo-web/api/v2/data`, dataset `GHCND`,
  station `GHCND:USW00014990` (Cedar Rapids Airport).
- **Auth:** free token, header `token: <NOAA_TOKEN>`, stored in `.env` (gitignored).
- **Formula:** `GDD50 = max(0, (min(max(TMAX,50),86) + min(max(TMIN,50),86))/2 − 50)`,
  accumulated from **May 1**.
- **Latency:** ~4 days for daily temps → the GDD *column* effectively lags ~1 week.
- **Code:** `noaa.py` — fully implemented (`fetch_daily_temps`, `compute_gdd50_daily`,
  `cumulative_gdd`, `write_to_workbook`).
- **Gotcha:** single request limited to 1 year; transient SSL timeouts are common — wrap in
  a retry (existing scripts retry 3×).

### 5.2 Crop-CASMA (NASA SMAP via CSISS/GMU) — soil moisture
The most intricate integration. Fully implemented in `casma.py`.

**Two-step protocol per (county, week, depth):**

1. Try the cached CSV directly:
   `https://nassgeo.csiss.gmu.edu/smap_cache/byFips/{LAYER}_{FIPS}/{LAYER}_{FIPS}_1.0_4.0_1.0.csv`
2. On 404, trigger computation via WPS, then fetch the URL it returns:
   ```
   https://nassgeo.csiss.gmu.edu/smap_service?service=WPS&version=1.0.0
     &request=Execute&identifier=GetStatByFips
     &DataInputs=layer={LAYER};fips={FIPS};minValue=1.0;maxValue=4.0;step=1.0
   ```

**Layer name format** (`casma.layer_name`):
```
SMAP-9KM-CATEGORY-WEEKLY-{TOP|SUB}_{YEAR}_{WEEK:02d}_{YYYY.MM.DD}_{YYYY.MM.DD}_AVERAGE
```
(the two dates are the Monday and Sunday of the ISO week).

**CSV payload:** `category,pixels` where 0 = no-data, 1 = Very Short, 2 = Short, 3 = Adequate,
4 = Surplus. **Compute percentages over categories 1–4 only** (exclude 0).

**Two distinct failure modes — do not conflate:**

| Server message | Meaning | Action |
|---|---|---|
| `Process failed, please check server error log` | Week not yet processed (**data latency**) | Wait; retrying is futile |
| `Maximum number of parallel running processes reached` | Transient queue throttling | Retry later (hours) |

Both surface as `casma.CasmaDataNotAvailable`. Note the server returns these as **HTTP 400 with
an `ows:ExceptionReport`** *and* (historically) as HTTP 200 with `wps:ProcessFailed` — the
parser handles both.

- **Latency: ~15–16 days after the observation week ends.** Measured empirically. The freshest
  pullable week is the one that ended ~2 weeks ago. Don't burn retries on weeks ending <10 days ago.
- **Local cache:** `cache/casma/{layer}_{fips}.csv` (765 files as of writing). Prevents
  re-triggering WPS.
- **Volume:** 9 counties × 2 depths = 18 fetches per week.

### 5.3 USDA Crop Progress — state condition (G+E, P+F)
NASS **state-level** Iowa condition still publishes weekly, even though district data is cut.

**Working method** (`cache/fetch_condition_direct.py`) — plain HTTP, no browser, no API key:
1. GET `https://esmis.nal.usda.gov/publication/crop-progress`
2. Regex the first `/sites/default/release-files/[^"]+\.txt` link (= latest release)
3. Fetch that TXT, find the `Corn Condition - Selected States` table, read the `Iowa` row
   (VP / P / F / G / E)
4. `G+E = G + E`, `P+F = P + F` (**P+F excludes Very Poor** — matches the workbook's convention)

Released **Mondays ~3–4pm CST** for the week ending the prior Sunday.

- ❌ `www.nass.usda.gov` returns **403** to scrapers. ❌ QuickStats API returns **401** without
  a key. ✅ `esmis.nal.usda.gov` serves fine.
- The same report has a `Corn Silking - Selected States` table — used **only as a cross-check**
  (§6, Convention C3).

### 5.4 Historical reference workbooks (read-only inputs)
Two IEM exports live beside the canonical workbook. They were used to fit the models and remain
the source for any refit:

| File | Contents |
|---|---|
| `PublicHISTORIC_CORN.xlsx` | District-level stage progress 1974–2025 (all 9 Iowa districts) + state condition |
| `PublicHISTORIC_Moisture.xlsx` | District topsoil/subsoil 2010–2025; state-level back to 1974 |

**Parsing gotcha:** the `* Dist` sheets stack multiple year-blocks **horizontally**. Each block
is a `DATE` header with district columns to its right; **`EC` sits 6 columns right of `DATE`**.
Scan the first ~12 rows for *every* `DATE` cell, not just the first — see
`cache/ec_vs_state_silking.py` for a correct reader.

---

## 6. Critical conventions

These caused real bugs. Understand them before touching anything.

**C1 — Report-date column alignment.** Column *Mon-X* holds the NASS report **released** on
Mon-X, which is data **as-of the prior Sunday (X−1)**. Planted, conditions, and stages all
follow this. Example: the Jul 13 report (week ending Jul 12) goes in the Jul 13 column.

**C2 — The GDD row uses a different convention.** `Crop Progress` row 25 stores cumulative GDD
**through the coming Sunday (Monday + 6)**. So within any single column, the GDD figure is
~1 week "ahead" of the stage/condition figures.
→ To reconcile, `GDD Stage Model` column C pulls the **prior** Monday's GDD (row R reads
Crop Progress column `R−26`). This makes a stage in column Mon-X reflect the week ending
Sun(X−1), matching the report in that column. **Row 25 itself was deliberately left on the
Monday+6 convention** — changing it would disturb historical GDD and the stage calibration.

**C3 — GDD is primary for stages; state data is cross-check only.** District stages come from
the GDD Stage Model. **Never fill a district stage from the state number**, even via the
EC≈state relationship. If the driving GDD hasn't published, the honest answer is "not available
yet" — let the formula fill it later.
*Validation relationship:* across 50 years of district data, **EC silking tracks the Iowa state
average at +1.6 pp** (it does **not** lag — the truly northern districts NW/NC/NE are what drag
the state average down). Use this to sanity-check, not to populate.

**C4 — Manual vs formula cells (2026 block).**

| Row | Source |
|---|---|
| 3 Planted | Manual (owner reports weekly) |
| 4–9 Stages | GDD Stage Model formulas |
| 10–11 P+F, G+E | Manual, from the USDA state report |
| 14–24 Soil | Formulas → Crop-CASMA archive |
| 25 GDD | Written by `noaa.write_to_workbook` |

When a current-week stage's GDD hasn't published, it is acceptable to write a temporary literal,
**but revert it to the formula once GDD lands and confirm the two agree.**

---

## 7. Weekly operating procedure

Runs Monday afternoon or later. **Close the workbook in Excel first** — openpyxl cannot write
to an open file (`PermissionError`).

1. **Back up** the workbook to a dated filename. Every script does this first.
2. **CASMA:** retry the last ~4 ISO weeks. Expect the most recent ~2 to fail (latency).
   Write successes to the Crop-CASMA archive.
3. **NOAA:** fetch May 1 → Dec 31, compute cumulative, write row 25. Retries on SSL timeout.
4. **Conditions:** fetch the latest report from ESMIS; write G+E → row 11, P+F → row 10 in the
   report-Monday column, with the full VP/P/F/G/E breakdown in a cell comment.
5. **Planted:** ask the owner; write to row 3.
6. **Sanity-check stages** against the state report (C3). Investigate divergence; don't paper over it.
7. **Regenerate the dashboard snapshot** and push:
   ```bash
   uv run python -m web.snapshot
   git add web/data.json && git commit -m "Snapshot YYYY-MM-DD" && git push
   ```
   Streamlit Cloud auto-redeploys on push. **If you skip this, the public dashboard goes stale.**

### Season milestones
- **Late July / early Aug:** peak-July subsoil stress is known → compute the real yield forecast
  (apply §4.2 calibration, then §4.1 model). Write to Yield Model rows 26 & 46.
- **Following May:** prior-year county yields publish → add the acre-weighted district actual,
  then consider a refit.

---

## 8. Known gaps, risks, and open questions

**Honest assessment of what is not done or not settled.**

### Code state — most of the package is stubs
| Module | Lines | State |
|---|---:|---|
| `casma.py` | 404 | ✅ Complete |
| `noaa.py` | 176 | ✅ Complete |
| `config.py` | 177 | ✅ Complete |
| `web/app.py`, `web/snapshot.py` | 923 / 273 | ✅ Complete |
| `cli.py` | 48 | ⚠ argparse skeleton; **every subcommand is an unimplemented stub** |
| `workbook.py`, `yield_model.py`, `gdd_stage.py`, `nass.py`, `usdm.py` | 5–8 each | ❌ Docstring-only stubs |

**The real weekly work is done by ~82 ad-hoc scripts in `cache/` — and `cache/` is
`.gitignore`d, so none of it transfers via git.** This is the single biggest gap for a handoff.
The highest-value ones to promote into the repo:

- `fetch_condition_direct.py` — the working condition lookup
- `refresh_*.py` / `weekly_update_*.py` — the weekly pipeline (many near-duplicate dated copies)
- `compute_2026_forecast.py` — forecast computation
- `ec_vs_state_silking.py` — the district-vs-state validation
- `build_forecast_pdf.py` — the manager-facing PDF
- `probe_casma_latency.py`, `probe_noaa_latency.py` — latency diagnostics

**Recommended first task for whoever picks this up:** consolidate those into real modules
(`workbook.py`, `yield_model.py`, `gdd_stage.py`) and implement the `cli.py` subcommands
(`weekly-update`, `backfill`, `verify`, `forecast`). Then the weekly procedure is one command
instead of a hand-edited script.

### Testing
`tests/test_config.py` has **6 tests, all constants sanity-checks** (county count, acre total,
Tama excluded, block spacing, stage keys, 2020 excluded). **There are zero tests for `casma.py`
or `noaa.py`** — no mocked-HTTP coverage, no parser tests. Both have real parsing logic that has
already broken once when CSISS changed its error format.

### Model issues
1. **Doughing GDD50 (2250) now exceeds Dented (2221.2)** — biologically out of order. Must be
   reconciled before the dough/dent window activates.
2. **Doughing 2250 and the 5% floor are hand-tuned**, anchored on judgment, not fitted.
3. **Harvested R² = 0.367** — near-useless. Consider a different predictor.
4. **Silking calibration history is messy**: it was shifted 1388→1550→1600 chasing an early-onset
   complaint, then **reverted to 1388** when the state cross-check showed the shifts overshot.
   The lesson is recorded in C3. Don't re-litigate without the state check.
5. **GE_Silking could return.** NASS state condition ratings resumed; a state-level GE feature
   might restore the ~0.6 bu/ac LOOCV that was lost. Untested.
6. **NDVI enhancement — queued, not started.** The owner asked for this. Rationale: NDVI is
   satellite-derived (so district-level is possible), correlates with condition ratings, and
   would see the disease/hail stress the current model is blind to — exactly the 2025 failure
   mode. Plan: pull district NDVI (VegScape from the same CSISS/GMU host as CASMA, or MODIS) for
   the silking→grain-fill window 2010–2024, refit, and **judge on LOOCV MAE, not R²** (14
   training years = real overfitting risk). Acid test: does it pull the 2025 residual toward
   zero? Keep the 2-feature model as fallback.
7. **Benton's 2025 yield (225.0) is imputed**, not observed — derived from the 8-county
   acre-weighted YoY ratio (0.943). Replace with the actual if it publishes.

### Data risks
- **CASMA has no SLA.** Undocumented API, unannounced schema changes (already happened once),
  multi-week queue throttling episodes. The `Drought Monitor` sheet + `usdm.py` exist as a
  fallback path that was never built.
- **2026 forecast is provisional** — CASMA weeks 30–31 were still processing when it was
  computed. Subsoil ran 50%+ surplus every July week, so it should hold, but confirm.

---

## 9. Environment

```powershell
# Toolchain: uv (Astral). Python pinned to 3.12 via .python-version.
cd C:\Users\artur\Projects\ec_iowa_corn
uv sync --extra dev
uv run pytest -q                       # 6 tests
uv run python -m web.snapshot          # regenerate dashboard data
uv run streamlit run web/app.py        # local dashboard
```

**PATH note:** in some shells `uv` is not on PATH; prefix with
`$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User');`

**Secrets** — `.env` (gitignored):
```
NOAA_TOKEN=<free token from https://www.ncdc.noaa.gov/cdo-web/token>
NASS_API_KEY=        # optional, unused; would come from https://quickstats.nass.usda.gov/api
```

**Deployment:** GitHub `MidWestOdessa/ec-iowa-corn` → Streamlit Community Cloud.
Streamlit Cloud detects `uv.lock` and runs `uv sync` **without extras** — therefore
`streamlit` and `plotly` must stay in **main** `[project.dependencies]`, not in an optional
group. `requirements.txt`/`runtime.txt` exist but are ignored when `uv.lock` is present.
The dashboard is password-gated via `st.secrets["APP_PASSWORD"]` (fails open if unset).

---

## 10. Pitfalls (each of these caused a real, diagnosed bug)

**P1 — openpyxl does not reliably shift formula references on column insert.** When the Mar-30
column was inserted at B, absolute refs like `'Crop-CASMA'!$C$96` in the moved formulas became
`$D$96` — wrong, because a lookup's *output column* should stay anchored. This silently
mislabelled 8 soil rows × 35 columns (~280 cells) and only surfaced when the archive was
populated: "Very Short" was displaying the Short value, and stress read 98% (apparent drought)
in a wet year. **After any structural change, verify that column-B and column-C formulas point
at the same source column.**

**P2 — openpyxl returns *stale cached values* for formula cells.** With `data_only=True` you get
what Excel last computed and saved. If openpyxl wrote the upstream data and the file hasn't been
reopened in Excel, dependent formulas still read `None`. **Fix: read the source-of-truth literal
cells, not the formula-derived display cells** (e.g. read 2026 soil moisture from the Crop-CASMA
archive, not the Crop Progress block). `web/snapshot.py` does exactly this.

**P3 — openpyxl silently drops conditional formatting and unknown extensions on save.** A
round-trip test showed all 26 CF rules, 1,713 formulas and 133 merged ranges survive, but the
file shrinks ~7% (x14-namespace extension data is lost). Acceptable, but **always back up before
the first save of a session.**

**P4 — The logistic never returns zero.** Far below a stage's GDD50 the curve still yields a
small positive tail (silking read 4.4% in June). Fixed with a **5% display floor** in all 252
stage formulas. **Fix tails with the floor, not by sliding GDD50** — moving the center breaks
the (correct) mid-range, which is exactly what went wrong with silking.

**P5 — The GDD model cannot see planting-to-emergence lag.** It predicts emergence from heat
alone, so in early May it can show emergence before seed is meaningfully in the ground.
Manual overrides were needed for weeks 18–21 of 2026. Expect this every spring.

**P6 — `cumulative_gdd` must stop at the last observed date.** It originally filled through
`last_day` regardless of data, so the running total got written into every future week's slot.
Now clipped to `max(daily_temps)`.

**P7 — Excel file locks.** Every write script must pre-flight
`config.WORKBOOK_PATH.open("ab")` and abort cleanly if the owner has the file open.

**P8 — Never modify 2021–2025 historical data** without explicit instruction.

---

## 11. Working style the owner expects

- **Small, confirmed steps** over large multi-step operations.
- **Show concrete diffs and run commands**, not abstract plans.
- **State limitations plainly.** The owner values "we don't have that data yet" over a
  confident guess. He has caught real errors by cross-checking — take challenges seriously and
  verify with data rather than defending.
- He is a **grain merchant/trader** with genuine agronomic domain knowledge. Don't over-explain
  FIPS, rollups, or regression. Do surface what a number means for a marketing decision.
- **Back up before every workbook write.** This is non-negotiable and every existing script does it.
