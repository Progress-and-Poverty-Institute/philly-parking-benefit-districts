"""Chatman-Manville targeting rules and sweep: one implementation, paired runs, per-cell tables."""
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

SMALL = dict(elasticity_values=[-0.2, -0.5], noise_sigmas=[0.0, 0.1], n_replications=3, rolls_forward_years=5)


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


# --------------------------------------------------------------------------- rules


def test_step_for_follows_the_band():
    cfg = tr.load_targeting_config()
    assert tr.step_for(cfg.occ_high + 0.01, cfg) == cfg.step_usd
    assert tr.step_for(cfg.occ_low - 0.01, cfg) == -cfg.step_usd
    assert tr.step_for(cfg.occ_low, cfg) == 0.0 == tr.step_for(cfg.occ_high, cfg)


def test_chatman_manville_band_is_the_seattle_band():
    cm, sea = tr.load_targeting_config(), load_seattle_config()
    assert (cm.occ_low, cm.occ_high, cm.step_usd) == (sea.occ_low, sea.occ_high, sea.step_usd)


def test_every_configured_rule_is_implemented():
    assert set(load_config("scenarios")["chatman_manville_sweep"]["rules"]) <= set(tr.RULE_NAMES)
    with pytest.raises(ValueError):
        tr.review("not_a_rule", _panel(lambda h: 0.5))


def test_peak_rule_raises_where_the_168_hour_mean_says_cut():
    # 10% of hours at 0.95, the rest low: q95 = 0.95 > 0.85 but the mean is far below 0.70.
    panel = _panel(lambda h: 0.95 if h % 10 == 0 else 0.30)
    assert panel["occupancy"].mean() < 0.70 and panel["occupancy"].quantile(0.95) > 0.85
    assert _price(tr.review("min_vacancy_peak", panel)) == 2.5
    assert _price(tr.review("avg_occupancy", panel)) == 1.5


def test_priced_hours_mean_holds_where_the_168_hour_mean_cuts():
    # 0.78 in ccc's priced hours, 0.20 elsewhere: priced mean 0.78 is inside the band.
    mask = frame_priced_mask(_panel(lambda h: 0.0))
    panel = _panel(lambda h: 0.78 if mask[h] else 0.20)
    assert panel["occupancy"].mean() < 0.70
    assert _price(tr.review("avg_occupancy", panel)) == 1.5
    assert _price(tr.review("avg_priced_hours", panel)) == 2.0


def test_band_rule_raises_on_any_band_above_and_cuts_only_when_all_below():
    cfg = tr.load_targeting_config()
    hot_one_band = _panel(lambda h: 0.95 if (_weekday_midday(h)) else 0.40)
    assert _price(tr.review("avg_priced_bands", hot_one_band, cfg)) == 2.5
    # Every band below 0.70 -> cut; one band inside the band -> hold.
    cold = _panel(lambda h: 0.40)
    assert _price(tr.review("avg_priced_bands", cold, cfg)) == 1.5
    held = _panel(lambda h: 0.78 if _weekday_midday(h) else 0.40)
    assert _price(tr.review("avg_priced_bands", held, cfg)) == 2.0


def test_zone_level_rules_respect_zone_floor_and_hold_unpriced_zones():
    cold = _panel(lambda h: 0.20, price=1.0)  # ccc floor is 1.00
    for rule in ("avg_occupancy", "avg_priced_hours", "avg_priced_bands", "min_vacancy_peak"):
        assert _price(tr.review(rule, cold)) == 1.0
    cold_other = _panel(lambda h: 0.20, zone="other", price=2.0)  # not in zones.yaml: never priced
    assert _price(tr.review("avg_priced_hours", cold_other), "other") == 2.0
    assert _price(tr.review("avg_priced_bands", cold_other), "other") == 2.0
    assert _price(tr.review("avg_occupancy", cold_other), "other") == 1.5  # looks at all 168 hours
    assert tr.review("seattle_rule", cold_other).empty


def test_seattle_rule_sets_a_price_per_band_on_priced_hours_only():
    # Midday band (12-16) hot, morning band (8-12) cold: Seattle moves the bands separately.
    priced = frame_priced_mask(_panel(lambda h: 0.0))
    panel = _panel(lambda h: 0.0 if not priced[h] else (0.97 if 12 <= h % 24 < 16 else 0.40))
    out = tr.review("seattle_rule", panel)
    assert set(out["hour_of_week"]) <= set(np.flatnonzero(priced))
    hod = out["hour_of_week"] % 24
    midday = out.loc[(out["hour_of_week"] // 24 < 5) & (hod >= 12) & (hod < 16), "price_usd_per_hr"]
    morning = out.loc[(out["hour_of_week"] // 24 < 5) & (hod >= 8) & (hod < 12), "price_usd_per_hr"]
    assert (midday == 3.0).all()      # >= 0.95 band mean -> two steps
    assert (morning == 1.5).all()     # < 0.70 -> one step down


# --------------------------------------------------------------------------- sweep


@pytest.fixture(scope="module")
def sweep():
    return chatman_manville_sweep(**SMALL)


def test_old_comparator_ordering_holds_replication_by_replication(sweep):
    """mean <= q95 on a diurnal panel, so the 168-hour mean rule never has less DWL or more revenue."""
    assert len(sweep.groupby(["elasticity", "noise_sigma", "replication", "year"])) == 2 * 2 * 3 * 5
    assert ordering_violations(sweep).empty
    j = sweep[sweep.rule == "avg_occupancy"].set_index(cm_sweep.KEYS[:2] + ["replication", "year"])
    k = sweep[sweep.rule == "min_vacancy_peak"].set_index(cm_sweep.KEYS[:2] + ["replication", "year"])
    assert (j["cruising_dwl_total"] > k["cruising_dwl_total"]).all()  # and strictly so on this fixture


def test_ordering_check_fails_when_the_comparator_statistic_exceeds_the_peak(monkeypatch):
    """Defect injection: a 168-hour 'average' that is really the max can raise what the peak rule holds."""
    real = tr._zone_statistic

    def broken(panel, rule, cfg):
        if rule == "avg_occupancy":
            return panel["occupancy"].groupby(panel["zone_id"].to_numpy()).max().to_dict()
        return real(panel, rule, cfg)

    monkeypatch.setattr(tr, "_zone_statistic", broken)
    bad = chatman_manville_sweep(**{**SMALL, "rules": ["min_vacancy_peak", "avg_occupancy"]})
    assert not ordering_violations(bad).empty


def test_ordering_is_a_property_of_mean_below_q95_not_of_the_rules():
    """A thin top atom over a concentrated bulk puts the mean above the q95; the ordering reverses."""
    cfg = tr.load_targeting_config()
    n = 1000
    occ = np.r_[np.full(int(0.952 * n), 0.849), np.full(n - int(0.952 * n), 0.99)]
    panel = pd.DataFrame({"zone_id": "ccc", "occupancy": occ, "price_usd_per_hr": 2.0,
                          "hour_of_week": np.arange(n) % 168})
    assert occ.mean() > cfg.occ_high > np.quantile(occ, cfg.peak_quantile)
    assert _price(tr.zone_rule_prices(panel, "avg_occupancy", cfg)) > _price(
        tr.zone_rule_prices(panel, "min_vacancy_peak", cfg))


def test_sweep_uses_the_shared_rule_implementation(monkeypatch):
    """Defect injection: if the sweep re-implemented the rules, a spy on `review` would never fire."""
    calls = []

    def hold(rule, panel, cfg=None):
        calls.append(rule)
        return panel[["zone_id", "price_usd_per_hr"]].drop_duplicates("zone_id")

    monkeypatch.setattr(cm_sweep, "review", hold)
    s = chatman_manville_sweep(elasticity_values=[-0.4], noise_sigmas=[0.0], n_replications=1,
                               rolls_forward_years=2, rules=["min_vacancy_peak", "avg_occupancy"])
    assert calls == ["min_vacancy_peak"] * 2 + ["avg_occupancy"] * 2
    # Holding every price means every rule yields identical rows.
    a, b = (s[s.rule == r].drop(columns="rule").reset_index(drop=True) for r in ("min_vacancy_peak", "avg_occupancy"))
    pd.testing.assert_frame_equal(a, b)


def test_rules_share_one_noise_draw_per_replication():
    s = chatman_manville_sweep(elasticity_values=[-0.4], noise_sigmas=[0.1], n_replications=2,
                               rolls_forward_years=1, rules=["avg_occupancy", "min_vacancy_peak"])
    np.testing.assert_array_equal(cm_sweep._noise(7, 0, 50), cm_sweep._noise(7, 0, 50))
    assert not np.array_equal(cm_sweep._noise(7, 0, 50), cm_sweep._noise(7, 1, 50))
    # sigma = 0 removes the noise entirely: replications are identical.
    s0 = chatman_manville_sweep(elasticity_values=[-0.4], noise_sigmas=[0.0], n_replications=2, rolls_forward_years=1)
    g = s0.groupby(["rule", "year"])["cruising_dwl_total"].nunique()
    assert (g == 1).all()
    assert s.groupby("rule")["cruising_dwl_total"].nunique().max() == 2  # noise differs between replications


def _saturated_priced_hours(segments: pd.DataFrame) -> pd.DataFrame:
    """Every priced hour at 0.97, meter-off hours at 0.30."""
    hours = np.arange(168)
    rows = []
    for seg in segments.itertuples():
        probe = pd.DataFrame({"zone_id": seg.zone_id, "hour_of_week": hours})
        occ = np.where(frame_priced_mask(probe), 0.97, 0.30)
        rows += [{"segment_id": seg.segment_id, "hour_of_week": int(h), "occupancy": float(o)}
                 for h, o in zip(hours, occ)]
    return pd.DataFrame(rows)


def _seattle_beats_peak(s: pd.DataFrame) -> bool:
    p = paired_table(s)
    p = p[p["rule"] == "seattle_rule"]
    return bool((p["dwl_diff_priced_median"] < 0).any() and (p["share_dwl_better_priced"] > 0).any())


def test_seattle_rule_beats_the_peak_rule_where_it_steps_faster():
    """Over-full priced hours: Seattle's two-step tier removes cruising faster than one peak step."""
    segs = make_synthetic_segments(n=20)
    s = chatman_manville_sweep(segments=segs, baseline_panel=_saturated_priced_hours(segs),
                               elasticity_values=[-0.4], noise_sigmas=[0.0], n_replications=1,
                               rolls_forward_years=3, rules=["min_vacancy_peak", "seattle_rule"])
    assert _seattle_beats_peak(s)
    y1 = s[s.year == 1].set_index("rule")["cruising_dwl_priced_hours"]
    assert y1["seattle_rule"] < y1["min_vacancy_peak"]


def test_seattle_beats_peak_check_fails_when_seattle_cannot_move(monkeypatch):
    """Defect injection: a Seattle rule that always holds cannot beat the peak rule."""
    monkeypatch.setattr(tr, "seattle_rule_prices",
                        lambda panel, cfg=None: panel[["zone_id", "hour_of_week", "price_usd_per_hr"]].iloc[0:0])
    segs = make_synthetic_segments(n=20)
    s = chatman_manville_sweep(segments=segs, baseline_panel=_saturated_priced_hours(segs),
                               elasticity_values=[-0.4], noise_sigmas=[0.0], n_replications=1,
                               rolls_forward_years=3, rules=["min_vacancy_peak", "seattle_rule"])
    assert not _seattle_beats_peak(s)


# --------------------------------------------------------------------------- provenance


def test_sweep_records_and_roundtrips_provenance(sweep, tmp_path):
    prov = sweep.attrs["provenance"]
    assert prov["segment_source"]["kind"] == "synthetic_fixture"
    assert prov["segment_source"]["n_segments"] == 20 and prov["segment_source"]["seed"] == 0
    assert prov["seed"] == 42 and prov["n_replications"] == 3 and prov["rules"] == list(tr.RULE_NAMES)
    assert {"scenarios", "pricing_rules", "zones"} <= set(prov["config_sha256"])
    path = save_sweep(sweep, tmp_path / "cm.parquet")
    assert path.with_suffix(".meta.json").exists()
    back = load_sweep(path)
    assert back.attrs["provenance"] == prov
    pd.testing.assert_frame_equal(back.reset_index(drop=True), sweep.reset_index(drop=True), check_like=True)


def test_tracked_sweep_carries_provenance_for_a_fixture_it_names():
    from phillyparking._config import outputs_dir

    path = outputs_dir() / "tables" / "cm_sweep_n200.parquet"
    if not path.exists():
        pytest.skip("no tracked sweep")
    prov = load_sweep(path).attrs.get("provenance")
    assert prov and prov["segment_source"]["kind"] != "unknown"
    assert prov["n_replications"] == load_config("scenarios")["chatman_manville_sweep"]["n_replications"]


# --------------------------------------------------------------------------- summaries


def _tiny() -> pd.DataFrame:
    rows = []
    for rep, (ref_dwl, ref_rev) in enumerate([(10.0, 100.0), (20.0, 100.0), (0.0, 100.0)]):
        for rule, dwl, rev in (("min_vacancy_peak", ref_dwl, ref_rev), ("a", 5 * ref_dwl + 1, 50.0), ("b", ref_dwl / 2, 150.0)):
            rows.append({"elasticity": -0.4, "noise_sigma": 0.1, "rule": rule, "replication": rep, "year": 1,
                         "cruising_dwl_total": dwl, "cruising_dwl_priced_hours": dwl,
                         "revenue_total": rev, "revenue_priced_hours": rev})
    return pd.DataFrame(rows)


def test_paired_table_ratios_are_per_replication_not_pooled():
    p = paired_table(_tiny()).set_index("rule")
    assert p.loc["a", "n_replications"] == 3
    # Per-replication DWL ratios of rule a: 51/10, 101/20, NaN (reference DWL 0); median of the two defined.
    assert p.loc["a", "dwl_ratio_median"] == pytest.approx(np.median([5.1, 5.05]))
    assert p.loc["a", "dwl_ratio_min"] == pytest.approx(5.05) and p.loc["a", "dwl_ratio_max"] == pytest.approx(5.1)
    assert p.loc["a", "dwl_diff_median"] == pytest.approx(np.median([41, 81, 1]))
    assert p.loc["a", "share_dwl_better"] == 0.0 and p.loc["b", "share_dwl_better"] == pytest.approx(2 / 3)  # a tie is not better
    assert p.loc["a", "revenue_ratio_median"] == 0.5 and p.loc["b", "share_revenue_better"] == 1.0


def test_window_dependence_counts_cells_and_never_pools():
    w = window_dependence(paired_table(_tiny())).set_index("rule")
    assert w.loc["a", "n_cells"] == 1 and w.loc["a", "cells_dwl_better"] == 0
    assert w.loc["b", "cells_dwl_better"] == 1 and w.loc["b", "cells_revenue_better"] == 1


def test_cell_table_reports_median_and_range():
    c = cell_table(_tiny(), metrics=("cruising_dwl_total",)).set_index("rule")
    assert c.loc["min_vacancy_peak", "cruising_dwl_total_median"] == 10.0
    assert (c.loc["min_vacancy_peak", "cruising_dwl_total_min"], c.loc["min_vacancy_peak", "cruising_dwl_total_max"]) == (0.0, 20.0)


def test_tracked_cell_tables_match_the_tracked_sweep():
    from phillyparking._config import outputs_dir

    tables = outputs_dir() / "tables"
    if not (tables / "cm_sweep_n200.parquet").exists() or not (tables / "cm_sweep_paired.csv").exists():
        pytest.skip("no tracked sweep tables")
    sw = load_sweep(tables / "cm_sweep_n200.parquet")
    on_disk = pd.read_csv(tables / "cm_sweep_paired.csv")
    fresh = paired_table(sw)
    assert len(on_disk) == len(fresh)
    np.testing.assert_allclose(on_disk["dwl_ratio_median"], fresh["dwl_ratio_median"], rtol=1e-4, equal_nan=True)
