"""Scenario Comparison page: table + bar charts for the three scenarios."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from phillyparking.scenarios.compare import comparison_table  # noqa: E402

from streamlit_app import get_scenarios  # noqa: E402


st.set_page_config(page_title="Scenario Comparison", layout="wide")
st.title("Scenario Comparison")


@st.cache_data
def _comparison_df_cached(_results_keys: tuple[str, ...]) -> pd.DataFrame:
    # Fetch fresh (cache_data hashes args; we use the keys tuple as a cheap key).
    results = get_scenarios()
    return comparison_table(results)


def _bar_chart(df: pd.DataFrame, metric: str, title: str | None = None):
    fig, ax = plt.subplots(figsize=(7, 4))
    if metric in df.index:
        row = df.loc[metric]
        ax.bar(row.index, row.values.astype(float))
        ax.set_ylabel(metric)
        ax.set_title(title or metric)
        ax.tick_params(axis="x", rotation=20)
    else:
        ax.text(0.5, 0.5, f"Metric '{metric}' missing", ha="center", va="center")
        ax.set_axis_off()
    fig.tight_layout()
    return fig


def main() -> None:
    results = get_scenarios()
    df = _comparison_df_cached(tuple(results.keys()))

    st.subheader("Comparison table")
    st.dataframe(df, use_container_width=True)

    st.subheader("Headline metrics")
    metrics = [
        ("total_revenue", "Total annual curb revenue (USD)"),
        ("cruising_dwl_total", "Annual cruising deadweight loss (USD)"),
        ("mean_price_ccc", "Mean price — Center City Core (USD/hr)"),
        ("mean_price_cca", "Mean price — Center City Area (USD/hr)"),
    ]
    cols = st.columns(2)
    for i, (m, label) in enumerate(metrics):
        with cols[i % 2]:
            st.pyplot(_bar_chart(df, m, label))

    st.subheader("Highlight a metric")
    options = [m for m, _ in metrics] + [
        "cs_change_total",
        "n_zones_at_ceiling",
        "pbd_revenue",
    ]
    options = [o for o in options if o in df.index]
    metric_choice = st.radio(
        "Metric", options=options, horizontal=True, index=0
    )
    st.pyplot(_bar_chart(df, metric_choice, metric_choice))


main()
