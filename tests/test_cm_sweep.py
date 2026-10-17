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
             observation_noise=[0.0, 0.1], occupancy_cap=[0.95, 0.99], n_replications=3, rolls_forward_years=4)
N_CELLS = 2 * 1 * 2 * 2 * 2
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
    assert len(sweep) == N_CELLS * len(cfg["rules"]) * 3 * 4
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
    assert set(s["occupancy_cap"]) == set(load_config("scenarios")["chatman_manville_sweep"]["occupancy_cap"])


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
    minutes = cm_sweep.load_search_cost_config().minutes_at_full_block
    assert np.allclose(a["search_cost_per_full_block_minute"] * minutes, a["search_cost"])


def test_cap_is_scored_on_one_price_path(sweep):
    """The rules never see the cap: across caps a rule-year has the same prices, revenue and
    surplus. The level is pinned at a full block, so a higher cap makes a full block cost the
    same and every block short of full cost less: the search cost falls in the cap."""
    keys = [a for a in cm_sweep.AXES if a != "occupancy_cap"] + ["rule", "replication", "year"]
    g = sweep.groupby(keys)
    assert (g["occupancy_cap"].nunique() == 2).all()
    for col in ("mean_price", "revenue", "cs_change", "share_block_hours_above_high"):
        assert (g[col].nunique() == 1).all(), col
    lo = sweep[sweep["occupancy_cap"] == 0.95].set_index(keys)["search_cost"]
    hi = sweep[sweep["occupancy_cap"] == 0.99].set_index(keys)["search_cost"].reindex(lo.index)
    assert (hi <= lo + 1e-9).all() and (hi < lo).any()


def test_every_welfare_term_counts_the_cars_that_park():
    """Defect test for audit 2026-10-16 finding 5. On a panel whose latent demand exceeds
    capacity on every priced block-hour, a rule that raises the price by one step a year
    leaves every block full: the surplus lost is exactly capacity x the rise on the served
    cars, which is what the revenue gain and the search cost count too. Scoring surplus on
    latent demand would charge d0 x capacity x the rise, 1.5x as much here."""
    from phillyparking.demand.response import demand_level

    def raise_one_step(rule, panel, cfg=None):
        out = panel.loc[frame_priced_mask(panel), ["zone_id", "price_usd_per_hr"]].drop_duplicates("zone_id")
        return out.assign(price_usd_per_hr=out["price_usd_per_hr"] + 0.5)

    segs = make_synthetic_segments(n=20, seed=3)
    priced_zones = {z["id"] for z in load_config("zones")["zones"]}
    segs = segs[segs["zone_id"].isin(priced_zones)].reset_index(drop=True)
    rows = [{"segment_id": sid, "hour_of_week": h, "occupancy": 1.0} for sid in segs["segment_id"] for h in range(168)]
    flat = pd.DataFrame(rows)
    eps, p0 = -0.1, 2.0
    import unittest.mock as um
    # Latent demand 1.5x capacity on every block-hour (the start-level scaling is bypassed so
    # that the demand stays over-full); after two $0.50 rises at e = -0.1 it is still 1.43.
    with um.patch.object(cm_sweep, "review", raise_one_step),             um.patch.object(cm_sweep, "_scale_to_start_occupancy", lambda d, *a, **k: 1.5 * d):
        s = chatman_manville_sweep(segments=segs, baseline_panel=flat, elasticity_values=[eps],
                                   start_occupancy=[1.0], block_dispersion=[0.0], observation_noise=[0.0],
                                   occupancy_cap=[0.99], n_replications=1, rolls_forward_years=2,
                                   rules=["mean_zone"], start_price=p0)
    assert 1.5 * float(demand_level(p0 + 1.0, eps, p0)) > 1.4
    cap = segs.set_index("segment_id")["capacity"]
    panel = flat.merge(segs[["segment_id", "zone_id", "capacity"]], on="segment_id")
    n_priced_cars = float(panel.loc[frame_priced_mask(panel), "capacity"].sum())
    for year in (1, 2):
        row = s[s["year"] == year].iloc[0]
        assert row["cs_change"] == pytest.approx(-n_priced_cars * 0.5 * year * 52, rel=1e-9)
        assert row["revenue"] == pytest.approx(n_priced_cars * (p0 + 0.5 * year) * 52, rel=1e-9)
        assert row["search_cost"] == pytest.approx(s[s["year"] == 1].iloc[0]["search_cost"])   # every block still full
        assert row["welfare_change"] == pytest.approx(0.0, abs=1e-6)   # a transfer between full blocks' parkers and the meter


def test_old_comparator_ordering_is_an_identity_on_priced_metrics():
    """mean <= q95 over the same window: the mean rule never has less search cost or less total surplus."""
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
    last = p[(p.year == 6) & (p.occupancy_cap == cm_sweep.load_search_cost_config().occupancy_cap)].iloc[0]
    assert last["share_comparator_searches_more"] == 1.0   # the mean rule prices lower
    c_star = last["breakeven_full_block_minutes_median"]
    assert 0 < c_star < 60
    cfg = cm_sweep.load_search_cost_config()
    gain = last["cs_diff_median"] + last["revenue_diff_median"]
    per_min = last["search_cost_diff_median"] / cfg.minutes_at_full_block
    assert gain - 0.5 * c_star * per_min > 0 > gain - 2.0 * c_star * per_min
    # The secondary column is the same level in minutes at the 95% reference block-hour.
    from phillyparking.welfare.search_cost import reference_minutes_per_full_block_minute
    assert last["breakeven_reference_minutes_median"] == pytest.approx(
        c_star * reference_minutes_per_full_block_minute(cfg))


def test_same_instrument_breakeven_sign_is_a_property_of_the_design():
    """For the mean against the peak statistic over the same block-hours the comparator's total
    surplus and search cost are both at least the reference's in every replication-year, so the
    breakeven is non-negative by construction; `ordering_violations` is that check."""
    s = chatman_manville_sweep(segments=SEGS, elasticity_values=[-0.4, -0.7], start_occupancy=[0.6, 0.9],
                               block_dispersion=[0.0, 0.6], observation_noise=[0.1], occupancy_cap=[0.99],
                               n_replications=2, rolls_forward_years=4,
                               rules=["peak_zone", "mean_zone", "peak_band", "mean_band"])
    for comp, ref in (("mean_zone", "peak_zone"), ("mean_band", "peak_band")):
        assert ordering_violations(s, comp, ref).empty
        p = paired_table(s, [(comp, ref)])
        assert (p["breakeven_full_block_minutes_min"].fillna(0) >= -1e-9).all()
        assert (p["cs_diff_min"] + p["revenue_diff_min"] >= -1e-6).all() or (
            (p["cs_diff_median"] + p["revenue_diff_median"]) >= -1e-6).all()


# --------------------------------------------------------------------------- provenance


def test_sweep_records_and_roundtrips_provenance(sweep, tmp_path):
    prov = sweep.attrs["provenance"]
    assert prov["segment_source"]["kind"] == "synthetic_fixture"
    assert prov["seed"] == 42 and prov["n_replications"] == 3
    assert prov["start_occupancy"] == [0.75] and prov["block_dispersion"] == [0.0, 0.3]
    assert {"scenarios", "pricing_rules", "zones"} <= set(prov["config_sha256"])
    assert prov["search_cost"]["minutes_at_full_block"] == cm_sweep.load_search_cost_config().minutes_at_full_block
    assert prov["occupancy_cap"] == [0.95, 0.99] and "served" in prov["welfare_population"]
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
    assert prov["occupancy_cap"] == cfg["occupancy_cap"]
    assert prov["search_cost"]["minutes_at_full_block"] == cm_sweep.load_search_cost_config().minutes_at_full_block


# --------------------------------------------------------------------------- summaries


def _tiny() -> pd.DataFrame:
    rows = []
    for rep, (ref_cost, ref_rev) in enumerate([(10.0, 100.0), (20.0, 100.0), (0.0, 100.0)]):
        for rule, cost, rev, cs in (("peak_zone", ref_cost, ref_rev, -10.0),
                                    ("a", 5 * ref_cost + 1, 50.0, 40.0), ("b", ref_cost / 2, 150.0, -60.0)):
            rows.append({"elasticity": -0.4, "start_occupancy": 0.75, "block_dispersion": 0.0,
                         "observation_noise": 0.1, "occupancy_cap": 0.95, "rule": rule, "replication": rep,
                         "year": 1, "welfare_change": cs + rev - cost, "cs_change": cs, "revenue": rev,
                         "search_cost": cost, "search_cost_per_full_block_minute": cost / 5.0})
    return pd.DataFrame(rows)


def test_paired_table_is_per_replication_and_breakeven_is_exact():
    p = paired_table(_tiny(), [("a", "peak_zone"), ("b", "peak_zone")]).set_index("rule")
    a, b = p.loc["a"], p.loc["b"]
    # a: welfare diff = (40 - -10) + (50 - 100) - (5c+1 - c) per replication: c = 10 -> -41, 20 -> -81, 0 -> -1
    assert a["welfare_diff_median"] == -41 and a["welfare_diff_min"] == -81 and a["welfare_diff_max"] == -1
    assert a["share_welfare_better"] == 0.0 and a["share_comparator_searches_more"] == 1.0
    # breakeven: gain 0 / per-minute search diff ((4c+1)/5): 0 at every replication; at cap
    # 0.95 the reference block-hour is the full block, so the two units coincide
    assert a["breakeven_full_block_minutes_median"] == 0.0 and a["breakeven_reference_minutes_median"] == 0.0
    # b: searches less; gain = -50 + 50 = 0 -> breakeven 0; NaN where both costs are 0 (rep 3)
    assert b["share_comparator_searches_more"] == 0.0
    assert b["share_search_cost_better"] == pytest.approx(2 / 3) and b["share_revenue_better"] == 1.0
    assert np.isnan(b["search_cost_ratio_max"]) or b["search_cost_ratio_max"] == 0.5


def test_paired_table_refuses_comparisons_absent_from_the_sweep():
    with pytest.raises(ValueError):
        paired_table(_tiny(), [("nope", "peak_zone")])


def test_cell_and_window_tables_never_pool_cells(sweep):
    cells = cell_table(sweep)
    assert len(cells) == N_CELLS * sweep["rule"].nunique() * sweep["year"].nunique()
    assert (cells["n_replications"] == 3).all()
    w = window_dependence(paired_table(sweep))
    assert set(zip(w["rule"], w["reference"])) == set(cm_sweep.comparisons_from_config())
    # One row per comparison and cap, over the cells of the other four axes.
    assert len(w) == len(cm_sweep.comparisons_from_config()) * 2
    assert (w["n_cells"] == N_CELLS // 2).all() and (w["year"] == 4).all()
    assert (w["cells_welfare_better"] <= w["n_cells"]).all()
    assert {"breakeven_full_block_minutes_median_cells_median", "breakeven_reference_minutes_median_cells_median",
            "cells_search_cost_better"} <= set(w.columns)


def test_breakeven_chart_draws_the_cited_range_per_cap(sweep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from phillyparking.viz.report_figures import cm_breakeven_chart
    from phillyparking.welfare.search_cost import cited_cruising_minutes
    paired = paired_table(sweep, [("mean_zone", "peak_zone")])
    fig = cm_breakeven_chart(paired, ("mean_zone", "peak_zone"), save_to=tmp_path / "b.png")
    try:
        assert fig.axes[0].get_ylabel().startswith("Breakeven minutes per arrival")
        assert len(fig.axes) == 2 * 1   # one row per cap, one column per start level
        labels = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
        assert any("those who cruise" in lab for lab in labels)
        assert not any("config level" in lab for lab in labels)
        cited = cited_cruising_minutes()
        heights = [p.get_height() for p in fig.axes[0].patches if hasattr(p, "get_height")]
        assert any(abs(h - (cited["high"] - cited["low"])) < 1e-6 for h in heights)
    finally:
        plt.close(fig)
