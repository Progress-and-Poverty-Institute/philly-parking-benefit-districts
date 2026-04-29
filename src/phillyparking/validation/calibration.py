"""Calibration plots and reliability diagnostics."""
from __future__ import annotations

import numpy as np
import pandas as pd


def calibration_curve(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    quantiles = np.linspace(0, 1, n_bins + 1)
    edges = np.quantile(y_pred, quantiles)
    edges[0] -= 1e-9
    edges[-1] += 1e-9
    bins = np.digitize(y_pred, edges[1:-1])
    rows = []
    for b in range(n_bins):
        mask = bins == b
        n = int(mask.sum())
        if n == 0:
            rows.append({"bin": b, "mean_pred": np.nan, "mean_true": np.nan, "n": 0, "ci_lo": np.nan, "ci_hi": np.nan})
            continue
        mean_pred = float(y_pred[mask].mean())
        mean_true = float(y_true[mask].mean())
        sd = float(y_true[mask].std(ddof=1)) if n > 1 else 0.0
        se = sd / np.sqrt(n) if n > 0 else 0.0
        rows.append({
            "bin": b,
            "mean_pred": mean_pred,
            "mean_true": mean_true,
            "n": n,
            "ci_lo": mean_true - 1.96 * se,
            "ci_hi": mean_true + 1.96 * se,
        })
    return pd.DataFrame(rows)


def calibration_slope(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    var = np.var(y_pred)
    if var == 0:
        return float("nan")
    cov = np.mean((y_pred - y_pred.mean()) * (y_true - y_true.mean()))
    return float(cov / var)


def reliability_diagram(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bins: int = 10,
    ax=None,
):
    import matplotlib.pyplot as plt
    curve = calibration_curve(y_true, y_pred, n_bins=n_bins)
    if ax is None:
        _, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect")
    ax.errorbar(
        curve["mean_pred"], curve["mean_true"],
        yerr=[curve["mean_true"] - curve["ci_lo"], curve["ci_hi"] - curve["mean_true"]],
        marker="o", linestyle="-", label="Observed",
    )
    ax.set_xlabel("Mean predicted")
    ax.set_ylabel("Mean observed")
    ax.set_title("Reliability diagram")
    ax.legend()
    return ax
