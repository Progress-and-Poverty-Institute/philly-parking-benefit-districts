# CLAUDE.md — Project-specific instructions for Claude Code

## Environment

**Python**: Always use `C:/Users/druss/miniconda3/python.exe` — the system `python` command
redirects to the Microsoft Store stub and does not work.

**Conda env issue**: `conda env create -f environment.yml` may fail with a libmamba DLL error
on this machine. Workaround: install missing packages directly into the base environment with
`C:/Users/druss/miniconda3/python.exe -m pip install <pkg>`, then `pip install -e .`.

**Package install**: `pip install -e .` from the project root; the `src/` layout means you must
do this before running any scripts or tests.

## Column naming convention

The canonical price column is **`price_usd_per_hr`** everywhere. Do NOT use `"price"` — this
caused integration failures when modules were wired together. Any new code that reads or writes
a price column must use `price_usd_per_hr`.

Revenue output column: **`annual_revenue_usd`** (not `revenue_usd`).

## Merge gotchas

When joining `occupancy_panel` (which carries `zone_id`) onto `segments` (which also carries
`zone_id`), drop `zone_id` and `capacity` from the panel **before** the merge to avoid
`zone_id_x` / `zone_id_y` splits. Pattern used in `revenue/forecast.py` and `scenarios/runner.py`:

```python
panel = occupancy_panel.drop(
    columns=[c for c in ("zone_id", "capacity") if c in occupancy_panel.columns]
).merge(seg, on="segment_id", how="inner")
```

## Synthetic baseline calibration

The synthetic baseline in `demand/synthetic_baseline.py` uses **per-segment slope/intercept
calibration** so every segment spans from its own off-peak floor to its own peak target. Key
parameters:

- `peak_target=0.92` (highest-λ segment)
- `low_demand_peak=0.62` (lowest-λ segment peak)
- `offpeak_floor=0.20`
- `temperature=2.5` (sharpened softmax for land-use mix)

Calibrated result: CCC weekday lunch peak ~0.83, other named zones ~0.62–0.67, overnight ~0.30.
**Do not re-z-score λ** — the original design z-scored lambda so half the segments had negative
lambda and all stuck near the off-peak floor. The fix was to normalize lambda to [0, 1] instead.

## Synthetic segment fallback in script 05

`scripts/05_run_scenarios.py` checks whether loaded segments have ≥5 entries in any named zone.
Real OSM data covers all of Philadelphia so only ~2 of 473 segments land in the narrow named-zone
bboxes. If the check fails, script 05 falls back to `make_synthetic_segments(n=120, seed=seed)`
and clears the demand panel cache. This is expected behavior for the demo run; it is not a bug.

## Import path for synthetic data helpers

`make_synthetic_segments` and `make_synthetic_panel` live at
`phillyparking.spatial.synthetic` (importable in production code).
`tests/fixtures/__init__.py` re-exports them for pytest.
**Never import from `tests.fixtures` in production modules** — it breaks outside pytest.

## Arnott-Inci zone pricing

`_arnott_zone_prices()` in `scenarios/runner.py` must guard against zones present in the
occupancy panel but absent from `current_prices`. Pattern:

```python
cur_row = current_prices[current_prices["zone_id"] == zone]
if cur_row.empty:
    continue
```

**Peak statistic: the zone's busiest priced hour of capacity-weighted occupancy.** For each
zone, average occupancy across its segments weighted by capacity, hour by hour, over the
zone's priced hours only; take the maximum; price so that hour sits at
`1 - target_vacancy`. Why this statistic and not another:

- Arnott-Inci treat a downtown area as one pool that a cruiser searches block by block, so
  search depends on the zone aggregate, not on any one segment. Hence capacity-weighted
  zone-hours, not segment-hours.
- A zone has one rate across all its priced hours, so the only rate that holds the aggregate
  at or below the target in *every* priced hour is the one that brings the busiest one there.
  Hence the maximum, which is also what "eliminates cruising at the busiest hour" says.
- Unpriced hours are excluded because the rate cannot act on them. Pooling them in (the old
  all-hours q90) let overnight residential occupancy set a downtown rate.
- The panel is a typical-week profile, each hour already an average over weeks, so its
  maximum is not one noisy draw. On real week-by-week data, revisit: a high quantile of
  zone-hours would be more stable.

The choice moves the full-PBD row's sign (audit 2026-10-14, finding 3), so do not swap it
without rerunning scripts 05/06 and updating the prose. Segment-level cruising remains after
the step because blocks busier than the zone average stay over the line; that is a property
of one rate per zone, not a bug. Capacity cancels in the formula, so the code passes
occupancy shares (`capacity=1.0`).

## Priced hours: one mask from `config/zones.yaml`

`phillyparking.pricing.priced_hours` is the only place that decides when a meter is on (per
zone, weekday / Saturday / Sunday windows; a zone absent from `zones.yaml`, such as the
fixture's `other`, is never priced). `apply_elasticity` (response), `annual_revenue` and
`revenue_curve` (revenue), `hourly_cruising_dwl` (DWL scorer), the Arnott-Inci peak and the
Seattle band statistics all read it. `apply_elasticity` and the DWL functions default to
`priced_hours_only=True` and need `zone_id` on the panel; only the Chatman-Manville sweep
passes `False`, because its design prices every hour.

Revenue per zone = zone capacity x the zone's own annual priced hours x capacity-weighted
priced-hour occupancy (x price); for a full weekly panel that equals 52 x the sum over
priced rows of occupancy x capacity x price. Full compliance is assumed.

The DWL scorer's threshold is the scenario's `pricing_policy.target_vacancy`, falling back to
`pricing_rules.yaml` `arnott_inci.target_vacancy`, so pricer and scorer use the same line.

## Seattle rule and convergence

`pricing/seattle_rule.py` follows SDOT's 2024 rule: one statistic, the band's average
capacity-weighted zone occupancy over the zone's priced hours, per `time_of_day_bands`
(`scenarios.yaml`); above `occ_high` +$0.50, below `occ_low` -$0.50, inside the band hold.
Prices are per zone x band; `priced_hours.hourly_prices` expands them to hours.

The runner reviews annually until no rate moves by more than $0.001 (a fixed point) or prices
repeat with period 2; `rolls_forward_years` is a cap, not a horizon. A two-cycle is reported
as both phases (`diagnostics["phases"]`, and `<name>_phase_a` / `_phase_b` columns in the
comparison table), never as one year's state. With the dead band, a cycle can still occur at
low rates where one $0.50 step changes the price by a larger ratio than 0.85/0.70.

## Script 06 synthetic fallback

`scripts/06_export_paper_figures.py` must apply the same named-zone check as script 05:
if fewer than 5 segments in named zones, fall back to `make_synthetic_segments(n=120)`.
Without this, the Laffer curve figure is silently skipped because real OSM segments
have only ~2/473 landing in named-zone bboxes.

## `hourly_cruising_dwl` drop-before-merge

`welfare/cruising_dwl.hourly_cruising_dwl` merges `segments[["segment_id", "capacity"]]`
onto the panel. If the panel already carries `capacity` (e.g., from an earlier merge in
`chatman_manville_sweep`), the merge produces `capacity_x`/`capacity_y` and
`df["capacity"]` raises `KeyError`. Always drop conflicting columns first:

```python
df = occupancy_panel.drop(
    columns=[c for c in ("capacity", "zone_id") if c in occupancy_panel.columns]
).merge(segments[["segment_id", "capacity"]], on="segment_id", how="left")
```

## Gini coefficient

`welfare/incidence.py` computes Gini via Lorenz curve. The curve **must** prepend (0, 0):

```python
lorenz = np.concatenate([[0.0], np.cumsum(sorted_weights) / total_wv])
```

Without the prepended zero, equal-income groups return 0.0625 instead of 0.0.

## CRS

- Storage: **EPSG:4326**
- Distance computations and buffering: **EPSG:32618** (UTM 18N)
- Always reproject before `.buffer()` or `.centroid` to avoid a GeoPandas CRS warning.

## Data acquisition

The RTKL packet for PPA transaction data is at `docs/rtkl/`. It is ready to submit. See
`docs/rtkl/README.md` for the submission procedure. PPA's RTKL email:
`OpenRecordsOfficer@philapark.org`.

## Saved results, provenance and report assets

Scripts 05 and 06 and the Streamlit app all use `runner.default_results_dir()`
(`outputs/models/<scenario>/`); the app only loads (`load_saved_scenarios`) and stops with
an instruction to run script 05 if results are missing; it never recomputes.
Each scenario's `meta.json` carries `provenance`: segment source (fixture name, n and seed,
or a file path; script 05 also records why it fell back), SHA-256 of every `config/*.yaml`,
git commit and dirty flag, the elasticity used, seed and a UTC timestamp. Rerun 05 from a
clean tree if the commit matters. `make_synthetic_segments` and `load_segments` set
`segments.attrs["segment_source"]`; a frame that lost its attrs is recorded as `unknown`.

`comparison_table` reads `allocate().to_dict()` keys (`pbd_usd`, `school_district_usd`,
`general_fund_usd`) strictly, so a renamed key raises instead of reading as 0.
`run_scenario` raises on a NaN or out-of-range occupancy panel and lists zones absent from
`zones.yaml` (the fixture's `other`) in `diagnostics["unpriced_zones"]`; they earn nothing.

`scripts/07_export_report_assets.py` writes the white paper's `scenario_comparison.tex` (at
the saved scenarios' own scale, no multiplier) and the zone map, occupancy/revenue and
Chatman-Manville year figures from config and saved results. Order: 05, 06, 07. `--check`
exits 1 if the table is stale; `--rebuild-cm-sweep` reruns the 200-replication sweep.

## Streamlit app

Streamlit app is at `app/streamlit_app.py`. It reads precomputed outputs from `outputs/models/`
and `outputs/tables/`. Run `scripts/05_run_scenarios.py` first to populate those directories.
The Map page requires `streamlit-folium` — install separately if missing.

## Tests

Run with `C:/Users/druss/miniconda3/python.exe -m pytest tests/` from the project root.
The full suite takes about 10 minutes, almost all of it in one test:
`test_hierarchical_bayes.py::test_fit_recovers_true_elasticity`. PyTensor finds no C compiler
on this machine ("g++ not detected"), so PyMC samples in pure Python. Every other test,
including the e2e test, runs in seconds. For rapid iteration, skip the PyMC test with
`-k "not hierarchical_bayes"`.
