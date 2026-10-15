"""Tests for revenue forecasting."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from phillyparking._config import load_config
from phillyparking.revenue.forecast import _project_occupancy, annual_revenue

# A test zone priced weekdays 8-20 only: 60 hours a week.
TEST_HOURS = {"z1": {"weekday": [8, 20], "saturday": None, "sunday": None}}


def _full_week_panel(segment_id: str, occ_priced: float, occ_unpriced: float, priced: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({
        "segment_id": segment_id,
        "hour_of_week": np.arange(168),
        "occupancy": np.where(priced, occ_priced, occ_unpriced),
    })


def test_annual_revenue_trivial():
    segments = pd.DataFrame({"segment_id": ["s0"], "capacity": [10], "zone_id": ["z1"]})
    how = np.arange(168)
    priced = ((how // 24) < 5) & ((how % 24) >= 8) & ((how % 24) < 20)
    panel = _full_week_panel("s0", 0.6, 0.6, priced)
    prices = pd.DataFrame({"zone_id": ["z1"], "price_usd_per_hr": [2.0]})
    result = annual_revenue(segments, panel, prices, hours=TEST_HOURS)
    assert len(result) == 1
    rev = float(result["annual_revenue_usd"].iloc[0])
    assert math.isclose(rev, 0.6 * 10 * 2 * 60 * 52, rel_tol=1e-9)


def test_revenue_hours_derived_from_config():
    """Each configured zone earns over its own zones.yaml hours, and only those.

    Occupancy is 0.5 in priced hours and 1.0 in every unpriced hour, so any leak of
    unpriced hours, a 168-hour mean, or a cross-zone hours figure moves the total.
    """
    zones = load_config("zones")["zones"]
    rows, panels, prices = [], [], []
    for i, z in enumerate(zones):
        sid = f"s{i}"
        rows.append({"segment_id": sid, "capacity": 7 + i, "zone_id": z["id"]})
        how = np.arange(168)
        day, hour = how // 24, how % 24
        priced = np.zeros(168, dtype=bool)
        for key, days in (("weekday", day < 5), ("saturday", day == 5), ("sunday", day == 6)):
            w = z["priced_hours"].get(key)
            if w is not None:
                priced |= days & (hour >= w[0]) & (hour < w[1])
        panels.append(_full_week_panel(sid, 0.5, 1.0, priced))
        prices.append({"zone_id": z["id"], "price_usd_per_hr": float(z["current_rate_usd_per_hr"])})
    segments = pd.DataFrame(rows)
    res = annual_revenue(segments, pd.concat(panels), pd.DataFrame(prices)).set_index("zone_id")

    for i, z in enumerate(zones):
        ph = z["priced_hours"]
        weekly = sum(
            (ph[k][1] - ph[k][0]) * mult
            for k, mult in (("weekday", 5), ("saturday", 1), ("sunday", 1)) if ph.get(k) is not None
        )
        cap = 7 + i
        assert res.loc[z["id"], "capacity_hours"] == pytest.approx(cap * weekly * 52)
        assert res.loc[z["id"], "paid_hours"] == pytest.approx(0.5 * cap * weekly * 52)
        assert res.loc[z["id"], "annual_revenue_usd"] == pytest.approx(
            0.5 * cap * weekly * 52 * z["current_rate_usd_per_hr"]
        )


def test_revenue_is_capacity_weighted_within_zone():
    segments = pd.DataFrame({"segment_id": ["a", "b"], "capacity": [30, 10], "zone_id": ["z1", "z1"]})
    how = np.arange(168)
    priced = ((how // 24) < 5) & ((how % 24) >= 8) & ((how % 24) < 20)
    panel = pd.concat([_full_week_panel("a", 0.9, 0.0, priced), _full_week_panel("b", 0.1, 0.0, priced)])
    prices = pd.DataFrame({"zone_id": ["z1"], "price_usd_per_hr": [1.0]})
    rev = float(annual_revenue(segments, panel, prices, hours=TEST_HOURS)["annual_revenue_usd"].iloc[0])
    assert rev == pytest.approx((0.9 * 30 + 0.1 * 10) * 60 * 52)


def test_hourly_prices_apply_hour_by_hour():
    segments = pd.DataFrame({"segment_id": ["s0"], "capacity": [10], "zone_id": ["z1"]})
    how = np.arange(168)
    priced = ((how // 24) < 5) & ((how % 24) >= 8) & ((how % 24) < 20)
    panel = _full_week_panel("s0", 0.5, 0.5, priced)
    hp = pd.DataFrame({"zone_id": "z1", "hour_of_week": how[priced],
                       "price_usd_per_hr": np.where((how[priced] % 24) < 12, 1.0, 3.0)})
    rev = float(annual_revenue(segments, panel, hp, hours=TEST_HOURS)["annual_revenue_usd"].iloc[0])
    assert rev == pytest.approx(0.5 * 10 * 52 * 5 * (4 * 1.0 + 8 * 3.0))


def test_scenario_projection_constant_elasticity():
    # baseline: occ=0.6, p=2 → new p=3, eps=-0.5 → new occ = 0.6*1.5^-0.5
    occ_old = np.array([0.6] * 100)
    p_old = np.array([2.0] * 100)
    p_new = np.array([3.0] * 100)
    occ_new = _project_occupancy(occ_old, p_old, p_new, -0.5)
    expected_occ = 0.6 * (1.5) ** -0.5
    assert math.isclose(float(occ_new.mean()), expected_occ, rel_tol=1e-6)
