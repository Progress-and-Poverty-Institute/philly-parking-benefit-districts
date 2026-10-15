"""Figures the white paper includes that are drawn from saved results and config.

Each function takes data (a sweep table, saved `ScenarioResults`, `config/zones.yaml`) and
returns a matplotlib figure, saving it when `save_to` is given. `scripts/07_export_report_assets.py`
calls them; nothing here holds a hand-typed number.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CM_METRIC_LABELS = {
    "cruising_dwl_total": "Annual cruising DWL (USD)",
    "revenue_total": "Annual Revenue (USD)",
    "peak_occupancy_share_above_85": "Share of zones with peak occupancy above 85%",
}

_SCENARIO_STYLE = {
    "status_quo": ("Status Quo", "#888888"),
    "seattle": ("Seattle Rule", "#1f6fd1"),
    "full_pbd": ("Full PBD", "#d62728"),
}


def _save(fig, save_to) -> None:
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")


def cm_sweep_year_chart(sweep: pd.DataFrame, metric: str, save_to: Path | None = None):
    """Chatman-Manville sweep: `metric` by year for each rule, one panel per noise level.

    The line is the mean and the band is +/- 1 SD over every row of that (noise level,
    rule, year) cell, i.e. over replications and elasticity values together.
    """
    import matplotlib.pyplot as plt

    sigmas = sorted(sweep["noise_sigma"].unique())
    n_rep = int(sweep["replication"].nunique())
    fig, axes = plt.subplots(1, len(sigmas), figsize=(5.5 * len(sigmas), 4), squeeze=False, sharey=True)
    for ax, sigma in zip(axes[0], sigmas):
        sub = sweep[sweep["noise_sigma"] == sigma]
        for rule, g in sub.groupby("rule"):
            agg = g.groupby("year")[metric].agg(["mean", "std"]).sort_index()
            ax.plot(agg.index, agg["mean"], marker="o", label=rule)
            ax.fill_between(agg.index, agg["mean"] - agg["std"], agg["mean"] + agg["std"], alpha=0.2)
        ax.set_title(f"Demand noise sigma={sigma}")
        ax.set_xlabel("Year")
        ax.set_xticks(sorted(sweep["year"].unique()))
        ax.legend()
    axes[0][0].set_ylabel(CM_METRIC_LABELS.get(metric, metric))
    fig.suptitle(f"Chatman-Manville sweep (n={n_rep}): {metric}")
    fig.tight_layout()
    _save(fig, save_to)
    return fig


def occupancy_and_revenue_detail(results: dict, zone: str = "ccc", target_vacancy: float = 0.15,
                                 save_to: Path | None = None):
    """Left: one zone's mean occupancy by hour of week per scenario. Right: revenue by zone.

    `results` maps scenario name to `ScenarioResults`; zones and their order come from
    `config/zones.yaml`. A scenario whose reviews cycle is drawn at its saved (later) phase
    and labelled with it. Hours 120 and up are the weekend.
    """
    import matplotlib.pyplot as plt

    from phillyparking._config import load_config

    zones = load_config("zones")["zones"]
    zone_name = next((z["name"] for z in zones if z["id"] == zone), zone)
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(13, 4.5))

    for name, r in results.items():
        label, color = _SCENARIO_STYLE.get(name, (name, "#444444"))
        if r.diagnostics.get("phases"):
            label += f" (phase {'ab'[len(r.diagnostics['phases']) - 1]})"
        occ = r.occupancy
        if "zone_id" not in occ.columns:
            occ = occ.merge(r.prices[["segment_id", "zone_id"]].drop_duplicates(), on="segment_id")
        prof = occ[occ["zone_id"] == zone].groupby("hour_of_week")["occupancy"].mean()
        # Status quo is drawn thick and underneath: where a reform leaves an hour alone the
        # lines coincide, and a thin line there would be hidden.
        thick = name == "status_quo"
        ax_l.plot(prof.index, prof.values, color=color, label=label,
                  linewidth=4.0 if thick else 1.6, alpha=0.55 if thick else 1.0, zorder=1 if thick else 2)
    ax_l.axhline(1.0 - target_vacancy, color="red", linestyle="--", linewidth=1,
                 label=f"{1.0 - target_vacancy:.0%} target")
    ax_l.axvspan(120, 168, color="grey", alpha=0.15)
    ax_l.set_xlim(0, 167)
    ax_l.set_xlabel("Hour of week (0 = Mon midnight)")
    ax_l.set_ylabel("Mean occupancy")
    ax_l.set_title(f"{zone_name}: Occupancy by Hour of Week")
    ax_l.legend(fontsize=8)

    zone_ids = [z["id"] for z in zones]
    width = 0.8 / max(len(results), 1)
    x = np.arange(len(zone_ids))
    for i, (name, r) in enumerate(results.items()):
        label, color = _SCENARIO_STYLE.get(name, (name, "#444444"))
        rev = r.revenue.groupby("zone_id")["annual_revenue_usd"].sum().reindex(zone_ids).fillna(0.0)
        ax_r.bar(x + (i - (len(results) - 1) / 2) * width, rev.values, width, color=color, label=label)
    ax_r.set_xticks(x)
    ax_r.set_xticklabels(zone_ids)
    ax_r.set_ylabel("Annual revenue (USD)")
    ax_r.set_title("Annual Revenue by Zone and Scenario")
    ax_r.yaxis.set_major_formatter(lambda v, _: f"${v / 1e6:.1f}M")
    ax_r.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, save_to)
    return fig


def zone_map_figure(save_to: Path | None = None):
    """The pricing zones' bounding boxes from `config/zones.yaml`, drawn as given.

    These are the boxes zone assignment uses, not the neighbourhood boundaries the zone
    names suggest; drawing the boxes makes that difference visible.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    from phillyparking._config import load_config

    zones = [z for z in load_config("zones")["zones"] if z.get("bbox")]
    palette = ["#1565c0", "#42a5f5", "#2e7d32", "#e65100", "#6a1b9a", "#b71c1c", "#00838f"]
    fig, ax = plt.subplots(figsize=(7, 7))
    handles = []
    for i, z in enumerate(zones):
        b = z["bbox"]
        color = palette[i % len(palette)]
        rect = Rectangle((b["west"], b["south"]), b["east"] - b["west"], b["north"] - b["south"],
                         facecolor=color, edgecolor=color, alpha=0.35, linewidth=2, label=z["name"])
        ax.add_patch(rect)
        handles.append(rect)
        # Label at the top-left corner so nested boxes do not share a label position.
        ax.text(b["west"] + 0.002, b["north"] - 0.002, z["id"], color=color, fontsize=9,
                fontweight="bold", va="top", ha="left")
    west = min(z["bbox"]["west"] for z in zones)
    east = max(z["bbox"]["east"] for z in zones)
    south = min(z["bbox"]["south"] for z in zones)
    north = max(z["bbox"]["north"] for z in zones)
    pad = 0.01
    ax.set_xlim(west - pad, east + pad)
    ax.set_ylim(south - pad, north + pad)
    ax.set_aspect(1.0 / np.cos(np.radians((south + north) / 2)))
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Pricing zone bounding boxes (config/zones.yaml)")
    ax.legend(handles=handles, loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    _save(fig, save_to)
    return fig
