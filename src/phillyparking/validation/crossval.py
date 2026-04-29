"""Spatial K-fold CV for ML occupancy models."""
from __future__ import annotations

from typing import Callable, Iterator

import numpy as np
import pandas as pd

from phillyparking.validation.calibration import calibration_slope


def neighborhood_kfold(
    panel: pd.DataFrame,
    n_splits: int = 5,
    seed: int = 42,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    nbhds = pd.Series(panel["neighborhood"]).astype(str).unique()
    rng.shuffle(nbhds)
    folds = np.array_split(nbhds, n_splits)
    idx = np.arange(len(panel))
    nbhd_arr = panel["neighborhood"].astype(str).to_numpy()
    for fold_nbhds in folds:
        test_mask = np.isin(nbhd_arr, fold_nbhds)
        yield idx[~test_mask], idx[test_mask]


def evaluate_occupancy_model(
    model_factory: Callable[[], "object"],
    panel: pd.DataFrame,
    segments: pd.DataFrame,
    n_splits: int = 5,
    seed: int = 42,
) -> pd.DataFrame:
    if "neighborhood" not in panel.columns:
        panel = panel.merge(segments[["segment_id", "neighborhood"]], on="segment_id", how="left")

    rows = []
    for fold, (train_idx, test_idx) in enumerate(neighborhood_kfold(panel, n_splits=n_splits, seed=seed)):
        train = panel.iloc[train_idx]
        test = panel.iloc[test_idx]
        model = model_factory()
        model.fit(train, segments)
        y_pred = np.asarray(model.predict(test, segments), dtype=float)
        y_true = test["occupancy"].to_numpy(dtype=float)
        mae = float(np.mean(np.abs(y_true - y_pred)))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        slope = calibration_slope(y_true, y_pred)
        rows.append({"fold": fold, "mae": mae, "rmse": rmse, "calibration_slope": slope, "n_test": len(test)})
    return pd.DataFrame(rows)
