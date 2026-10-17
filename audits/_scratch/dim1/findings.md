# Wave 1c findings (dimension 1 + parameter provenance), 2026-10-16

Agent: Sonnet, medium effort. Worktree commit b27c7b2. The agent's harness refused a direct
write of this file, so the orchestrator saved the agent's returned report here verbatim.
Probes and outputs in this directory: parameters.md, probe_breakeven.py/.out, probe_modules.py/.out,
probe_symbols.py/.out, probe_deadkeys.py/.out, probe_notebooks.py/.out, probe_zone_occ.out, probe_bbox.out.
Not run: scripts 01/02/05/06/07. Run: derive_baseline_anchors.py --check (up to date).

## Summary
The three deliverables claim: (1) the white paper says demand-responsive pricing in five zones raises
revenue and cuts cruising; (2) the Chatman-Manville paper says when peak targeting beats mean targeting
on welfare; (3) the tool is a Seattle-style rule pricer with "ML/RL advanced mode". The code computes:
(1) fixed-point prices of two rules on 3,145 zoning-selected real segments under a stated occupancy
profile, and both CUT revenue (status quo $140.7M, Seattle $75.7M, full PBD $82.0M); (2) a welfare
breakeven over a random n=120 fixture with every zone started at $2; (3) saved-scenario viewer, plus a
revenue page on an n=20 fixture and a placeholder equity page. The strength gap is the main one: the CM
ordering is a theorem of the design (all 108 same-instrument cells have the same sign pattern, every
replication), and only the size of the breakeven is a measurement. The scenario sign is set by stated
occupancy levels; no zone's busiest priced hour reaches 0.85 (CCC 0.758), and four of five zones end on
invented floors. README is still fixture-era (120 segments, $4.3M, x10, PPA_DATA_SOURCE swap into dead
code, "ML/RL"). Web checks: Act 84, Bill 240335, PPA CCC/CCA/long-term rates, SDOT 70/85 and $0.50, Shoup
3.5-14, PASDA classes, Mexico City 30% all verified. Not verifiable or not found: Lehner-Peer -0.40 /
bracket / "higher prices more elastic" (abstract has none; paywalled); PPA rates for UCity $2.00, South
Philly/Fishtown $1.50 (not in any PPA notice); USDOT "2024 $17.90" (latest guidance is 2016).

## Findings (id | severity proposed | confidence)
1-1 README states pre-PR#4-12 data, scale, real-data swap, modules, n=200 | Material | Verified read+ran
1-2 Scenario population is a zoning stand-in (28% class-5 locals; classes 13/18 undefined) but documents say "metered" | Material | Verified read
1-3 Reform sign still set by stated levels (prior #1 open) | Material | Verified ran
1-4 CM result: qualitative claim is a theorem; only c* is measured | Material | Verified ran
1-5 Plan/memory sweep numbers (up to 19 min, 46/54) do not match tracked CSV (max cell median 7.33; 52/54); sweep built at commit 7744eeb, git dirty | Advisory | Verified ran
1-6 "Both cut" unfalsifiable except by constants; 4/5 zones sit at configured floors | Material | Verified ran
1-7 Zone boxes now decide rates; CCC box: 455 of 993 segments north of Arch, 18th-20th excluded (prior A14 changed) | Material | Verified ran
1-8 Mechanisms named but unimplemented: market-priced permits, RL, optimizer, context shifts, dwell time, cross elasticities, validation, Gini/MC claims in qmd | Material | Verified read
1-9 Question moved deliberately; recorded only in CLAUDE.md/memory, not README top/PLAN | Advisory | Verified read
1-10 Lehner-Peer attribution unsupported by abstract (prior #26 open) | Material | Verified read/Suspected
1-11 Seattle rule vs SDOT: SDOT reviews 3x/yr, own bands, no double step; band and step verified | Advisory | Verified read
1-12 Only CCC, CCA, long-term rates sourced; Report vs config disagree on 9 of 15 numbers (prior #27 open) | Material | Verified read
1-13 Shoup range verified but not the quantity used; config cites nonexistent key cruising_minutes_at_reference; 5 min and VOT 20 hard-coded in scorer | Advisory | Verified read
1-14 App Revenue Forecast page runs on n=20 fixture, contradicting "app only loads saved results" | Material | Verified read
1-15 Dead keys/modules/notebooks sweep (14 dead keys; 8 zero-caller modules; 21 notebook call defects in 6 of 10) | Advisory | Verified ran
1-16 Floors/rates/min_commercial_share/VOT/levels absent from all sensitivity ranges | Material | Verified ran

Clean list: 15 items (Act 84 text, Bill 240335 fees, PPA Core/Area/long-term rates, SDOT band and step,
Shoup range, ecoParq 30%, PASDA codes, anchors --check, 3,145/22,653 reconciliation, saved status-quo
prices, sweep pairs complete, no tests.fixtures in app/, no x10 multiplier in src, CLAUDE.md "real OSM"
line gone, shared CM/Seattle bands).

Could not finish: Lehner-Peer full text, USDOT 2016 table at source (403), SDOT decrease-step amount,
Report/qmd prose (out of scope), PR #10 threshold sensitivity not re-run, README "skipped if cached" for
script 01 not run.

## Prior-audit status (dimension 1 items)
#1 open; #2 closed for scenarios, open for sweep and app page 3; #12 partly closed (multiplier gone, no
external check, README still claims it); #16 open; #25 closed in code/config, open in papers; #26 open;
#27 open as config premise (9 of 15 numbers); A6 open and wider; A11 closed; A14 changed (boxes now decide
rates); A15 open; A16 open.

## Detail for key findings
1-4 evidence: probe_breakeven.out. Year 8, mean_zone vs peak_zone and mean_band vs peak_band, 108 cells:
breakeven min 1.09, median 2.02, max 7.33 minutes; comparator_searches_more share = 1.0 in every cell;
cs+revenue diff > 0 in all 108; peak wins at 5 min in 52 of 54 cells per instrument. Cross-instrument
peak_band vs peak_zone is not sign-determined (breakeven -3958 to 161, 10 NaN, 3 negative).
welfare_diff(c) is linear in c by construction (cm_sweep.py:299-331). The design cannot produce a
same-instrument cell where the lower-priced rule has less search cost or more surplus. The only way to
make the claim wrong is a measured Philadelphia search time above c* (about 1-7 min at 95%, 10 spaces).
1-3/1-6 evidence (probe_zone_occ.out): capacity-weighted priced-hour occupancy of the saved status-quo
panel, mean / busiest hour: ccc 0.600/0.758, cca 0.524/0.621, ucity 0.526/0.641, fishtown 0.475/0.593,
south_philly 0.453/0.538. Saved reform prices: cca 1.0 and ucity 1.0 (configured floors), fishtown 0.5
and south_philly 0.5 (floors); only CCC is interior (Seattle $1.50-3.50, mean 2.33; full PBD 2.75).
Floors are unsourced and Report.tex gives different ones.
1-7 evidence (probe_bbox.out): Arch lat 39.9537, Locust 39.9476, Vine 39.9574, Spring Garden 39.9618,
4th lon -75.1471, 20th -75.1740, 18th -75.1707. CCC box lat 39.945-39.960, lon -75.170 to -75.140: about
290 m south of Locust, 690 m north of Arch, starts at 18th St, about 600 m east of 4th. 455 of 993 priced
CCC segments lie north of Arch, 64 south of Locust.
1-8 table (named in -> consumer): scenarios.yaml:32,37-38 market-priced permits / rpp_policy.kind -> none
(runner.py:325 reads only revenue_share_to_pbd); zones.yaml:81-89 market_pricing_targets -> only
app/pages/4_Equity_Analysis.py:28 (illustrative, unweighted mean x 80,000 permits); README:7 and PLAN:10
"ML/RL" -> none (ml_occupancy has no non-test caller); PLAN optimizer for permits ->
optimizer.solve_pbd_pricing no non-test caller; elasticity_priors context_shifts/dwell_time/cross ->
priors.central_prior and cross_priors have no non-test caller, dwell_time read by nothing, the runner
applies one scalar to every zone; scenarios.yaml cycle_years -> dead; 02-methods.qmd "hierarchical fit",
"30 Monte Carlo replications", "Gini on incidence" -> not run / not implemented; PLAN validation (spatial
CV, manual-count backtest) -> validation/* no non-test caller.
1-1 README premises tested: README:88-107 (120 segments, $4.31M/$3.61M/$3.56M) false, saved results are
3,145 segments, $140.7M/$75.7M/$82.0M; README:93-95 (x10, "$40-50M consistent with PPA") no multiplier in
code, model is 3x the claim; README:62,120-121 PPA_DATA_SOURCE=real swap points at
io/ppa_stub.load_transactions, which has no non-test caller (real path is ppa_ingest.yaml -> scripts/03b
-> 05 --ppa); README layout lists a "Chatman-Manville" pricing module that is now targeting_rules.py;
README:151 "n=200" vs config 100.
1-14: app/pages/3_Revenue_Forecast.py:30-33 uses make_synthetic_segments(n=20); pages 1-2 read saved results.

## Dead modules (probe_modules.out / probe_symbols.out)
Zero non-test importers: cli (console entry only), demand.ml_occupancy, demand.occupancy_estimator,
elasticity.priors, pricing.optimizer, validation.crossval, validation.manual_counts,
welfare.consumer_surplus, welfare.incidence. Only-dead importers: demand.features (only ml_occupancy),
validation.calibration (only crossval), io.ppa_stub.load_transactions and generate_rpp_issuances (module
itself live for write_known_answer_export via script 03b). Live but with dead public symbols (37 of 212
top-level public symbols have zero non-test references): cli x3; occupancy_estimator.hourly_to_weekly,
occupancy_panel_from_stub; response.elasticity_at, revenue_maximising_price; synthetic_baseline.expand_panel;
hierarchical_bayes.load_fit; priors.central_prior, cross_priors, named_scenario; osm_loader.graph_to_segments;
ppa_stub.generate_rpp_issuances, load_transactions; arnott_inci.demand_function; optimizer.solve_pbd_pricing;
forecast.revenue_per_segment_hour, revenue_under_scenarios; spatial.synthetic.make_synthetic_panel;
zones.aggregate_to_zones, assign_zones; calibration.reliability_diagram; crossval.evaluate_occupancy_model;
manual_counts.backtest, backtest_summary, load_manual_counts; viz.maps.occupancy_heatmap;
consumer_surplus.aggregate_cs_change, consumer_surplus_change_batch; incidence.cs_change_by_decile,
incidence_summary, income_deciles_from_acs, payment_burden_by_decile, simple_incidence_summary,
trip_origin_decile (gini has test-only use).
Notebooks (probe_notebooks.out): 21 defects in 6 of 10 notebooks. 06_revenue_scenarios 6, 01_data_acquisition 5,
02_spatial_panel_construction 4, 05_seattle_pricing_simulation 3, 00_setup_check 2, 07_welfare_incidence 1.
Notebook 06 and Quarto 03-results call run_all_scenarios() with no segments, which silently falls to a
20-segment fixture. scripts/build_notebooks.py still emits tests.fixtures imports (lines 114, 381).
App: no tests.fixtures import; page 3 on n=20 fixture; page 4 placeholders.

Dead config keys: zones description, role, long_term_meter_rate (x2), rpp motorcycle/household_cap/
low_income/temp_15/temp_30; elasticity dwell_time, context_shifts.mixed_use and long_run; scenarios
description, notes, cycle_years (x2), rpp_policy.kind and annual_fee_usd; ppa_ingest sessions.columns.channel.
