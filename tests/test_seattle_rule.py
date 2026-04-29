"""Tests for the Seattle ±$0.50 adjustment rule."""
from __future__ import annotations

import numpy as np
import pandas as pd

from phillyparking.pricing.seattle_rule import SeattleRuleConfig, adjust_price


def _panel(occ_by_hour: dict[int, float], default: float = 0.5) -> pd.DataFrame:
    rows = []
    for how in range(168):
        day = how // 24
        hour = how % 24
        if day < 5 and 8 <= hour < 20:
            o = occ_by_hour.get(hour, default)
        else:
            o = 0.1
        rows.append({"hour_of_week": how, "occupancy": o})
    return pd.DataFrame(rows)


def _flat_panel(occ_priced: float) -> pd.DataFrame:
    return _panel({h: occ_priced for h in range(8, 20)}, default=occ_priced)


CFG = SeattleRuleConfig()


def test_step_up_when_peak_high():
    # Peak window 11-14 has 0.90, rest priced hours moderate so avg is ok.
    panel = _panel({11: 0.90, 12: 0.90, 13: 0.90}, default=0.75)
    new, diag = adjust_price(4.00, panel, CFG)
    assert diag["direction"] == "up"
    assert diag["n_steps"] == 1
    assert new == 4.50


def test_step_down_when_avg_low():
    # All priced hours = 0.50 → peak < high, avg < low.
    panel = _flat_panel(0.50)
    new, diag = adjust_price(4.00, panel, CFG)
    assert diag["direction"] == "down"
    assert new == 3.50


def test_hold_when_in_band():
    panel = _panel({11: 0.80, 12: 0.80, 13: 0.80}, default=0.75)
    new, diag = adjust_price(4.00, panel, CFG)
    assert diag["direction"] == "hold"
    assert new == 4.00


def test_ceiling_clamp():
    panel = _flat_panel(1.0)
    new, diag = adjust_price(9.50, panel, CFG)
    # Very-high triggers +2*step = +$1.00 → would be $10.50, clamped to $10.00.
    assert diag["n_steps"] == 2
    assert new == 10.00


def test_step_up_double_when_very_high():
    panel = _panel({11: 0.97, 12: 0.97, 13: 0.97}, default=0.80)
    new, diag = adjust_price(4.00, panel, CFG)
    assert diag["direction"] == "up"
    assert diag["n_steps"] == 2
    assert new == 5.00
