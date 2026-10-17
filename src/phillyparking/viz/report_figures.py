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
    "welfare_change": "Welfare change since the start (USD a year)",
    "cs_change": "Consumer surplus change since the start (USD a year)",
    "revenue": "Annual revenue, priced hours (USD)",
    "search_cost": "Annual search cost (USD)",
    "search_cost_per_cruising_minute": "Annual search cost per cruising minute of the level (USD)",
    "share_block_hours_above_high": "Share of priced block-hours above the band",
    "share_block_hours_below_low": "Share of priced block-hours below the band",
    "mean_price": "Mean price, priced hours (USD/hr)",
}
CM_AXIS_LABELS = {
    "elasticity": "elasticity", "start_occupancy": "start mean occupancy m",
    "block_dispersion": "block dispersion tau", "observation_noise": "observation noise sigma",
    "occupancy_cap": "search cost cap",
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


def cm_sweep_year_chart(sweep: pd.DataFrame, metric: str, facet: str = "start_occupancy",
                        save_to: Path | None = None, fixed: dict | None = None):
    """Chatman-Manville sweep: `metric` by year for each rule, one panel per value of `facet`.

    Each point is built from per-cell medians (median over replications within one cell of
    the sweep's axes x rule x year). The line is the median of those cell medians across the
    other axes and the band is their minimum to maximum, so the band is the spread between
    cells, not a standard deviation of pooled rows. `fixed` holds axes to fix at one value
    (for example the search-cost cap, so that `search_cost` and `welfare_change` are drawn
    at one scoring and not pooled across caps); they are named in the title.
    """
    import matplotlib.pyplot as plt
    from phillyparking.scenarios.cm_sweep import AXES

    fixed = dict(fixed or {})
    for k, v in fixed.items():
        sweep = sweep[np.isclose(sweep[k], v)]
    if sweep.empty:
        raise ValueError(f"no sweep rows at {fixed}")
    axes_cols = [a for a in AXES if a in sweep.columns and a not in fixed]
    cells = sweep.groupby(axes_cols + ["rule", "year"])[metric].median().reset_index()
    levels = sorted(cells[facet].unique())
    others = [a for a in axes_cols if a != facet]
    n_rep = int(sweep["replication"].nunique())
    n_other = int(cells.groupby(others).ngroups) if others else 1
    fig, axes = plt.subplots(1, len(levels), figsize=(4.6 * len(levels), 4), squeeze=False, sharey=True)
    for ax, level in zip(axes[0], levels):
        sub = cells[cells[facet] == level]
        for rule, g in sub.groupby("rule", sort=False):
            agg = g.groupby("year")[metric].agg(["median", "min", "max"]).sort_index()
            ax.plot(agg.index, agg["median"], marker="o", label=rule)
            ax.fill_between(agg.index, agg["min"], agg["max"], alpha=0.15)
        ax.set_title(f"{CM_AXIS_LABELS.get(facet, facet)} = {level}")
        ax.set_xlabel("Year")
        ax.set_xticks(sorted(sweep["year"].unique()))
        ax.axhline(0, color="black", lw=0.5)
    axes[0][0].legend(fontsize=8)
    axes[0][0].set_ylabel(CM_METRIC_LABELS.get(metric, metric))
    fixed_note = "".join(f"; {CM_AXIS_LABELS.get(k, k)} = {v:g}" for k, v in fixed.items())
    fig.suptitle(f"Chatman-Manville sweep (n={n_rep} replications): {metric}{fixed_note}; "
                 f"line = median, band = range over {n_other} cells of the other axes")
    fig.tight_layout()
    _save(fig, save_to)
    return fig


def cm_breakeven_chart(paired: pd.DataFrame, comparison: tuple[str, str], year: int | None = None,
                       save_to: Path | None = None, cap_minutes: float = 60.0):
    """Breakeven search time for one comparison: one row of panels per search-cost cap, one
    panel per start occupancy, bars by block dispersion.

    The breakeven is in the search-cost level's units, the mean cruising time of the
    drivers who cruise when every block is full (`breakeven_cruising_minutes`). Each bar is the median
    over replications within one cell (one elasticity and noise level); bars within a group
    are the cells of elasticity x noise. Above the bar the higher-priced rule gives more
    welfare; below it the lower-priced rule does. Blue bars: the comparator searches more
    (prices lower); red: it searches less. The shaded band is the range of average cruising
    times the config cites (`cited_cruising_minutes`, Shoup 2006, Table 1), with its mean as
    a line, in the same units as the bars. For a same-instrument pair the sign of the bars is a
    property of the design (see `cm_sweep.paired_table`); their size against the band is
    the content. The axis is capped at `cap_minutes`.
    """
    import matplotlib.pyplot as plt
    from phillyparking.welfare.search_cost import cited_cruising_minutes

    comparator, reference = comparison
    year = int(paired["year"].max()) if year is None else int(year)
    p = paired[(paired["rule"] == comparator) & (paired["reference"] == reference) & (paired["year"] == year)]
    if p.empty:
        raise ValueError(f"no rows for {comparison} at year {year}")
    col = "breakeven_cruising_minutes_median"
    levels = sorted(p["start_occupancy"].unique())
    taus = sorted(p["block_dispersion"].unique())
    caps = sorted(p["occupancy_cap"].unique())
    cited = cited_cruising_minutes()
    fig, axes = plt.subplots(len(caps), len(levels), figsize=(4.6 * len(levels), 3.6 * len(caps)),
                             squeeze=False, sharey=True)
    for r, cap in enumerate(caps):
        for ax, level in zip(axes[r], levels):
            sub = p[(p["start_occupancy"] == level) & np.isclose(p["occupancy_cap"], cap)]
            for k, tau in enumerate(taus):
                g = sub[sub["block_dispersion"] == tau].sort_values(["elasticity", "observation_noise"])
                n = len(g)
                x = k + (np.arange(n) - (n - 1) / 2) * (0.8 / max(n, 1))
                ax.bar(x, g[col], width=0.8 / max(n, 1),
                       color=["#1f6fd1" if m else "#d62728" for m in g["share_comparator_searches_more"] > 0.5])
            ax.axhspan(cited["low"], cited["high"], color="#999999", alpha=0.25,
                       label=f"cited average cruising time of those who cruise ({cited['low']:g}-{cited['high']:g} min)")
            ax.axhline(cited["mean"], color="#555555", ls="--", lw=0.8, label=f"cited mean ({cited['mean']:g} min)")
            ax.set_xticks(range(len(taus)))
            ax.set_xticklabels([f"tau={t}" for t in taus])
            ax.set_title(f"start mean occupancy m = {level}; search cost cap = {cap:g}", fontsize=10)
        axes[r][0].set_ylabel("Breakeven cruising minutes\n(per cruiser, blocks full)")
    axes[0][0].legend(fontsize=7, loc="upper left")
    # Where the two rules price nearly alike the breakeven is a ratio of two small numbers;
    # the axis is capped so the informative bars stay readable (bars beyond it are clipped).
    lo = min(0.0, float(p[col].min()))
    hi = max(float(p[col].max()) * 1.05, cited["high"] * 1.1) + 1e-9
    axes[0][0].set_ylim(max(lo, -cap_minutes), min(hi, cap_minutes))
    fig.suptitle(f"{comparator} vs {reference}, year {year}: cruising time per cruiser, blocks full, at "
                 f"which the two rules give equal welfare (bars: cells of elasticity x noise)")
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
