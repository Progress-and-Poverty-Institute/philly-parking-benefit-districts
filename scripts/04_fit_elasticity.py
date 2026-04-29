"""Fit the hierarchical elasticity model (PyMC) with a prior-only fallback."""
from __future__ import annotations

import logging
from pathlib import Path

import click
import pandas as pd

from phillyparking._config import data_dir, outputs_dir, load_config
from phillyparking.spatial.segments import load_segments, build_segments, save_segments
from phillyparking.spatial.zones import assign_zones
from phillyparking.demand.synthetic_baseline import baseline_occupancy

log = logging.getLogger(__name__)

NEIGHBORHOOD_FOR_ZONE = {
    "ccc": "Center City",
    "cca": "Center City",
    "ucity": "University City",
    "south_philly": "South Philly",
    "fishtown": "Fishtown",
    "other": "Other",
}


def _zone_prices() -> pd.DataFrame:
    zones = load_config("zones")["zones"]
    return pd.DataFrame([
        {"zone_id": z["id"], "price_usd_per_hr": float(z["current_rate_usd_per_hr"])}
        for z in zones
    ])


def _attach_meta(panel: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    seg_meta = pd.DataFrame(segments)[["segment_id", "zone_id"]].copy()
    if "neighborhood" in segments.columns:
        seg_meta["neighborhood"] = segments["neighborhood"]
    else:
        seg_meta["neighborhood"] = seg_meta["zone_id"].map(NEIGHBORHOOD_FOR_ZONE).fillna("Other")
    seg_meta["neighborhood"] = seg_meta["neighborhood"].fillna(
        seg_meta["zone_id"].map(NEIGHBORHOOD_FOR_ZONE).fillna("Other")
    )
    p = panel.drop(columns=[c for c in ("zone_id", "neighborhood") if c in panel.columns])
    p = p.merge(seg_meta, on="segment_id", how="left")
    p = p.merge(_zone_prices(), on="zone_id", how="left")
    return p


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


@click.command()
@click.option("--draws", default=500, type=int)
@click.option("--tune", default=500, type=int)
@click.option("--chains", default=2, type=int)
@click.option("--seed", default=42, type=int)
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(draws: int, tune: int, chains: int, seed: int, verbose: bool) -> None:
    """Fit elasticity model; write fit + posterior summary into outputs/models/."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    proc = data_dir() / "processed"
    seg_path = proc / "segments.parquet"
    panel_path = proc / "demand_panel.parquet"

    try:
        segs = load_segments(seg_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load segments (%s); rebuilding", exc)
        segs = build_segments()
        segs = assign_zones(segs)
        save_segments(segs, seg_path)

    if panel_path.exists():
        panel = pd.read_parquet(panel_path)
        log.info("Loaded panel %s (rows=%d)", panel_path, len(panel))
    else:
        log.info("Panel missing; computing baseline_occupancy")
        panel = baseline_occupancy(segs, seed=seed)
        panel.to_parquet(panel_path)

    panel_full = _attach_meta(panel, segs)

    out_dir = outputs_dir() / "models" / "elasticity_fit"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_path = out_dir / "summary.parquet"
    fit_path = out_dir / "fit.pkl"

    try:
        from phillyparking.elasticity.hierarchical_bayes import (
            fit_elasticity_model, save_fit, posterior_zone_elasticity,
        )
        log.info("Fitting PyMC model (draws=%d tune=%d chains=%d)", draws, tune, chains)
        fit = fit_elasticity_model(panel_full, draws=draws, tune=tune, chains=chains, seed=seed)
        save_fit(fit, fit_path)
        summary = posterior_zone_elasticity(fit)
        summary["source"] = "pymc_posterior"
        summary.to_parquet(summary_path)
        log.info("PyMC fit complete -> %s", summary_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("PyMC unavailable / fit failed (%s); writing prior-only summary", exc)
        summary = _prior_summary()
        summary.to_parquet(summary_path)

    print(f"elasticity fit -> {summary_path}")


if __name__ == "__main__":
    main()
