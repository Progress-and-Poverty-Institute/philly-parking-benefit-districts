"""Tests for the Seattle ±$0.50 zone x time-of-day rule.

Thresholds are read from config/pricing_rules.yaml, so these fail if the rule stops
using the configured dead band, not when the band itself is retuned.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phillyparking.pricing.seattle_rule import (
    adjust_price, adjust_zone_prices, load_seattle_config, zone_band_occupancy,
)

CFG = load_seattle_config()
EPS = 1e-6
BANDS = [[8, 12], [12, 16], [16, 20]]


def test_raise_just_above_high_threshold():
    new, diag = adjust_price(4.00, CFG.occ_high + EPS, CFG, zone_id="ccc")
    assert diag["direction"] == "up" and diag["n_steps"] == 1
    assert new == pytest.approx(4.00 + CFG.step_usd)


def test_cut_just_below_low_threshold():
    new, diag = adjust_price(4.00, CFG.occ_low - EPS, CFG, zone_id="ccc")
    assert diag["direction"] == "down"
    assert new == pytest.approx(4.00 - CFG.step_usd)


@pytest.mark.parametrize("occ", [CFG.occ_low, (CFG.occ_low + CFG.occ_high) / 2, CFG.occ_high])
def test_hold_inside_dead_band(occ):
    new, diag = adjust_price(4.00, occ, CFG, zone_id="ccc")
    assert diag["direction"] == "hold"
    assert new == 4.00


def test_two_steps_at_very_high():
    new, diag = adjust_price(4.00, CFG.occ_very_high, CFG, zone_id="ccc")
    assert diag["n_steps"] == CFG.max_step_per_cycle
    assert new == pytest.approx(4.00 + CFG.max_step_per_cycle * CFG.step_usd)


def test_zone_floor_clamps():
    new, _ = adjust_price(1.00, 0.10, CFG, zone_id="ccc")  # ccc floor is $1.00 in zones.yaml
    assert new == 1.00


def _panel(zone: str, occ_fn) -> pd.DataFrame:
    how = np.arange(168)
    return pd.DataFrame({
        "segment_id": "s0", "zone_id": zone, "capacity": 10,
        "hour_of_week": how, "occupancy": [occ_fn(h // 24, h % 24) for h in how],
    })


def test_band_statistic_uses_priced_hours_including_saturday():
    # Weekdays 0.60, Saturday 0.90, everything else 1.0. ccc is priced Mon-Sat 8-20, so
    # each band averages 5 weekdays at 0.60 and Saturday at 0.90; unpriced hours are ignored.
    panel = _panel("ccc", lambda d, h: 0.60 if d < 5 else 0.90 if d == 5 else 1.0)
    stats = zone_band_occupancy(panel, BANDS)
    assert len(stats) == 3
    assert stats["band_occ"].tolist() == pytest.approx([(5 * 0.60 + 0.90) / 6] * 3)
    assert stats["n_hours"].tolist() == [24, 24, 24]


def test_band_statistic_respects_zone_hours():
    # south_philly is priced 8-18, so its 16-20 band covers 16-18 only.
    panel = _panel("south_philly", lambda d, h: 0.9 if h in (16, 17) else 0.1 if h in (18, 19) else 0.5)
    stats = zone_band_occupancy(panel, BANDS).set_index("band")
    assert stats.loc["16-20", "n_hours"] == 12
    assert stats.loc["16-20", "band_occ"] == pytest.approx(0.9)


def test_each_band_moves_on_its_own_statistic():
    panel = _panel("ccc", lambda d, h: 0.97 if 8 <= h < 12 else 0.75 if 12 <= h < 16 else 0.40)
    out = adjust_zone_prices(panel, pd.DataFrame({"zone_id": ["ccc"], "price_usd_per_hr": [4.0]}), BANDS, config=CFG)
    got = out.set_index("band")["price_usd_per_hr"].to_dict()
    assert got == pytest.approx({
        "8-12": 4.0 + CFG.max_step_per_cycle * CFG.step_usd,
        "12-16": 4.0,
        "16-20": 4.0 - CFG.step_usd,
    })
    # A second review starts from the per-band prices.
    again = adjust_zone_prices(panel, out, BANDS, config=CFG).set_index("band")["previous_price"].to_dict()
    assert again == pytest.approx(got)
