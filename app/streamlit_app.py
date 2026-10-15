"""Streamlit landing page for the Philadelphia curb pricing policy tool."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure the src/ layout is importable when running `streamlit run app/streamlit_app.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from phillyparking.scenarios.runner import (  # noqa: E402
    ScenarioResults,
    default_results_dir,
    load_saved_scenarios,
)


st.set_page_config(page_title="Philly Curb Pricing", layout="wide")


@st.cache_resource
def get_scenarios() -> dict[str, ScenarioResults]:
    """Load the scenario results scripts 05 and 06 write (`default_results_dir()`).

    Cached for the lifetime of the Streamlit process so all pages share one copy. It never
    recomputes: if the results are missing the app stops and says how to produce them, so
    the numbers shown always come from a recorded run (see `provenance` in each meta.json).
    """
    try:
        return load_saved_scenarios(default_results_dir())
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()


def _sidebar() -> None:
    st.sidebar.header("Controls")
    st.sidebar.selectbox(
        "Elasticity scenario",
        options=["pessimistic", "central", "optimistic"],
        index=1,
        key="elasticity_scenario",
        help=(
            "Selects the price-elasticity prior. Note: the cached scenario "
            "results currently use 'central' for all three policy bundles. "
            "This selector is a future hook for re-running with a different "
            "elasticity scenario."
        ),
    )
    if st.sidebar.button("Reset cache"):
        get_scenarios.clear()
        st.sidebar.success("Cache cleared. Re-run a page to recompute.")


def main() -> None:
    _sidebar()

    st.title("Philadelphia Curb Pricing & Parking Benefit Districts")

    st.markdown(
        """
This tool models curb-pricing reform for Philadelphia by combining three
intellectual traditions:

- **Shoupian curb pricing** — set meter prices to target ~85% occupancy so a
  driver can almost always find a space without circling. Eliminate cruising
  deadweight loss.
- **Georgist land-rent capture** — the value of a curb space is largely a
  *location rent* created by the surrounding city. Charging market prices for
  curb and residential permits captures rent that is currently given away,
  and earmarks it for local public goods (a Parking Benefit District).
- **Academic transportation economics** — Arnott / Inci optimal pricing,
  Chatman-Manville rule sensitivity, Lehner-Peer (2019) elasticity meta.

### What's in this app

- **Map** — Folium choropleth of segment-level prices under each scenario.
- **Scenario Comparison** — side-by-side table and bar charts for
  *status quo* vs. *Seattle rule* vs. *Full PBD*.
- **Revenue Forecast** — Laffer-style curve and 10-year fan chart by
  elasticity prior, with CSV download.
- **Equity Analysis** — rent currently given away under flat $75 RPP, plus
  placeholder ACS-decile incidence (LODES join pending).

Use the sidebar on the left to navigate between pages.
        """
    )

    # Trigger a load so subsequent pages hit a warm cache.
    with st.spinner("Loading scenarios..."):
        results = get_scenarios()

    st.success(f"Loaded {len(results)} scenarios: {', '.join(results.keys())}")
    src = next(iter(results.values())).provenance.get("segment_source", {})
    st.caption(f"Segment source: {src or 'not recorded (results predate provenance)'}")

    cols = st.columns(3)
    for col, (name, r) in zip(cols, results.items()):
        col.metric(
            name.replace("_", " ").title(),
            f"${r.revenue['annual_revenue_usd'].sum() / 1e6:.1f}M",
            help=f"Annual curb revenue under '{name}'",
        )


if __name__ == "__main__":
    main()
else:
    main()
