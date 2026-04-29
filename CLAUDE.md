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

## Streamlit app

Streamlit app is at `app/streamlit_app.py`. It reads precomputed outputs from `outputs/models/`
and `outputs/tables/`. Run `scripts/05_run_scenarios.py` first to populate those directories.
The Map page requires `streamlit-folium` — install separately if missing.

## Tests

Run with `C:/Users/druss/miniconda3/python.exe -m pytest tests/` from the project root.
The full test suite includes an e2e test (`test_e2e.py`) that runs all three scenarios on a
10-segment synthetic fixture; it is slow (~30 s) and can be skipped with `-k "not e2e"` for
rapid iteration.
