# CLAUDE.md — Project-specific instructions for Claude Code

## Environment

- **Python**: always `C:/Users/druss/miniconda3/python.exe` (the system `python` is the Microsoft
  Store stub). `conda env create -f environment.yml` may fail with a libmamba DLL error: install
  missing packages into base with `python.exe -m pip install <pkg>`.
- Run `pip install -e .` from the project root before any script or test (`src/` layout).

## Code gotchas

- **Columns**: price is **`price_usd_per_hr`** everywhere, never `"price"` (it broke the wiring of
  modules); revenue output is **`annual_revenue_usd`**, not `revenue_usd`.
- **Merging a panel onto `segments`**: drop the panel's `zone_id` and `capacity` **before** the
  merge, or you get `zone_id_x` / `zone_id_y` and `capacity_x` / `capacity_y`. Used in
  `revenue/forecast.py`, `scenarios/runner.py` and `hourly_search_cost` (which merges
  `segments[["segment_id", "capacity", "zone_id"]]`; the sweep's panel already carries both):

  ```python
  panel = occupancy_panel.drop(
      columns=[c for c in ("zone_id", "capacity") if c in occupancy_panel.columns]
  ).merge(seg, on="segment_id", how="inner")
  ```
- **`attrs` are fragile**: `pd.concat` and similar drop them. `segments.attrs["segment_source"]`
  (set by `make_synthetic_segments` and `load_segments`) picks the anchor set and feeds provenance;
  a frame that lost it is recorded as `unknown`, and the baseline needs `anchor_set=` passed.
- **Synthetic helpers** `make_synthetic_segments` / `make_synthetic_panel` live at
  `phillyparking.spatial.synthetic`; `tests/fixtures/__init__.py` re-exports them for pytest.
  **Never import from `tests.fixtures` in production modules** — it breaks outside pytest.
- **CRS**: store in **EPSG:4326**; distances and buffering in **EPSG:32618** (UTM 18N). Reproject
  before `.buffer()` or `.centroid`.
- **Gini** (`welfare/incidence.py`, via Lorenz curve): the curve **must** prepend (0, 0), or equal
  incomes return 0.0625 instead of 0.0:
  `lorenz = np.concatenate([[0.0], np.cumsum(sorted_weights) / total_wv])`.

## Synthetic baseline calibration

`demand/synthetic_baseline.py` scales each segment's weekly profile between its own off-peak floor
and peak, interpolated by a latent demand intensity. Every anchor is absolute and lives in
`config/demand_baseline.yaml`: covariates are standardised as (log1p(x) - center) / scale with
fixed centers and scales, intensity maps to peak occupancy between fixed `intensity_low` /
`intensity_high`, and the land-use mix is centred on the same centers. A segment's baseline never
depends on which other segments are loaded (audit finding 24); never reintroduce quantiles,
z-scores or means taken over the loaded set.

**Anchor sets**, one per reference set of segments: `synthetic_fixture` (the fixture's moments,
rounded) and `philadelphia` (the priced curb of the real `segments.parquet`, written by
`scripts/derive_baseline_anchors.py` between BEGIN/END markers; rerun it after script 02 or any
change to the priced-curb rule or inventory). `baseline_occupancy` picks the set from
`segments.attrs["segment_source"]["kind"]` via `source_anchor_sets` (fixture -> `synthetic_fixture`,
file or PPA inventory -> `philadelphia`) and raises when there is no source. Weights and occupancy
levels (`peak_target`, `low_demand_peak`, off-peak floor) are shared and stated, not measured.
It warns when more than `max_clipped_share` of segments sit at the cap or floor
(`panel.attrs["calibration"]` has the set and shares). Segments the PPA panel covers should use
observed occupancy instead.

## Segments in scripts 03, 05, 06: real, fallback, cache

Scripts 03, 05 and 06 load real segments with `load_priced_segments`, which keeps only segments
whose `zone_id` `zones.yaml` prices (the rest earn nothing and carry no trips) and records the
filter and counts in `segment_source`. Script 05 uses `make_synthetic_segments(n=120, seed=seed)`
when `data/processed/segments.parquet` is missing or has fewer than 5 segments in named zones,
recording why in `segment_source.fallback_reason`; it never builds segments from the network. The
cached baseline panel (`demand_panel.parquet`) is reused only if `demand_panel.key` matches
`panel_cache_key(segments, seed)` (segment ids and covariates, anchors, seed); script 03 writes the
same key. `--ppa <dir>` runs on the Parking Authority panel instead, with no fallback.
`scripts/06_export_paper_figures.py` applies the same named-zone check and computes the (cheap)
baseline panel itself rather than reading a cache that could belong to other segments; without
the fallback the Laffer figure would be skipped.

## Arnott-Inci zone pricing

`_arnott_zone_prices()` in `scenarios/runner.py` must skip zones present in the occupancy panel but
absent from `current_prices`:

```python
cur_row = current_prices[current_prices["zone_id"] == zone]
if cur_row.empty:
    continue
```

**Peak statistic: the zone's busiest priced hour of capacity-weighted occupancy.** For each zone,
average occupancy across its segments weighted by capacity, hour by hour, over the zone's priced
hours only; take the maximum; price so that hour sits at `1 - target_vacancy`. Why:

- Arnott-Inci treat a downtown area as one pool that a cruiser searches block by block, so search
  depends on the zone aggregate. Hence capacity-weighted zone-hours, not segment-hours.
- A zone has one rate across all its priced hours, so the only rate that holds the aggregate at or
  below the target in *every* priced hour brings the busiest one there. Hence the maximum, which
  is also what "eliminates cruising at the busiest hour" says.
- Unpriced hours are excluded because the rate cannot act on them (the old all-hours q90 let
  overnight residential occupancy set a downtown rate).
- The panel is a typical-week profile, each hour already an average over weeks, so its maximum is
  not one noisy draw. On real week-by-week data, revisit: a high quantile of zone-hours would be
  more stable.

The choice moves the full-PBD row's sign (audit 2026-10-14, finding 3): do not swap it without
rerunning scripts 05/06 and updating the prose. Segment-level cruising remains after the step
(blocks busier than the zone average stay over the line): a property of one rate per zone, not a
bug. Capacity cancels in the formula, so the code passes occupancy shares (`capacity=1.0`).

**Floors and ceilings.** The rate is the unclipped solution held to the zone's `floor` / `ceiling`
(`seattle_rule.zone_bounds`, shared with the Seattle and Chatman-Manville rules; global bounds in
`pricing_rules.yaml` for a zone without its own). Zone bounds in `zones.yaml` are stated
assumptions with no PPA source; where one binds it sets the rate. Kept visible by: (1)
`n_zones_at_floor` beside `n_zones_at_ceiling` in the comparison table, against the bound in force;
(2) *target slack* = target occupancy minus busiest-hour occupancy (positive: no rate above the
floor reaches the target; the unclipped solution may be below zero), recorded per zone with
`peak_occ`, `target_occ`, `target_slack`, `unclipped_price`, clipped rate, bounds and `at_floor` /
`at_ceiling` in `diagnostics["zone_pricing"]` (`first_review` at posted rates, `last_review` at the final state);
(3) `run_scenario(..., use_zone_floors=False)` ignores zone floors (global floor and ceilings still
apply; `diagnostics["use_zone_floors"]`; see "Ranges and sensitivity runs").

## Demand form: one law for every price response

`demand/response.py` is the only place demand moves with price. The elasticity priors
(`elasticity_priors.yaml` `scenarios`) are the elasticity *at the zone's posted rate*; the form
(`demand_form`, default `exponential`: q = q_ref exp(e (p - p_ref) / p_ref), elasticity
e p / p_ref) says what happens away from it, so revenue peaks at p_ref / |e| and the Laffer figure
has an interior maximum (audit finding 14). `constant_elasticity` (no peak for |e| < 1) and
`linear` (a choke price) are selectable for sensitivity. Do not reintroduce `(p_new / p_old) ** e`
anywhere.

**The priors are elasticities of occupancy (EPO), the quantity the model moves, and the form and
the values (-0.60 central, the -0.40 / -0.90 bracket, the context shifts) are stated
assumptions**, informed by, never read from, Lehner and Peer (2019, TR-A 121: 177-191; copy in
`research/`; EPO = EPD + EPV); the header of `config/elasticity_priors.yaml` gives the interval
behind each value (the model's elasticity acts on latent demand, which is why -0.90 is plausible).
`dwell_time` carries the paper's EPD and nothing reads it. The paper supports only the sign of the
rise of elasticity with price (a cross-study gradient on price relative to GDP per capita); it
estimates no functional form, and its gradient lies between constant elasticity and the
exponential (linear rises faster than either). What the form implies is the content to state:
elasticity doubles when the price doubles, and revenue peaks at p_ref / |e|. The research note's
"revenue rises monotonically" for the central case is the constant-elasticity reading, which the
default form does not share.

**Per-zone anchoring is an assumption.** Each zone's prior is its elasticity at its own posted rate
(-0.60 at $1.50 in Fishtown and at $4.00 in Center City Core), so zones do not share one demand
curve: one exponential law with -0.60 at $1.50 would give -1.60 at $4.00. The sensitivity is one
citywide law: e at a single reference price p0, each zone's elasticity at its posted rate following
from the law (`citywide_zone_elasticities`; re-anchoring a law at a point on its own curve leaves
it unchanged, so the per-zone machinery follows the single law exactly, for every form). Run with
`run_scenario(..., citywide_reference_price=p0)`; `diagnostics["demand_law"]` records the
anchoring, p0 and every zone's elasticity at its posted rate. p0 is
`runner.citywide_reference_price`, the capacity-weighted mean posted rate of the priced segments:
the central prior is one number for the city, so it sits at the price of the average priced space
(a zone's own rate would make the other zones extrapolations).

**Every caller passes the reference price.** `apply_elasticity(..., reference_price=<posted
rates>)` raises without one; `revenue_curve` and `_project_occupancy` use the baseline price;
`optimal_price_arnott_inci` takes `reference_price` (the runner passes the status-quo rate, not the
rate in force); the Chatman-Manville sweep anchors at its start price; `cs_change` is the exact
integral of the same law and `cs_change_served` the integral of min(q, capacity) (see "Welfare
objects"). The hierarchical model fits log occupancy on log price: that estimate is the elasticity
at the observed prices, which is what the prior slot means.

## Priced hours: one mask from `config/zones.yaml`

`phillyparking.pricing.priced_hours` alone decides when a meter is on (per zone, weekday / Saturday
/ Sunday windows; a zone absent from `zones.yaml`, such as the fixture's `other`, is never priced).
`apply_elasticity`, `annual_revenue`, `revenue_curve`, `hourly_search_cost`, the Arnott-Inci peak
and the Seattle band statistics all read it; `apply_elasticity` and the search-cost functions
default to `priced_hours_only=True` and need `zone_id` on the panel. The Chatman-Manville sweep
prices only priced hours too, through its own closed-form demand update.

Revenue per zone = zone capacity x the zone's annual priced hours x capacity-weighted priced-hour
occupancy (x price); for a full weekly panel, 52 x the sum over priced rows of occupancy x capacity
x price. Full compliance is assumed. The Arnott-Inci target is the scenario's
`pricing_policy.target_vacancy`, else `pricing_rules.yaml` `arnott_inci.target_vacancy`
(`diagnostics["target_vacancy"]`). The cruising scorer has no target in it.

## Seattle rule and convergence

`pricing/seattle_rule.py` follows SDOT's 2024 rule: one statistic, the band's average
capacity-weighted zone occupancy over the zone's priced hours, per `time_of_day_bands`
(`scenarios.yaml`); above `occ_high` +$0.50, below `occ_low` -$0.50, inside the band hold. Prices
are per zone x band; `priced_hours.hourly_prices` expands them to hours.

The runner reviews annually until no rate moves by more than $0.001 (a fixed point) or prices
repeat with period 2; `rolls_forward_years` is a cap, not a horizon. A two-cycle is reported as both
phases (`diagnostics["phases"]`, `<name>_phase_a` / `_phase_b` columns), never as one year's state.
A cycle needs one $0.50 step to move demand across the whole band: under the exponential form a
step multiplies demand by exp(|e| 0.5 / p_ref), which exceeds 0.85/0.70 only when |e| / p_ref is
above about 0.39 (the $1.50 zones at the central and pessimistic elasticities, and at the central
one only if the band's occupancy lands in a thin window). `full_pbd` needs more than 10 reviews to
reach its fixed point at the central and pessimistic elasticities and without zone floors, so its
`rolls_forward_years` is 20.

## Welfare objects: one cruising model, one population

`welfare/search_cost.py` is the only cruising cost: the runner's cruising row
(`ScenarioResults.search_cost`, `search_cost.parquet`, `search_cost_total` in the comparison table)
and the sweep's scorer. An arriving driver checks a block of K = `search_unit_spaces` spaces at the
occupancy o of the segment they arrive at; it is full with probability o^K, and the driver passes
p/(1-p) full blocks; cost per segment-hour = served arrivals (occupancy x capacity /
`mean_duration_hr`) x minutes x value of time. Convex in occupancy, with no occupancy target in it.

**The search unit is the block, not the segment.** A segment is a piece of centerline cut at
intersections, attribute breaks and by the builder at about 80 m (`spatial/segments.py`); its
capacity counts one curb side, length / 7 m x 0.85, so its size is set by where the data break the
street. Passing a block costs the same minutes anywhere, so a segment-sized unit would charge a
short segment far more per arrival at the same occupancy (85 minutes for one space at the 0.99 cap
against 8.1 for ten). With the fixed unit, search minutes per arrival depend on occupancy alone
(`expected_search_minutes` takes no capacity), capacity enters only through arrivals, and the cost
is additive over any cut of the curb (`test_cost_is_additive_over_any_cut_of_the_curb`); keep it
that way. Rejected: pooling segments into blocks by centerline topology (priced curb is fragmented
and the centerline breaks at alleys, so short pieces stay short); a per-segment unit whose pass
time scales with its spaces (agrees near the cap, where K o^K / (1 - o^K) hardly depends on K, but
depends on the cut at moderate occupancy). The unit's size matters only away from the cap: it
barely moves the reform scenarios (at the cap) but moves the status quo several-fold (no
status-quo priced block-hour is near the cap), so read that cell as unpinned by this model.

**Level units.** `cruising_minutes_at_full_block` (`search_cost:` in `pricing_rules.yaml`) is the
mean search of the drivers who cruise when every block is full: the units of
`cited_cruising_minutes` (Shoup's per-cruiser range), set at its mean. A cruiser passes
1/(1 - cap^K) full blocks, so the per-block constant is level x (1 - cap^K); an arrival at a full
block cruises with probability cap^K, so its expected search
(`SearchCostConfig.minutes_at_full_block`) is cap^K x level. The `occupancy_cap` decides how much
more a full block costs than a 95% one (multiples in the `pricing_rules.yaml` comments); it must be
below 1. No Philadelphia measurement of any of these exists. There is no second cruising model: the
old linear proxy (excess over the target x minutes x value of time) had the target built in and
scored zero below it, so it could only restate the band; do not reintroduce it, and do not put a
cruising constant in a function default.

**One population: the cars that park.** Consumer surplus is `demand.response.cs_change_served`,
the exact integral of min(q(x), capacity) (the block is rationed to the parkers who value it most);
revenue is served cars x price; the search cost charges served arrivals. A block-hour whose latent
demand exceeds capacity loses exactly capacity x the price rise when it stays full, and the cars it
turns away carry neither surplus nor search cost. The runner (`_annual_cs_change`) and the sweep
both use the served integral; `cs_change` (latent) remains for the integral's own tests.

The scenario table (and the app) prints parkers' surplus + meter revenue as one row, a change from
the status quo (`surplus_plus_revenue_change` in `compare.py`, a valid partial object), and the
search cost labelled with its level; it never prints a net of the two. The level is a stated
assumption, so the project reports the sweep's breakevens, not a net at the config level.

## Chatman-Manville sweep: one rule module, paired runs, scored on welfare

`pricing/targeting_rules.py` is the only implementation of the sweep's rules: statistic (peak =
q95 of block-hours, or their mean) x instrument (one rate per zone, or per zone and time-of-day
band) gives `peak_zone`, `mean_zone`, `peak_band`, `mean_band`; `seattle_rule` is the project's
own; `min_vacancy_peak` / `avg_occupancy` are the original 168-hour rules, kept for
`ordering_violations`. All step +-$0.50 against the same 0.70 / 0.85 band (`chatman_manville:` in
`pricing_rules.yaml`, kept equal to Seattle's by a test), honour `zones.yaml` floors and ceilings,
read only priced hours, and take the rate in force from priced rows (meter-off rows may carry a
stale price). `scenarios/cm_sweep.py` runs them and builds the summaries.

**Welfare and the breakeven.** Search cost falls in price and revenue rises in it (up to the
revenue peak), so on either alone the higher statistic wins by construction. Each priced
block-hour is scored by `welfare/targeting_welfare.py`: surplus change + revenue - search cost, all
on the cars that park. Welfare is linear in the search-cost level, so every row carries
`search_cost_per_cruising_minute` and `paired_table` reports the level at which two rules tie:
`breakeven_cruising_minutes` (the headline, in the cited studies' per-cruiser units) and
`breakeven_reference_minutes` (the same level as search per arrival at the 95% reference
block-hour, c* x `reference_minutes_per_cruising_minute`; it depends on the cap, so it is not
comparable across caps).

For a same-instrument pair (`mean_zone` vs `peak_zone`, `mean_band` vs `peak_band`) the SIGN of the
breakeven is a property of the design, not a finding: a mean is never above a q95 of the same
block-hours, so the mean rule prices at or below the peak rule, total surplus is higher at the
lower price and search cost higher at the higher occupancy, in every replication. The content is
the SIZE of the breakeven against `search_cost.cited_cruising_minutes` (Shoup 2006, the same units;
`cm_breakeven_*.png` shade that range). The sign is not an identity across instruments or for
`seattle_rule`.

**`ordering_violations`** checks per replication-year that the comparator's search cost is not
below the reference's and its total surplus (`cs_change + revenue`) is not below the reference's.
Not revenue (no sign around the revenue peak) and not the price paths (mean pricing at or below
peak is the premise, not tested). Total surplus falls in price under every form, since
d(CS + p q)/dp = p q'(p) <= 0 (0 on a rationed block), so an empty frame is the ordering holding on
the sweep's draws.

**Axes** (`chatman_manville_sweep:` in `scenarios.yaml`, commented there): elasticity,
`start_occupancy` (set by scaling latent demand; the band edges are avoided), `block_dispersion`,
`observation_noise` (rules review true occupancy + noise; welfare is scored on the truth, so noise
biases a peak statistic upward), `occupancy_cap` (rules never see it: each price path runs once and
is scored per cap, its rows differing only in `search_cost`, `search_cost_per_cruising_minute` and
`welfare_change`). Demand is latent and unclipped, d = d0 x `demand_level(p)` in closed form (path
independent, the law of `apply_elasticity`); occupancy is min(d, 1). Block multipliers and noise
draws are shared by every rule and cell in a replication (paired). Fixture: n=120, seed 42, without
the never-priced "other" segments, on the `synthetic_fixture` anchors.

Report per cell, never pooled: `cell_table`, `paired_table` (each configured `comparisons` pair per
replication), `window_dependence` (across the other four axes, per comparison and cap, so the
breakeven's stability across caps is visible). Year charts use the default cap. It is a mechanism
study on a fixture: within-day shape from the baseline, unmeasured search-cost parameters, zones
nothing like Philadelphia's. Provenance: `outputs/tables/cm_sweep.meta.json`. Rebuild:
`scripts/07_export_report_assets.py --rebuild-cm-sweep` (over an hour at 100 replications).

**Demand-form sensitivity.** `07 --rebuild-cm-form-sensitivity` (run alone, about 15 minutes)
reruns the grid under all three forms at `FORM_SENSITIVITY_REPLICATIONS` (replication r of a short
run is replication r of a long one), writing `cm_sweep_form_sensitivity.csv` (breakeven and welfare
difference over cells, `cells_welfare_better`), `cm_sweep_form_beyond_peak.csv` (each form's
revenue-maximising price and the share of rule-years priced above it) and
`cm_sweep_form_sensitivity.meta.json`. The forms agree near the $2 start price and disagree where
the rules go: the peak rules settle well above it, so at -0.90 nearly all their rule-years are
extrapolated past its revenue peak by the exponential law (read the shares and gaps in the files).
A statement about the sweep is a statement about its form until the form-sensitivity rows agree.

## Data acquisition: public layers

Every loader goes through `io/raw_cache.load_layer`. A real fetch is cached under the layer's own
filename with a sidecar `<file>.provenance.json` (layer, kind real/synthetic, source, URL, UTC
fetch time); failures are retried, then raise `LayerFetchError`. A synthetic stand-in is written
only with `allow_synthetic=True` / `PHILLYPARKING_ALLOW_SYNTHETIC=1` (scripts: `--allow-synthetic`),
and only as `<stem>.synthetic<suffix>`. A file with no marker is refused (`UnknownProvenanceError`):
refetch an old cache with `scripts/01_download_public_data.py --refresh`. Script 01 exits 1 if any
layer is not real; script 02 records every layer's marker in `data/processed/segments.meta.json`
and never skips a join.

Source URLs are in the `io/` loaders (checked live 2026-10-15). Gotchas: RPP blocks are POINTS
with `district_number`; ACS block groups need `CENSUS_API_KEY` and take geometry and `ALAND` from
the cartographic boundary file (cenpy cannot request these vintages); LODES jobs sit at the
crosswalk's block internal points; the SEPTA GTFS archive holds bus and rail zips, read as two
feeds. There is no public meter inventory: `fetch_meters` raises; meters come from the Parking
Authority release. Census API errors are re-raised without the request URL, which carries the key.

**Which segments a zone prices** (`zones.yaml` `priced_curb`, `spatial/segments.py`).
`build_segments` drops centerline classes with no curb (`no_curb_classes`: expressways, ramps,
driveways, walkways) and keeps `street_class`. `assign_priced_curb` sets `zone_box` (the box the
segment lies in) and makes `zone_id` that box only for priced curb, else `other`. With `--meters`
priced curb is `has_meter`; without an inventory it is a stand-in: class 2-5 and
`commercial_frontage_share >= min_commercial_share` (`join_zoning`: share of zoned land within
25 m, flat ends, in the Commercial/Commercial Mixed-Use group; zoning stops at the property line,
so the buffer must reach across half the street). The rule is recorded as `priced_curb_rule` in
`segments.meta.json`; changing it or the inventory changes the `philadelphia` anchors.

Join columns are defined in the `spatial/join.py` docstring. `jobs_within_200m` counts LODES jobs
of the blocks whose internal point lies in the buffer; ACS attributes are buffer-share weighted and
renormalised over the covered part. Zone boxes overlap; `zones.zone_for_point` gives a point to the
smallest box containing it. The builder keys ids on `seg_id`, or `osmid|u|v|key`, splits
MultiLineStrings, drops reverse twins of two-way OSM edges, and counts everything in
`segments.attrs["build_report"]`.

## Parking Authority data: ingestion and identification

The RTKL packet and request status are in `docs/rtkl/` (`docs/rtkl/README.md`; PPA's RTKL email
`OpenRecordsOfficer@philapark.org`). `ingest/ppa.py` (script `03b_ingest_ppa.py`) reads sessions,
the meter inventory and the rate schedule through `config/ppa_ingest.yaml`, a column mapping: when
the real export arrives, edit the mapping, not the code. It writes a panel by segment x calendar
period x hour of week with `price_usd_per_hr` = the posted rate in that period; periods are cut at
the schedule's effective dates. Occupancy = paid minutes / (spaces x 60 x calendar dates of that
weekday in the period) / (1 - `unpaid_share[zone]`); `unpaid_use.unpaid_share` must be stated
(0.0 = paid occupancy, a lower bound). Every ambiguity raises `PPAIngestError` (module docstring).
`runner_inputs` picks one period for the runner and refuses one whose posted rates differ from
`zones.yaml`. `--stub` ingests `ppa_stub.make_known_answer_export` into `data/processed/ppa_stub/`,
never into `data/processed/ppa/`.

`elasticity/identification.check_identification` rank-tests the design (zone intercepts, zone x log
price, hour-of-week and period effects) and raises `IdentificationError` when no zone's elasticity
is identified; `fit_elasticity_model` calls it before importing PyMC and adds `delta[period]` when
the panel has a `period` column. Script 04 fits only priced hours of an ingested panel and exits 1
when nothing is identified (`--allow-prior-only` writes the prior labelled `prior_only`). One
period (one price per zone) identifies nothing; two zones whose rates both changed, with no
unchanged zone, are not identified once the period term is in.

## Scenario runs: saved results, sensitivity runs, allocation, report assets

**Saved results.** Scripts 05 and 06 and the Streamlit app (`app/streamlit_app.py`; the Map page
needs `streamlit-folium`, installed separately) use `runner.default_results_dir()`
(`outputs/models/<scenario>/`); the app only loads (`load_saved_scenarios`), stops with an
instruction to run script 05 if results are missing, and never recomputes. Each scenario's
`meta.json` carries `provenance`: segment source (fixture name, n and seed, or a file path, and
script 05's fallback reason), SHA-256 of every `config/*.yaml`, git commit and dirty flag,
elasticity, seed and UTC timestamp; rerun 05 from a clean tree if the commit matters.
`comparison_table` reads `allocate().to_dict()` keys (`pbd_usd`, `pbd_unfunded_usd`,
`school_district_usd`, `general_fund_usd`) strictly, so a renamed key raises instead of reading as
0. `run_scenario` raises on a NaN or out-of-range occupancy panel and lists zones absent from
`zones.yaml` (the fixture's `other`) in `diagnostics["unpriced_zones"]`; they earn nothing.

**Ranges and sensitivity runs.** Script 05 writes `scenario_ranges.csv` and `scenario_runs.csv`
(copied to `outputs/tables/` by 06): the other two named elasticities at the headline seed, and the
central elasticity at fixture seeds 0..n-1 (`--n-seeds`, default 20). On segments that are not the
synthetic fixture nothing depends on the seed (the panel is deterministic in the covariates and
the surplus term is an integral), so the seed loop is skipped. `pessimistic` (-0.90) gives the
highest revenue because both reforms are net price cuts. A Seattle two-cycle pools both phases in
each range cell. Ranges carry `search_cost_total`, `cs_change_total`, `surplus_plus_revenue_change`
and the at-bound counts like any row. Two sensitivities run all three scenarios at the central
elasticity and headline seed; each is a different run and never enters the seed range:
- zone floors removed: `no_zone_floors_lo` / `_hi` columns (rows with `floors == global_only`);
- one citywide demand law: `citywide_law_*` columns (`law` / `law_reference_price` in runs).

**Consumer surplus.** `cs_change_total` is annual dollars: over every priced block-hour, the
integral of served demand min(q, capacity) from the posted rate to the scenario's hourly price
(`runner._annual_cs_change` via `cs_change_served`, with the baseline panel's demand as q_ref),
times 52; no search-time term. A zone with priced block-hours and no price raises; no default price
is invented. `welfare/consumer_surplus.py` (nested-logit logsums) is no longer used.

**Allocation.** `revenue/allocation.py` follows 75 Pa.C.S. § 6109(g) (text and citation in
`config/allocation.yaml`): General Fund first, up to the $35M minimum, then the PBD share of what
is left, then the School District. The statute has no PBD payee and does not reduce the City's
amount by expenses, so a PBD can only be paid from the School District's excess; the unpaid part is
`pbd_unfunded_usd`. At fixture scale the General Fund takes everything: read the allocation as an
order of payment, not a forecast. The model uses gross revenue and no escalator; the statute, net
revenue citywide and an escalated minimum.

**Report assets.** `scripts/07_export_report_assets.py` writes the white paper's
`scenario_comparison.tex` (at the saved scenarios' own scale, no multiplier) and the zone map,
occupancy/revenue and Chatman-Manville year and breakeven figures from config and saved results.
Script 06 draws the Center City Core Laffer curve at the central elasticity (read from config):
`laffer_curve_ccc.png` under the configured form and `laffer_curve_ccc_forms.png` with all three
forms (`viz.charts.laffer_curve_forms`; `revenue_curve(..., form=)`), so the peak is visibly the
form's. `incidence_by_decile.png` is a constant placeholder, stamped as such; `Report.tex` still
includes it.

## Revenue scale: the model against the Parking Authority's meter revenue

The model's status-quo gross meter revenue is several times the Parking Authority's booked meter
revenue (the On Street "Revenue - Meters" line, FY2025; unaudited and gross, citywide, before the
July 2025 Center City increase, while the model covers five zone boxes at post-increase rates).
Nothing in the model is calibrated to close that; the ratio is a diagnostic. The figure, its
source and what it is and is not are in `config/benchmarks.yaml` (with a 12/9-annualised context
row). Script 06 writes `outputs/tables/revenue_benchmark.csv` (current values live there);
`tests/test_revenue_benchmark.py` ties it to the config and recomputes the ratio, and bounds
nothing about the gap's size.

**The identity.** Per zone, revenue = priced spaces x priced hours per year x capacity-weighted
occupancy over priced hours x capacity-weighted posted price x interaction (1 within a zone) x paid
share (1.0). `validation/revenue_benchmark.revenue_identity` raises unless the factors' product
reproduces `annual_revenue` per zone and in total, and script 06 raises unless that total equals
script 05's saved status-quo revenue; in the city total the interaction is the cross-zone
covariance of price and occupancy. `outputs/tables/revenue_gap_decomposition.csv` gives each
factor's model value, an external value where `gap_factors` in the config cites one (else "no
source found"; only the metered space count has sources, and the model exceeds them) and the value
that would close the gap all else equal; it does not split the gap among factors. **Capacity counts
one curb side**: both sides would double the gap. The RTKL data will settle spaces, metered sides
and paid share; until then those, occupancy levels and priced windows are stated assumptions.

## Tests, regeneration order and staleness guards

Run `C:/Users/druss/miniconda3/python.exe -m pytest tests/` from the project root. The full suite
takes about 10 minutes, almost all in `test_hierarchical_bayes.py::test_fit_recovers_true_elasticity`
(PyTensor reports "g++ not detected", so PyMC samples in pure Python); everything else, the e2e test
included, runs in seconds. For iteration skip it with `-k "not hierarchical_bayes"`.

- Order: rerun `scripts/derive_baseline_anchors.py` after script 02; scenario artifacts 05, 06, 07.
  The sweep (`07 --rebuild-cm-sweep`) and form sensitivity (`07 --rebuild-cm-form-sensitivity`)
  are separate rebuilds.
- `--check` modes exit 1 when stale: `derive_baseline_anchors.py --check` (anchors vs
  `segments.parquet`), `scripts/07_export_report_assets.py --check` (the `.tex` table).
- **Artifacts are tied to the config.** `scenarios/provenance.config_hashes()` hashes every
  `config/*.yaml` (CRLF read as LF, so Windows and Linux checkouts agree); scenario `meta.json`
  and `cm_sweep.meta.json` record it, and `tests/test_config_ties.py` fails naming the script to
  rerun (05, 06, 07 for scenarios; `07 --rebuild-cm-sweep` for the sweep). Any config edit, a
  comment included, stales the tracked sweep until rebuilt. The same file pins direction of change
  instead of values: raising `peak_target` or `low_demand_peak` raises baseline revenue and each
  zone's unclipped Arnott-Inci price; raising `search_cost.cruising_minutes_at_full_block` scales
  every scenario's search cost by the same factor and leaves revenue alone.
