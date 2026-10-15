"""Can the data identify each zone's price elasticity? Checked before any fit.

The model (`hierarchical_bayes.fit_elasticity_model`) is

    log occupancy = alpha[zone] + eps[zone] * log price + gamma[hour_of_week] + delta[period]

A zone's `eps` is identified by the data only if its `zone x log price` column is not a
linear combination of the other columns. With one posted price per zone (the old design:
one `zones.yaml` rate attached to every row) no zone is identified, and the posterior is the
prior (audit finding 5). A zone observed across a rate change is identified when something
else pins the period effect: zones whose rate did not change, or zones whose rates changed by
different ratios plus enough of them.

`check_identification` computes this exactly with a rank test on the design at the level
of distinct (zone, period, hour, price) cells and raises `IdentificationError` when no zone
is identified.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class IdentificationError(ValueError):
    """The data cannot identify any zone's price elasticity; a fit would return the prior."""


def _design(cells: pd.DataFrame, zones: list[str], period_col: str | None):
    """Design matrix and the index of each zone's eps column."""
    cols, names = [], []
    for z in zones:
        cols.append((cells["zone_id"] == z).to_numpy(float))
        names.append(("alpha", z))
    eps_idx = {}
    for z in zones:
        eps_idx[z] = len(cols)
        cols.append(((cells["zone_id"] == z) * cells["log_price"]).to_numpy(float))
        names.append(("eps", z))
    for t in sorted(cells["hour_of_week"].unique())[1:]:
        cols.append((cells["hour_of_week"] == t).to_numpy(float))
    if period_col:
        for p in sorted(cells[period_col].unique())[1:]:
            cols.append((cells[period_col] == p).to_numpy(float))
    return np.column_stack(cols), eps_idx


def identification_table(panel: pd.DataFrame, period_col: str | None = "period",
                         price_col: str = "price_usd_per_hr") -> pd.DataFrame:
    """Per zone: number of distinct prices and whether its elasticity is identified."""
    need = ["zone_id", "hour_of_week", price_col]
    missing = [c for c in need if c not in panel.columns]
    if missing:
        raise IdentificationError(f"panel lacks {missing}")
    if period_col and period_col not in panel.columns:
        period_col = None
    df = panel[panel[price_col] > 0]
    if df.empty:
        raise IdentificationError("no rows with a positive price")
    keep = ["zone_id", "hour_of_week", price_col] + ([period_col] if period_col else [])
    cells = df[keep].drop_duplicates().copy()
    cells["zone_id"] = cells["zone_id"].astype(str)
    cells["log_price"] = np.log(cells[price_col].astype(float))
    zones = sorted(cells["zone_id"].unique())
    X, eps_idx = _design(cells, zones, period_col)
    full = np.linalg.matrix_rank(X)
    rows = []
    for z in zones:
        reduced = np.linalg.matrix_rank(np.delete(X, eps_idx[z], axis=1))
        rows.append({"zone_id": z,
                     "n_prices": int(cells.loc[cells["zone_id"] == z, price_col].nunique()),
                     "identified": bool(full - reduced == 1)})
    return pd.DataFrame(rows)


def check_identification(panel: pd.DataFrame, period_col: str | None = "period",
                         price_col: str = "price_usd_per_hr") -> pd.DataFrame:
    """Raise `IdentificationError` if no zone's elasticity is identified; warn for the rest."""
    tab = identification_table(panel, period_col, price_col)
    if not tab["identified"].any():
        raise IdentificationError(
            "no zone's price elasticity is identified: "
            + ", ".join(f"{r.zone_id} ({r.n_prices} price{'s' if r.n_prices != 1 else ''})"
                        for r in tab.itertuples())
            + ". A fit would return the prior. Elasticity needs within-zone price variation "
              "(a zone observed across a rate change) and a period effect pinned by zones "
              "whose rates did not change."
        )
    un = tab.loc[~tab["identified"], "zone_id"].tolist()
    if un:
        log.warning("elasticity not identified by the data for zones %s; their posteriors come "
                    "from the prior and the hierarchy only", un)
    return tab
