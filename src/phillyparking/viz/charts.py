"""Static charts for papers."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def revenue_fan_chart(
    revenue_curves: pd.DataFrame,
    title: str = "Revenue forecast under elasticity scenarios",
    save_to: Path | None = None,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    for scenario, g in revenue_curves.groupby("scenario"):
        g = g.sort_values("year")
        ax.plot(g["year"], g["revenue_mean"], label=scenario)
        ax.fill_between(g["year"], g["revenue_lo"], g["revenue_hi"], alpha=0.2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Revenue (USD)")
    ax.set_title(title)
    ax.legend()
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")
    return fig


def incidence_bar_chart(
    incidence: pd.DataFrame,
    save_to: Path | None = None,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.4
    x = np.arange(len(incidence))
    ax.bar(x - width / 2, incidence["mean_payment"], width, label="Mean payment")
    ax.bar(x + width / 2, incidence["mean_cs_change"], width, label="Mean CS change")
    ax.set_xticks(x)
    ax.set_xticklabels(incidence["decile"].astype(str))
    ax.set_xlabel("Income decile")
    ax.set_ylabel("USD")
    ax.set_title("Incidence by decile")
    ax.legend()
    ax.axhline(0, color="k", linewidth=0.5)
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")
    return fig


def chatman_manville_results_chart(
    sweep: pd.DataFrame,
    metric: str = "cruising_dwl_total",
    save_to: Path | None = None,
):
    import matplotlib.pyplot as plt

    sigmas = sorted(sweep["noise_sigma"].unique())
    fig, axes = plt.subplots(1, len(sigmas), figsize=(5 * len(sigmas), 4), squeeze=False, sharey=True)
    for ax, sigma in zip(axes[0], sigmas):
        sub = sweep[sweep["noise_sigma"] == sigma]
        for rule, g in sub.groupby("rule"):
            agg = g.groupby("elasticity")[metric].mean()
            ax.plot(agg.index, agg.values, marker="o", label=rule)
        ax.set_title(f"sigma={sigma}")
        ax.set_xlabel("Elasticity")
        ax.legend()
    axes[0][0].set_ylabel(metric)
    fig.suptitle(f"Chatman-Manville sweep: {metric}")
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")
    return fig


def laffer_curve(
    revenue_curve: pd.DataFrame,
    save_to: Path | None = None,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(revenue_curve["price"], revenue_curve["revenue"], marker="o")
    peak = revenue_curve.loc[revenue_curve["revenue"].idxmax()]
    ax.axvline(peak["price"], color="red", linestyle="--", alpha=0.5,
               label=f"Peak @ ${peak['price']:.2f}")
    ax.set_xlabel("Price (USD/hr)")
    ax.set_ylabel("Revenue (USD)")
    ax.set_title("Laffer curve")
    ax.legend()
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")
    return fig
