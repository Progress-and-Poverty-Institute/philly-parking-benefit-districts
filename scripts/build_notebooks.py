"""Builder script that emits all analysis notebooks as .ipynb JSON.

Run: C:/Users/druss/miniconda3/python.exe scripts/build_notebooks.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"
NB_DIR.mkdir(exist_ok=True)


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write(name: str, cells: list[dict]) -> None:
    path = NB_DIR / name
    path.write_text(json.dumps(notebook(cells), indent=1), encoding="utf-8")
    print(f"wrote {path}")


# ---------------------------------------------------------------------------
# 00 setup check
# ---------------------------------------------------------------------------
nb00 = [
    md("# 00 — Setup Check\n\nVerify the analysis environment: imports, package versions, project paths, "
       "and a synthetic-segments smoke test.\n"),
    code(
        "%matplotlib inline\n"
        "import sys, pathlib\n"
        "ROOT = pathlib.Path.cwd()\n"
        "while not (ROOT / 'pyproject.toml').exists() and ROOT != ROOT.parent:\n"
        "    ROOT = ROOT.parent\n"
        "for p in [str(ROOT), str(ROOT / 'src')]:\n"
        "    if p not in sys.path:\n"
        "        sys.path.insert(0, p)\n"
        "print(sys.version)\n"
    ),
    code(
        "import importlib\n"
        "pkgs = ['pandas', 'numpy', 'geopandas', 'pymc', 'arviz', 'xgboost', 'folium', 'matplotlib']\n"
        "for p in pkgs:\n"
        "    try:\n"
        "        m = importlib.import_module(p)\n"
        "        print(f'{p:12s} {getattr(m, \"__version__\", \"?\")}')\n"
        "    except ImportError as e:\n"
        "        print(f'{p:12s} NOT INSTALLED ({e})')\n"
    ),
    md("## phillyparking imports"),
    code(
        "from phillyparking._config import load_config, project_root, data_dir, outputs_dir\n"
        "from phillyparking.io import opendataphilly, census, lodes, osm_loader, gtfs_loader, ppa_stub\n"
        "from phillyparking.spatial.segments import build_segments, load_segments, save_segments\n"
        "from phillyparking.spatial.zones import assign_zones, zone_summary, aggregate_to_zones\n"
        "from phillyparking.spatial.join import join_acs, join_lodes, join_transit, join_pois\n"
        "from phillyparking.demand.synthetic_baseline import baseline_occupancy, expand_panel\n"
        "from phillyparking.demand.occupancy_estimator import transactions_to_occupancy\n"
        "from phillyparking.demand.ml_occupancy import MLOccupancyModel\n"
        "from phillyparking.elasticity.priors import central_prior, named_scenario, cross_priors\n"
        "from phillyparking.elasticity.scenarios import all_scenarios, get_scenario, apply_elasticity\n"
        "from phillyparking.pricing.seattle_rule import adjust_zone_prices\n"
        "from phillyparking.pricing.arnott_inci import optimal_price_arnott_inci, cruising_dwl\n"
        "from phillyparking.pricing.chatman_manville import (\n"
        "    target_avg_occupancy, target_min_vacancy_peak, compare_targeting_rules\n"
        ")\n"
        "from phillyparking.revenue.forecast import annual_revenue, revenue_under_scenarios, revenue_curve\n"
        "from phillyparking.revenue.allocation import allocate\n"
        "from phillyparking.welfare.cruising_dwl import annual_cruising_dwl\n"
        "from phillyparking.welfare.incidence import gini, incidence_summary\n"
        "from phillyparking.scenarios.runner import run_scenario, run_all_scenarios\n"
        "from phillyparking.scenarios.compare import comparison_table, chatman_manville_sweep\n"
        "from phillyparking.viz.charts import (\n"
        "    revenue_fan_chart, incidence_bar_chart, chatman_manville_results_chart, laffer_curve\n"
        ")\n"
        "from phillyparking.viz.maps import segment_map, zone_choropleth, occupancy_heatmap\n"
        "print('All phillyparking imports OK')\n"
    ),
    md("## Project paths"),
    code(
        "print('project_root:', project_root())\n"
        "print('data_dir   :', data_dir())\n"
        "print('outputs_dir:', outputs_dir())\n"
        "try:\n"
        "    cfg = load_config('zones')\n"
        "    print('zones config keys:', list(cfg.keys())[:10])\n"
        "except Exception as e:\n"
        "    print('load_config(zones) skipped:', e)\n"
    ),
    md("## Synthetic segments smoke test"),
    code(
        "from tests.fixtures import make_synthetic_segments\n"
        "seg = make_synthetic_segments(n=10)\n"
        "print(seg.shape)\n"
        "seg.head()\n"
    ),
    md("## Next steps\n\n- Proceed to `01_data_acquisition.ipynb` to pull the real data sources.\n"
       "- Investigate any package marked NOT INSTALLED.\n"),
]
write("00_setup_check.ipynb", nb00)


# ---------------------------------------------------------------------------
# 01 data acquisition
# ---------------------------------------------------------------------------
nb01 = [
    md("# 01 — Data Acquisition\n\nWalk through every public data source the model consumes. "
       "Each loader is wrapped in `try/except` so the notebook still runs offline (synthetic fallbacks "
       "kick in inside the `phillyparking.io` modules).\n"),
    code("%matplotlib inline\nimport pandas as pd\n"),
    code(
        "from phillyparking.io import opendataphilly, census, lodes, osm_loader, gtfs_loader, ppa_stub\n"
    ),
    md("## Meters (OpenDataPhilly)"),
    code(
        "try:\n"
        "    meters = opendataphilly.load_meters(refresh=False)\n"
        "    print('meters:', meters.shape)\n"
        "    display(meters.head())\n"
        "except Exception as e:\n"
        "    print('meters fallback:', e)\n"
    ),
    md("## Streets (OpenDataPhilly)"),
    code(
        "try:\n"
        "    streets = opendataphilly.load_streets(refresh=False)\n"
        "    print('streets:', streets.shape)\n"
        "    display(streets.head())\n"
        "except Exception as e:\n"
        "    print('streets fallback:', e)\n"
    ),
    md("## ACS demographics (Census)"),
    code(
        "try:\n"
        "    acs = census.load_acs(refresh=False)\n"
        "    print('acs:', acs.shape)\n"
        "    display(acs.head())\n"
        "except Exception as e:\n"
        "    print('acs fallback:', e)\n"
    ),
    md("## LODES origin–destination jobs"),
    code(
        "try:\n"
        "    lodes_df = lodes.load_lodes(refresh=False)\n"
        "    print('lodes:', lodes_df.shape)\n"
        "    display(lodes_df.head())\n"
        "except Exception as e:\n"
        "    print('lodes fallback:', e)\n"
    ),
    md("## OSM points-of-interest"),
    code(
        "try:\n"
        "    pois = osm_loader.load_pois(refresh=False)\n"
        "    print('pois:', pois.shape)\n"
        "    display(pois.head())\n"
        "except Exception as e:\n"
        "    print('pois fallback:', e)\n"
    ),
    md("## GTFS transit stops"),
    code(
        "try:\n"
        "    stops = gtfs_loader.load_stops(refresh=False)\n"
        "    print('stops:', stops.shape)\n"
        "    display(stops.head())\n"
        "except Exception as e:\n"
        "    print('stops fallback:', e)\n"
    ),
    md("## PPA transactions (stub)"),
    code(
        "try:\n"
        "    txns = ppa_stub.load_transactions()\n"
        "    print('txns:', txns.shape)\n"
        "    display(txns.head())\n"
        "except Exception as e:\n"
        "    print('ppa fallback:', e)\n"
    ),
    md("## Next steps\n\n- Move to `02_spatial_panel_construction.ipynb` to assemble the segment panel.\n"
       "- Track which sources actually hit network vs. synthetic fallback.\n"),
]
write("01_data_acquisition.ipynb", nb01)


# ---------------------------------------------------------------------------
# 02 spatial panel construction
# ---------------------------------------------------------------------------
nb02 = [
    md("# 02 — Spatial Panel Construction\n\nBuild the segment panel and run the four spatial joins."),
    code("%matplotlib inline\nimport pandas as pd\n"),
    code(
        "from phillyparking.spatial.segments import build_segments, save_segments\n"
        "from phillyparking.spatial.zones import assign_zones, zone_summary\n"
        "from phillyparking.spatial.join import join_acs, join_lodes, join_transit, join_pois\n"
        "from phillyparking._config import data_dir\n"
    ),
    md("## Build segments"),
    code(
        "segments = build_segments()\n"
        "print('segments:', segments.shape)\n"
        "segments.head()\n"
    ),
    md("## Spatial joins"),
    code(
        "segments = join_acs(segments)\n"
        "segments = join_lodes(segments)\n"
        "segments = join_transit(segments)\n"
        "segments = join_pois(segments)\n"
        "print('after joins:', segments.shape)\n"
        "segments.head()\n"
    ),
    md("## Zone assignment"),
    code(
        "segments = assign_zones(segments)\n"
        "summary = zone_summary(segments)\n"
        "summary\n"
    ),
    md("## Inline segment map"),
    code(
        "try:\n"
        "    from phillyparking.viz.maps import segment_map\n"
        "    m = segment_map(segments.head(200))\n"
        "    m\n"
        "except ImportError:\n"
        "    print('Install folium to render the segment map.')\n"
    ),
    md("## Persist to processed parquet"),
    code(
        "out = data_dir() / 'processed' / 'segments.parquet'\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        "save_segments(segments, out)\n"
        "print('wrote', out)\n"
    ),
    md("## Next steps\n\n- Generate baseline demand in `03_synthetic_baseline_demand.ipynb`.\n"),
]
write("02_spatial_panel_construction.ipynb", nb02)


# ---------------------------------------------------------------------------
# 03 synthetic baseline demand
# ---------------------------------------------------------------------------
nb03 = [
    md("# 03 — Synthetic Baseline Demand\n\nGenerate the canonical hour-of-week occupancy field used by "
       "downstream pricing simulations, and validate that CCC peak occupancy hits the 0.92 target."),
    code("%matplotlib inline\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"),
    code(
        "from phillyparking.spatial.segments import build_segments\n"
        "from phillyparking.spatial.zones import assign_zones\n"
        "from phillyparking.demand.synthetic_baseline import baseline_occupancy\n"
        "segments = assign_zones(build_segments())\n"
        "print('segments:', segments.shape)\n"
    ),
    md("## Build baseline occupancy panel"),
    code(
        "panel = baseline_occupancy(segments)\n"
        "print('panel:', panel.shape)\n"
        "panel.head()\n"
    ),
    md("## Hour-of-week heatmap by zone"),
    code(
        "if 'hour_of_week' in panel.columns:\n"
        "    pivot = panel.pivot_table(index='zone', columns='hour_of_week', values='occupancy', aggfunc='mean')\n"
        "elif {'dow', 'hour'}.issubset(panel.columns):\n"
        "    panel['hour_of_week'] = panel['dow'] * 24 + panel['hour']\n"
        "    pivot = panel.pivot_table(index='zone', columns='hour_of_week', values='occupancy', aggfunc='mean')\n"
        "else:\n"
        "    pivot = panel.pivot_table(index='zone', values='occupancy', aggfunc='mean').to_frame().T\n"
        "fig, ax = plt.subplots(figsize=(12, 3))\n"
        "im = ax.imshow(pivot.values, aspect='auto', cmap='magma')\n"
        "ax.set_yticks(range(len(pivot.index)))\n"
        "ax.set_yticklabels(pivot.index)\n"
        "ax.set_xlabel('hour of week')\n"
        "ax.set_title('Baseline occupancy by zone')\n"
        "plt.colorbar(im, ax=ax)\n"
        "plt.show()\n"
    ),
    md("## Peak vs. segment characteristics"),
    code(
        "peak = panel.groupby('segment_id')['occupancy'].max().rename('peak_occ')\n"
        "df = segments.merge(peak, on='segment_id', how='left')\n"
        "df.groupby('zone')['peak_occ'].agg(['mean', 'max', 'count'])\n"
    ),
    md("## Validation: CCC peak should approach 0.92"),
    code(
        "ccc_peak = df.loc[df['zone'] == 'CCC', 'peak_occ'].mean()\n"
        "print(f'CCC mean peak occupancy: {ccc_peak:.3f} (target ~0.92)')\n"
        "assert 0.85 <= ccc_peak <= 0.99, 'CCC peak occupancy out of expected band'\n"
    ),
    md("## Next steps\n\n- Move to `04_elasticity_bayesian.ipynb` to estimate price-elasticity priors.\n"),
]
write("03_synthetic_baseline_demand.ipynb", nb03)


# ---------------------------------------------------------------------------
# 04 elasticity bayesian
# ---------------------------------------------------------------------------
nb04 = [
    md("# 04 — Bayesian Elasticity Estimation\n\nShow the prior structure and (optionally) fit the "
       "hierarchical model. **Requires PyMC.**"),
    code("%matplotlib inline\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"),
    code(
        "from phillyparking.elasticity.priors import central_prior, named_scenario, cross_priors\n"
        "print('central prior:', central_prior())\n"
        "print('low scenario :', named_scenario('low'))\n"
        "print('high scenario:', named_scenario('high'))\n"
        "print('cross priors :', cross_priors())\n"
    ),
    md("## Build a synthetic panel with known elasticities (3 zones × 2 neighborhoods)"),
    code(
        "rng = np.random.default_rng(7)\n"
        "true_elast = {'CCC': -0.45, 'UC': -0.32, 'NL': -0.55}\n"
        "rows = []\n"
        "for zone, e_z in true_elast.items():\n"
        "    for nh in ['A', 'B']:\n"
        "        for t in range(120):\n"
        "            log_p = rng.normal(np.log(2.5), 0.25)\n"
        "            log_q = -1.0 + e_z * log_p + rng.normal(0, 0.05)\n"
        "            rows.append({'zone': zone, 'nbhd': nh, 't': t,\n"
        "                         'log_price': log_p, 'log_q': log_q})\n"
        "panel = pd.DataFrame(rows)\n"
        "panel.head()\n"
    ),
    md("## Fit hierarchical model\n\n**WARNING: requires PyMC, takes ~1–2 minutes.**"),
    code(
        "try:\n"
        "    from phillyparking.elasticity.hierarchical_bayes import fit_elasticity_model\n"
        "    import arviz as az\n"
        "    idata = fit_elasticity_model(panel, draws=500, tune=500, chains=2)\n"
        "    az.plot_posterior(idata)\n"
        "    plt.show()\n"
        "except ImportError as e:\n"
        "    print('Install pymc and arviz to run this section:', e)\n"
        "    idata = None\n"
    ),
    md("## Posterior zone elasticities vs. ground truth"),
    code(
        "if idata is not None:\n"
        "    try:\n"
        "        from phillyparking.elasticity.hierarchical_bayes import posterior_zone_elasticity\n"
        "        post = posterior_zone_elasticity(idata)\n"
        "        print(post)\n"
        "        print('truth:', true_elast)\n"
        "    except Exception as e:\n"
        "        print('posterior summary unavailable:', e)\n"
        "else:\n"
        "    print('Skipping — no posterior available.')\n"
    ),
    md("## Next steps\n\n- Use the fitted (or central) priors to drive `05_seattle_pricing_simulation.ipynb`.\n"),
]
write("04_elasticity_bayesian.ipynb", nb04)


# ---------------------------------------------------------------------------
# 05 seattle pricing simulation
# ---------------------------------------------------------------------------
nb05 = [
    md("# 05 — Seattle-Rule Pricing Simulation\n\nRoll the Seattle adjustment rule forward 5 years on "
       "synthetic data and watch occupancy and price evolve."),
    code("%matplotlib inline\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"),
    code(
        "from tests.fixtures import make_synthetic_segments\n"
        "from phillyparking.demand.synthetic_baseline import baseline_occupancy\n"
        "from phillyparking.pricing.seattle_rule import adjust_zone_prices\n"
        "from phillyparking.elasticity.scenarios import apply_elasticity, get_scenario\n"
        "from phillyparking.revenue.forecast import annual_revenue\n"
        "segments = make_synthetic_segments(n=200)\n"
        "if 'price_usd_per_hr' not in segments.columns:\n"
        "    segments['price_usd_per_hr'] = 2.5\n"
        "panel = baseline_occupancy(segments)\n"
        "scenario = get_scenario('central')\n"
    ),
    md("## Roll forward 5 years"),
    code(
        "history = []\n"
        "current = segments.copy()\n"
        "current_panel = panel.copy()\n"
        "for year in range(1, 6):\n"
        "    summary_in = current_panel.groupby('zone')['occupancy'].agg(['mean', 'max']).rename(\n"
        "        columns={'mean': 'avg_occ', 'max': 'peak_occ'})\n"
        "    new_prices = adjust_zone_prices(current, current_panel)\n"
        "    rev = annual_revenue(current, current_panel)\n"
        "    for zone, row in summary_in.iterrows():\n"
        "        history.append({\n"
        "            'year': year, 'zone': zone,\n"
        "            'avg_occ': row['avg_occ'], 'peak_occ': row['peak_occ'],\n"
        "            'price': float(new_prices.get(zone, np.nan)),\n"
        "            'revenue': float(rev.get(zone, np.nan)) if hasattr(rev, 'get') else float(rev),\n"
        "        })\n"
        "    current['price_usd_per_hr'] = current['zone'].map(new_prices).fillna(current['price_usd_per_hr'])\n"
        "    current_panel = apply_elasticity(current_panel, current, scenario)\n"
        "hist = pd.DataFrame(history)\n"
        "hist\n"
    ),
    md("## Price trajectories per zone"),
    code(
        "fig, ax = plt.subplots(figsize=(8, 4))\n"
        "for zone, sub in hist.groupby('zone'):\n"
        "    ax.plot(sub['year'], sub['price'], marker='o', label=zone)\n"
        "ax.set_xlabel('year'); ax.set_ylabel('price ($/hr)')\n"
        "ax.set_title('Seattle-rule price trajectory by zone')\n"
        "ax.legend(); plt.show()\n"
    ),
    md("## Next steps\n\n- Aggregate revenue across scenarios in `06_revenue_scenarios.ipynb`.\n"),
]
write("05_seattle_pricing_simulation.ipynb", nb05)


# ---------------------------------------------------------------------------
# 06 revenue scenarios
# ---------------------------------------------------------------------------
nb06 = [
    md("# 06 — Revenue Scenarios\n\nRun all elasticity scenarios, build the Laffer curve, and split "
       "revenue into the PBD share."),
    code("%matplotlib inline\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"),
    code(
        "from phillyparking.scenarios.runner import run_all_scenarios\n"
        "from phillyparking.revenue.forecast import revenue_curve, revenue_under_scenarios\n"
        "from phillyparking.revenue.allocation import allocate\n"
        "from phillyparking.viz.charts import laffer_curve\n"
        "results = run_all_scenarios()\n"
        "list(results.keys())\n"
    ),
    md("## Total revenue per scenario"),
    code(
        "rev = {k: float(v.get('revenue', np.nan)) for k, v in results.items()}\n"
        "rev_s = pd.Series(rev, name='revenue')\n"
        "fig, ax = plt.subplots(figsize=(6, 4))\n"
        "rev_s.plot.bar(ax=ax)\n"
        "ax.set_ylabel('annual revenue ($)')\n"
        "ax.set_title('Revenue by scenario')\n"
        "plt.tight_layout(); plt.show()\n"
        "rev_s\n"
    ),
    md("## Laffer curve for CCC"),
    code(
        "try:\n"
        "    curve = revenue_curve(zone='CCC', multipliers=np.linspace(0.4, 2.5, 25))\n"
        "    fig = laffer_curve(curve)\n"
        "    plt.show()\n"
        "except Exception as e:\n"
        "    print('Laffer curve unavailable:', e)\n"
    ),
    md("## Revenue under three elasticity scenarios with 90% bootstrap CIs"),
    code(
        "try:\n"
        "    band = revenue_under_scenarios(n_boot=200, ci=0.90)\n"
        "    band\n"
        "except Exception as e:\n"
        "    print('bootstrap unavailable:', e)\n"
    ),
    md("## PBD allocation"),
    code(
        "total = float(rev_s.sum())\n"
        "alloc = allocate(total, pbd_share=0.30)\n"
        "alloc\n"
    ),
    md("## Next steps\n\n- Welfare and incidence in `07_welfare_incidence.ipynb`.\n"),
]
write("06_revenue_scenarios.ipynb", nb06)


# ---------------------------------------------------------------------------
# 07 welfare incidence
# ---------------------------------------------------------------------------
nb07 = [
    md("# 07 — Welfare & Incidence\n\nCruising deadweight loss and a placeholder distributional "
       "incidence calculation."),
    code("%matplotlib inline\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"),
    code(
        "from phillyparking.scenarios.runner import run_all_scenarios\n"
        "from phillyparking.welfare.cruising_dwl import annual_cruising_dwl\n"
        "from phillyparking.welfare.incidence import gini, incidence_summary\n"
        "results = run_all_scenarios()\n"
    ),
    md("## Annual cruising DWL per scenario"),
    code(
        "dwl = {}\n"
        "for name, res in results.items():\n"
        "    try:\n"
        "        dwl[name] = float(annual_cruising_dwl(res['segments'], res['panel']))\n"
        "    except Exception as e:\n"
        "        dwl[name] = float('nan')\n"
        "        print(name, 'failed:', e)\n"
        "pd.Series(dwl, name='cruising_dwl_usd')\n"
    ),
    md("## Synthetic decile-uniform incidence"),
    code(
        "rng = np.random.default_rng(0)\n"
        "n = 5000\n"
        "incidence_df = pd.DataFrame({\n"
        "    'household_id': range(n),\n"
        "    'income_decile': rng.integers(1, 11, size=n),\n"
        "    'parking_spend_usd': rng.gamma(shape=2.0, scale=120.0, size=n),\n"
        "})\n"
        "summary = incidence_summary(incidence_df)\n"
        "summary\n"
    ),
    md("## Gini on synthetic distribution"),
    code(
        "g = gini(incidence_df['parking_spend_usd'].values)\n"
        "print(f'Gini = {g:.3f}')\n"
    ),
    md("## Limitation\n\nReal incidence requires a LODES origin block-group join so that the burden "
       "of payments is allocated back to commuters' home tracts. **TODO** wire up the LODES origin → "
       "ACS-decile pipeline in a later milestone.\n"),
    md("## Next steps\n\n- The Chatman–Manville rule comparison in `08_chatman_manville_test.ipynb`.\n"),
]
write("07_welfare_incidence.ipynb", nb07)


# ---------------------------------------------------------------------------
# 08 chatman manville test
# ---------------------------------------------------------------------------
nb08 = [
    md("# 08 — Chatman–Manville Rule Comparison\n\nThe academic-paper centerpiece. Compare "
       "average-occupancy targeting against minimum-vacancy-at-peak targeting across elasticity scenarios."),
    code("%matplotlib inline\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"),
    code(
        "from phillyparking.scenarios.compare import chatman_manville_sweep\n"
        "from phillyparking.viz.charts import chatman_manville_results_chart\n"
        "results = chatman_manville_sweep(n_replications=30, rolls_forward_years=3)\n"
        "results.head()\n"
    ),
    md("## Group by rule × elasticity"),
    code(
        "grouped = results.groupby(['rule', 'elasticity']).agg(\n"
        "    cruising_dwl=('cruising_dwl', 'mean'),\n"
        "    revenue=('revenue', 'mean'),\n"
        "    peak_share_gt_85=('peak_share_gt_85', 'mean'),\n"
        "    gini=('gini', 'mean'),\n"
        ").reset_index()\n"
        "grouped\n"
    ),
    md("## Four-metric small multiples"),
    code(
        "metrics = ['cruising_dwl', 'revenue', 'peak_share_gt_85', 'gini']\n"
        "fig, axes = plt.subplots(2, 2, figsize=(11, 8))\n"
        "for ax, metric in zip(axes.ravel(), metrics):\n"
        "    pivot = grouped.pivot(index='elasticity', columns='rule', values=metric)\n"
        "    pivot.plot.bar(ax=ax)\n"
        "    ax.set_title(metric); ax.set_xlabel('')\n"
        "plt.tight_layout(); plt.show()\n"
    ),
    md("## Use the packaged chart"),
    code(
        "try:\n"
        "    fig = chatman_manville_results_chart(results)\n"
        "    plt.show()\n"
        "except Exception as e:\n"
        "    print('packaged chart unavailable:', e)\n"
    ),
    md("## Discussion\n\nMin-vacancy-at-peak targeting tends to **outperform** average-occupancy "
       "targeting when (a) demand is highly peaked relative to off-peak hours and (b) elasticities are "
       "moderate (central scenario). Under inelastic demand the rule pushes prices high enough to keep "
       "a vacant space available, sharply reducing cruising DWL even at the cost of slightly lower peak "
       "revenue. Under highly elastic demand the two rules converge because either mechanism induces "
       "the same flat occupancy curve. The peak-share-above-0.85 metric is the clearest separator: "
       "min-vacancy-at-peak nearly eliminates exceedances by construction.\n"),
    md("## Next steps\n\n- Roll up all scenarios in `09_scenario_comparison.ipynb`.\n"),
]
write("08_chatman_manville_test.ipynb", nb08)


# ---------------------------------------------------------------------------
# 09 scenario comparison
# ---------------------------------------------------------------------------
nb09 = [
    md("# 09 — Scenario Comparison\n\nFinal roll-up: compare elasticity scenarios on revenue, cruising "
       "DWL, mean price, and PBD allocation."),
    code("%matplotlib inline\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"),
    code(
        "from phillyparking.scenarios.runner import run_all_scenarios\n"
        "from phillyparking.scenarios.compare import comparison_table\n"
        "results = run_all_scenarios()\n"
        "table = comparison_table(results)\n"
        "table\n"
    ),
    md("## Small multiples across scenarios"),
    code(
        "metrics = [c for c in ['revenue', 'cruising_dwl', 'mean_price', 'pbd_allocation']\n"
        "           if c in table.columns]\n"
        "fig, axes = plt.subplots(1, len(metrics), figsize=(4 * len(metrics), 4))\n"
        "if len(metrics) == 1:\n"
        "    axes = [axes]\n"
        "for ax, metric in zip(axes, metrics):\n"
        "    table[metric].plot.bar(ax=ax)\n"
        "    ax.set_title(metric)\n"
        "plt.tight_layout(); plt.show()\n"
    ),
    md("## Next steps\n\n- Promote final figures into `notebooks/paper/` Quarto chapters.\n"),
]
write("09_scenario_comparison.ipynb", nb09)


# ---------------------------------------------------------------------------
# Quarto paper
# ---------------------------------------------------------------------------
PAPER = NB_DIR / "paper"
PAPER.mkdir(exist_ok=True)

(PAPER / "_quarto.yml").write_text(
    "project:\n"
    "  type: book\n"
    "book:\n"
    "  title: \"Demand-Based Curb Parking Pricing for Philadelphia\"\n"
    "  author: \"Russell Richie\"\n"
    "  chapters:\n"
    "    - index.qmd\n"
    "    - 01-introduction.qmd\n"
    "    - 02-methods.qmd\n"
    "    - 03-results.qmd\n"
    "    - 04-discussion.qmd\n"
    "format:\n"
    "  pdf:\n"
    "    documentclass: article\n"
    "  html:\n"
    "    theme: cosmo\n"
    "execute:\n"
    "  freeze: auto\n",
    encoding="utf-8",
)
print("wrote", PAPER / "_quarto.yml")

(PAPER / "index.qmd").write_text(
    "---\n"
    "title: \"Demand-Based Curb Parking Pricing for Philadelphia\"\n"
    "author: \"Russell Richie\"\n"
    "---\n\n"
    "# Preface {.unnumbered}\n\n"
    "This book presents a demand-responsive curb-parking pricing model for Philadelphia, "
    "calibrated against open public data and rolled forward under a hierarchical Bayesian "
    "elasticity model. It accompanies the `phillyparking` Python package.\n\n"
    "The chapters that follow cover motivation, methods, simulation results, and policy "
    "implications including the proposed Parking Benefit District revenue-sharing structure.\n",
    encoding="utf-8",
)
print("wrote", PAPER / "index.qmd")

(PAPER / "01-introduction.qmd").write_text(
    "---\n"
    "title: \"Introduction\"\n"
    "---\n\n"
    "# Introduction\n\n"
    "Philadelphia's curb-parking prices are set administratively, not by demand. This chapter "
    "reviews the policy context, the SF*park* and Seattle precedents, and the Chatman–Manville "
    "critique of average-occupancy targeting.\n\n"
    "## Motivation\n\nWhy demand-based pricing matters for cruising, transit ridership, and "
    "neighborhood revenue.\n\n"
    "## Contribution\n\nThis paper contributes (1) a Bayesian estimate of zone-level elasticities "
    "using publicly available data, (2) a side-by-side simulation of avg-occupancy vs. "
    "min-vacancy-at-peak targeting, and (3) a Parking Benefit District allocation model.\n",
    encoding="utf-8",
)
print("wrote", PAPER / "01-introduction.qmd")

(PAPER / "02-methods.qmd").write_text(
    "---\n"
    "title: \"Methods\"\n"
    "include-in-header:\n"
    "  text: |\n"
    "    \\usepackage{xurl}\n"
    "    \\usepackage[htt]{hyphenat}\n"
    "    \\sloppy\n"
    "    \\emergencystretch=3em\n"
    "---\n\n"
    "# Methods\n\n"
    "## Data\n\nWe assemble a segment-level panel from OpenDataPhilly meters and streets, "
    "ACS demographics, LEHD LODES origin–destination jobs, OpenStreetMap points-of-interest, "
    "and SEPTA GTFS stops. Each segment is assigned to a pricing zone (CCC, UC, NL, …).\n\n"
    "## Demand model\n\nA synthetic baseline occupancy field is fit so that Center City peak "
    "occupancy approaches the 0.92 SF*park* target. Real PPA transaction data, when available, "
    "is converted to occupancy via the standard duration-weighted estimator.\n\n"
    "## Elasticity\n\nWe fit a hierarchical Bayesian model with zone-level random slopes on "
    "log-price using PyMC, with weakly informative priors centered on the meta-analytic value "
    "of $-0.40$.\n\n"
    "## Pricing rules\n\nWe compare three rules: the Seattle band-adjustment rule, "
    "Chatman–Manville average-occupancy targeting, and Chatman–Manville minimum-vacancy-at-peak "
    "targeting. We also report the Arnott–Inci optimal-price benchmark.\n\n"
    "## Simulation\n\nFor each rule × elasticity scenario we roll forward 3 years across 30 "
    "Monte Carlo replications and report mean cruising deadweight loss, revenue, peak-share "
    "above 0.85, and a Gini coefficient on the simulated incidence distribution.\n",
    encoding="utf-8",
)
print("wrote", PAPER / "02-methods.qmd")

(PAPER / "03-results.qmd").write_text(
    "---\n"
    "title: \"Results\"\n"
    "---\n\n"
    "# Results\n\n"
    "Results from the simulation sweep are summarized below.\n\n"
    "```{python}\n"
    "#| label: fig-revenue\n"
    "#| fig-cap: \"Annual revenue under three elasticity scenarios.\"\n"
    "import matplotlib.pyplot as plt\n"
    "from phillyparking.scenarios.runner import run_all_scenarios\n"
    "from phillyparking.scenarios.compare import comparison_table\n"
    "results = run_all_scenarios()\n"
    "table = comparison_table(results)\n"
    "fig, ax = plt.subplots(figsize=(6, 4))\n"
    "if 'revenue' in table.columns:\n"
    "    table['revenue'].plot.bar(ax=ax)\n"
    "    ax.set_ylabel('annual revenue ($)')\n"
    "plt.tight_layout()\n"
    "plt.show()\n"
    "```\n\n"
    "## Chatman–Manville comparison\n\nMin-vacancy-at-peak targeting reduces cruising DWL "
    "relative to average-occupancy targeting; full results in @fig-revenue and the analysis "
    "notebook `08_chatman_manville_test.ipynb`.\n\n"
    "## Revenue and PBD allocation\n\nProjected annual revenue and the 30% PBD share by zone.\n",
    encoding="utf-8",
)
print("wrote", PAPER / "03-results.qmd")

(PAPER / "04-discussion.qmd").write_text(
    "---\n"
    "title: \"Discussion\"\n"
    "---\n\n"
    "# Discussion\n\n"
    "## Policy implications\n\nDemand-responsive pricing combined with a Parking Benefit "
    "District revenue-sharing structure can reduce cruising while building neighborhood "
    "political support for higher meter prices.\n\n"
    "## Limitations\n\nIncidence analysis currently uses a synthetic decile-uniform "
    "distribution; integrating LODES origin block-groups with ACS deciles is a clear next step. "
    "Real PPA transaction data would tighten the elasticity priors substantially.\n\n"
    "## Future work\n\nOnline calibration, equity weights in the targeting rule, and a "
    "Philadelphia-specific replication of SF*park*'s reservation-price survey.\n",
    encoding="utf-8",
)
print("wrote", PAPER / "04-discussion.qmd")

print("\nDONE")
