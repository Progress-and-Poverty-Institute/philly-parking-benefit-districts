"""Chatman-Manville targeting rules and sweep: one implementation, paired runs, welfare, per-cell tables."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phillyparking._config import load_config
from phillyparking.pricing import targeting_rules as tr
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.seattle_rule import load_seattle_config
from phillyparking.scenarios import cm_sweep
from phillyparking.scenarios.cm_sweep import (
    cell_table, chatman_manville_sweep, load_sweep, ordering_violations, paired_table,
    save_sweep, window_dependence,
)
from phillyparking.spatial.synthetic import make_synthetic_segments

SMALL = dict(elasticity_values=[-0.2, -0.5], start_occupancy=[0.75], block_dispersion=[0.0, 0.3],
             observation_noise=[0.0, 0.1], n_replications=3, rolls_forward_years=4)
SEGS = make_synthetic_segments(n=30, seed=1)


def _panel(occ_fn, zone: str = "ccc", price: float = 2.0, n_seg: int = 2) -> pd.DataFrame:
    """Segment-hour panel for one zone: occupancy = occ_fn(hour_of_week), uniform price."""
    hours = np.arange(168)
    rows = [{"segment_id": f"S{i}", "zone_id": zone, "hour_of_week": h, "occupancy": float(occ_fn(h)),
             "capacity": 10.0, "price_usd_per_hr": price}
            for i in range(n_seg) for h in hours]
    return pd.DataFrame(rows)


def _weekday_midday(h):  # inside ccc's priced hours (weekday 8-20) and the 12-16 band
    return (h // 24) < 5 and 12 <= (h % 24) < 16


def _price(prices: pd.DataFrame, zone="ccc") -> float:
    return float(prices.loc[prices["zone_id"] == zone, "price_usd_per_hr"].iloc[0])


def _band_price(prices: pd.DataFrame, start: int, end: int, zone="ccc") -> float:
    hod = prices["hour_of_week"] % 24
    sel = prices[(prices["zone_id"] == zone) & (hod >= start) & (hod < end)]["price_usd_per_hr"]
    assert sel.nunique() == 1
    return float(sel.iloc[0])


# --------------------------------------------------------------------------- rules


def test_step_for_follows_the_band():
    cfg = tr.load_targeting_config()
    assert tr.step_for(cfg.occ_high + 0.01, cfg) == cfg.step_usd
    assert tr.step_for(cfg.occ_low - 0.01, cfg) == -cfg.step_usd
    assert tr.step_for(cfg.occ_low, cfg) == 0.0 == tr.step_for(cfg.occ_high, cfg)


def test_chatman_manville_band_is_the_seattle_band():
    cm, sea = tr.load_targeting_config(), load_seattle_config()
    assert (cm.occ_low, cm.occ_high, cm.step_usd) == (sea.occ_low, sea.occ_high, sea.step_usd)


def test_every_configured_rule_and_comparison_is_implemented():
    cfg = load_config("scenarios")["chatman_manville_sweep"]
    assert set(cfg["rules"]) <= set(tr.RULE_NAMES)
    assert all(a in cfg["rules"] and b in cfg["rules"] for a, b in cfg["comparisons"])
    with pytest.raises(ValueError):
        tr.review("not_a_rule", _panel(lambda h: 0.5))


def test_peak_rule_raises_where_the_mean_says_cut():
    # One priced hour in ten at 0.95, the rest low: q95 > 0.85 but the mean is far below 0.70.
    priced = frame_priced_mask(_panel(lambda h: 0.0))
    panel = _panel(lambda h: (0.95 if h % 10 == 0 else 0.30) if priced[h] else 0.1)
    assert _price(tr.review("peak_zone", panel)) == 2.5
    assert _price(tr.review("mean_zone", panel)) == 1.5


def test_zone_rules_read_only_priced_hours_and_the_168_hour_rules_read_all():
    # 0.78 in ccc's priced hours, 0.20 when the meter is off: the priced mean is inside the band.
    priced = frame_priced_mask(_panel(lambda h: 0.0))
    panel = _panel(lambda h: 0.78 if priced[h] else 0.20)
    assert panel["occupancy"].mean() < 0.70
    assert _price(tr.review("mean_zone", panel)) == 2.0
    assert _price(tr.review("peak_zone", panel)) == 2.0
    assert _price(tr.review("avg_occupancy", panel)) == 1.5
    assert _price(tr.review("min_vacancy_peak", panel)) == 2.0


def test_zone_rules_take_the_rate_in_force_from_priced_rows():
    """A panel can carry a stale price on meter-off rows; the review must not read it."""
    priced = frame_priced_mask(_panel(lambda h: 0.0))
    panel = _panel(lambda h: 0.78)
    panel["price_usd_per_hr"] = np.where(priced, 3.0, 2.0)
    assert _price(tr.review("mean_zone", panel)) == 3.0      # hold at the priced-row rate
    assert _price(tr.review("peak_zone", panel)) == 3.0


def test_band_rules_move_each_band_on_its_own_statistic():
    # Midday band 12-16 hot at the top (q95 > 0.85, mean < 0.85), morning band 8-12 cold.
    priced = frame_priced_mask(_panel(lambda h: 0.0))

    def occ(h):
        if not priced[h]:
            return 0.1
        hod = h % 24
        if 12 <= hod < 16:
            return 0.95 if (h // 24) == 0 else 0.75   # Monday hot, other days inside the band
        return 0.40
    panel = _panel(occ)
    peak = tr.review("peak_band", panel)
    mean = tr.review("mean_band", panel)
    assert set(peak["hour_of_week"]) <= set(np.flatnonzero(priced))
    assert _band_price(peak, 12, 16) == 2.5 and _band_price(mean, 12, 16) == 2.0
    assert _band_price(peak, 8, 12) == 1.5 and _band_price(mean, 8, 12) == 1.5


def test_rules_respect_zone_floor_and_hold_unpriced_zones():
    cold = _panel(lambda h: 0.20, price=1.0)  # ccc floor is 1.00
    for rule in ("peak_zone", "mean_zone", "min_vacancy_peak", "avg_occupancy"):
        assert _price(tr.review(rule, cold)) == 1.0
    assert (tr.review("peak_band", cold)["price_usd_per_hr"] == 1.0).all()
    cold_other = _panel(lambda h: 0.20, zone="other", price=2.0)  # not in zones.yaml: never priced
    assert _price(tr.review("mean_zone", cold_other), "other") == 2.0
    assert _price(tr.review("avg_occupancy", cold_other), "other") == 1.5  # looks at all 168 hours
    assert tr.review("mean_band", cold_other).empty
    assert tr.review("seattle_rule", cold_other).empty


def test_seattle_rule_sets_a_price_per_band_on_priced_hours_only():
    priced = frame_priced_mask(_panel(lambda h: 0.0))
    panel = _panel(lambda h: 0.0 if not priced[h] else (0.97 if 12 <= h % 24 < 16 else 0.40))
    out = tr.review("seattle_rule", panel)
    assert set(out["hour_of_week"]) <= set(np.flatnonzero(priced))
    assert _band_price(out, 12, 16) == 3.0      # >= 0.95 band mean -> two steps
    assert _band_price(out, 8, 12) == 1.5       # < 0.70 -> one step down


# --------------------------------------------------------------------------- sweep


@pytest.fixture(scope="module")
def sweep():
    return chatman_manville_sweep(segments=SEGS, **SMALL)


def test_sweep_grid_and_start_state(sweep):
    cfg = load_config("scenarios")["chatman_manville_sweep"]
    n_cells = 2 * 1 * 2 * 2
    assert len(sweep) == n_cells * len(cfg["rules"]) * 3 * 4
    assert set(sweep["rule"]) == set(cfg["rules"])
    assert sweep.attrs["provenance"]["segment_source"]["kind"] == "synthetic_fixture"
    assert sweep.attrs["provenance"]["segment_source"]["n_priced_segments"] == int(
        SEGS["zone_id"].isin({z["id"] for z in load_config("zones")["zones"]}).sum())


def test_each_zone_starts_at_the_configured_mean_occupancy():
    """The level axis pins each zone's priced-hour mean occupancy at the start price."""
    seen = {}
    real = cm_sweep.review

    def spy(rule, panel, cfg=None):
        if "start" not in seen:  # the first review sees year-0 occupancy with no noise
            seen["start"] = panel.loc[frame_priced_mask(panel)].groupby("zone_id")["occupancy"].mean()
        return real(rule, panel, cfg)

    import unittest.mock as um
    with um.patch.object(cm_sweep, "review", spy):
        chatman_manville_sweep(segments=SEGS, elasticity_values=[-0.4], start_occupancy=[0.62],
                               block_dispersion=[0.5], observation_noise=[0.0], n_replications=1,
                               rolls_forward_years=1, rules=["mean_zone"])
    assert np.allclose(seen["start"].to_numpy(), 0.62, atol=1e-5)


def test_sweep_uses_the_shared_rule_implementation(monkeypatch):
    """Defect injection: if the sweep re-implemented the rules, a spy on `review` would never fire."""
    calls = []

    def hold(rule, panel, cfg=None):
        calls.append(rule)
        return panel[["zone_id", "price_usd_per_hr"]].drop_duplicates("zone_id")

    monkeypatch.setattr(cm_sweep, "review", hold)
    s = chatman_manville_sweep(segments=SEGS, elasticity_values=[-0.4], start_occupancy=[0.75],
                               block_dispersion=[0.0], observation_noise=[0.0], n_replications=1,
                               rolls_forward_years=2, rules=["peak_zone", "mean_zone"])
    assert calls == ["peak_zone"] * 2 + ["mean_zone"] * 2
    a, b = (s[s.rule == r].drop(columns="rule").reset_index(drop=True) for r in ("peak_zone", "mean_zone"))
    pd.testing.assert_frame_equal(a, b)
    assert (s["welfare_change"] == 0).all() and (s["cs_change"] == 0).all()  # holding changes nothing


def test_closed_form_demand_is_apply_elasticity_applied_step_by_step():
    """d = d0 x demand_level(p) is what `apply_elasticity` gives after any sequence of steps."""
    from phillyparking.demand.response import demand_level
    from phillyparking.elasticity.scenarios import apply_elasticity
    panel = _panel(lambda h: 0.6, n_seg=3)
    priced = frame_priced_mask(panel)
    stepped = panel.copy()
    for _ in range(3):
        step = stepped[["zone_id", "price_usd_per_hr"]].drop_duplicates("zone_id")
        step["price_usd_per_hr"] += 0.5
        stepped = apply_elasticity(stepped, step, -0.4, reference_price=2.0)
    closed = 0.6 * float(demand_level(2.0 + 1.5, -0.4, 2.0))
    assert np.allclose(stepped.loc[priced, "occupancy"], closed, atol=1e-12)
    assert np.allclose(stepped.loc[~priced, "occupancy"], 0.6)  # meter-off hours do not respond


def test_block_dispersion_and_observation_noise_are_paired_draws():
    np.testing.assert_array_equal(cm_sweep._block_draw(7, 0, 50), cm_sweep._block_draw(7, 0, 50))
    assert not np.array_equal(cm_sweep._block_draw(7, 0, 50), cm_sweep._block_draw(7, 1, 50))
    assert not np.array_equal(cm_sweep._observation_draw(7, 0, 1, 50), cm_sweep._observation_draw(7, 0, 2, 50))
    seen = []
    real = cm_sweep.review

    def spy(rule, panel, cfg=None):
        seen.append(panel["occupancy"].to_numpy().copy())
        return real(rule, panel, cfg)

    import unittest.mock as um
    with um.patch.object(cm_sweep, "review", spy):
        s = chatman_manville_sweep(segments=SEGS, elasticity_values=[-0.4], start_occupancy=[0.75],
                                   block_dispersion=[0.0, 0.3], observation_noise=[0.0, 0.1],
                                   n_replications=2, rolls_forward_years=1, rules=["peak_zone"])
    g = s.groupby(["block_dispersion", "observation_noise"])["revenue"].nunique()
    assert g[(0.0, 0.0)] == 1          # no draw reaches a noise-free, undispersed cell
    assert g[(0.3, 0.0)] == 2          # the block draw differs between replications
    # Reviews in order: rep 0 (tau 0: sigma 0, 0.1; tau 0.3: sigma 0, 0.1), then rep 1.
    assert np.array_equal(seen[0], seen[4])              # tau 0, sigma 0: identical across reps
    assert not np.array_equal(seen[1], seen[5])          # sigma 0.1: the review sees a different draw
    assert np.array_equal(seen[1] - seen[0], seen[1] - seen[0])
    assert not np.array_equal(seen[1] - seen[0], seen[5] - seen[4])


def test_observation_noise_biases_the_peak_statistic_not_the_mean():
    """What the rule reviews is truth + noise: a q95 of a noisy panel is above the true q95,
    a mean is not. On a flat 0.80 panel the noisy peak rule raises and the mean rule holds."""
    cfg = tr.load_targeting_config()
    panel = _panel(lambda h: 0.80, n_seg=20)
    z = np.random.default_rng(3).standard_normal(len(panel))
    noisy = panel.assign(occupancy=np.clip(panel["occupancy"] + 0.15 * z, 0.0, 1.0))
    assert tr._zone_statistic(panel, "peak_zone", cfg)["ccc"] == pytest.approx(0.80)
    assert tr._zone_statistic(noisy, "peak_zone", cfg)["ccc"] > cfg.occ_high
    assert tr._zone_statistic(noisy, "mean_zone", cfg)["ccc"] == pytest.approx(0.80, abs=0.01)
    assert _price(tr.review("peak_zone", noisy)) == 2.5 and _price(tr.review("peak_zone", panel)) == 2.0
    assert _price(tr.review("mean_zone", noisy)) == 2.0


def test_welfare_is_surplus_plus_revenue_minus_search_cost(sweep):
    """The start levels cancel between two rules on the same draw, so the identity is checkable."""
    keys = cm_sweep.AXES + ["replication", "year"]
    a = sweep[sweep.rule == "peak_zone"].set_index(keys)
    b = sweep[sweep.rule == "mean_zone"].set_index(keys).reindex(a.index)
    lhs = a["welfare_change"] - b["welfare_change"]
    rhs = (a["cs_change"] - b["cs_change"]) + (a["revenue"] - b["revenue"]) - (a["search_cost"] - b["search_cost"])
    assert np.allclose(lhs, rhs, rtol=1e-9, atol=1e-6)
    assert (a["search_cost"] > 0).all() and (a["revenue"] > 0).all()
    minutes = cm_sweep.load_search_cost_config().minutes_at_reference
    assert np.allclose(a["search_cost_per_minute"] * minutes, a["search_cost"])


def test_old_comparator_ordering_is_an_identity_on_priced_metrics():
    """mean <= q95 over the same window: the mean rule never has less proxy DWL or more revenue."""
    s = chatman_manville_sweep(segments=SEGS, elasticity_values=[-0.4], start_occupancy=[0.75],
                               block_dispersion=[0.0, 0.6], observation_noise=[0.0], n_replications=2,
                               rolls_forward_years=3, rules=["min_vacancy_peak", "avg_occupancy",
                                                             "peak_zone", "mean_zone"])
    assert ordering_violations(s).empty
    assert ordering_violations(s, "mean_zone", "peak_zone").empty


def test_ordering_check_fails_when_the_comparator_statistic_exceeds_the_peak(monkeypatch):
    """Defect injection: an 'average' that is really the max can raise what the peak rule holds."""
    real = tr._zone_statistic

    def broken(panel, rule, cfg):
        if rule == "avg_occupancy":
            return panel["occupancy"].groupby(panel["zone_id"].to_numpy()).max().to_dict()
        return real(panel, rule, cfg)

    monkeypatch.setattr(tr, "_zone_statistic", broken)
    # A start level low enough that the q95 rule holds or cuts while the max raises.
    bad = chatman_manville_sweep(segments=SEGS, elasticity_values=[-0.4], start_occupancy=[0.4],
                                 block_dispersion=[0.0], observation_noise=[0.0], n_replications=1,
                                 rolls_forward_years=2, rules=["min_vacancy_peak", "avg_occupancy"])
    assert not ordering_violations(bad).empty


def test_welfare_ordering_is_not_an_identity():
    """The cruising cost level decides which rule gives more welfare: cheap cruising favours the
    mean rule, costly cruising the peak rule. Both signs occur on the same price paths."""
    s = chatman_manville_sweep(segments=SEGS, elasticity_values=[-0.4], start_occupancy=[0.75],
                               block_dispersion=[0.3], observation_noise=[0.0], n_replications=1,
                               rolls_forward_years=6, rules=["peak_zone", "mean_zone"])
    p = paired_table(s, [("mean_zone", "peak_zone")])
    last = p[p.year == 6].iloc[0]
    assert last["share_comparator_searches_more"] == 1.0   # the mean rule prices lower
    c_star = last["breakeven_minutes_median"]
    assert 0 < c_star < 60
    cfg = cm_sweep.load_search_cost_config()
    gain = last["cs_diff_median"] + last["revenue_diff_median"]
    per_min = last["search_cost_diff_median"] / cfg.minutes_at_reference
    assert gain - 0.5 * c_star * per_min > 0 > gain - 2.0 * c_star * per_min


# --------------------------------------------------------------------------- provenance


def test_sweep_records_and_roundtrips_provenance(sweep, tmp_path):
    prov = sweep.attrs["provenance"]
    assert prov["segment_source"]["kind"] == "synthetic_fixture"
    assert prov["seed"] == 42 and prov["n_replications"] == 3
    assert prov["start_occupancy"] == [0.75] and prov["block_dispersion"] == [0.0, 0.3]
    assert {"scenarios", "pricing_rules", "zones"} <= set(prov["config_sha256"])
    assert prov["search_cost"]["minutes_at_reference"] == cm_sweep.load_search_cost_config().minutes_at_reference
    path = save_sweep(sweep, tmp_path / "cm.parquet")
    assert path.with_suffix(".meta.json").exists()
    back = load_sweep(path)
    assert back.attrs["provenance"] == prov
    pd.testing.assert_frame_equal(back.reset_index(drop=True), sweep.reset_index(drop=True), check_like=True)


def test_tracked_sweep_carries_provenance_for_a_fixture_it_names():
    from phillyparking._config import outputs_dir

    path = outputs_dir() / "tables" / "cm_sweep.parquet"
    if not path.exists():
        pytest.skip("no tracked sweep")
    prov = load_sweep(path).attrs.get("provenance")
    cfg = load_config("scenarios")["chatman_manville_sweep"]
    assert prov and prov["segment_source"]["kind"] != "unknown"
    assert prov["n_replications"] == cfg["n_replications"]
    assert prov["rules"] == cfg["rules"] and prov["start_occupancy"] == cfg["start_occupancy"]


# --------------------------------------------------------------------------- summaries


def _tiny() -> pd.DataFrame:
    rows = []
    for rep, (ref_cost, ref_rev) in enumerate([(10.0, 100.0), (20.0, 100.0), (0.0, 100.0)]):
        for rule, cost, rev, cs in (("peak_zone", ref_cost, ref_rev, -10.0),
                                    ("a", 5 * ref_cost + 1, 50.0, 40.0), ("b", ref_cost / 2, 150.0, -60.0)):
            rows.append({"elasticity": -0.4, "start_occupancy": 0.75, "block_dispersion": 0.0,
                         "observation_noise": 0.1, "rule": rule, "replication": rep, "year": 1,
                         "welfare_change": cs + rev - cost, "cs_change": cs, "revenue": rev,
                         "search_cost": cost, "search_cost_per_minute": cost / 5.0, "cruising_dwl": cost})
    return pd.DataFrame(rows)


def test_paired_table_is_per_replication_and_breakeven_is_exact():
    p = paired_table(_tiny(), [("a", "peak_zone"), ("b", "peak_zone")]).set_index("rule")
    a, b = p.loc["a"], p.loc["b"]
    # a: welfare diff = (40 - -10) + (50 - 100) - (5c+1 - c) per replication: c = 10 -> -41, 20 -> -81, 0 -> -1
    assert a["welfare_diff_median"] == -41 and a["welfare_diff_min"] == -81 and a["welfare_diff_max"] == -1
    assert a["share_welfare_better"] == 0.0 and a["share_comparator_searches_more"] == 1.0
    # breakeven: gain 0 / per-minute search diff ((4c+1)/5): 0 at every replication
    assert a["breakeven_minutes_median"] == 0.0
    # b: searches less; gain = -50 + 50 = 0 -> breakeven 0; NaN where both costs are 0 (rep 3)
    assert b["share_comparator_searches_more"] == 0.0
    assert b["share_dwl_better"] == pytest.approx(2 / 3) and b["share_revenue_better"] == 1.0
    assert np.isnan(b["dwl_ratio_max"]) or b["dwl_ratio_max"] == 0.5


def test_paired_table_refuses_comparisons_absent_from_the_sweep():
    with pytest.raises(ValueError):
        paired_table(_tiny(), [("nope", "peak_zone")])


def test_cell_and_window_tables_never_pool_cells(sweep):
    cells = cell_table(sweep)
    n_cells = 2 * 1 * 2 * 2
    assert len(cells) == n_cells * sweep["rule"].nunique() * sweep["year"].nunique()
    assert (cells["n_replications"] == 3).all()
    w = window_dependence(paired_table(sweep))
    assert set(zip(w["rule"], w["reference"])) == set(cm_sweep.comparisons_from_config())
    assert (w["n_cells"] == n_cells).all() and (w["year"] == 4).all()
    assert (w["cells_welfare_better"] <= w["n_cells"]).all()
