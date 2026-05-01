"""Sanity checks for config.py constants — guards against typos in FIPS, acres, offsets."""
from __future__ import annotations

from ec_iowa import config


def test_nine_counties_in_district_60():
    assert len(config.EC_IOWA_COUNTIES) == 9


def test_total_corn_acres_matches_handoff():
    # Handoff §1: total = 1,530,000
    assert config.TOTAL_CORN_ACRES == 1_530_000


def test_tama_excluded():
    assert "19171" not in config.EC_IOWA_COUNTIES


def test_year_blocks_25_rows_apart():
    blocks = config.CROP_PROGRESS_YEAR_BLOCKS
    years = sorted(blocks.keys(), reverse=True)
    for newer, older in zip(years, years[1:]):
        gap = blocks[older]["title"] - blocks[newer]["title"]
        assert gap == 26, f"{newer}->{older} gap is {gap}, expected 26"


def test_gdd_stage_params_have_all_seven_stages():
    expected = {
        "planted", "emerged", "silking", "doughing",
        "dented", "corn_mature", "corn_harvested",
    }
    assert set(config.GDD_STAGE_PARAMS.keys()) == expected


def test_yield_model_excludes_2020():
    assert 2020 in config.YIELD_MODEL["training_excluded_years"]
