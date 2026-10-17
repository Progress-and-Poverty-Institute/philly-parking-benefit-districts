# Wave 1b findings (dimension 4: demand law -> rules -> revenue -> welfare -> sweep -> outputs), 2026-10-16

Agent: Sonnet, high effort. Worktree commit b27c7b2. The agent's harness refused a direct write of
this file, so the orchestrator saved the agent's returned report here verbatim. Evidence beside it:
`p*.py` with `.out`, `guard/*.pytest.txt`, `guard_summary.txt`. Nothing was written to the tracked tree.

## Summary
The numbers reproduce exactly and the code computes what it says. The problems are interpretive, guard
gaps and documentation drift.
- Reproduction. Script 05 on the real segments, run in scratch, matches the tracked tables and the saved
  models byte for byte (comparison_table.csv, scenario_ranges.csv, scenario_runs.csv, all 12 saved
  parquets). Saved meta.json records commit 7744eeb with dirty=false; HEAD is b27c7b2. src/ and config/
  are identical between the two and config hashes are equal.
- Sweep. A 3-replication, 3-year run of the full 54-cell grid matches the tracked parquet in all 2,430
  rows. The tracked cm_sweep.meta.json says dirty: true.
- Hand recomputation: revenue (3 scenarios) matches to under 3e-8 dollars; CS Seattle $87,928,556.38
  matches; DWL totals match; Act 84 waterfall seven cases match; full-PBD zone prices re-derived from the
  status-quo occupancy match to 0.0; Seattle saved prices are a fixed point (0 of 15 zone-bands move).
- Demand law. Exponential law, cs_change vs quadrature (1e-14), revenue_curve peak (p_ref/|e|) verify.
  Every path uses the configured exponential form. The sweep anchors at a flat $2 start price, not the
  posted rates, and CLAUDE.md wrongly says it is constant elasticity (4b-6). Only the dead optimizer.py
  has the old law; the grep gives 6 lines, 3 inside response.py.

## Findings
- 4b-1 Material, ran. Both reforms are set by floors in 4 of 5 zones. Unclipped Arnott prices: cca 0.75,
  ucity 0.59, fishtown 0.15, south_philly -0.22, against floors 1.0, 1.0, 0.5, 0.5. Those four zones end
  at identical prices, and an identical $44.1M revenue loss, under both reforms: 75% of the full-PBD loss;
  cca alone is 51% of Seattle's. Only ccc is set by a rule: 2.86 under max, 2.67 under q90, 1.57 under
  q75, 1.0 under mean. So the comparison between reforms is the ccc rule difference.
- 4b-2 Material, ran. The sweep's peak-versus-mean result sits in the exponential law's extrapolated
  range. Peak rules reach a median year-8 price of $4.80-4.85 from a $2 start; they exceed the
  revenue-maximising price 2/|e| in 88% of rep-years at e=-0.7 and 43-46% at -0.4. Swapping to constant
  elasticity at year 3 moves breakeven by up to 0.7 min and welfare_diff by up to 3.6x in one cell. No
  demand-form sensitivity is stored.
- 4b-7 Material, ran. No guard ties a tracked artifact to its config. 07 --check compares only the tex
  file with comparison_table.csv; it passes with a corrupted cm_sweep_paired.csv. The tracked-sweep test
  passes under constant elasticity, 50-minute search cost and a $6 ccc rate. Nothing compares config_sha256.
- 4b-3 Advisory, ran. ordering_violations returns 12 rep-years on the tracked sweep for each of the two
  pairs it was run on (the revenue half only). The "identity" is a constant-elasticity result; the
  docstring and CLAUDE.md say "empty frame = holds".
- 4b-4 Advisory, ran. window_dependence pools breakevens with opposite meaning for peak_band vs
  peak_zone. The -3958 minute cell is dominance (comparator has more surplus and less search), so c* is
  meaningless; 10 cells NaN; no direction column. Mean-type rows range 1.1-7.3 minutes; the plan's "up to
  19" is not reproduced.
- 4b-5 Advisory, ran. The tau=0, sigma=0 cells (9 of 54) hold 100 identical replications.
- 4b-6 Advisory, read. Stale CLAUDE.md sweep paragraph (constant-elasticity law). pricing_rules.yaml:41
  cites a nonexistent key. The 5-minute / $20 constants sit in several places.
- 4b-8 Advisory, ran. derive_baseline_anchors.py:62 ignores PHILLYPARKING_CONFIG_DIR; without --check it
  would write the tracked file. --check fires correctly on a stale config and on stale data.
- 4b-9 Advisory, ran. Guard injection, 15 one-at-a-time changes against a control of 335 passed: 13
  fire 1-16 tests (mostly literal pins); search_cost.minutes_at_reference 5->50 and mean_duration_hr
  1.5->3 fire none. O11 refuted for 13 of 15. Table in guard_summary.txt.
- 4b-10 Advisory, ran. A segment missing from the panel is silently imputed the zone-mean occupancy
  (hand case: revenue 149,760 where "no demand" gives 74,880). All segments present in the real run.
- 4b-11 Advisory. K3/O10 confirmed: no code path mixes observed and baseline occupancy. --ppa runs on
  the stub; block-face ids have no join to centerline segments.
- 4b-12 Advisory, analytic. A log-log fit across a 3->4 rate change returns -0.348 against a prior-slot
  meaning of -0.40 (about 13% low). PyMC not run.
- 4b-13 Advisory. optimizer.py is dead and carries the constant-elasticity law. App page 3 uses a
  20-segment fixture and no priced-hours mask.
- 4b-14 Advisory, ran. The DWL proxy and revenue truncate at occupancy 1. 9.1% of Seattle priced
  block-hours (505,544 car-hours a year) have latent demand above capacity and are charged nothing. The
  CS share attributable to unservable demand is only 0.2%.
- 4b-15 Advisory, ran. The seed range is degenerate on real segments (n_seeds=1). Inside the elasticity
  range, Seattle beats full PBD on revenue at optimistic ($58.5M vs $55.2M) and loses at central and
  pessimistic.
- 4b-16 Advisory, ran. O1 refined: baseline priced-hour mean 0.45-0.60. Raising the stated levels to
  0.49-0.64 and then 0.57-0.70 still leaves four zones cut; the size changes a lot (Seattle revenue 0.54,
  0.63, 0.78 of the status quo).
- 4b-17 Advisory. No external scale check: $6,209 revenue per space-year; 22,653 modelled spaces vs
  15,406 citywide (the prior audit's Controller figure, not re-verified).

## Prior audit (current code)
| Status | Findings |
|---|---|
| Closed | 7, 8, 9, 10, 11, 14, 15, 23, A1, A2, A12 |
| Closed as defect, with residual | 3 (4b-1), 4 (4b-3, 4b-4) |
| Partly or mostly open | 5 (tool done, no real fit), 6, 13, 20, 21 (notebooks still scaffolds), 22 (page 3), A4, A13 |
| Open (dead code) | A5 |
| Moot on real segments | A3 |
The two-cycle branch is exercised only by a constructed test; no real run cycles at any of the three elasticities.

Clean list: 30 items.

## Other checks
- 07 --check fires correctly on stale tex files.
- Identification verdicts: one period raises; two zones both changed with no control raises; one changed
  plus one control identified; three periods with no control identified.
- --stub ingestion reproduces the known answer with zero difference; the expected table is hand
  arithmetic, independent of the ingest code.
- Dead modules: consumer_surplus.py, optimizer.py, validation/*, ml_occupancy.py, occupancy_estimator.py,
  features.py, ppa_stub.load_transactions, welfare/incidence.py, elasticity/priors.py have callers only in
  tests or notebook-builder strings. At least 2 notebook-builder calls no longer match current signatures.

## Not done
The sweep was not run at year 8 under an alternative demand form (capped at 3 years). The PyMC test was
not run. External numbers (Controller space count, Act 84 figures) were not re-verified (no network).
