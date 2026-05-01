"""Command-line entry point.

Subcommands (per handoff §9, Phase 4):
  weekly-update --year YYYY --week WW
  backfill      --year YYYY --start-week WW --end-week WW
  verify
  forecast      --year YYYY

All subcommands are stubs until the underlying modules are implemented.
"""
from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ec-iowa", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=False)

    wu = sub.add_parser("weekly-update", help="Run CASMA + NOAA fetchers for one week")
    wu.add_argument("--year", type=int, required=True)
    wu.add_argument("--week", type=int, required=True)

    bf = sub.add_parser("backfill", help="Run weekly-update across a range")
    bf.add_argument("--year", type=int, required=True)
    bf.add_argument("--start-week", type=int, required=True)
    bf.add_argument("--end-week", type=int, required=True)

    sub.add_parser("verify", help="Recalc workbook and report formula errors")

    fc = sub.add_parser("forecast", help="Run yield model with current inputs")
    fc.add_argument("--year", type=int, required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command is None:
        _build_parser().print_help()
        return 0
    print(f"[stub] command '{args.command}' is not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
