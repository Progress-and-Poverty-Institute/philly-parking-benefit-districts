"""Tests for transactions-to-occupancy estimator."""
from __future__ import annotations

import pandas as pd

from phillyparking.demand.occupancy_estimator import transactions_to_occupancy


def _one_segment_one_session_per_day(n_days: int = 1, capacity: int = 5):
    segs = pd.DataFrame({
        "segment_id": ["s1"],
        "capacity": [capacity],
        "zone_id": ["ccc"],
    })
    rows = []
    base = pd.Timestamp("2025-01-06 12:00:00")  # Monday
    for d in range(n_days):
        rows.append({
            "transaction_id": d,
            "segment_id": "s1",
            "meter_id": "s1-m0",
            "start_time": base + pd.Timedelta(days=d),
            "end_time": base + pd.Timedelta(days=d) + pd.Timedelta(minutes=60),
            "paid_minutes": 60,
            "paid_amount_usd": 4.0,
            "payment_method": "mobile",
            "rate_usd_per_hr": 4.0,
        })
    return segs, pd.DataFrame(rows)


def test_single_session_hour_12_occupancy():
    segs, tx = _one_segment_one_session_per_day(n_days=1, capacity=5)
    panel = transactions_to_occupancy(tx, segs, no_pay_correction={"ccc": 1.0, "default": 1.0})
    row = panel[panel["hour_of_week"] == 1 * 0 + 12]  # Monday 12:00 -> hour_of_week = 12
    assert len(row) == 1
    expected = 60.0 / (5 * 60.0)  # 1/capacity
    assert abs(float(row["occupancy"].iloc[0]) - expected) < 1e-9


def test_no_pay_correction_factor_applied():
    segs, tx = _one_segment_one_session_per_day(n_days=1, capacity=5)
    panel = transactions_to_occupancy(tx, segs, no_pay_correction={"ccc": 1.5, "default": 1.0})
    row = panel[panel["hour_of_week"] == 12].iloc[0]
    expected = 60.0 / (5 * 60.0) * 1.5
    assert abs(float(row["occupancy"]) - expected) < 1e-9


def test_default_correction_used_for_unknown_zone():
    segs = pd.DataFrame({"segment_id": ["s1"], "capacity": [5], "zone_id": ["unknown_zone"]})
    base = pd.Timestamp("2025-01-06 12:00:00")
    tx = pd.DataFrame([{
        "transaction_id": 0, "segment_id": "s1", "meter_id": "s1-m0",
        "start_time": base, "end_time": base + pd.Timedelta(minutes=60),
        "paid_minutes": 60, "paid_amount_usd": 4.0,
        "payment_method": "mobile", "rate_usd_per_hr": 4.0,
    }])
    panel = transactions_to_occupancy(tx, segs, no_pay_correction={"default": 2.0})
    row = panel[panel["hour_of_week"] == 12].iloc[0]
    expected = 60.0 / (5 * 60.0) * 2.0
    assert abs(float(row["occupancy"]) - expected) < 1e-9
