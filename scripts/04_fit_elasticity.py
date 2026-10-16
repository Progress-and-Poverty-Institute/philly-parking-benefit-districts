"""Fit the hierarchical elasticity model (PyMC) on a panel with observed posted prices.

The panel must carry the posted rate by calendar period, as `scripts/03b_ingest_ppa.py`
writes it (`data/processed/ppa/panel.parquet`: segment_id, zone_id, period, hour_of_week,
occupancy, price_usd_per_hr). Only priced hours (`config/zones.yaml`) enter the fit.

Before sampling, the script checks that the data identify at least one zone's elasticity
(`elasticity.identification`). If not, it exits 1. With --allow-prior-only it instead writes
the prior as the summary, labelled `prior_only`, and exits 0. It never labels a summary
`pymc_posterior` unless a fit on identified data ran.
"""
from __future__ import annotations

import logging
import sys

import click
import pandas as pd

from phillyparking._config import data_dir, load_config, outputs_dir
from phillyparking.elasticity.identification import check_identification
from phillyparking.pricing.priced_hours import frame_priced_mask

log = logging.getLogger(__name__)

NEIGHBORHOOD_FOR_ZONE = {
    "ccc": "Center City",
    "cca": "Center City",
    "ucity": "University City",
    "south_philly": "South Philly",
    "fishtown": "Fishtown",
    "other": "Other",
}


def _prior_summary() -> pd.DataFrame:
    cfg = load_config("elasticity_priors")
    mean = float(cfg["central"]["mean"])
    sd = float(cfg["central"]["sd"])
    rows = []
    for z in load_config("zones")["zones"]:
        rows.append({
            "zone_id": z["id"],
            "mean": mean,
            "sd": sd,
            "hdi_lo": mean - 2 * sd,
            "hdi_hi": mean + 2 * sd,
            "source": "prior_only",
        })
    return pd.DataFrame(rows)


def fit_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Priced hours only, with a neighborhood column for the hierarchy."""
    need = {"segment_id", "zone_id", "hour_of_week", "occupancy", "price_usd_per_hr"}
    missing = need - set(panel.columns)
    if missing:
        raise ValueError(f"panel lacks {sorted(missing)}; build it with scripts/03b_ingest_ppa.py")
    p = panel[frame_priced_mask(panel)].copy()
    if p.empty:
        raise ValueError("no panel rows fall in priced hours")
    if "neighborhood" not in p.columns:
        p["neighborhood"] = p["zone_id"].map(NEIGHBORHOOD_FOR_ZONE).fillna("Other")
    return p


@click.command()
@click.option("--panel", "panel_path", default=None, type=click.Path(),
              help="Panel parquet (default: data/processed/ppa/panel.parquet).")
@click.option("--allow-prior-only", is_flag=True,
              help="If the data identify no elasticity, write the prior (labelled prior_only) "
                   "and exit 0 instead of exiting 1.")
@click.option("--draws", default=500, type=int)
@click.option("--tune", default=500, type=int)
@click.option("--chains", default=2, type=int)
@click.option("--seed", default=42, type=int)
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(panel_path, allow_prior_only, draws, tune, chains, seed, verbose) -> None:
    """Fit elasticity model; write fit + posterior summary into outputs/models/elasticity_fit/."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    path = panel_path or (data_dir() / "processed" / "ppa" / "panel.parquet")
    out_dir = outputs_dir() / "models" / "elasticity_fit"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.parquet"

    try:
        panel = fit_panel(pd.read_parquet(path))
        log.info("Loaded panel %s (priced-hour rows=%d)", path, len(panel))
        tab = check_identification(panel)
        log.info("Identification:\n%s", tab.to_string(index=False))
    except (FileNotFoundError, ValueError) as exc:  # IdentificationError is a ValueError
        log.error("Cannot fit: %s", exc)
        if not allow_prior_only:
            sys.exit(1)
        _prior_summary().to_parquet(summary_path)
        print(f"elasticity: data identify nothing; wrote the PRIOR (prior_only) -> {summary_path}")
        return

    from phillyparking.elasticity.hierarchical_bayes import (
        fit_elasticity_model, posterior_zone_elasticity, save_fit,
    )
    log.info("Fitting PyMC model (draws=%d tune=%d chains=%d)", draws, tune, chains)
    fit = fit_elasticity_model(panel, draws=draws, tune=tune, chains=chains, seed=seed)
    save_fit(fit, out_dir / "fit.pkl")
    summary = posterior_zone_elasticity(fit).merge(tab, on="zone_id", how="left")
    summary["source"] = "pymc_posterior"
    summary.to_parquet(summary_path)
    print(f"elasticity fit -> {summary_path}")


if __name__ == "__main__":
    main()
