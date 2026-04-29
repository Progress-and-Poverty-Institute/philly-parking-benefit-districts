from __future__ import annotations

import pytest

pytest.importorskip("geopandas")

from phillyparking.io.ppa_stub import TX_SCHEMA, generate_transactions
from tests.fixtures import make_synthetic_segments


def test_transactions_deterministic():
    seg = make_synthetic_segments()
    a = generate_transactions(seg, n_days=3, seed=123)
    b = generate_transactions(seg, n_days=3, seed=123)
    assert len(a) == len(b)
    assert (a["transaction_id"].values == b["transaction_id"].values).all()
    assert (a["paid_minutes"].values == b["paid_minutes"].values).all()


def test_schema_columns():
    seg = make_synthetic_segments()
    df = generate_transactions(seg, n_days=2, seed=1)
    for col in TX_SCHEMA:
        assert col in df.columns, f"missing {col}"


def test_arrival_rate_ordering():
    """Weekday lunch peak (Mon 12-14h) should produce more transactions than
    weekend night (Sun 0-2h) for the same segments."""
    seg = make_synthetic_segments()
    df = generate_transactions(seg, n_days=7, seed=7)
    df["dow"] = df["start_time"].dt.dayofweek
    df["hour"] = df["start_time"].dt.hour
    weekday_lunch = df[(df["dow"] < 5) & (df["hour"].between(12, 13))]
    weekend_night = df[(df["dow"] >= 5) & (df["hour"].between(0, 1))]
    assert len(weekday_lunch) > len(weekend_night)
