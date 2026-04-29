"""Tests for nested-logit consumer surplus."""
from __future__ import annotations

import pandas as pd

from phillyparking.welfare.consumer_surplus import (
    NestedLogitSpec, utilities, logsum, consumer_surplus_change,
)


def _flat_spec() -> NestedLogitSpec:
    return NestedLogitSpec(
        nests={"all": ["curb", "transit"]},
        nest_lambda={"all": 1.0},
        alpha_price=-0.40,
        beta_walk=-0.10,
        asc={"curb": 0.0, "transit": -0.5},
    )


def _vu(spec, curb_price, transit_price=2.5, walk_curb=2.0, walk_transit=8.0):
    prices = pd.DataFrame({"price_usd": [curb_price, transit_price]}, index=["curb", "transit"])
    walks = pd.DataFrame({"walk_min": [walk_curb, walk_transit]}, index=["curb", "transit"])
    return utilities(spec, prices, walks)


def test_cs_decreases_when_price_rises():
    spec = _flat_spec()
    V_before = _vu(spec, curb_price=2.0)
    V_after = _vu(spec, curb_price=4.0)
    dcs = consumer_surplus_change(spec, V_before, V_after)
    assert dcs < 0


def test_cs_zero_when_no_change():
    spec = _flat_spec()
    V = _vu(spec, curb_price=2.0)
    assert abs(consumer_surplus_change(spec, V, V)) < 1e-12


def test_cs_magnitude_reasonable():
    spec = _flat_spec()
    V_before = _vu(spec, curb_price=2.0)
    V_after = _vu(spec, curb_price=3.0)
    dcs = consumer_surplus_change(spec, V_before, V_after)
    assert -2.0 < dcs < 0.0


def test_logsum_finite():
    spec = _flat_spec()
    V = _vu(spec, curb_price=2.0)
    assert abs(logsum(spec, V)) < 100.0
