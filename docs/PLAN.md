# Plan: Demand-Based Curb Parking Pricing Model for Philadelphia

## Context

The research document at [research/demand-based-curb-parking-pricing-model-for-philadelphia---claude-2026-04-28.md](research/demand-based-curb-parking-pricing-model-for-philadelphia---claude-2026-04-28.md) lays out theory, literature, Philadelphia institutional context, and methodology for a demand-responsive curb pricing model. The project directory is otherwise empty — no code, no data, no git repo. This plan turns the research into a concrete implementation roadmap supporting three deliverables:

1. **PPI/5th Square white paper** (Georgist framing: Philadelphia is giving away rent on public land)
2. **Academic paper** testing the Chatman–Manville (2014) hypothesis: does targeting *minimum vacancy at peak* beat targeting *average occupancy*?
3. **Operational simulation/pricing tool** (Seattle-style rule-based core; ML/RL as optional advanced mode)

Key design decisions from the research:
- **Theory**: Arnott–Inci (2006) cruising-elimination, not Shoup's 85% heuristic.
- **Operational benchmark**: Seattle (transaction-based occupancy estimation, ±$0.50 annual zone-level adjustments, no in-pavement sensors).
- **Elasticity prior**: Lehner & Peer (2019) meta-analysis, central ε ≈ −0.4, with hierarchical neighborhood pooling.
- **PPA transaction data is not yet available** — must build with public data + synthetic baseline first; swap real data in via stable interface when an RTKL request closes.

## Project Structure

```
philly-parking-benefit-districts/
├── README.md, pyproject.toml, environment.yml, .gitignore, .env.example
├── research/                         # existing research doc
├── config/                           # zones.yaml, pricing_rules.yaml,
│                                     # elasticity_priors.yaml, scenarios.yaml
├── data/{raw,interim,processed,external}/
│   └── raw/{opendataphilly,census_acs,lehd_lodes,septa_gtfs,osm,penndot,ppa}/
├── src/phillyparking/                # installable package (`pip install -e .`)
│   ├── io/                           # opendataphilly, census, lodes, osm_loader,
│   │                                 # gtfs_loader, ppa_stub
│   ├── spatial/                      # segments, join, zones
│   ├── demand/                       # synthetic_baseline, occupancy_estimator,
│   │                                 # features, ml_occupancy
│   ├── elasticity/                   # priors, hierarchical_bayes, scenarios
│   ├── pricing/                      # seattle_rule, arnott_inci, optimizer,
│   │                                 # chatman_manville
│   ├── revenue/forecast.py
│   ├── welfare/                      # consumer_surplus, cruising_dwl, incidence
│   ├── scenarios/                    # runner, compare
│   ├── validation/                   # crossval, calibration, manual_counts
│   └── viz/                          # maps, charts
├── notebooks/                        # 00_setup..09_scenarios + paper/ (Quarto)
├── app/                              # Streamlit: streamlit_app.py + pages/
├── outputs/{figures,tables,models,reports/{white_paper,academic_paper}}/
├── tests/                            # pytest, with fixtures
└── scripts/                          # CLI entry points 01..06
```

The unit of spatial analysis is the **street segment** (canonical 50–100 m segments keyed by `segment_id`), aggregated upward into **pricing zones**.

## Implementation Phases

**Phase 0 — Bootstrap (week 1)**
- `git init`, `pyproject.toml` pinning the full stack, conda `environment.yml` pointing at `C:/Users/druss/miniconda3/python.exe`.
- Pre-commit (ruff, black, nbstripout); empty pytest passes.

**Phase 1 — Data foundation (weeks 1–3)**
- Implement `src/phillyparking/io/*` for all public sources.
- Build canonical segment GeoParquet via `spatial/segments.py`.
- Spatial joins: meters↔segments, ACS block groups↔segments, RPP zones↔segments, SEPTA frequency-weighted access.
- **Milestone**: queryable DuckDB view of `data/processed/segments.parquet` for any pilot zone.

**Phase 2 — Synthetic baseline demand (weeks 3–4)** *(load-bearing while PPA data is delayed)*
- `demand/synthetic_baseline.py` predicts hour-of-week occupancy from land-use mix (OSM POIs), jobs (LODES), residents (ACS), transit access, distance to CBD. Calibrate intercept to match published Center City peak occupancy (~85%).
- `io/ppa_stub.py` generates synthetic transactions with same schema as expected real PPA dumps so swap-in is mechanical.
- **Milestone**: `demand_panel.parquet` (segment × hour × occupancy + uncertainty).

**Phase 3 — Elasticity module (weeks 4–6)**
- `elasticity/priors.py`: Normal(−0.4, 0.15) Lehner–Peer prior with context shifts (CBD, residential, mixed).
- `elasticity/hierarchical_bayes.py` (PyMC): `log(occ_zt) = α_z + ε_z·log(price_zt) + β·X_zt + γ_t + η_zt` with partial pooling on ε at neighborhood→city levels.
- Scenario wrappers: pessimistic −0.7, central −0.4, optimistic −0.2.

**Phase 4 — Seattle-style pricing engine (weeks 6–7)**
- `pricing/seattle_rule.py` ±$0.50 update:
  ```
  peak_occ = q90(occ in weekday peak window)
  avg_occ  = mean(occ in priced hours)
  if peak_occ >= 0.85:  new = current + 0.50
  elif avg_occ < 0.70:  new = max(floor, current - 0.50)
  else:                 new = current
  ```
- `pricing/chatman_manville.py` exposes both `avg_occupancy` and `min_vacancy_peak` targeting modes as toggles for the academic experiment.
- `pricing/arnott_inci.py` solves for p* such that D(p*) = (1−v*)·K and computes cruising DWL.
- `pricing/optimizer.py` (cvxpy) for the full-PBD scenario where residential permits are also priced.

**Phase 5 — Revenue, welfare, incidence (weeks 7–9)**
- `revenue/forecast.py`: `revenue = price × hours × occupancy(price, ε)` with bootstrap CIs.
- `welfare/consumer_surplus.py`: nested-logit logsum (xlogit / pylogit) over park / walk-and-transit / forgo trip; `CS_change = (1/α)·[logsum(scenario) − logsum(baseline)]`.
- `welfare/cruising_dwl.py`: Arnott–Inci closed-form DWL.
- `welfare/incidence.py`: payment burden + trip surplus by ACS income decile of trip origin (LODES-based).

**Phase 6 — Scenario comparison & Chatman–Manville test (weeks 9–10)**
- `scenarios/runner.py` runs `{status_quo, seattle, full_pbd} × {pessimistic, central, optimistic}` elasticities.
- Notebook 08 sweeps elasticity, demand shape, and noise to map the regime where min-vacancy-at-peak targeting outperforms avg-occupancy on cruising DWL, revenue stability, and equity. *This is the publishable academic contribution.*

**Phase 7 — Streamlit tool + papers (weeks 10–12)**
- App pages (precomputed outputs, no online refit):
  1. **Map** — pydeck/folium choropleth, current vs proposed prices, sidebar scenario/elasticity sliders.
  2. **Scenario Comparison** — bar charts of revenue, DWL, avg price, % zones binding floor/ceiling.
  3. **Revenue Forecast** — 10-yr fan chart across elasticity scenarios; CSV download.
  4. **Equity Analysis** — incidence by ACS income decile; Georgist headline ("rent currently given away").
- Quarto build for academic paper from `notebooks/paper/`; Pandoc/Quarto white paper drawing the same `outputs/` figures.

**Phase 8 — PPA data integration (when RTKL closes)**
- Replace `ppa_stub` calls; rerun pipeline; recalibrate. Interface is stable so this is mechanical.

## Critical Files to Implement

- [src/phillyparking/spatial/segments.py](src/phillyparking/spatial/segments.py) — canonical street-segment table; the spine of the data model.
- [src/phillyparking/demand/synthetic_baseline.py](src/phillyparking/demand/synthetic_baseline.py) — load-bearing while PPA data is delayed.
- [src/phillyparking/io/ppa_stub.py](src/phillyparking/io/ppa_stub.py) — schema-faithful synthetic transactions, swappable for real data.
- [src/phillyparking/elasticity/hierarchical_bayes.py](src/phillyparking/elasticity/hierarchical_bayes.py) — neighborhood-level partial pooling.
- [src/phillyparking/pricing/seattle_rule.py](src/phillyparking/pricing/seattle_rule.py) — operational baseline algorithm.
- [src/phillyparking/pricing/chatman_manville.py](src/phillyparking/pricing/chatman_manville.py) — academic paper centerpiece.
- [src/phillyparking/scenarios/runner.py](src/phillyparking/scenarios/runner.py) — orchestrates all comparisons.
- [config/scenarios.yaml](config/scenarios.yaml), [config/pricing_rules.yaml](config/pricing_rules.yaml), [config/elasticity_priors.yaml](config/elasticity_priors.yaml) — single source of truth for all parameters.

## Data Acquisition

**Download immediately (public)**: Open Data Philly (meters, RPP zones, streets, parcels, zoning, neighborhoods); Census ACS 5-yr block group (income, vehicle ownership, tenure); LEHD LODES WAC+RAC for Philadelphia County; SEPTA GTFS; PennDOT AADT; OSMnx drive network + amenity POIs.

**Stub now, swap later**: PPA meter transactions, Parkmobile/Flowbird sessions — `ppa_stub.generate(segments, n_days)` mirrors real schema.

**Hand-collect for validation**: 2–3 days of manual occupancy counts on 5–10 segments across Center City, University City, South Philly → `data/external/manual_counts_YYYYMMDD.csv`.

## Validation

- **Unit tests**: Seattle-rule edge cases (floor/ceiling/exact-threshold), elasticity prior shape, occupancy estimator on synthetic transactions with known ground truth, segment-construction idempotence.
- **Integration test**: 10-segment × 1-week fixture city runs all three scenarios in <60 s; snapshot-test key outputs.
- **Spatial K-fold CV**: hold out *neighborhoods*, not random rows, when assessing ML occupancy; report MAE and calibration slope.
- **Calibration plots**: predicted vs observed occupancy decile-binned with 45° reference; reliability diagrams.
- **Manual-count back-test**: bias, RMSE, coverage of 90% prediction intervals.
- **Sensitivity tornado**: revenue and DWL sensitivity to elasticity, target occupancy, no-pay correction factor, dwell-time distribution.
- **Reproducibility**: a single `make reproduce` (or PowerShell equivalent) chains `scripts/01..06_*.py` from raw data to paper figures.

## End-to-End Verification

To verify a working build:
1. `pip install -e .` succeeds; `pytest` green.
2. `python scripts/01_download_public_data.py` populates `data/raw/` from public sources.
3. `python scripts/02_build_segments.py` writes `data/processed/segments.parquet`.
4. `python scripts/03_fit_baseline_demand.py` writes the synthetic demand panel.
5. `python scripts/05_run_scenarios.py` writes scenario outputs to `outputs/models/`.
6. `streamlit run app/streamlit_app.py` loads the precomputed scenarios; map and equity pages render.
7. `quarto render notebooks/paper/` produces the academic paper PDF; `outputs/figures/` and `outputs/tables/` are populated.
