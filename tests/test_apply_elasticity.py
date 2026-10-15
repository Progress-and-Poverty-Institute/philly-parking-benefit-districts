"""Tests for constant-elasticity demand application."""
from __future__ import annotations

import pandas as pd
import pytest

from phillyparking.elasticity.scenarios import (
    all_scenarios,
    apply_elasticity,
    get_scenario,
)


def test_apply_elasticity_basic():
    base = pd.DataFrame({
        "segment_id": ["s1"],
        "zone_id": ["ccc"],
        "hour_of_week": [12],
        "occupancy": [0.6],
        "price": [2.0],
    })
    new = pd.DataFrame({
        "segment_id": ["s1"],
        "hour_of_week": [12],
        "price": [4.0],
    })
    out = apply_elasticity(base, new, elasticity=-0.5)
    expected = 0.6 * (4.0 / 2.0) ** -0.5
    assert float(out["occupancy"].iloc[0]) == pytest.approx(expected, abs=1e-9)


def test_apply_elasticity_clipped_to_unit_interval():
    base = pd.DataFrame({
        "segment_id": ["s1"],
        "zone_id": ["ccc"],
        "hour_of_week": [12],
        "occupancy": [0.95],
        "price": [4.0],
    })
    new = pd.DataFrame({"segment_id": ["s1"], "hour_of_week": [12], "price": [0.5]})
    out = apply_elasticity(base, new, elasticity=-1.0)
    assert 0.0 <= float(out["occupancy"].iloc[0]) <= 1.0


def test_apply_elasticity_only_in_priced_hours():
    # ccc: Monday 03:00 and Sunday noon are unpriced, Monday noon and Saturday noon priced.
    hours = [3, 6 * 24 + 12, 12, 5 * 24 + 12]
    base = pd.DataFrame({
        "segment_id": "s1", "zone_id": "ccc", "hour_of_week": hours,
        "occupancy": 0.6, "price_usd_per_hr": 2.0,
    })
    new = pd.DataFrame({"zone_id": ["ccc"], "price_usd_per_hr": [4.0]})
    out = apply_elasticity(base, new, elasticity=-0.5)
    moved = 0.6 * 2.0 ** -0.5
    assert out["occupancy"].tolist() == pytest.approx([0.6, 0.6, moved, moved])
    everywhere = apply_elasticity(base, new, elasticity=-0.5, priced_hours_only=False)
    assert everywhere["occupancy"].tolist() == pytest.approx([moved] * 4)


def test_apply_elasticity_needs_zone_for_the_mask():
    base = pd.DataFrame({"segment_id": ["s1"], "hour_of_week": [12], "occupancy": [0.6], "price": [2.0]})
    new = pd.DataFrame({"segment_id": ["s1"], "price": [4.0]})
    with pytest.raises(ValueError, match="zone_id"):
        apply_elasticity(base, new, elasticity=-0.5)


def test_get_scenario_and_all():
    assert get_scenario("central").elasticity == pytest.approx(-0.40)
    names = {s.name for s in all_scenarios()}
    assert names == {"pessimistic", "central", "optimistic"}
