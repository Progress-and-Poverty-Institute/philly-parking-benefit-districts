"""Tests for the panel-level price response (`apply_elasticity`)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phillyparking.demand.response import demand_factor
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
    out = apply_elasticity(base, new, elasticity=-0.5, reference_price=2.0)
    expected = 0.6 * float(demand_factor(4.0, 2.0, -0.5, 2.0))
    assert float(out["occupancy"].iloc[0]) == pytest.approx(expected, abs=1e-9)
    assert expected == pytest.approx(0.6 * np.exp(-0.5))   # the exponential form at p_ref = 2


def test_apply_elasticity_needs_the_reference_price_and_reads_it_per_zone():
    base = pd.DataFrame({"segment_id": ["s1", "s2"], "zone_id": ["ccc", "cca"], "hour_of_week": [12, 12],
                         "occupancy": [0.6, 0.6], "price_usd_per_hr": [4.0, 3.5]})
    new = pd.DataFrame({"zone_id": ["ccc", "cca"], "price_usd_per_hr": [5.0, 4.5]})
    with pytest.raises(ValueError, match="reference_price"):
        apply_elasticity(base, new, elasticity=-0.4)
    ref = pd.DataFrame({"zone_id": ["ccc", "cca"], "price_usd_per_hr": [4.0, 3.5]})
    out = apply_elasticity(base, new, elasticity=-0.4, reference_price=ref)
    assert out["occupancy"].tolist() == pytest.approx([0.6 * np.exp(-0.4 * 1.0 / 4.0), 0.6 * np.exp(-0.4 * 1.0 / 3.5)])
    with pytest.raises(ValueError, match="no reference price"):
        apply_elasticity(base, new, elasticity=-0.4, reference_price=ref.iloc[:1])
    # A zone the table does not cover is fine while its price does not move.
    held = apply_elasticity(base, new.iloc[:1], elasticity=-0.4, reference_price=ref.iloc[:1])
    assert held["occupancy"].iloc[1] == 0.6


def test_apply_elasticity_clipped_to_unit_interval():
    base = pd.DataFrame({
        "segment_id": ["s1"],
        "zone_id": ["ccc"],
        "hour_of_week": [12],
        "occupancy": [0.95],
        "price": [4.0],
    })
    new = pd.DataFrame({"segment_id": ["s1"], "hour_of_week": [12], "price": [0.5]})
    out = apply_elasticity(base, new, elasticity=-1.0, reference_price=4.0)
    assert 0.0 <= float(out["occupancy"].iloc[0]) <= 1.0


def test_apply_elasticity_only_in_priced_hours():
    # ccc: Monday 03:00 and Sunday noon are unpriced, Monday noon and Saturday noon priced.
    hours = [3, 6 * 24 + 12, 12, 5 * 24 + 12]
    base = pd.DataFrame({
        "segment_id": "s1", "zone_id": "ccc", "hour_of_week": hours,
        "occupancy": 0.6, "price_usd_per_hr": 2.0,
    })
    new = pd.DataFrame({"zone_id": ["ccc"], "price_usd_per_hr": [4.0]})
    out = apply_elasticity(base, new, elasticity=-0.5, reference_price=2.0)
    moved = 0.6 * float(demand_factor(4.0, 2.0, -0.5, 2.0))
    assert out["occupancy"].tolist() == pytest.approx([0.6, 0.6, moved, moved])
    everywhere = apply_elasticity(base, new, elasticity=-0.5, priced_hours_only=False, reference_price=2.0)
    assert everywhere["occupancy"].tolist() == pytest.approx([moved] * 4)


def test_apply_elasticity_needs_zone_for_the_mask():
    base = pd.DataFrame({"segment_id": ["s1"], "hour_of_week": [12], "occupancy": [0.6], "price": [2.0]})
    new = pd.DataFrame({"segment_id": ["s1"], "price": [4.0]})
    with pytest.raises(ValueError, match="zone_id"):
        apply_elasticity(base, new, elasticity=-0.5, reference_price=2.0)


def test_get_scenario_and_all():
    assert get_scenario("central").elasticity == pytest.approx(-0.40)
    names = {s.name for s in all_scenarios()}
    assert names == {"pessimistic", "central", "optimistic"}
