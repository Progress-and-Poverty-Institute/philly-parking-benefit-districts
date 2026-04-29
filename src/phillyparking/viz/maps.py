"""Folium maps. Used by Streamlit and notebooks."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _colormap(values: np.ndarray, scale: str = "viridis"):
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    cmap = cm.get_cmap(scale)
    vmin, vmax = float(np.nanmin(values)), float(np.nanmax(values))
    if vmax == vmin:
        vmax = vmin + 1e-9
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    return [mcolors.to_hex(cmap(norm(v))) for v in values]


def segment_map(
    segments,
    color_by: str = "current_rate",
    color_scale: str = "viridis",
    tooltip_cols: list[str] | None = None,
    zoom_start: int = 13,
    save_to: Path | None = None,
):
    import folium

    centroid = segments.geometry.unary_union.centroid
    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=zoom_start)
    values = segments[color_by].to_numpy(dtype=float) if color_by in segments.columns else np.zeros(len(segments))
    colors = _colormap(values, color_scale)
    tooltip_cols = tooltip_cols or ["segment_id", color_by]
    for (_, row), color in zip(segments.iterrows(), colors):
        coords = [(y, x) for x, y in row.geometry.coords]
        tooltip = "<br>".join(f"{c}: {row[c]}" for c in tooltip_cols if c in row.index)
        folium.PolyLine(coords, color=color, weight=4, tooltip=tooltip).add_to(m)
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        m.save(str(save_to))
    return m


def zone_choropleth(
    segments,
    metric: pd.DataFrame,
    metric_name: str = "value",
    save_to: Path | None = None,
):
    import folium

    seg_with_metric = segments.merge(metric, on="zone_id", how="left")
    centroid = segments.geometry.unary_union.centroid
    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=13)
    values = seg_with_metric["value"].to_numpy(dtype=float)
    colors = _colormap(values, "viridis")
    for (_, row), color in zip(seg_with_metric.iterrows(), colors):
        coords = [(y, x) for x, y in row.geometry.coords]
        folium.PolyLine(coords, color=color, weight=4,
                        tooltip=f"{row['zone_id']}: {metric_name}={row['value']:.2f}").add_to(m)
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        m.save(str(save_to))
    return m


def occupancy_heatmap(
    panel: pd.DataFrame,
    save_to: Path | None = None,
):
    import matplotlib.pyplot as plt

    pivot = panel.pivot_table(index="zone_id", columns="hour_of_week", values="occupancy", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(12, max(2, 0.4 * len(pivot))))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="magma", vmin=0, vmax=1)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("Hour of week")
    ax.set_title("Occupancy heatmap")
    fig.colorbar(im, ax=ax, label="Occupancy")
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_to, dpi=150, bbox_inches="tight")
    return fig
