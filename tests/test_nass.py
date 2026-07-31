"""Tests for the USDA Crop Progress report parser.

Uses a fixture excerpt rather than the network, so these run offline and pin
the exact table shapes USDA publishes.
"""
from __future__ import annotations

import pytest

from ec_iowa import nass

# Verbatim excerpt from the 2026-07-27 release (prog3026.txt), trimmed.
REPORT = """
Corn Condition - Selected States: Week Ending July 26, 2026
[These 18 States planted 91% of the 2025 corn acreage]
----------------------------------------------------------------------------
      State     : Very poor :   Poor    :   Fair    :   Good    : Excellent
----------------------------------------------------------------------------
                :                          percent
                :
Illinois .......:     3          10          27          47          13
Iowa ...........:     1           4          15          61          19
Kansas .........:     5           8          23          50          14

Corn Silking - Selected States
[These 18 States planted 91% of the 2025 corn acreage]
-----------------------------------------------------------------
                 :            Week ending            :
                 :-----------------------------------:
      State      : July 26,  : July 19,  : July 26,  : 2021-2025
                 :   2025    :   2026    :   2026    :  Average
-----------------------------------------------------------------
Illinois ........:    88          79          91          86
Iowa ............:    81          72          87          80

Corn Dough - Selected States
[These 18 States planted 91% of the 2025 corn acreage]
------------------------------------------------------------------------
                :               Week ending               :
                :-----------------------------------------:
      State     :  July 26,   :  July 19,   :  July 26,   :  2021-2025
                :    2025     :    2026     :    2026     :   Average
------------------------------------------------------------------------
Illinois .......:     35            11           31            29
Iowa ...........:     32             8           28            25
"""


def test_condition_parses_all_five_categories():
    c = nass.iowa_condition(REPORT)
    assert (c.very_poor, c.poor, c.fair, c.good, c.excellent) == (1, 4, 15, 61, 19)


def test_condition_categories_sum_to_100():
    c = nass.iowa_condition(REPORT)
    total = c.very_poor + c.poor + c.fair + c.good + c.excellent
    assert total == 100


def test_good_excellent_and_poor_fair():
    c = nass.iowa_condition(REPORT)
    assert c.good_excellent == 80          # 61 + 19
    assert c.poor_fair == 19               # 4 + 15 — excludes Very Poor
    assert c.very_poor not in (c.poor_fair,)


def test_condition_captures_week_ending():
    assert nass.iowa_condition(REPORT).week_ending == "July 26, 2026"


def test_progress_columns_are_not_misread():
    """The first number on the row is LAST YEAR'S, not this week's.

    Misreading this once produced a false 'model is 8pp hot' conclusion about
    silking.
    """
    p = nass.iowa_progress("Silking", REPORT)
    assert p.last_year == 81
    assert p.last_week == 72
    assert p.this_week == 87        # NOT 81
    assert p.five_year_avg == 80


def test_dough_progress():
    p = nass.iowa_progress("Dough", REPORT)
    assert (p.last_week, p.this_week) == (8, 28)


def test_unreported_stage_raises():
    with pytest.raises(nass.NassError):
        nass.iowa_progress("Dent", REPORT)


def test_missing_condition_table_raises():
    with pytest.raises(nass.NassError):
        nass.iowa_condition("no tables here")
