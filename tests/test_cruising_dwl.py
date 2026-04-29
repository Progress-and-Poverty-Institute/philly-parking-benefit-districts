"""Tests for cruising DWL."""
from __future__ import annotations

import pandas as pd

from phillyparking.welfare.cruising_dwl import hourly_cruising_dwl, annual_cruising_dwl


def test_one_segment_one_hour():
    segments = pd.DataFrame({
        "segment_id": ["s0"],
        "capacity": [10],
        "zone_id": ["ccc"],
    })
    panel = pd.DataFrame({
        "segment_id": ["s0"],
        "hour_of_week": [0],
        "occupancy": [1.0],
    })
    out = hourly_cruising_dwl(panel, segments, target_vacancy=0.15,
                              avg_cruising_minutes=5.0, value_of_time_usd_per_hr=20.0)
    assert len(out) == 1
    assert abs(out["demand_excess"].iloc[0] - 1.5) < 1e-9
    assert abs(out["dwl_usd"].iloc[0] - 2.50) < 1e-9


def test_no_dwl_when_below_threshold():
    segments = pd.DataFrame({"segment_id": ["s0"], "capacity": [10], "zone_id": ["ccc"]})
    panel = pd.DataFrame({"segment_id": ["s0"], "hour_of_week": [0], "occupancy": [0.5]})
    out = hourly_cruising_dwl(panel, segments)
    assert out["dwl_usd"].iloc[0] == 0.0


def test_annual_scaling():
    segments = pd.DataFrame({"segment_id": ["s0"], "capacity": [10], "zone_id": ["ccc"]})
    panel = pd.DataFrame({"segment_id": ["s0"], "hour_of_week": [0], "occupancy": [1.0]})
    out = annual_cruising_dwl(panel, segments, priced_weeks=52)
    assert abs(out["annual_dwl_usd"].iloc[0] - 2.50 * 52) < 1e-6
