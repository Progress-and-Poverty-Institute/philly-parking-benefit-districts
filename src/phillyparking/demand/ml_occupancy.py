"""XGBoost occupancy estimator on logit(occupancy)."""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from phillyparking.demand.features import segment_features, time_features


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1.0 - p))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _build_X(panel: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    seg_x = segment_features(segments)
    panel_t = time_features(panel)
    merged = panel_t.merge(seg_x, left_on="segment_id", right_index=True, how="left")
    feature_cols = list(seg_x.columns) + [
        "hour", "dow", "is_weekday", "is_peak", "is_evening", "hour_sin", "hour_cos",
    ]
    return merged[feature_cols]


class MLOccupancyModel:
    def __init__(self, n_estimators: int = 400, max_depth: int = 6, seed: int = 42):
        from xgboost import XGBRegressor
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.seed = seed
        self.model = XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=0.05,
            random_state=seed,
            tree_method="hist",
            n_jobs=1,
        )
        self.feature_cols: list[str] | None = None

    def fit(self, panel: pd.DataFrame, segments: pd.DataFrame) -> "MLOccupancyModel":
        X = _build_X(panel, segments)
        y = _logit(panel["occupancy"].to_numpy())
        self.feature_cols = list(X.columns)
        self.model.fit(X.to_numpy(), y)
        return self

    def predict(self, panel_template: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
        X = _build_X(panel_template, segments)
        y_logit = self.model.predict(X.to_numpy())
        out = panel_template[["segment_id", "hour_of_week"] if "hour_of_week" in panel_template.columns
                             else ["segment_id", "timestamp"]].copy()
        out["occupancy"] = _sigmoid(y_logit)
        return out

    def save(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "feature_cols": self.feature_cols,
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "seed": self.seed,
            }, f)
        return path

    @classmethod
    def load(cls, path) -> "MLOccupancyModel":
        with open(path, "rb") as f:
            blob = pickle.load(f)
        obj = cls(n_estimators=blob["n_estimators"], max_depth=blob["max_depth"], seed=blob["seed"])
        obj.model = blob["model"]
        obj.feature_cols = blob["feature_cols"]
        return obj
