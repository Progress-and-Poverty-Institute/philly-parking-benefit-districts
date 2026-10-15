# Deep methods review: plan (2026-10-14)

This is the plan for an adversarial audit of the model's methods, following the
`analysis-audit` skill. It is a planning document, not the audit: nothing below is a finding
until a wave agent has verified it and a refuter has failed to knock it down. Numbers in this
file are hand-typed observations frozen on 2026-10-14 and will go stale; the audit report will
carry its own frozen numbers.

**Deliverable of the audit:** one dated file, `audits/audit_2026-10-14.md`, holding a scoped
findings list (severity × confidence, each with evidence and a reproduction path), a coverage
statement naming what was and was not examined, a refuted-candidates section, and a ranked work
list. The audit changes nothing in the repo.

**Out of scope, by the user's instruction:** the white paper's prose (`Report.tex`) and the
Quarto draft. Dimension 5 (reporting) is off. Two exceptions, because they encode *premises*
rather than prose: (a) factual statements in `README.md`, `CLAUDE.md` and the memory files about
what data the pipeline runs on and what the tests cover are claims the audit must test, and
(b) where the paper's scenario description names a mechanism the code does not implement, that
is a dimension-1 scope-drift finding about the model, not a prose finding.

---

## 1. The argument under review

The project makes three claims, each resting on the same pipeline:

1. **White paper (PPI / 5th Square).** Philadelphia under-prices its curb. A Seattle-style
   annual ±$0.50 rule or an Arnott–Inci "price that eliminates cruising at the busiest hour"
   would change revenue and cruising deadweight loss (DWL) by stated amounts, scaled by 10× from
   a 120-segment synthetic city to "real Philadelphia" (status quo ≈ $43M, Seattle ≈ $36M,
   full PBD ≈ $25M to the General Fund plus ≈ $11M to parking benefit districts).
2. **Academic paper (Chatman–Manville test).** A pricing rule that targets minimum vacancy at
   the peak hour yields ~53× lower cruising DWL and ~2.5× higher revenue at year 5 than a rule
   targeting average occupancy, across elasticities −0.2 to −0.7 and three noise levels
   (`outputs/tables/cm_sweep_n200.parquet`).
3. **Operational tool (Streamlit).** The same engine can be driven by real PPA transaction data
   when the Right-to-Know request closes, via a schema-stable swap of `io/ppa_stub.py`.

The evidence offered for 1 and 2 is the output of `scripts/05_run_scenarios.py` and the
`chatman_manville_sweep` function. The inferential step is: *a synthetic occupancy panel
calibrated to published peak occupancy, pushed through constant-elasticity demand and two
pricing rules, tells us the direction and rough magnitude of what the real policy would do.*
Whether that step is valid is the audit's central question.

---

## 2. Scope decisions

| Decision | Choice | Why |
|---|---|---|
| Depth | **deep** | User asked that every output-affecting decision be scrutinised. The codebase is small enough (≈3,750 source lines, 6 scripts, 4 YAML files) that full enumeration is feasible. |
| Dimensions | 1, 2, 3, 4. Dimension 5 off (see exceptions above). | User instruction. |
| Canonical artifacts | `config/*.yaml`, `src/phillyparking/`, `scripts/0[1-6]_*.py`, `outputs/tables/*`, `outputs/figures/*`, `outputs/models/{status_quo,seattle,full_pbd}/`. | These are what the papers and app consume. |
| Historical / non-canonical | `docs/PLAN.md` (pre-implementation roadmap), `research/*.md` (literature review, treated as a *source of claims to verify*, not evidence), `notebooks/*.ipynb` (never executed; see §4), `outputs/models/scenarios/` (a stale earlier run). | Being out of date is expected for these; do not file staleness findings against them, but do file findings where live code or the app depends on them. |
| Prior audits | None on disk. Commits `9d7aee0` and `f0f2a84` (2026-04-29) describe an "autonomous audit session" that fixed three bugs; the memory file `project_state.md` records its conclusions. | Treat those conclusions as claims. In particular "validated numbers" in memory were validated against the model's own output, not against anything external. |
| Expensive | Full pytest run exceeds 5 minutes (killed at 300 s on 2026-10-14; `CLAUDE.md` says ~30 s). `run_all_scenarios` with 10-year PBD roll-forward plus the 200-trip CS loop is the slow part. `chatman_manville_sweep(n_replications=200)` produces 36,000 rows and was presumably run ad hoc; budget 10–30 min. `scripts/01_download_public_data.py --refresh` hits the network and would **overwrite cached raw layers**. | Agents re-run things only into scratch, via `PHILLYPARKING_OUTPUTS_DIR` / `PHILLYPARKING_DATA_DIR`, and never pass `--refresh`. |
| Must not write to | `outputs/`, `data/`, `docs/`, `README.md`, `CLAUDE.md`, memory. | Audit posture. Findings and probe scripts go to `audits/_scratch/` (to be gitignored). |

---

## 3. What the survey established (verified today)

These are facts, not findings. They define the terrain the agents will work on.

### 3.1 Data provenance: what `data/raw/` actually holds

Every loader in `io/` has a synthetic fallback, and the fetch wrapper **caches the synthetic
result under the same filename as a real download**, so a later run cannot tell them apart and
never retries the network ([opendataphilly.py:41](../src/phillyparking/io/opendataphilly.py:41)).
Opened on 2026-10-14:

| Layer | File | Real or synthetic | Evidence |
|---|---|---|---|
| Streets | `opendataphilly/streets.parquet` | **Synthetic** | 100 rows named `Synth St N`, random segments across the city bbox |
| Meters | `opendataphilly/meters.parquet` | **Synthetic** | 200 rows, `M00000…`, normal cloud around one point |
| Neighborhoods, RPP zones | `opendataphilly/*.parquet` | **Synthetic** | 10 grid rectangles each |
| ACS block groups | `census_acs/acs_bg_2022.parquet` | **Synthetic** | 120 grid cells, GEOIDs `42101000000…`, income a linear function of distance to one point |
| LODES WAC / RAC | `lehd_lodes/pa_*_2021.parquet` | Real (likely) | 9,248 blocks, 676k jobs, real 15-digit geocodes |
| OSM POIs | `osm/pois.parquet` | Real (likely) | 6,627 features, 391 OSM tag columns |
| SEPTA GTFS | `septa_gtfs/septa.zip` | Real (likely) | 21 MB feed |
| OSM drive graph | `osm/drive.graphml` | **Absent** | never fetched |

Consequences already visible in `data/processed/segments.parquet`: 473 segments cut from 100
synthetic streets, 471 of them in zone `other`, `has_meter` false for all 473, `n_meters` zero
for all. `CLAUDE.md` attributes the near-empty named zones to "real OSM data covering all of
Philadelphia"; the actual cause is random synthetic streets.

### 3.2 What the headline results were computed on

Scripts 05 and 06 detect the empty named zones and fall back to `make_synthetic_segments(n=120,
seed=42)` ([spatial/synthetic.py:21](../src/phillyparking/spatial/synthetic.py:21)): 120 random
line segments inside one bbox with randomly assigned zone labels, random capacity 4–15, and
random covariates (jobs 8,000–9,500 if labelled CCC else 50–3,000, POIs 0–59, transit 0–40).
`data/processed/demand_panel.parquet` carries those fixture ids (`T0000`…). **No result in the
README, the white paper, or `outputs/` descends from any Philadelphia geography or any real
layer.** The real LODES, POI and GTFS layers are joined only onto the discarded 473-segment table.

### 3.3 Pipeline map (what actually runs, in order)

```
config/zones.yaml ──┐
make_synthetic_segments(120) ─► baseline_occupancy(seed=42) ─► 168-hour panel per segment
                                      │  (hand-tuned kernels × softmax land-use mix,
                                      │   per-segment linear rescale to [seg_off, seg_peak])
                                      ▼
run_scenario(name):  attach zone price ─► policy loop (0 / 5 / 10 yrs):
     fixed            : nothing
     seattle_rule     : adjust_zone_prices ─► apply_elasticity(ε=-0.4) on all 168 h
     arnott_inci      : p* = p0·(0.85·K / q90(occ)·K)^(1/ε) per zone, clipped ─► apply_elasticity
                       ─► annual_revenue  (zone mean occ over 168 h × zone capacity
                                           × mean priced-hours/yr across zones × price)
                       ─► allocate(total, pbd_share)   ($35M GF minimum, then SDP residual)
                       ─► annual_cruising_dwl (excess over 0.85·K × 5 min × $20/h × 52)
                       ─► _synthetic_cs_change (200 random trips, ad hoc nested logit)
comparison_table ─► outputs/tables/comparison_table.csv
chatman_manville_sweep (re-implements both rules inline; does NOT call pricing/chatman_manville.py)
```

Never on the path to any tracked output: `elasticity/hierarchical_bayes.py` (no fit exists;
`outputs/models/elasticity_fit/` is absent), `pricing/optimizer.py`, `pricing/chatman_manville.py`,
`demand/occupancy_estimator.py`, `demand/ml_occupancy.py`, `validation/*`, `welfare/incidence.py`
except `gini`, the `context_shifts` and `cross` priors, the `rpp` block of `zones.yaml`, the
`time_of_day_bands` of the Seattle scenario, and the `market_clearing` RPP policy.

### 3.4 Provenance of tracked outputs

| Artifact | Produced by | Status |
|---|---|---|
| `outputs/models/{status_quo,seattle,full_pbd}/` | script 05, 120 synthetic segments | matches README table |
| `outputs/models/scenarios/*` | an earlier run on ~20 segments (full PBD total $200K) | **stale; this is the directory the Streamlit app reads** (`app/streamlit_app.py:31`) |
| `outputs/tables/comparison_table.csv` | script 06 | PBD revenue column reads 0 for full PBD; README says $1.07M (see O8) |
| `outputs/tables/cm_sweep_n200.parquet` | **no script or notebook produces n=200** (script 06 runs n=20 × 3 yr; notebook 08 runs n=30 × 3 yr) | provenance unknown; presumably an ad hoc call |
| `outputs/figures/*.png` | script 06 plus unknown calls for `cm_sweep_n200_*` and the two 2026-04-29 13:38 figures | partly untraceable |
| `outputs/figures/incidence_by_decile.png` | `_synthetic_incidence()` in script 06: constants 50 and −10 for every decile | placeholder, not a result |

### 3.5 Guard set

106 tests in 22 files. Full run on 2026-10-14: 106 passed in 579 s. One test,
`test_hierarchical_bayes.py::test_fit_recovers_true_elasticity`, took 571 s of that. PyTensor
finds no C compiler on this machine ("g++ not detected") and samples in pure Python. Every
other test finishes in under 3 s, including the e2e test (0.6 s). The fast subset is
`-k "not hierarchical_bayes"`. The notebooks have never been
executed (no outputs in any `.ipynb`), notebook 04 calls `named_scenario('low')` which does not
exist in config, and notebook 08 aggregates columns (`cruising_dwl`, `revenue`, `gini`) that
`chatman_manville_sweep` does not emit. No `--check` mode, no CI, no README number generation.

---

## 4. Decision inventory: the denominator

Every decision below changes a number in `outputs/`. For each, the audit must record: where it
lives, what it is set to, what justifies it, whether the justification was checked, and what
happens to the headline results if it is wrong. Dimension tags: **Q** question, **A**
assumption, **I** inference, **C** code. Priority **L** = load-bearing for a headline claim.

### A. Inputs and data acquisition (`io/`, scripts 01–02)

| # | Decision | Where | Tags |
|---|---|---|---|
| A1 | Silent synthetic fallback on any fetch failure, cached as if real; no provenance flag written. | `io/opendataphilly.py:41`, `io/census.py`, `io/lodes.py`, `io/gtfs_loader.py`, `io/osm_loader.py` | C, A, **L** |
| A2 | Carto SQL query shape `SELECT *, ST_AsGeoJSON(the_geom) AS geometry … &format=geojson` and the five table names. Does this endpoint exist and return these tables? Why did all five fail on 2026-04-28? | `io/opendataphilly.py:34` | C |
| A3 | ACS 2022 via `cenpy` only if `CENSUS_API_KEY` is set; otherwise synthetic without warning at the call site. | `io/census.py` | C, A |
| A4 | LODES 2021 WAC/RAC, all jobs (`S000_JT00`); filtered by county prefix on a string column. | `io/lodes.py` | A |
| A5 | OSM POI tags: `amenity ∈ {restaurant, cafe, bar}`, all `shop`, all `office`. | `io/osm_loader.py` | A |
| A6 | GTFS stop frequency: first day of first week, 07:00–09:00 band only, `num_trips` summed per stop. | `io/gtfs_loader.py` | A |
| A7 | PPA stub: Poisson arrivals with hand-set hour-of-week multipliers, lognormal dwell (median 45 min, σ 0.5), capacity factor; the "schema-faithful" claim rests on a guessed schema. | `io/ppa_stub.py` | A |
| A8 | Occupancy-from-transactions estimator: minutes-in-hour / (capacity × 60 × ISO-week count); no-pay correction 1.10–1.20 by zone, 1.15 default "Seattle uses". | `demand/occupancy_estimator.py:61`, `config/pricing_rules.yaml` | A, C |

### B. Segment construction and spatial joins (`spatial/`)

| # | Decision | Where | Tags |
|---|---|---|---|
| B1 | Segment = centerline split at ≈80 m; capacity = ⌊length / 7 m × 0.85⌋ regardless of side, street class, curb regulation, or metered status. | `spatial/segments.py:50`, constants at top | A, **L** |
| B2 | `has_meter` / `n_meters` are computed (15 m buffer) but **never used** to restrict pricing or revenue to metered curb. | `spatial/segments.py:147`; no consumer anywhere | C, A, **L** |
| B3 | Zone assignment by axis-aligned bbox on the segment centroid, first match in YAML order (CCC listed before the enclosing CCA). | `spatial/segments.py:42`, `spatial/zones.py` | A, C |
| B4 | ACS join: 15 m buffer, area-weighted; `pop_density` = pop / intersection area × 1e6 (per km²). Observed values up to 4.4M/km² on the synthetic grid: check the weighting algebra. | `spatial/join.py:15-28` | C |
| B5 | LODES join: county job total allocated to segments **proportional to buffer area**, so every segment gets ≈ the same jobs count; `jobs_within_200m` is therefore not a spatial measure. Docstring admits it. | `spatial/join.py:43-62` | C, A, **L** |
| B6 | POI join: 100 m buffer, `within`. Transit join: 400 m buffer, trips summed over all stops in buffer. | `spatial/join.py:74-128` | A |
| B7 | Synthetic fixture distribution (zone shares 25/20/15/15/15/10, covariate ranges, CCC jobs 8,000–9,500 vs ≤3,000 elsewhere). This fixture *is* the city the results describe. | `spatial/synthetic.py:21` | A, **L** |

### C. Zones, prices, priced hours (`config/zones.yaml`)

| # | Decision | Where | Tags |
|---|---|---|---|
| C1 | Zone bboxes. CCC is given as −75.170…−75.140 × 39.945…39.960; the description says Arch–Locust × 4th–20th. The audit must verify against street-grid coordinates (per the global rule on geographic facts) and record the mismatch, if any. Same for CCA, UCity, South Philly, Fishtown. | `config/zones.yaml` | A |
| C2 | Current rates $4.00 / $3.50 / $2.00 / $1.50 / $1.50; long-term meter rate $2.50 unused; MeterUP tiered pricing ignored. Verify against PPA's July 2025 schedule. | `config/zones.yaml` | A |
| C3 | Priced hours 8–20 weekday and Saturday, Sunday free (South Philly 8–18). Verify against PPA. Revenue uses the **mean across zones** of these (`int(np.mean(totals))`), not per-zone hours. | `config/zones.yaml`; `revenue/forecast.py:22-35` | A, C, **L** |
| C4 | Floors and ceilings per zone ($1–$8 CCC, etc.) and global $0.50 / $10. Where do these come from? | `config/zones.yaml`, `config/pricing_rules.yaml` | A |
| C5 | RPP block (fees, caps, market-clearing targets $500–$2,500) is configured but unused. The "full PBD" scenario description promises market-priced permits. | `config/zones.yaml` `rpp`; `scenarios/runner.py` | Q, **L** |

### D. Synthetic baseline demand (`demand/synthetic_baseline.py`)

| # | Decision | Where | Tags |
|---|---|---|---|
| D1 | Three hand-drawn 168-hour kernels (office / retail / residential) with hard-coded step levels. | `:40-105` | A, **L** |
| D2 | Land-use mix = softmax over (log jobs, 1.2·log POIs, 0.9·log pop), column-centred, temperature 2.5. | `:112` | A |
| D3 | Latent intensity λ = 0.55·z(log jobs) + 0.35·z(log POIs) + 0.25·z(log pop) − 0.15·z(log transit). Weights unexplained. | `:130` | A |
| D4 | λ normalised to [0,1] between its 5th and 95th percentiles **within the loaded segment set**, so calibration is relative to whatever fixture is loaded, not absolute. | `:162` | A, C, **L** |
| D5 | Per-segment peak = 0.62 + 0.30·λ (so max 0.92), off-peak = 0.20 + 0.10·λ; occupancy rescaled linearly to span [off, peak]; clipped 0.99. Calibration target "~85% CCC peak" rests on an unnamed publication. | `:139-180` | A, **L** |
| D6 | `occupancy_sd` is a deterministic 0.04–0.06 function of occupancy plus 1e-9 noise, i.e. the panel carries no real uncertainty; `expand_panel` adds logit-normal noise but is unused. | `:176-178`, `:188` | A, C |
| D7 | Baseline occupancy is **price-independent**: segments in zones priced $1.50 and $4.00 get the same occupancy for the same covariates. Every scenario then applies elasticity to a baseline that embeds no price response. | design | A, I, **L** |

### E. Elasticity (`config/elasticity_priors.yaml`, `elasticity/`)

| # | Decision | Where | Tags |
|---|---|---|---|
| E1 | Central ε = −0.40, sd 0.15, attributed to Lehner & Peer (2019) RP-only; scenarios −0.2 / −0.4 / −0.7. Verify the citation actually supports these numbers (the research doc's own summary gives "−0.3 to −0.5" and cites Concas & Nayak −0.39). | `config/elasticity_priors.yaml` | A, **L** |
| E2 | Constant elasticity over price ratios from 0.375× to 2× and over 5–10 annual steps; no long-run shift despite `long_run: −0.30` in config; no dwell-time decomposition; no cross-elasticities. | `elasticity/scenarios.py:36`; config `context_shifts` unused | A, I, **L** |
| E3 | `apply_elasticity` scales occupancy multiplicatively and clips at 1.0, on **all 168 hours** including unpriced overnight and Sunday hours. | `elasticity/scenarios.py:36` | C, A |
| E4 | Hierarchical PyMC model: `log occ = α_z + ε_z log p + γ_t`. With one price per zone, ε_z is collinear with α_z; the docstring concedes it "shrinks fully to the prior". The fit was never produced and nothing consumes it. The named scenarios bypass it. | `elasticity/hierarchical_bayes.py:36` | Q, I, **L** |
| E5 | Sequential compounding: each roll-forward year applies ε to the *previous* year's already-adjusted panel against the previous year's price. Check the algebra equals a one-shot (p_T/p_0)^ε, and what the clip at 1.0 does across steps. | `scenarios/runner.py:219-229` | C, I |

### F. Pricing rules (`pricing/`, `scenarios/runner.py`)

| # | Decision | Where | Tags |
|---|---|---|---|
| F1 | "Seattle rule" as implemented: up one step if q90 of weekday 11–14 occupancy ≥ 0.85 (two steps ≥ 0.95); **down** one step if the mean over weekday 8–20 < 0.70; else hold. Asymmetric statistics. Verify against SDOT's published rule (target 70–85 %, by time-of-day band). The configured `time_of_day_bands` are unused: one price per zone. | `pricing/seattle_rule.py:61`, `config/scenarios.yaml` | A, C, **L** |
| F2 | Seattle zone occupancy is capacity-weighted across segments before the rule; Saturday hours (priced in config) are excluded by `_priced_hours_mask` (`day < 5`). | `pricing/seattle_rule.py:54,108` | C |
| F3 | "Arnott–Inci" price: `p* = p0 · (0.85·K / D0)^(1/ε)` with `D0 = q90(all 168 h) × mean capacity`. This is the inverse of a constant-elasticity demand curve, not the Arnott–Inci (2006) stock-flow cruising equilibrium; the name claims more than the formula. Why q90 over all 168 hours rather than the busiest priced hour? | `pricing/arnott_inci.py:20`, `scenarios/runner.py:109-133` | A, Q, **L** |
| F4 | Both policies iterate for `rolls_forward_years` (5 and 10) with nothing else changing year to year: no demand growth, no inflation, no long-run elasticity, so "year 10" is the fixed point of a deterministic map. | `scenarios/runner.py:218-229` | A, I |
| F5 | `pricing/chatman_manville.py` and `pricing/optimizer.py` are dead on the result path; the sweep re-implements the two rules inline with a different down-trigger (`< 0.70` on the *same* statistic). Which is the rule the paper describes? | `scenarios/compare.py:84-91` vs `pricing/chatman_manville.py:21,61` | C, Q, **L** |

### G. Revenue (`revenue/`)

| # | Decision | Where | Tags |
|---|---|---|---|
| G1 | Annual revenue = zone-mean occupancy over **all 168 hours** × zone capacity × priced hours per year × price. Mixing unpriced overnight/Sunday occupancy into the mean, then multiplying by priced hours, is a unit mismatch. | `revenue/forecast.py:43-75` | C, **L** |
| G2 | Full compliance assumed: every occupied space-hour pays the posted rate; no no-pay correction (A8) in reverse, no RPP holders, no placards, no time limits, no MeterUP tiers. | `revenue/forecast.py` | A, **L** |
| G3 | Scaling to "real Philadelphia" is ×10 (README) / "≈1,200 metered block-faces in the five zones" (paper). Neither number is derived in the repo. PPA's reported on-street revenue mixes meters, permits and tickets; check what the ≈$43M is being compared to. | README, Report | I, **L** |
| G4 | Allocation: PBD share off the top, then `min(residual, $35M)` to the General Fund, then SDP. Applied to a $4.3M synthetic total the GF minimum binds, so SDP is 0 in every scenario; the paper's "revenue increases accrue to the School District" message cannot appear at this scale. | `revenue/allocation.py` | I, C |
| G5 | `comparison_table` reads keys `pbd_revenue_usd` / `sdp_revenue_usd`; `allocate().to_dict()` emits `pbd_usd` / `school_district_usd`. The tracked CSV shows PBD revenue 0; the README's $1.07M was read from `meta.json` by hand. | `scenarios/compare.py:34-35` vs `revenue/allocation.py:27` | C |
| G6 | Bootstrap CI in `revenue_under_scenarios` adds N(0, 0.03) noise to occupancy and calls it uncertainty; unused on the result path but exposed to the app. | `revenue/forecast.py:77` | A |

### H. Welfare (`welfare/`, `pricing/arnott_inci.py:31`)

| # | Decision | Where | Tags |
|---|---|---|---|
| H1 | Cruising DWL = max(0, occ·K − 0.85·K) × 5 min × $20/h per segment-hour, × 52 weeks, over all 168 hours. Linear in excess demand, zero below 85 %, threshold tied to the Seattle target. Sources for 5 minutes and $20 (config says USDOT ≈ $17.90, "bumped") are unverified. Not the Arnott–Inci DWL. | `welfare/cruising_dwl.py:8`, `config/pricing_rules.yaml` | A, **L** |
| H2 | With the baseline calibrated to a CCC peak of ≈0.83, the model's status quo has almost no cruising (DWL ≈ $6K on 120 segments) and **both reforms raise DWL** (≈$97K Seattle, ≈$74K PBD). The white paper's premise is that the status quo wastes rent and generates cruising; the model, as calibrated, says the opposite. | `outputs/tables/comparison_table.csv` | I, **L** |
| H3 | Consumer surplus: ad hoc nested logit (λ 0.7/0.9, ASCs 0/−0.5/−1/−2, garage $4–6, walk times uniform) over 200 random segments, with the **elasticity −0.40 reused as the price coefficient** (a marginal utility of money is not an elasticity). The total (≈$46) is reported as `cs_change_total`. | `scenarios/runner.py:137-180` | A, C |
| H4 | Incidence: `incidence_by_decile.png` is constants; the sweep's "gini" is the Gini of zone mean prices, not of any burden. `consumer_surplus_change` in the sweep is hard-coded 0. | script 06 `_synthetic_incidence`; `scenarios/compare.py:109-110` | C, Q |

### I. Scenario orchestration, the sweep, and output provenance (`scenarios/`, scripts 05–06)

| # | Decision | Where | Tags |
|---|---|---|---|
| I1 | Fallback to the 120-segment fixture when fewer than five loaded segments are in named zones, deleting the cached panel. `CLAUDE.md` calls this "expected behavior… not a bug"; the audit must decide whether a demo fixture can carry the published numbers. | `scripts/05_run_scenarios.py`, `scripts/06_export_paper_figures.py` | Q, I, **L** |
| I2 | The CM sweep: 20 synthetic segments by default (what did the n=200 run use?); a single price $2.00 for every zone regardless of `zones.yaml`; demand noise drawn **once** before the year loop (so "noise level" is initial-condition noise, not demand variability); same up/down thresholds for both rules applied to zone mean vs zone q95; DWL scored at the segment-hour level against the same 0.85 threshold the peak rule targets. | `scenarios/compare.py:41-112` | A, I, **L** |
| I3 | The "2.5× revenue" result: with constant elasticity and |ε| < 1, revenue rises monotonically with price, so any rule that raises prices more wins on revenue by construction. The "53× DWL" result: the peak rule targets the statistic the metric penalises. The audit must determine whether anything in the sweep could have come out the other way. | `scenarios/compare.py` | I, **L** |
| I4 | Sweep revenue = Σ(occ × cap × price) × 52 over all 168 hours (the `× 52/168 × 168` is a no-op), i.e. revenue is collected overnight and on Sundays. | `scenarios/compare.py:97` | C |
| I5 | Seeds: `run_scenario(seed)` seeds the fixture only when none is passed; script 05 passes the loaded panel; script 06 regenerates the panel with the same seed. Confirm run-to-run and script-to-script reproducibility of every tracked number. | scripts 05–06 | C |
| I6 | Two scenario result trees exist (`outputs/models/<name>/` and `outputs/models/scenarios/<name>/`) with different numbers; the app reads the stale one. | §3.4 | C |
| I7 | `cm_sweep_n200.parquet` and four figures have no producing script. | §3.4 | C |

### J. Validation and guards (`validation/`, `tests/`)

| # | Decision | Where | Tags |
|---|---|---|---|
| J1 | Calibration, spatial CV, and manual-count back-test modules exist but nothing feeds them (no ML model is trained on the result path; `data/external/` has no counts). The project has **no external validation of any kind**. | `validation/*`, `data/external/` | A, I, **L** |
| J2 | Tests check internal consistency (column names, monotone directions, round-trips), not correctness against an independent calculation. The e2e test asserts only `revenue > 0`. Test the guards: perturb a threshold or a unit (e.g. priced hours) and record which tests fire. | `tests/` | C |
| J3 | `CLAUDE.md` names the e2e test as the slow one (~30 s). The slow test is actually the PyMC test (§3.5), and the e2e test takes under a second. | `CLAUDE.md` | C |

### K. The real-data swap path

| # | Decision | Where | Tags |
|---|---|---|---|
| K1 | The claim that real PPA data "swaps in mechanically": `load_transactions` returns a frame, but no code path turns transactions into the baseline panel the runner consumes (`transactions_to_occupancy` exists; nothing calls it on the result path), the ACS/LODES/POI joins would need real streets and meters (A1, B2, B5), and the elasticity model cannot identify ε from a single cross-section of prices (E4). | `io/ppa_stub.py:load_transactions`, scripts 03–05 | Q, A, **L** |

---

## 5. Pre-audit observations (candidate findings, to be verified independently)

Recorded so the waves can start from them. None is settled; the refutation wave applies to all
of them. Confidence as of this survey: **read** = traced in code; **ran** = observed by running.

- **O1 (ran).** All Open Data Philly layers and ACS in `data/raw/` are synthetic fallbacks
  (§3.1). `CLAUDE.md`'s explanation of the named-zone fallback is wrong about the cause.
- **O2 (ran).** `has_meter` is false for every segment and unused downstream; unmetered curb is
  priced and generates revenue in every scenario (B2).
- **O3 (ran + read).** Every tracked number descends from `make_synthetic_segments(120, 42)`;
  no real layer reaches a published result (§3.2). The README's "Data Status" and the paper's
  "Model design" describe a pipeline whose output was discarded.
- **O4 (ran + read).** No elasticity was ever estimated; the model is unidentified by design;
  downstream reads the config scalar (E4).
- **O5 (read).** Revenue uses a 168-hour mean occupancy times priced hours, and a cross-zone mean
  of priced hours (G1, C3).
- **O6 (read + tracked CSV).** DWL is a linear-excess proxy; status quo DWL ≈ $6K and both reforms
  raise it (H1, H2). This inverts the white paper's premise inside the project's own model.
- **O7 (read).** The CM sweep's two headline ratios follow from the metric definition and from
  |ε| < 1, independent of any empirical content (I2, I3).
- **O8 (ran).** Key mismatch between `allocate().to_dict()` and `comparison_table` (G5).
- **O9 (ran).** The Streamlit app reads a stale, smaller run (I6).
- **O10 (read).** The implemented Seattle rule is asymmetric and ignores configured time bands;
  CCA falls $3.50 → $1.50 because synthetic weekday shoulder hours sit near 0.2–0.3 (F1, D5).
- **O11 (read).** The full-PBD scenario never prices residential permits (C5).
- **O12 (ran).** The n=200 sweep file has no producer; notebooks are unexecuted and reference
  non-existent names (I7, §3.5).
- **O13 (read + meta.json).** The $35M General Fund minimum swallows every synthetic total, so the
  SDP residual is identically zero (G4).
- **O14 (ran).** Test suite > 5 min (J3).
- **O15 (unverified).** Hand-typed literature and geographic parameters with no verification
  trail: ε prior (E1), no-pay 1.15 (A8), VOT $20 and 5-minute cruise (H1), zone bboxes versus the
  actual street grid (C1), PPA rates and hours (C2, C3), the ×10 / 1,200-block-face scale (G3).

---

## 6. Execution plan

### 6.1 Waves and agents

Cap: three agents concurrently, at most one on the top tier at a time (two only in wave 3 if the
budget check passes). Every agent writes each confirmed item to
`audits/_scratch/<dim>/findings.md` as it goes and returns only a summary plus the list.

**Wave 1: orient (mid tier, high effort; one cheap agent).** Produces the traced map that wave 2
starts from.

| Agent | Dimension | Brief (scope only; full prompt written at launch) |
|---|---|---|
| 1a | 4 (data → segments → demand) | Reproduce §3.1 independently. Re-run scripts 02–03 into scratch dirs via env vars (no `--refresh`); diff against `data/processed/`. Probe A1 by making a fetch fail and showing the cache hides it. Check B1–B7 and D1–D7 by running the functions on hand-built inputs with known answers. Confirm determinism across seeds and scripts (I5). |
| 1b | 4 (pricing → revenue → welfare → outputs) | Re-run `run_all_scenarios` and `chatman_manville_sweep` at small n into scratch; diff every README number against its artifact; establish the provenance of `cm_sweep_n200.parquet` and the four orphan figures (I7). Verify E3, E5, F2, G1, G5, H1, I4 by independent hand calculation on a two-segment panel. Guard test: perturb priced hours and the 0.85 threshold, record which tests fire (J2). Time the suite (J3). |
| 1c | 1 + parameter provenance (cheap tier, tools) | The two-restatement diff: what the README/paper say each scenario does versus what `run_scenario` computes (C5, F1, F3, F5, K1). Build the parameter provenance table for O15: for each hand-typed constant, find the primary source (Lehner & Peer 2019 abstract/tables, SDOT paid-parking annual report, USDOT VOT guidance, PPA July 2025 rate notice, street-grid coordinates for the CCC boundary) and record match / mismatch / not found. Flag judgment calls; do not settle them. |

**Wave 2: soundness (top tier, xhigh effort; serial).** Each receives wave 1's findings files
in the prompt.

| Agent | Dimension | Brief |
|---|---|---|
| 2a | 2 Assumptions | Enumerate every assumption in §4 plus any wave 1 surfaced; classify load-bearing / not; for each load-bearing one, state what would make it false and whether anything in the repo or the literature tests it. Lead with D7, E2, E4, G2, H1, I2, J1, K1. |
| 2b | 3 Inference | For each of the three claims in §1: estimand versus claim; whether the synthetic → real step is valid under 2a's list; what in the results is true by construction (I3, O6/H2); the ×10 scaling (G3); what "year 5 / year 10" means for a deterministic fixed-point map (F4); which conclusions would survive real data and which cannot be rescued by it. |

Dimension 1's two-restatement diff (1c) may need 2a's output; if 1c cannot settle a scope-drift
item, hand it to 2b.

**Wave 3: refute (top tier, high effort; one or two at a time).** Every Blocking or Material
candidate goes to a fresh refuter with file paths and the claimed defect only, told to find the
benign reading. Three lenses where a finding could fail more than one way: does it reproduce;
is the code path as claimed; is there an intended design the finding misreads. Survivors keep
their severity; the rest move to "refuted candidates".

**Synthesis (top tier, in the main session).** Triage, count findings by dimension (if 2 and 3
are thin relative to 4, go back), write `audits/audit_2026-10-14.md` from the skill's template,
and the ranked work list.

### 6.2 Budget

| Item | Estimate |
|---|---|
| Wave 1 (3 agents) | ≈ 0.6M tokens |
| Wave 2 (2 top-tier agents) | ≈ 0.5M |
| Wave 3 (expect 10–15 B/M candidates at ≈ 80k each) | ≈ 1.0M |
| Synthesis and report | ≈ 0.3M |
| **Total** | **≈ 2.5M tokens**, roughly 2M on the top tier |

Check remaining budget before each wave. If wave 3 cannot be afforded in full, refute the
Blocking candidates only and mark Material ones "unrefuted" in the report rather than skipping
refutation of the headline items.

### 6.3 Stop rules and hygiene

- No agent runs `scripts/01_download_public_data.py` with `--refresh`, writes under `outputs/`
  or `data/`, or edits source. Probes and re-runs use `PHILLYPARKING_OUTPUTS_DIR` and
  `PHILLYPARKING_DATA_DIR` pointed at `audits/_scratch/`.
- Add `audits/_scratch/` to `.gitignore` before launching wave 1 (the one repo edit this plan
  permits).
- A check with no output has not passed: every negative result must print what it scanned.
- If the budget runs out, the report says where the audit stopped.

### 6.4 Model and effort allocation

Wave 1 is bounded tracing work: Sonnet at high effort. Waves 2 and 3 and the synthesis are
adversarial judgment with nothing to look up: Fable at xhigh. Agent 1c is compare-two-things
work plus web lookups: Haiku or Sonnet at medium. These follow the global guidance on allocating
by the shape of the work rather than uniformly.

---

## 7. Deferred and out of scope

- Prose of `Report.tex` and `notebooks/paper/*.qmd` (user instruction). The `docs/TODO.md` garage-
  price item stays in the TODO.
- Streamlit app behaviour beyond which directory it reads (I6).
- Performance, style, refactoring (`code-refactor` territory). The slow test suite is in scope
  only as a guard-cost fact.
- Repo tidiness: orphan files, the stale `outputs/models/scenarios/` tree (`repo-hygiene`
  territory), except where a live consumer depends on them.

## 8. Decisions needed from the user before launch

1. Approve the scope above, in particular treating the fixture-based results as in scope for
   soundness rather than exempt as a "demo".
2. Confirm the budget order of magnitude (≈2.5M tokens) is acceptable, or name a cap so the
   waves can be trimmed in advance (wave 3 first, then 1c).
