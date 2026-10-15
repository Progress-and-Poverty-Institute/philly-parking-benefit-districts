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


PLACEHOLDER_NOTE = "PLACEHOLDER: constants, not a result"


def incidence_bar_chart(
    incidence: pd.DataFrame,
    save_to: Path | None = None,
    placeholder: bool = False,
):
    """Mean payment and mean CS change by income decile.

    No pipeline stage produces decile incidence yet (it needs trip origins joined to ACS
    income). Pass `placeholder=True` for any frame that is not computed from data: the title
    and a stamp across the plot then say so, in the figure itself.
    """
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
    ax.set_title("Incidence by decile" + (f" ({PLACEHOLDER_NOTE})" if placeholder else ""))
    ax.legend()
    ax.axhline(0, color="k", linewidth=0.5)
    if placeholder:
        ax.text(0.5, 0.5, "PLACEHOLDER\nnot data", transform=ax.transAxes, ha="center", va="center",
                fontsize=44, color="red", alpha=0.25, rotation=25, fontweight="bold")
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")
    return fig


def chatman_manville_results_chart(
    sweep: pd.DataFrame,
    metric: str = "cruising_dwl_total",
    save_to: Path | None = None,
):
    """`metric` against elasticity for each rule in the sweep's last year, one panel per noise level.

    Each point is the median over replications of one elasticity x noise x rule cell in the
    final year; nothing is pooled across years or cells. A DWL metric is drawn on a log axis
    when every value is positive, because the rules differ by an order of magnitude.
    """
    import matplotlib.pyplot as plt

    last = sweep[sweep["year"] == sweep["year"].max()]
    cells = last.groupby(["noise_sigma", "rule", "elasticity"])[metric].median().reset_index()
    sigmas = sorted(cells["noise_sigma"].unique())
    fig, axes = plt.subplots(1, len(sigmas), figsize=(4.6 * len(sigmas), 4), squeeze=False, sharey=True)
    for ax, sigma in zip(axes[0], sigmas):
        for rule, g in cells[cells["noise_sigma"] == sigma].groupby("rule", sort=False):
            g = g.sort_values("elasticity")
            ax.plot(g["elasticity"], g[metric], marker="o", label=rule)
        ax.set_title(f"sigma={sigma}")
        ax.set_xlabel("Elasticity")
        if metric.startswith("cruising_dwl") and (cells[metric] > 0).all():
            ax.set_yscale("log")
    axes[0][0].legend(fontsize=8)
    axes[0][0].set_ylabel(metric)
    fig.suptitle(f"Chatman-Manville sweep, year {int(last['year'].max())}: {metric} (median over replications)")
    fig.tight_layout()
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
