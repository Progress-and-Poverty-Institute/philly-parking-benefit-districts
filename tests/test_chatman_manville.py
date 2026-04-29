"""Tests for Chatman-Manville comparison of targeting rules."""
from __future__ import annotations

import numpy as np
import pandas as pd

from phillyparking.pricing.chatman_manville import (
    compare_targeting_rules,
    target_avg_occupancy,
    target_min_vacancy_peak,
)


def _panel() -> pd.DataFrame:
    # Top ~5% of hours sit at 0.95 (peak), rest low so overall mean ≈ 0.50.
    # Use 100 hourly rows so 95th-percentile lands cleanly on the peak block.
    rows = []
    n = 100
    n_peak = 10  # top 10% at peak so the 95th-percentile is squarely inside the peak block
    peak_val = 0.95
    target_mean = 0.50
    other_val = (target_mean * n - peak_val * n_peak) / (n - n_peak)
    for i in range(n):
        occ = peak_val if i < n_peak else other_val
        rows.append({"hour_of_week": i, "occupancy": occ})
    return pd.DataFrame(rows)


def test_avg_rule_decreases_when_mean_below_target():
    panel = _panel()
    new_price, diag = target_avg_occupancy(panel, current_price=4.00, elasticity=-0.4)
    assert diag["direction"] == "down"
    assert new_price < 4.00


def test_min_vacancy_rule_increases_when_peak_above_target():
    panel = _panel()
    new_price, diag = target_min_vacancy_peak(panel, current_price=4.00, elasticity=-0.4)
    assert diag["direction"] == "up"
    assert new_price > 4.00


def test_rules_disagree_chatman_manville_hypothesis():
    panel = _panel()
    df = compare_targeting_rules(panel, current_price=4.00, elasticity=-0.4)
    avg_row = df[df["rule"] == "avg_occupancy"].iloc[0]
    peak_row = df[df["rule"] == "min_vacancy_peak"].iloc[0]
    assert avg_row["new_price"] < 4.00
    assert peak_row["new_price"] > 4.00
    assert avg_row["new_price"] != peak_row["new_price"]
