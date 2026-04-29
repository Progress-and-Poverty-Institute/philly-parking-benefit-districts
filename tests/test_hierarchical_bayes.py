"""Tests for the hierarchical Bayes elasticity model.

Marked slow because PyMC sampling is heavy. Skipped if pymc isn't installed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pm = pytest.importorskip("pymc")
az = pytest.importorskip("arviz")

from phillyparking.elasticity.hierarchical_bayes import (  # noqa: E402
    fit_elasticity_model,
    posterior_zone_elasticity,
)


@pytest.mark.slow
def test_fit_recovers_true_elasticity():
    rng = np.random.default_rng(0)
    zones = ["z1", "z2", "z3"]
    nbhds = {"z1": "n1", "z2": "n1", "z3": "n2"}
    true_eps = {"z1": -0.5, "z2": -0.3, "z3": -0.6}

    rows = []
    for z in zones:
        eps = true_eps[z]
        for h in range(100):
            price = rng.uniform(2.0, 5.0)
            log_occ = -0.2 + eps * np.log(price) + rng.normal(0, 0.05)
            rows.append({
                "segment_id": f"{z}-seg",
                "zone_id": z,
                "neighborhood": nbhds[z],
                "hour_of_week": h % 24,
                "occupancy": float(np.exp(log_occ)),
                "price_usd_per_hr": price,
            })
    panel = pd.DataFrame(rows)

    fit = fit_elasticity_model(panel, draws=200, tune=200, chains=1, seed=42)
    summary = posterior_zone_elasticity(fit)
    summary = summary.set_index("zone_id")
    for z, eps in true_eps.items():
        assert abs(summary.loc[z, "mean"] - eps) < 0.15
