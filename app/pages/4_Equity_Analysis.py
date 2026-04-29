"""Equity Analysis page: rent given away under flat $75 RPP + decile incidence."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from phillyparking._config import load_config  # noqa: E402
from phillyparking.viz.charts import incidence_bar_chart  # noqa: E402


st.set_page_config(page_title="Equity Analysis", layout="wide")
st.title("Equity Analysis")


def main() -> None:
    zones_cfg = load_config("zones")
    rpp = zones_cfg.get("rpp", {})
    base_fee = float(rpp.get("base_annual_fee_usd", 75.0))
    targets: dict[str, float] = rpp.get("market_pricing_targets_usd_per_year", {}) or {}

    st.markdown(
        f"""
### Rent currently given away under flat ${base_fee:.0f}/yr RPP

Philadelphia's Residential Permit Parking program currently charges a flat
${base_fee:.0f}/year regardless of where the permit is used. In the highest-demand
zones (Center City Core), the *market-clearing* annual price for a residential
permit is estimated at **${targets.get('ccc', 2500):,.0f}** — the difference is rent
the city is giving away to whichever residents happen to hold permits today.
        """
    )

    n_permits = st.number_input(
        "Estimated permits citywide (n_permits)",
        min_value=1_000,
        max_value=500_000,
        value=80_000,
        step=1_000,
        help="Rough total Philadelphia RPP volume. Configure as needed.",
    )

    # Mix assumption: weight market targets by a rough share of permits per zone class.
    # Without LODES yet, we use an illustrative uniform-by-zone-class average.
    mean_target = float(np.mean(list(targets.values()))) if targets else 1500.0
    rent_given_away = float(n_permits) * (mean_target - base_fee)

    st.metric(
        "Rent given away annually under flat RPP",
        f"${rent_given_away / 1e6:,.1f}M / yr",
        help=(
            f"n_permits ({n_permits:,}) × (mean market target "
            f"${mean_target:,.0f} − flat fee ${base_fee:.0f})"
        ),
    )

    with st.expander("Per-zone-class breakdown"):
        rows = []
        for zid, target in targets.items():
            rows.append(
                {
                    "zone_class": zid,
                    "market_target_usd_per_yr": float(target),
                    "current_flat_fee_usd_per_yr": base_fee,
                    "rent_per_permit": float(target) - base_fee,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.subheader("Incidence by ACS income decile (placeholder)")
    st.caption(
        "Synthetic uniform deciles. The LODES × ACS join that would replace this "
        "with real residential incidence is pending — see research doc §6."
    )
    deciles = np.arange(1, 11)
    # Uniform-ish synthetic payments and consumer-surplus changes.
    mean_payment = np.full_like(deciles, fill_value=120.0, dtype=float)
    mean_cs_change = -np.linspace(20, 200, 10)  # progressive: top deciles bear more
    incidence = pd.DataFrame(
        {
            "decile": deciles,
            "mean_payment": mean_payment,
            "mean_cs_change": mean_cs_change,
        }
    )
    st.pyplot(incidence_bar_chart(incidence))

    st.subheader("Georgist framing: where does the revenue go?")
    st.markdown(
        """
The white paper argues curb and residential-permit revenue should be treated
as a **location rent** owed to the public, not a transportation user fee.
A defensible split:

- **General Fund minimum** — at least **$35M/yr** to backfill prior PPA
  contributions (avoid a fiscal hole).
- **School District residual** — Philadelphia's School District has a
  statutory residual claim on city-collected rents; meaningful share above
  the GF minimum should flow there.
- **Parking Benefit Districts** — a per-zone share (e.g., 30% on the Mexico
  City EcoParq precedent) returns to the neighborhood that generated it,
  funding sidewalks, lighting, ADA ramps, transit shelters.

This three-way split aligns with the Georgist principle (rent → public)
*and* the Shoupian principle (visible local benefits build political
support for market pricing).
        """
    )


main()
