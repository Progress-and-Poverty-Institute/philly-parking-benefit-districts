"""The priced-hours mask must reproduce config/zones.yaml hour by hour.

Expected values are re-derived here from the raw YAML with an independent reading of the
`priced_hours` blocks, so the tests fail if the mask code drifts from the config (e.g. a
hard-coded weekday 8-20) and keep passing when the config itself is edited.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import yaml

from phillyparking._config import project_root
from phillyparking.pricing.priced_hours import (
    annual_priced_hours, hourly_prices, priced_mask, weekly_priced_hours,
)

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _raw_zones() -> list[dict]:
    with open(project_root() / "config" / "zones.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["zones"]


def _expected_priced(zone: dict, day_name: str, hour: int) -> bool:
    ph = zone["priced_hours"]
    key = "saturday" if day_name == "sat" else "sunday" if day_name == "sun" else "weekday"
    window = ph.get(key)
    return window is not None and window[0] <= hour < window[1]


ZONES = _raw_zones()


@pytest.mark.parametrize("zone", ZONES, ids=[z["id"] for z in ZONES])
def test_mask_matches_config_every_hour_of_week(zone):
    hours = np.arange(168)
    got = priced_mask(np.full(168, zone["id"], dtype=object), hours)
    expected = np.array([_expected_priced(zone, DAY_NAMES[h // 24], h % 24) for h in hours])
    assert (got == expected).all(), np.flatnonzero(got != expected)


@pytest.mark.parametrize("zone", ZONES, ids=[z["id"] for z in ZONES])
def test_weekly_and_annual_hours_match_config(zone):
    expected = sum(
        _expected_priced(zone, DAY_NAMES[d], h) for d in range(7) for h in range(24)
    )
    assert weekly_priced_hours(zone["id"]) == expected
    assert annual_priced_hours(zone["id"]) == expected * 52


def test_saturday_counts_where_priced_and_sunday_does_not():
    for zone in ZONES:
        sat_noon, sun_noon = 5 * 24 + 12, 6 * 24 + 12
        m = priced_mask(np.array([zone["id"]] * 2, dtype=object), np.array([sat_noon, sun_noon]))
        assert m[0] == (zone["priced_hours"].get("saturday") is not None)
        assert m[1] == (zone["priced_hours"].get("sunday") is not None)


def test_unconfigured_zone_is_never_priced():
    assert not priced_mask(np.full(168, "other", dtype=object), np.arange(168)).any()
    assert weekly_priced_hours("other") == 0


def test_hourly_prices_reject_a_priced_hour_outside_every_band():
    prices = pd.DataFrame({"zone_id": ["ccc"], "band_start": [8], "band_end": [12], "price_usd_per_hr": [4.0]})
    with pytest.raises(ValueError, match="fall in no price band"):
        hourly_prices(prices)


def test_hourly_prices_cover_exactly_the_priced_hours():
    zone_level = pd.DataFrame({"zone_id": [z["id"] for z in ZONES], "price_usd_per_hr": 2.0})
    hp = hourly_prices(zone_level)
    for z in ZONES:
        assert (hp["zone_id"] == z["id"]).sum() == weekly_priced_hours(z["id"])
