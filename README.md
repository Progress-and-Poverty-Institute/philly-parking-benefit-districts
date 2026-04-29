# Philadelphia Curb Parking Pricing Model

**GitHub**: [Progress-and-Poverty-Institute/philly-parking-benefit-districts](https://github.com/Progress-and-Poverty-Institute/philly-parking-benefit-districts)

A demand-responsive curb parking pricing model for Philadelphia, supporting three deliverables:

1. **PPI / 5th Square white paper** — Georgist framing of curb pricing as land-rent capture.
2. **Academic paper** — empirical test of the Chatman–Manville (2014) hypothesis: targeting *minimum vacancy at peak* vs *average occupancy*.
3. **Operational simulation/pricing tool** — Seattle-style transparent rule-based pricing, with ML/RL as advanced mode.

See [research/demand-based-curb-parking-pricing-model-for-philadelphia---claude-2026-04-28.md](research/demand-based-curb-parking-pricing-model-for-philadelphia---claude-2026-04-28.md) for the literature review and design rationale, and `docs/PLAN.md` (mirrored from the planning session) for the implementation roadmap.

## Quickstart

```bash
# 1. Create environment
conda env create -f environment.yml
conda activate phillyparking
# NOTE: if conda create fails with a libmamba DLL error, install packages directly:
#   C:/Users/druss/miniconda3/python.exe -m pip install -r <(grep -v '#' environment.yml | grep '  - ' | sed 's/  - //')
# then: pip install -e . and continue from step 3.

# 2. Install package in editable mode
pip install -e .

# 3. Run the synthetic-data end-to-end pipeline
python scripts/01_download_public_data.py    # public data (OSM, ACS, etc.); skipped if cached
python scripts/02_build_segments.py          # canonical street-segment table
python scripts/03_fit_baseline_demand.py     # synthetic baseline demand panel
python scripts/04_fit_elasticity.py          # hierarchical Bayesian elasticities
python scripts/05_run_scenarios.py           # status_quo | seattle | full_pbd × 3 elasticities
python scripts/06_export_paper_figures.py    # figures and tables for the papers

# 4. Launch interactive policy tool
streamlit run app/streamlit_app.py
```

## Project Layout

```
src/phillyparking/        # Installable package
  io/                     # Data loaders (Open Data Philly, ACS, LODES, GTFS, OSM, PPA stub)
  spatial/                # Street segments, joins, pricing zones
  demand/                 # Synthetic baseline + occupancy estimator + ML
  elasticity/             # Lehner-Peer priors + hierarchical Bayes
  pricing/                # Seattle rule, Arnott-Inci, Chatman-Manville, optimizer
  revenue/                # Revenue forecasting under elasticity scenarios
  welfare/                # Consumer surplus, cruising DWL, incidence by income decile
  scenarios/              # Orchestration of status_quo | seattle | full_pbd
  validation/             # Spatial CV, calibration, manual count back-test
  viz/                    # Maps and chart helpers

config/                   # YAML parameter files (single source of truth)
data/                     # raw / interim / processed / external
notebooks/                # Numbered analysis notebooks; paper/ for Quarto book
app/                      # Streamlit policy tool
outputs/                  # figures / tables / models / reports
tests/                    # pytest suite
scripts/                  # CLI entry points
```

## Data Status

- **Public sources** (Open Data Philly, Census ACS, LEHD LODES, SEPTA GTFS, PennDOT, OSM): downloaded by `scripts/01_download_public_data.py`. Some endpoints require a free Census API key (set `CENSUS_API_KEY` in `.env`).
- **PPA meter transactions**: not yet available. The pipeline runs against `phillyparking.io.ppa_stub`, which generates schema-faithful synthetic transactions. When a Right-to-Know Law (RTKL) request closes, swap by setting `PPA_DATA_SOURCE=real` in `.env` and pointing `PPA_DATA_PATH` at the dump.

## Key calibration numbers (synthetic baseline)

Running on 120 synthetic segments:

| Zone | Weekday lunch peak occ | Overnight occ | Status-quo annual revenue |
|---|---|---|---|
| CCC (Center City Core) | ~0.83 | ~0.30 | ~$1.8M |
| Other zones | 0.62–0.67 | 0.20–0.25 | varies |
| **All 120 segments** | — | — | **~$4.3M** |

Real Philadelphia has ~10× the metered inventory, so the central real-data estimate would be
~$40–50M — consistent with PPA annual reports.

## PPA Data (RTKL)

A complete Right-to-Know Law request packet for PPA transaction data is at [`docs/rtkl/`](docs/rtkl/).
Submit the request to `OpenRecordsOfficer@philapark.org` using the OOR standard form. When real
data arrives, set `PPA_DATA_SOURCE=real` in `.env` and point `PPA_DATA_PATH` at the dump; the
stub interface is schema-identical.

## License

Code: MIT. Research document and white paper draft: CC-BY-4.0.
