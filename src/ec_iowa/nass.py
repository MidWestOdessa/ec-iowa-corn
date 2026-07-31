"""USDA Crop Progress report client.

NASS cut the *district*-level breakdown, but the national Crop Progress report
still publishes weekly and carries a **state**-level Iowa row. We use it for:

  * condition ratings (G+E, P+F) -> written to the workbook's state rows
  * stage progress (silking, dough, dent) -> **cross-check only**, never to
    populate a district cell (see MODEL_HANDOFF.md, convention C3)

Fetched over plain HTTP from USDA ESMIS. Notes on why this host:
  * www.nass.usda.gov  -> 403 to scrapers
  * quickstats API     -> 401 without a key
  * esmis.nal.usda.gov -> works, no auth

Released Mondays ~3-4pm CST for the week ending the prior Sunday.

Public API:
    latest_report_url()            -> str
    fetch_report(url=None)         -> ReportText
    iowa_condition(report=None)    -> Condition
    iowa_progress(stage, report=None) -> Progress
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests

ESMIS_BASE = "https://esmis.nal.usda.gov"
PUBLICATION_URL = f"{ESMIS_BASE}/publication/crop-progress"
_UA = {"User-Agent": "Mozilla/5.0 (ec_iowa research)"}

# Progress tables ("Corn Silking", "Corn Dough", ...) are four numeric columns:
#   last year | last week | this week | 5-year average
# The FIRST number on the Iowa row is LAST YEAR'S, not this week's. Misreading
# this produced a false conclusion once; see MODEL_HANDOFF.md §5.3.
_PROGRESS_COLUMNS = ("last_year", "last_week", "this_week", "five_year_avg")


class NassError(RuntimeError):
    pass


@dataclass(frozen=True)
class Condition:
    """Iowa corn condition, one weekly observation."""
    very_poor: int
    poor: int
    fair: int
    good: int
    excellent: int
    week_ending: str | None = None

    @property
    def good_excellent(self) -> int:
        """G+E — written to the workbook's ge_state row."""
        return self.good + self.excellent

    @property
    def poor_fair(self) -> int:
        """P+F. Excludes Very Poor, matching the workbook's convention."""
        return self.poor + self.fair

    @property
    def breakdown(self) -> str:
        return (f"VP={self.very_poor}% P={self.poor}% F={self.fair}% "
                f"G={self.good}% E={self.excellent}%")


@dataclass(frozen=True)
class Progress:
    """Iowa stage progress. Cross-check only — never write to a district cell."""
    stage: str
    last_year: int | None
    last_week: int | None
    this_week: int | None
    five_year_avg: int | None


def latest_report_url() -> str:
    """URL of the most recent Crop Progress report in plain-text form."""
    r = requests.get(PUBLICATION_URL, headers=_UA, timeout=30)
    if r.status_code != 200:
        raise NassError(f"publication page returned HTTP {r.status_code}")
    links = re.findall(r'href="(/sites/default/release-files/[^"]+\.txt)"', r.text)
    if not links:
        raise NassError("no .txt release links found on the publication page")
    return ESMIS_BASE + links[0]          # newest first


def fetch_report(url: str | None = None) -> str:
    """Full text of a Crop Progress report (defaults to the latest)."""
    url = url or latest_report_url()
    r = requests.get(url, headers=_UA, timeout=30)
    if r.status_code != 200:
        raise NassError(f"report fetch returned HTTP {r.status_code}")
    return r.text


def _iowa_row(report: str, header_pattern: str) -> tuple[str, str] | None:
    """Return (section header line, Iowa data line) for a named table."""
    lines = report.split("\n")
    i = next((k for k, l in enumerate(lines)
              if re.search(header_pattern, l, re.IGNORECASE)), -1)
    if i < 0:
        return None
    iowa = next((l for l in lines[i:i + 30] if re.match(r"\s*Iowa", l)), None)
    return (lines[i].strip(), iowa) if iowa else None


def iowa_condition(report: str | None = None) -> Condition:
    """Parse the 'Corn Condition - Selected States' table."""
    report = report if report is not None else fetch_report()
    found = _iowa_row(report, r"Corn Condition")
    if not found:
        raise NassError("no 'Corn Condition' table in this report")
    header, iowa = found
    nums = [int(n) for n in re.findall(r"\d+", iowa)]
    if len(nums) < 5:
        raise NassError(f"expected 5 condition values, parsed {nums!r}")
    m = re.search(r"Week Ending\s+(.+?)\s*$", header, re.IGNORECASE)
    return Condition(*nums[:5], week_ending=m.group(1) if m else None)


def iowa_progress(stage: str, report: str | None = None) -> Progress:
    """Parse a progress table. `stage` is matched loosely, e.g. 'dough', 'silk'.

    Returns all four columns; use `.this_week` for the current value. A stage
    that has not started yet simply has no table — that raises NassError.
    """
    report = report if report is not None else fetch_report()
    found = _iowa_row(report, rf"Corn {re.escape(stage)}")
    if not found:
        raise NassError(f"no 'Corn {stage}' table — stage likely not yet reported")
    _, iowa = found
    nums = [int(n) for n in re.findall(r"\d+", iowa)]
    vals: list[int | None] = list(nums[:4]) + [None] * (4 - len(nums[:4]))
    return Progress(stage, *vals)
