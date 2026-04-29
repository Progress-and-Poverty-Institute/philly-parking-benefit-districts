"""Revenue Forecast page: Laffer curve + 10-year fan chart by elasticity."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from phillyparking._config import load_config  # noqa: E402
from phillyparking.demand.synthetic_baseline import baseline_occupancy  # noqa: E402
from phillyparking.elasticity.scenarios import all_scenarios, apply_elasticity  # noqa: E402
from phillyparking.revenue.forecast import revenue_curve  # noqa: E402
from phillyparking.viz.charts import laffer_curve, revenue_fan_chart  # noqa: E402


st.set_page_config(page_title="Revenue Forecast", layout="wide")
st.title("Revenue Forecast")


@st.cache_data
def _segments_and_panel(seed: int = 42):
    from tests.fixtures import make_synthetic_segments

    segments = make_synthetic_segments(n=20)
    panel = baseline_occupancy(segments, seed=seed)
    return segments, panel


@st.cache_data
def _zones_df() -> pd.DataFrame:
    zones = load_config("zones")["zones"]
    return pd.DataFrame(
        [
            {
                "zone_id": z["id"],
                "zone_name": z.get("name", z["id"]),
                "current_rate_usd_per_hr": float(z["current_rate_usd_per_hr"]),
            }
            for z in zones
        ]
    )


def _baseline_prices() -> pd.DataFrame:
    zdf = _zones_df()
    return zdf.rename(columns={"current_rate_usd_per_hr": "price_usd_per_hr"})[
        ["zone_id", "price_usd_per_hr"]
    ]


def main() -> None:
    zones = _zones_df()
    zone_id = st.sidebar.selectbox(
        "Zone (Laffer curve)",
        options=zones["zone_id"].tolist(),
        format_func=lambda z: f"{z} — {zones.set_index('zone_id').loc[z, 'zone_name']}",
    )
    elasticity = st.sidebar.slider(
        "Own-price elasticity (Laffer)",
        min_value=-1.0,
        max_value=-0.1,
        value=-0.4,
        step=0.05,
    )
    mult_lo, mult_hi = st.sidebar.slider(
        "Price multiplier range",
        min_value=0.25,
        max_value=4.0,
        value=(0.5, 3.0),
        step=0.25,
    )

    try:
        segments, panel = _segments_and_panel()
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not build synthetic baseline: {e}")
        return

    baseline_prices = _baseline_prices()

    # --- Laffer curve for the selected zone ---
    grid = np.linspace(mult_lo, mult_hi, 26)
    rc = revenue_curve(
        segments=segments,
        baseline_panel=panel,
        baseline_prices=baseline_prices,
        elasticity=elasticity,
        price_multiplier_grid=grid,
    )
    rc_zone = rc[rc["zone_id"] == zone_id].sort_values("price")
    st.subheader(f"Laffer curve — zone {zone_id} (elasticity {elasticity:+.2f})")
    if rc_zone.empty:
        st.warning(f"No revenue curve data for zone {zone_id}.")
    else:
        st.pyplot(laffer_curve(rc_zone[["price", "revenue"]].copy()))

    # --- 10-year fan chart across the three named elasticity scenarios ---
    st.subheader("10-year revenue projection by elasticity scenario")
    horizon = 10
    scenarios = all_scenarios()

    # Project revenue with a simple compounding loop. We fix prices at the
    # Seattle-style 1.5x of current rate as an illustrative path; demand
    # responds via apply_elasticity, then we re-aggregate annual revenue.
    target_prices = baseline_prices.assign(
        price_usd_per_hr=lambda d: d["price_usd_per_hr"] * 1.5
    )

    panel_with_zone = panel.merge(
        segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left"
    ).merge(baseline_prices, on="zone_id", how="left")

    fan_rows: list[dict] = []
    rng = np.random.default_rng(42)
    for sc in scenarios:
        eps_mean = sc.elasticity
        eps_sd = sc.sd
        cur_panel = panel_with_zone.copy()
        # Year-by-year compounding: each year apply elasticity once, slight
        # demand drift via noise. Track annual revenue across all zones.
        for year in range(1, horizon + 1):
            cur_panel = apply_elasticity(cur_panel, target_prices, eps_mean)
            yearly_rev = float(
                (
                    cur_panel["occupancy"]
                    * cur_panel["capacity"]
                    * cur_panel["price_usd_per_hr"]
                ).sum()
                * 52.0
            )
            # Synthetic 90% interval from elasticity SD: scale revenue by
            # exp(±1.645 * sd * ln(price ratio)) — a back-of-envelope band.
            ratio = 1.5  # price multiplier vs. baseline
            band = abs(np.log(ratio)) * eps_sd * 1.645
            lo = yearly_rev * np.exp(-band)
            hi = yearly_rev * np.exp(+band)
            fan_rows.append(
                {
                    "scenario": sc.name,
                    "year": year,
                    "revenue_mean": yearly_rev,
                    "revenue_lo": lo,
                    "revenue_hi": hi,
                }
            )

    fan_df = pd.DataFrame(fan_rows)
    st.pyplot(revenue_fan_chart(fan_df, title="10-year revenue by elasticity scenario"))

    st.dataframe(fan_df, use_container_width=True)
    csv = fan_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download forecast (CSV)",
        data=csv,
        file_name="revenue_forecast_10y.csv",
        mime="text/csv",
    )


main()
