"""Audit finding 5 (code part): a fit is refused when the data cannot identify any zone's
elasticity. Audit finding 24: the baseline calibration is absolute, so a segment's occupancy
does not depend on the other segments loaded."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.elasticity.identification import (IdentificationError, check_identification,
                                                     identification_table)
from phillyparking.scenarios.runner import run_scenario
from phillyparking.spatial.synthetic import make_synthetic_segments


def _panel(prices: dict[tuple[str, str], float], hours=range(8, 12)) -> pd.DataFrame:
    """One row per (zone, period, hour) with the given price and some occupancy."""
    rng = np.random.default_rng(0)
    rows = [{"segment_id": f"{z}-1", "zone_id": z, "period": p, "hour_of_week": h,
             "price_usd_per_hr": price, "occupancy": float(rng.uniform(0.3, 0.9))}
            for (z, p), price in prices.items() for h in hours]
    return pd.DataFrame(rows)


def test_one_price_per_zone_identifies_nothing():
    panel = _panel({("ccc", "a"): 4.0, ("cca", "a"): 3.5, ("ucity", "a"): 2.0})
    with pytest.raises(IdentificationError, match="no zone's price elasticity"):
        check_identification(panel)


def test_rate_change_against_an_unchanged_zone_is_identified():
    panel = _panel({("ccc", "a"): 3.0, ("ccc", "b"): 4.0, ("ucity", "a"): 2.0, ("ucity", "b"): 2.0})
    tab = check_identification(panel).set_index("zone_id")["identified"]
    assert tab.to_dict() == {"ccc": True, "ucity": False}


def test_two_changed_zones_without_a_control_are_not_identified_with_a_period_term():
    """2 zones x 2 periods give 4 cell means for alpha x2, eps x2 and one period effect."""
    panel = _panel({("ccc", "a"): 3.0, ("ccc", "b"): 4.0, ("cca", "a"): 2.5, ("cca", "b"): 3.5})
    with pytest.raises(IdentificationError):
        check_identification(panel)
    # Without the period term the same data would be read as identified, which is the
    # confound the period term exists to remove.
    assert identification_table(panel, period_col=None)["identified"].all()


def test_fit_is_refused_before_sampling(monkeypatch):
    """`fit_elasticity_model` raises before importing PyMC when nothing is identified."""
    import sys

    from phillyparking.elasticity.hierarchical_bayes import fit_elasticity_model

    monkeypatch.setitem(sys.modules, "pymc", None)  # any PyMC import would now fail
    panel = _panel({("ccc", "a"): 4.0, ("cca", "a"): 3.5}).assign(neighborhood="Center City")
    with pytest.raises(IdentificationError):
        fit_elasticity_model(panel)
    with pytest.raises(ValueError, match="no panel rows"):
        fit_elasticity_model(panel.assign(occupancy=0.0))


# --- absolute calibration anchors ----------------------------------------------------------

def _peaks(panel: pd.DataFrame) -> pd.Series:
    return panel.groupby("segment_id")["occupancy"].max()


def test_a_segment_baseline_does_not_depend_on_its_companions():
    big = make_synthetic_segments(n=120, seed=42)
    other = make_synthetic_segments(n=63, seed=9)
    alone = _peaks(baseline_occupancy(big.iloc[[5]]))
    inside = _peaks(baseline_occupancy(big))
    mixed = _peaks(baseline_occupancy(pd.concat([big.iloc[[5]], other], ignore_index=True)))
    sid = big["segment_id"].iloc[5]
    assert alone[sid] == pytest.approx(inside[sid], abs=1e-12)
    assert mixed[sid] == pytest.approx(inside[sid], abs=1e-12)


def test_an_extreme_segment_does_not_move_the_others():
    segs = make_synthetic_segments(n=60, seed=1)
    before = _peaks(baseline_occupancy(segs))
    extreme = segs.iloc[[0]].copy()
    extreme["segment_id"] = "EXTREME"
    extreme["jobs_within_200m"] = 1e7
    after = _peaks(baseline_occupancy(pd.concat([segs, extreme], ignore_index=True)))
    assert np.allclose(after.drop("EXTREME").sort_index(), before.sort_index(), atol=1e-12)


def test_covariates_off_the_anchors_scale_are_flagged(caplog):
    segs = make_synthetic_segments(n=40, seed=2)
    segs["jobs_within_200m"] *= 1000  # e.g. a join that returns a different unit
    with caplog.at_level(logging.WARNING):
        panel = baseline_occupancy(segs)
    assert panel.attrs["calibration"]["share_at_cap"] > 0.2
    assert "do not suit these covariates" in caplog.text


def test_nan_covariate_raises():
    segs = make_synthetic_segments(n=10, seed=3)
    segs.loc[2, "pop_density"] = np.nan
    with pytest.raises(ValueError, match="NaN pop_density"):
        baseline_occupancy(segs)


def test_zone_with_zero_occupancy_gets_a_clear_error_from_the_arnott_step():
    segs = make_synthetic_segments(n=30, seed=4)
    panel = baseline_occupancy(segs)
    ucity = segs.loc[segs["zone_id"] == "ucity", "segment_id"]
    panel.loc[panel["segment_id"].isin(ucity), "occupancy"] = 0.0
    with pytest.raises(ValueError, match="'ucity' has zero occupancy"):
        run_scenario("full_pbd", segments=segs, baseline_panel=panel, seed=4)
