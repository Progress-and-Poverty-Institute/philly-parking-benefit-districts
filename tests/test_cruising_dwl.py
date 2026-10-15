"""Tests for cruising DWL."""
from __future__ import annotations

import pandas as pd
import pytest

from phillyparking.welfare.cruising_dwl import hourly_cruising_dwl, annual_cruising_dwl

MON_NOON = 12        # ccc is priced weekdays 8-20 in zones.yaml
MON_3AM = 3          # unpriced everywhere
SUN_NOON = 6 * 24 + 12


def _one(occ: float, how: int, zone: str = "ccc"):
    segments = pd.DataFrame({"segment_id": ["s0"], "capacity": [10], "zone_id": [zone]})
    panel = pd.DataFrame({"segment_id": ["s0"], "hour_of_week": [how], "occupancy": [occ]})
    return segments, panel


def test_one_segment_one_hour():
    segments, panel = _one(1.0, MON_NOON)
    out = hourly_cruising_dwl(panel, segments, target_vacancy=0.15,
                              avg_cruising_minutes=5.0, value_of_time_usd_per_hr=20.0)
    assert len(out) == 1
    assert abs(out["demand_excess"].iloc[0] - 1.5) < 1e-9
    assert abs(out["dwl_usd"].iloc[0] - 2.50) < 1e-9


def test_no_dwl_when_below_threshold():
    segments, panel = _one(0.5, MON_NOON)
    out = hourly_cruising_dwl(panel, segments)
    assert out["dwl_usd"].iloc[0] == 0.0


@pytest.mark.parametrize("how", [MON_3AM, SUN_NOON])
def test_unpriced_hours_score_zero(how):
    segments, panel = _one(1.0, how)
    assert hourly_cruising_dwl(panel, segments)["dwl_usd"].iloc[0] == 0.0
    assert hourly_cruising_dwl(panel, segments, priced_hours_only=False)["dwl_usd"].iloc[0] > 0.0


def test_unconfigured_zone_scores_zero():
    segments, panel = _one(1.0, MON_NOON, zone="other")
    assert hourly_cruising_dwl(panel, segments)["dwl_usd"].iloc[0] == 0.0


def test_threshold_follows_target_vacancy():
    segments, panel = _one(0.82, MON_NOON)
    assert hourly_cruising_dwl(panel, segments, target_vacancy=0.15)["dwl_usd"].iloc[0] == 0.0
    assert hourly_cruising_dwl(panel, segments, target_vacancy=0.20)["demand_excess"].iloc[0] == pytest.approx(0.2)


def test_annual_scaling():
    segments, panel = _one(1.0, MON_NOON)
    out = annual_cruising_dwl(panel, segments, priced_weeks=52)
    assert abs(out["annual_dwl_usd"].iloc[0] - 2.50 * 52) < 1e-6
