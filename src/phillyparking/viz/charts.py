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
    metric: str = "welfare_change",
    save_to: Path | None = None,
):
    """`metric` against block dispersion for each rule in the sweep's last year, one panel per start level.

    Each point is the median over replications and over the other axes' cell medians of one
    start level x dispersion x rule cell in the final year; nothing is pooled across years.
    """
    import matplotlib.pyplot as plt
    from phillyparking.scenarios.cm_sweep import AXES

    last = sweep[sweep["year"] == sweep["year"].max()]
    axes_cols = [a for a in AXES if a in last.columns]
    cells = last.groupby(axes_cols + ["rule"])[metric].median().reset_index()
    cells = cells.groupby(["start_occupancy", "block_dispersion", "rule"])[metric].median().reset_index()
    levels = sorted(cells["start_occupancy"].unique())
    fig, axes = plt.subplots(1, len(levels), figsize=(4.6 * len(levels), 4), squeeze=False, sharey=True)
    for ax, level in zip(axes[0], levels):
        for rule, g in cells[cells["start_occupancy"] == level].groupby("rule", sort=False):
            g = g.sort_values("block_dispersion")
            ax.plot(g["block_dispersion"], g[metric], marker="o", label=rule)
        ax.set_title(f"start mean occupancy m={level}")
        ax.set_xlabel("Block dispersion tau")
        ax.axhline(0, color="black", lw=0.5)
    axes[0][0].legend(fontsize=8)
    axes[0][0].set_ylabel(metric)
    fig.suptitle(f"Chatman-Manville sweep, year {int(last['year'].max())}: {metric} (median over cells)")
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
    rc = revenue_curve.sort_values("price").reset_index(drop=True)
    ax.plot(rc["price"], rc["revenue"], marker="o")
    k = int(rc["revenue"].idxmax())
    if 0 < k < len(rc) - 1:
        ax.axvline(rc.loc[k, "price"], color="red", linestyle="--", alpha=0.5,
                   label=f"Peak @ ${rc.loc[k, 'price']:.2f}")
    else:
        # The maximum sits on the edge of the grid: the curve has no peak in this range.
        ax.plot([], [], " ", label="no peak within the price range shown")
    ax.set_xlabel("Price (USD/hr)")
    ax.set_ylabel("Revenue (USD)")
    ax.set_title("Revenue against price")
    ax.legend()
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")
    return fig
