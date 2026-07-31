"""Command-line entry point — the weekly routine as one command.

    ec-iowa weekly-update [--year Y] [--weeks N]   refresh CASMA + NOAA + conditions
    ec-iowa forecast      [--year Y]               compute the yield forecast
    ec-iowa verify                                 health checks, no writes
    ec-iowa conditions                             show latest USDA report figures

`weekly-update` writes to the canonical workbook. Close it in Excel first.
Every write path backs up beforehand. Regenerate the dashboard afterwards:

    uv run python -m web.snapshot && git add web/data.json && git commit && git push
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from ec_iowa import casma, config, gdd_stage, nass, noaa
from ec_iowa import workbook as wbio
from ec_iowa import yield_model


def _iso_weeks_back(n: int, today: date | None = None) -> list[int]:
    """The n most recent ISO weeks, oldest first."""
    today = today or date.today()
    wk = today.isocalendar()[1]
    return [w for w in range(wk - n + 1, wk + 1) if w > 0]


# ─────────────────────────────── commands ───────────────────────────────

def cmd_weekly_update(args) -> int:
    year = args.year or date.today().year
    weeks = _iso_weeks_back(args.weeks)
    print(f"Weekly update — {year}, ISO weeks {weeks[0]}–{weeks[-1]}\n")

    # CASMA. The most recent ~2 weeks routinely aren't processed yet
    # (~15-16 day latency); that is expected, not an error.
    print(f"[1/4] Crop-CASMA soil moisture")
    rollups = {}
    for wk in weeks:
        try:
            data = casma.fetch_district_week(year, wk)
        except casma.CasmaDataNotAvailable as exc:
            print(f"  wk{wk:02d}  not ready ({exc})")
            continue
        except Exception as exc:                      # noqa: BLE001
            print(f"  wk{wk:02d}  ERROR {exc!r}")
            continue
        top = casma.compute_district_rollup(data, "TOP")
        sub = casma.compute_district_rollup(data, "SUB")
        if top and sub:
            rollups[wk] = (top, sub)
            print(f"  wk{wk:02d}  TOP {top.pcts}  SUB {sub.pcts}")

    # NOAA. Transient SSL timeouts are common; retry before giving up.
    print(f"\n[2/4] NOAA growing degree days")
    start, end = date(year, 5, 1), date(year, 12, 31)
    daily, cum = {}, {}
    for attempt in (1, 2, 3):
        try:
            daily = noaa.fetch_daily_temps(config.NOAA_STATION_ID, start, end)
            break
        except Exception as exc:                      # noqa: BLE001
            print(f"  attempt {attempt} failed ({exc!r})")
    if daily:
        cum = noaa.cumulative_gdd(daily, start, end)
        latest = max(daily)
        print(f"  through {latest}: {cum[latest]:.1f} cumulative GDD")
    else:
        print("  skipped — NOAA unreachable")

    # Conditions (state-level; correct to store in the state rows).
    print(f"\n[3/4] USDA crop condition")
    cond = None
    try:
        cond = nass.iowa_condition()
        print(f"  week ending {cond.week_ending}: {cond.breakdown}")
        print(f"  G+E {cond.good_excellent}%   P+F {cond.poor_fair}%")
    except Exception as exc:                          # noqa: BLE001
        print(f"  unavailable ({exc})")

    if args.dry_run:
        print("\n[4/4] dry run — nothing written")
        return 0

    print(f"\n[4/4] Writing to {config.WORKBOOK_PATH.name}")
    try:
        wb, bak = wbio.open_for_write("weekly")
    except wbio.WorkbookLocked as exc:
        print(f"  ABORT: {exc}")
        return 1
    print(f"  backup: {bak.name}")

    for wk, (top, sub) in rollups.items():
        row = casma.write_to_archive(wb, year, wk, top, sub)
        print(f"  CASMA wk{wk:02d} -> Crop-CASMA row {row}")
    if cum:
        n = noaa.write_to_workbook(wb, year, cum, accum_start=start)
        print(f"  GDD -> {n} cells")
    if cond is not None:
        ws = wb[config.SHEET_CROP_PROGRESS]
        blk = config.CROP_PROGRESS_YEAR_BLOCKS[year]
        # Report-date convention: the report released this Monday describes the
        # week ending the prior Sunday, and belongs in this Monday's column.
        monday = date.today() - timedelta(days=date.today().weekday())
        try:
            col = wbio.column_for_monday(ws, blk["dates"], monday)
            note = (f"USDA Crop Progress, week ending {cond.week_ending}. "
                    f"Iowa: {cond.breakdown}. Fetched {date.today()}.")
            wbio.set_with_note(ws, blk["dates"] + config.DATA_ROW_OFFSETS["ge_state"],
                               col, cond.good_excellent, note)
            wbio.set_with_note(ws, blk["dates"] + config.DATA_ROW_OFFSETS["pf_state"],
                               col, cond.poor_fair, note)
            print(f"  conditions -> column {col} (Mon {monday})")
        except ValueError as exc:
            print(f"  conditions skipped: {exc}")

    wb.save(config.WORKBOOK_PATH)
    print(f"  saved ({config.WORKBOOK_PATH.stat().st_size:,} bytes)")
    print("\nNext: uv run python -m web.snapshot, then commit web/data.json")
    return 0


def cmd_forecast(args) -> int:
    year = args.year or date.today().year
    try:
        fc = yield_model.forecast(year)
    except (wbio.WorkbookLocked, wbio.WorkbookMissing) as exc:
        print(f"Cannot read the workbook: {exc}")
        return 1
    except ValueError as exc:
        print(f"Cannot compute a forecast: {exc}")
        return 1
    s = fc.substress
    print(f"{year} yield forecast — EC Iowa (District 60)\n")
    print(f"  {fc.yield_bu_ac:.1f} bu/ac      95% band {fc.low_95:.1f} – {fc.high_95:.1f}")
    print(f"  ~{fc.district_bushels / 1e6:.1f}M bushels across "
          f"{config.TOTAL_CORN_ACRES:,} acres\n")
    print(f"  peak-July subsoil stress")
    print(f"    raw CASMA        {s.raw_casma:.2f}%")
    print(f"    NASS-equivalent  {s.nass_equivalent:.2f}%   (calibrated)")
    print(f"    peak week ending {s.week_ending}")
    print(f"    July weeks seen  {s.weeks_observed}")
    if not s.is_complete:
        print(f"\n  PROVISIONAL — only {s.weeks_observed} July week(s) observed; "
              f"CASMA runs ~2 weeks behind, so late-July data may still move this.")
    print(f"\n  Expected error ±{config.YIELD_MODEL['loocv_mae']} bu/ac "
          f"(cross-validated). The model cannot see disease, insects or hail.")
    return 0


def cmd_conditions(_args) -> int:
    report = nass.fetch_report()
    cond = nass.iowa_condition(report)
    print(f"Iowa corn condition — week ending {cond.week_ending}")
    print(f"  {cond.breakdown}")
    print(f"  G+E {cond.good_excellent}%    P+F {cond.poor_fair}%\n")
    print("Stage progress (cross-check only — never write to district cells):")
    for stage in ("Silking", "Dough", "Dent", "Mature"):
        try:
            p = nass.iowa_progress(stage, report)
            print(f"  {stage:8s} this week {p.this_week}%   "
                  f"last week {p.last_week}%   5-yr avg {p.five_year_avg}%")
        except nass.NassError:
            print(f"  {stage:8s} not yet reported")
    return 0


def cmd_verify(_args) -> int:
    ok = True

    broken = gdd_stage.check_ordering()
    if broken:
        ok = False
        print(f"  FAIL  stage GDD50 out of order at: {', '.join(broken)}")
    else:
        print("  ok    stage GDD50 thresholds increase monotonically")

    try:
        wbio.ensure_writable()
        print(f"  ok    workbook reachable and writable")
    except wbio.WorkbookMissing:
        ok = False
        print(f"  FAIL  workbook not found at {config.WORKBOOK_PATH}")
        print(f"        set EC_IOWA_WORKBOOK to a local copy (see .env.example)")
    except wbio.WorkbookLocked:
        ok = False
        print("  FAIL  workbook is open in Excel")

    # config vs workbook drift: nothing keeps the stage table in sync.
    try:
        ws = wbio.load(data_only=True)[config.SHEET_GDD_STAGE]
        drift: list[str] = []
        for i, stage in enumerate(gdd_stage.STAGE_ORDER):
            sheet_g50 = ws.cell(13 + i, 2).value
            cfg_g50 = config.GDD_STAGE_PARAMS[stage]["GDD50"]
            if sheet_g50 is None or abs(float(sheet_g50) - float(cfg_g50)) > 0.05:
                drift.append(f"{stage}: workbook={sheet_g50} config={cfg_g50}")
        if drift:
            ok = False
            for d in drift:
                print(f"  FAIL  stage parameter drift — {d}")
        else:
            print("  ok    workbook stage parameters match config.py")
    except (wbio.WorkbookLocked, wbio.WorkbookMissing):
        print("  skip  stage-parameter comparison (workbook unavailable)")
    except Exception as exc:                          # noqa: BLE001
        ok = False
        print(f"  FAIL  could not compare stage parameters ({exc})")

    print("\nAll checks passed." if ok else "\nProblems found — see above.")
    return 0 if ok else 1


# ─────────────────────────────── wiring ───────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ec-iowa",
        description="EC Iowa corn yield model — weekly data pipeline.")
    sub = p.add_subparsers(dest="command")

    w = sub.add_parser("weekly-update", help="refresh CASMA, GDD and conditions")
    w.add_argument("--year", type=int, help="defaults to the current year")
    w.add_argument("--weeks", type=int, default=4,
                   help="how many recent ISO weeks to attempt (default 4)")
    w.add_argument("--dry-run", action="store_true",
                   help="fetch and report, but write nothing")
    w.set_defaults(func=cmd_weekly_update)

    f = sub.add_parser("forecast", help="compute the yield forecast")
    f.add_argument("--year", type=int, help="defaults to the current year")
    f.set_defaults(func=cmd_forecast)

    c = sub.add_parser("conditions", help="show the latest USDA report figures")
    c.set_defaults(func=cmd_conditions)

    v = sub.add_parser("verify", help="health checks; makes no changes")
    v.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    # The workbook path contains Cyrillic characters; the default Windows
    # console codepage (cp1252) cannot encode them, so any message quoting the
    # path would raise UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
