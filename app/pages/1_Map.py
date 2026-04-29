"""Map page: Folium choropleth of segment prices under a chosen scenario."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from phillyparking.spatial.segments import load_segments  # noqa: E402
from phillyparking.viz.maps import segment_map, zone_choropleth  # noqa: E402

# Pull the shared scenario cache from the landing page.
from streamlit_app import get_scenarios  # noqa: E402


st.set_page_config(page_title="Map", layout="wide")
st.title("Map: segment-level prices by scenario")


@st.cache_data
def _load_segments_cached():
    return load_segments()


def _zone_prices(prices_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse segment-level prices to one row per zone."""
    return (
        prices_df.groupby("zone_id", as_index=False)["price_usd_per_hr"]
        .mean()
        .rename(columns={"price_usd_per_hr": "value"})
    )


def main() -> None:
    results = get_scenarios()
    scenario_name = st.sidebar.selectbox(
        "Scenario",
        options=list(results.keys()),
        index=0,
    )
    r = results[scenario_name]

    try:
        segments = _load_segments_cached()
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load segments: {e}")
        return

    zone_metric = _zone_prices(r.prices)

    # Try the choropleth helper; fall back to the segment_map.
    folium_map = None
    try:
        folium_map = zone_choropleth(segments, zone_metric, metric_name="price_usd_per_hr")
    except Exception:
        try:
            seg_with_price = segments.merge(
                zone_metric.rename(columns={"value": "current_rate"}),
                on="zone_id",
                how="left",
            )
            folium_map = segment_map(seg_with_price, color_by="current_rate")
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not render map: {e}")

    if folium_map is not None:
        try:
            from streamlit_folium import folium_static  # type: ignore

            folium_static(folium_map, width=1100, height=600)
        except ImportError:
            st.markdown(
                folium_map._repr_html_(),
                unsafe_allow_html=True,
            )
            st.caption(
                "Tip: `pip install streamlit-folium` for an interactive embed."
            )

    st.subheader(f"Zone summary — scenario: {scenario_name}")

    # Build per-zone table: zone_id, current price, scenario price, expected occ, revenue.
    from phillyparking._config import load_config

    zones_cfg = load_config("zones")["zones"]
    zone_meta = pd.DataFrame(
        [
            {
                "zone_id": z["id"],
                "zone_name": z.get("name", z["id"]),
                "current_price_usd_per_hr": float(z["current_rate_usd_per_hr"]),
            }
            for z in zones_cfg
        ]
    )
    scenario_price = (
        r.prices.groupby("zone_id", as_index=False)["price_usd_per_hr"]
        .mean()
        .rename(columns={"price_usd_per_hr": "scenario_price_usd_per_hr"})
    )
    occ = (
        r.occupancy.groupby("zone_id", as_index=False)["occupancy"].mean()
        if "zone_id" in r.occupancy.columns
        else r.occupancy.merge(
            r.prices[["segment_id", "zone_id"]].drop_duplicates(),
            on="segment_id",
            how="left",
        )
        .groupby("zone_id", as_index=False)["occupancy"]
        .mean()
    )
    rev = r.revenue.groupby("zone_id", as_index=False)["annual_revenue_usd"].sum()

    table = (
        zone_meta.merge(scenario_price, on="zone_id", how="left")
        .merge(occ, on="zone_id", how="left")
        .merge(rev, on="zone_id", how="left")
    )
    st.dataframe(table, use_container_width=True)


main()
