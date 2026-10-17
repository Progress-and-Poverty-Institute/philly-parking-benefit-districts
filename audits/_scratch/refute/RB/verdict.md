# Refuter B verdict (Chatman-Manville sweep): written as I go, 2026-10-16

Posture: try to knock each sub-claim down (benign reading, intended design, failed reproduction,
wrong quantifier). Probes under audits/_scratch/refute/RB/. Independence: no findings.md read.

## B1(i) c* > 0 in every same-instrument cell is a theorem

**Probe:** `RB/rb1_tracked.py` -> `rb1_tracked.out` (read-only on `outputs/tables/cm_sweep.parquet`).
Replication-year level, 43,200 rep-years per pair:
- mean_zone vs peak_zone: mean price comparator <= reference in 43,200/43,200; strictly lower in
  39,831; in every one of those 39,831 gain = cs_diff + revenue_diff > 0 AND search_cost_diff > 0;
  the other 3,369 have identical prices (gain = scd = 0, breakeven NaN). Not one rep-year with
  gain <= 0 while scd > 0. Same for mean_band vs peak_band (42,981 strictly lower, all gain > 0).
- The revenue-peak lens: in 12 rep-years per pair (all e = -0.7, peak price $4.4-5.0 above the
  exponential form's revenue peak $2.86) the LOWER-priced rule earns MORE revenue, and gain is
  still > 0 (min $3.76M). That is expected: total surplus CS(p) + p min(q(p), cap) has derivative
  p q'(p) < 0 where q < cap and cap - q < 0 where q > cap, so it falls in price pointwise under any
  downward-sloping law, whatever revenue does. Revenue non-monotonicity cannot break (i).
- Not a theorem for seattle_rule vs peak_band (different statistic, two-step rule): 63 rep-years
  with breakeven <= 0, 126 with the Seattle rule priced higher. (i) is correctly restricted to the
  same-instrument pairs.
(Unit note: rb1 prints breakeven in units of the config level, i.e. c*/5; min 0.118 x 5 = 0.59 min,
max 7.34 x 5 = 36.7 min, matching the paired CSV's breakeven_minutes_max.)

**Benign reading tried:** the project already says welfare is linear in the level and reports c*
("that breakeven is the result", CLAUDE.md:180-181; README:93-95), so c* > 0 is disclosed by
reporting it. Does not hold fully: nothing in CLAUDE.md, the cm_sweep/targeting_welfare docstrings
or the tests says that gain > 0 and scd > 0 are guaranteed, i.e. that c* is ALWAYS positive and
finite, so that "where the peak statistic beats the mean" (cm_sweep.py:8) is answered by
construction as "wherever c > c*". CLAUDE.md:171-175 ("Why welfare") argues that the proxy and
revenue are monotone, "the sweep therefore scores on welfare", which implies the welfare ordering
is not monotone by construction; at a fixed c it is monotone in the one free parameter c.
`test_welfare_ordering_is_not_an_identity` (see B4) in fact asserts the identity.

**Verdict: SURVIVES, narrowed.** The sweep's sign content is a theorem (mean <= q95 => lower price
=> higher total surplus and higher search cost); its only empirical content is c*'s magnitude,
which (ii)-(v) show is the scorer's shape and the bounds'. Correct statement: "c* is positive by
construction; the sweep estimates its size under the stated search-cost shape". The conditional
reading of CLAUDE.md:180-181 is defensible as written; what is missing is the sentence that the
condition's threshold is always positive, and the "peak better in 52 of 54 cells"
(`cm_sweep_window_dependence.csv` cells_welfare_better = 2) is then only "c* < 5 min in 52 cells".
**Severity: Material** (overreach, no headline flip: the stated conclusion is conditional).
Contradicts: cm_sweep.py:3-8 and :29-35 (asks "where", implying an open question), CLAUDE.md:171-175,
tests/test_cm_sweep.py:289-303 (name and docstring), plan section 1 item 2 ("only when cruising is
costly enough" is true but trivially so).

## B2 "up to 19 minutes", "3 to 7 at high dispersion", "46 of 54" are not in the tracked tables

**Probe:** `RB/rb2_old_sweep.out` (`git show 55be807:outputs/tables/cm_sweep_*.csv`, the PR #11
rebuild under the constant-elasticity law, before PR #12).
- Pre-#12 sweep, year 8, mean_zone vs peak_zone: breakeven cell-median max 18.51 (e = -0.2,
  start 0.9, tau 0.6); by start x tau the high-dispersion column is 2.18 / 3.34 / 7.14; cells with
  peak better at 5 min: 46 of 54 (mean_band: 48). These are exactly the quoted numbers.
- Current tracked (f779618, exponential form): max 7.33 at year 8 (8.84 at year 1, mean_band),
  high-dispersion column 2.66 / 3.03 / 3.63, peak better in 52 of 54. `rb1_tracked.out`.
- The two sweeps differ ONLY in `elasticity_priors.yaml` (the `demand_form` key; same seed, same
  100 replications, same other config hashes per the two meta.json files), so the pair is also a
  100-replication form comparison on identical draws: the inelastic/high-demand corner's c* fell
  from 18.5 to 7.3 with the form (bears on B1(iv)).

**Benign reading tried:** stale numbers in agent-facing files (memory `project_state.md`, written at
the PR #11 merge; the plan's section 1, which says its numbers are hand-typed). Holds for the
tracked artifacts: `cm_sweep_paired.csv`, `_window_dependence.csv`, README and CLAUDE.md carry no
such number. Does not hold for the plan and the draft report: `review_plan_2026-10-16.md:41-42`
and `audits/audit_2026-10-16.md:27` ("3 to 7 at high block dispersion") restate the pre-#12 values
as the argument under review.
**Verdict: SURVIVES as a stale-number finding, NARROWED to the plan, the draft report and memory.**
No canonical artifact is wrong. **Severity: Advisory** (fix the three files; the draft report must
quote the current tables: 1.1-7.3 min at year 8, 52 of 54). Note for the orchestrator: the form
change moved the top of the range by 2.5x, which is the strongest evidence for B1(iv).

## B4 the identity test and `ordering_violations`

**Read:** `tests/test_cm_sweep.py:289-303`. The assertions are (a) share_comparator_searches_more
== 1.0 (scd > 0 in the one replication), (b) 0 < c* < 60, (c) gain - 0.5 c* per_min > 0 >
gain - 2 c* per_min. With c* = gain / per_min, (c) reduces to gain > 0 (median versions aside). So
the test asserts gain > 0 and scd > 0: exactly the identity of B1(i). It cannot fail on any
downward-sloping demand law unless the scorer has a sign error. The docstring's "both signs occur
on the same price paths" is true for c on either side of c*, which is guaranteed once c* > 0.
The name says the welfare ordering is not an identity; what it verifies is that the ordering AT
A GIVEN c is decided by c, which is the identity. **Name wrong, assertion fine as a sign guard.**

**Probe:** `rb1_tracked.out` B4 section: `ordering_violations(raw, "mean_zone", "peak_zone")` on
the tracked sweep returns 12 rep-years (12 for mean_band/peak_band), all the revenue half, all in
one cell (e = -0.7, start 0.9, tau 0.3, sigma 0), peak prices $4.44-5.02 against the exponential
revenue peak p0/|e| = $2.86. The docstring (cm_sweep.py:385-386) conditions the revenue half on
"|elasticity| < 1"; under the exponential form the elasticity at $4.44 is 0.7 x 4.44 / 2 = 1.55,
so the stated condition is not met there and the docstring is literally right. CLAUDE.md:174-175
("`ordering_violations` documents that identity") and
`test_old_comparator_ordering_is_an_identity_on_priced_metrics` (a 3-year sweep at e = -0.4 that
cannot reach $5) present an empty frame as the norm on the tracked sweep, which it is not.
**Verdict: SURVIVES, narrowed:** rename/redocument the test (it guards the sign of gain and scd);
state the revenue condition as "elasticity at the prices reached, e p / p_ref, below 1 in
magnitude", which the tracked sweep violates in 12 rep-years per pair (0.03%). **Severity: Advisory.**
Contradicts: CLAUDE.md:174-175 ("documents that identity" with no condition), cm_sweep.py:382-388
(the condition is on the anchor elasticity as read), test name at test_cm_sweep.py:289.

## B1(ii) c*'s size is the search-cost shape's

**Probes:** `RB/rb3_replica.py` (one replication, 54 cells, 8 years; validated: replication 0 of the
tracked parquet reproduced to 0 on welfare_change, cs_change, revenue, search_cost;
`rb3_replica_default.out`), `RB/rb4_fullblock_units.out`, cell tables `rb3_cells_*_default.csv`.
- 92% (median over cells; 54-108%) of the search-cost DIFFERENCE between the mean and the peak rule
  comes from block-hours at 100% occupancy (the mean rule leaves 33% of priced block-hours full,
  the peak rule 0.4%). So c* is set by what a full block costs, and that is `occupancy_cap`:
  at cap 0.99 a full 10-space block costs 31.7 min when the reference (95%) costs 5, i.e. 6.34x;
  at cap 0.95 it costs 5.0 (1x); at cap 0.999, 333 min (67x). c* at the reference: 1.90 / 9.51 /
  0.21 min (medians, caps 0.99 / 0.95 / 0.999), a 45x range from one unsourced number whose only
  documentation is "a full block costs a finite search; above this drivers give up"
  (pricing_rules.yaml:49). Reproduces the probe's 1.9 -> 10.2 (mine 9.5 on one replication).
- Re-expressed as minutes of search AT A FULL BLOCK (c* x the cap's multiplier), c* is stable:
  medians 12.1 / 9.5 / 13.8, minima 6.6 / 4.3 / 6.7, maxima 28.3 / 28.8 / 27.7 across the three
  caps (mean_band pair: 11.6 / 9.3 / 13.1). The robust quantity is the full-block cost at which the
  rules tie, roughly 10-14 min median, 4-8 min at the low cells, 26-32 at the high ones.
- Consequence for the config level: 5 min at 95% implies 31.7 min at a full block, above the
  3.5-14 min averages the config itself cites from Shoup (pricing_rules.yaml:38-40). At a
  full-block cost of 14 min the peak rule is better in 39 of 54 cells, at 8 min in 1-6, at 3.5 min
  in 0 (rb4). The tracked "peak better in 52 of 54 cells" (`cm_sweep_window_dependence.csv`,
  cells_welfare_better = 2) is therefore the statement that a full block costs 32 minutes.
- The zone-pool (26-33 min) and linear-proxy (55 min) variants in the candidate were not re-run; they
  are consistent with the mechanism above (pooling to the zone aggregate removes the full
  block-hours that carry 92% of the gap, so the gap shrinks and c* rises) and the zone pool is the
  project's own cruising model in the scenario pipeline (CLAUDE.md Arnott-Inci section).

**Benign readings tried.** (a) "The shape is a stated assumption and the level is what is varied"
(targeting_welfare.py:12-15, 17-18; CLAUDE.md:178-181). Holds only in form: the level is the one
parameter that does NOT decide the comparison (welfare is linear in it, so it cancels out of c*),
while the cap, which does, is neither varied nor flagged, and the result is quoted in a unit
(minutes at 95% on 10 spaces) that hides the 6.34x premium on the full block-hours that carry the
gap. (b) "Cap 0.95 is unfair because it flattens the cost above the reference". Partly: cap 0.95
removes the convexity the docstring argues for (targeting_welfare.py:14-16), so it is a bracket,
not a replacement; but cap 0.999 is the opposite bracket and gives the same full-block c*, which is
the point: in the reported unit the number is the cap's, in full-block units it is not.
(c) The config comment pricing_rules.yaml:40-41 says the sweep varies the level through
`config/scenarios.yaml cruising_minutes_at_reference`; no such key exists (grep output in the
transcript); the design reports c* instead. Stale comment.

**Verdict: SURVIVES.** Correct statement: "c* at the 95% reference is 1-4 min under cap 0.99; the
gap is carried by full block-hours, so the robust statement is the full-block search cost at which
the rules tie, about 10-14 min (one replication; range 4-32 across cells); the config's 5 min at
95% means 32 min at a full block, above the cited Shoup range, so 'peak better in 52 of 54 at the
config level' is not supported in the range the config cites." **Severity: Material**, bordering
Blocking for the 52-of-54 statement wherever it is presented as a conclusion (it is in the memory
file as 46/54 and in the window_dependence table; not in README or CLAUDE.md prose). Contradicts:
CLAUDE.md:176-181 (the level "is set by minutes_at_reference", the breakeven quoted at 95%),
pricing_rules.yaml:35-49 (comment and cap), targeting_welfare.py:10-18 (the reference as the level),
README:93-95, plan section 1 item 2 (the "1 to 3 minutes at 95%" unit).

## B1(iii) surplus on latent demand, search cost on served arrivals

**Probe:** `rb3_replica_default.out` columns c_cs_served (CS = -int min(q, cap) dp, efficient
rationing, closed form; equal to the latent formula wherever d0 <= 1) and c_sc_latent_arr (search
cost with arrivals = latent demand).
- mean_zone vs peak_zone, year 8, rep 0: c* tracked 1.90 (1.04-4.46); served CS 1.66 (0.85-2.56);
  latent arrivals 1.44 (0.86-2.51). The high-dispersion / high-demand cells move most (start 0.9,
  tau 0.6: 2.64 -> 1.73). Reproduces the probe's 0.85-2.8 vs 1.1-6.0 (2 reps).
- Mechanism (read): on a block-hour with q > cap under both rules, raising the price from p_m to
  p_p costs the latent integral int_{p_m}^{p_p} q dp of surplus but only cap (p_p - p_m) of
  revenue is transferred; the difference int (q - cap) dp is the willingness-to-pay of parkers
  who were never served at either price. The docstring's defence (targeting_welfare.py:21-22,
  "parkers who want a space at p and cannot find one pay the search cost instead") would hold if
  those parkers appeared in the search-cost term, but arrivals there are the SERVED cars
  (targeting_welfare.py:91, `o * k / mean_duration`): the unserved parkers earn surplus in one
  term and pay nothing in the other. Either consistent treatment (served CS, or latent arrivals)
  lowers c* and halves the top of the range. `test_cs_change_uses_demand_not_capacity_clipped_occupancy`
  asserts the latent design as intended.
- The "40% of cs_diff credited to block-hours with d0 > 1" attribution is not a valid variant
  (dropping those block-hours' CS while keeping their revenue goes negative); the served-CS variant
  is the right correction.

**Benign reading tried:** latent CS is the right object if rationing is by search (everyone who
wants a space eventually gets one after cruising). Then the search-cost term must count the
latent arrivals, which it does not; and under that story a full block would admit unlimited
arrivals, which the capped occupancy denies. The two terms model two different populations.
**Verdict: SURVIVES.** Correct statement: the welfare object is internally inconsistent under
rationing; under either consistent choice c* is 15-45% lower at the median and about half at the
top of the range (1.7-1.8 min medians, max 2.5-2.9). No headline flip (1-3 min stays).
**Severity: Material** (undefended welfare object; moves the quoted range top). Contradicts:
targeting_welfare.py:19-22 docstring (the rationale), CLAUDE.md:175-176 ("on demand, not clipped
occupancy"), plan section 1 item 2's "3 to 7 at high dispersion" (also stale per B2).

## B1(iv) the demand form extrapolates

**Probes:** `rb1_tracked.out` (iv) section, `rb3_replica_default.out` (iv) lines, `rb2_old_sweep.out`.
- At e = -0.7 the peak rules' mean priced-hour price exceeds the exponential revenue peak
  p0/|e| = $2.86 in 77% of rep-years (year-8 median $4.12; the candidate's 88% is presumably per
  zone); per zone at year 8 (rep 0), 16 of 18 e = -0.7 cells have zones above it (4.8 of 5 on
  average), 10 of 18 at e = -0.4. At $4.80 the law's elasticity is 2.4e; at the $6-8 ceilings
  3-4e. Nothing in the fixture anchors demand there.
- Effect on c*: the two tracked sweeps (55be807 constant elasticity, f779618 exponential) share
  seed, replications and every other config hash, so they are a 100-replication form comparison:
  the year-8 cell-median c* (mean_zone pair) median moved 1.90 -> 2.06 but the maximum 18.5 -> 7.3
  (e = -0.2, start 0.9, tau 0.6), the high-dispersion column 2.18/3.34/7.14 -> 2.66/3.03/3.63.
  The 2-replication year-3 probe (0.7 min max) understates this because it sits away from the
  corner. welfare_diff in dollars moves up to 3.6x where it is small (p08_form_cmp: -464k vs -95k).

**Benign reading tried:** the form is a stated, selectable assumption (elasticity_priors.yaml
comment; response.py docstring) and the sweep records it in its meta.json. Holds for the median;
the top of the quoted range is the form's. Extrapolation of a local elasticity to 2.4-4x the
anchor price is a property of any sweep that lets a +$0.50 rule run 8 years from $2, and is not
documented in the sweep's own docstring or CLAUDE.md's sweep section (which lists the within-day
shape, the search-cost parameters and the fixture's zones as the limits, not the law's reach).
**Verdict: NARROWED.** Correct statement: "c*'s median is robust to the demand form (1.9 vs 2.1
min at 100 replications); its range top is not (7.3 vs 18.5); the peak rules price 2-4x above the
anchor at which the elasticity is a prior." **Severity: Advisory** (add to the stated limits; do
not quote the range top as a result). Contradicts: CLAUDE.md:196-199 (the list of the sweep's
limits), cm_sweep.py:14-18.

## B1(v) zones.yaml floors and ceilings bind

**Probes:** `rb3_replica_default.out` (v) lines and `rb3_replica_nobounds.out` (same replication
under `RB/cfg_nobounds/`: floors 0.01, ceilings 100; PHILLYPARKING_CONFIG_DIR).
- Year 8, rep 0, mean_zone pair: the mean rule has every zone at its floor in 9 of 54 cells (all
  start 0.60) and some zone in 17; the peak rule has at least one zone at its ceiling in 37 of 54
  (2-3 zones in 36: fishtown and south_philly at $4, ucity at $6); some bound binds on one side in
  48 of 54 cells. The candidate's "17 cells" undercounts ceilings.
- Without bounds, c* median 1.90 -> 1.90 (mean_band 1.82 -> 1.92), min 1.04 -> 0.75, max
  4.46 -> 4.65; by cell the start-0.60 row falls 1.55/1.50/2.11 -> 1.17/1.37/1.99 (the mean rule
  cuts below $1 instead of stopping), the rest moves < 0.2. A floor is unavoidable at e = -0.2
  (the mean rule would otherwise cut to a negative price: 6 cells hit even the $0.01 floor).

**Benign reading tried:** the bounds are a documented part of every rule (targeting_rules.py:23-24,
"every rule applies the zone's zones.yaml floor and ceiling") and are the City's own rate bounds,
which a real rule would honour. Holds. The sweep's docstring and CLAUDE.md's sweep section do not
say the bounds bind in most cells, and the paired tables do not flag bound-set cells.
**Verdict: NARROWED.** Correct statement: "Philadelphia's zone bounds bind on the peak rule in
about two thirds of cells and on the mean rule at start 0.60; c* is insensitive to them except at
start 0.60, where it falls by about a quarter without a floor." **Severity: Advisory** (state it;
flag bound-set cells in `cell_table`). Contradicts: nothing stated; an omission in cm_sweep.py:38-40
and CLAUDE.md:184-191.

## B3 the observation-noise axis is a one-sided bias axis

**Read:** cm_sweep.py:27-29 ("Noise biases a peak statistic upward and leaves a mean almost
unchanged"), `test_observation_noise_biases_the_peak_statistic_not_the_mean` (test_cm_sweep.py:235-246),
scenarios.yaml comment ("sd of the occupancy the rule reviews"). The null-control probe
(dim3/probe_c_null_control.out: flat panel, sigma 0 ties exactly, sigma 0.1 gives the peak rule a
$0.6-1.2M/yr loss and a 20-33 min breakeven) demonstrates exactly the property the docstring
states and the test asserts. On the tracked sweep the bias barely moves c*: year-8 cell-median
breakeven at sigma 0 vs 0.1 is 1.93 vs 1.89 (e = -0.7), 1.98 vs 1.94 (-0.4), 2.19 vs 2.52 (-0.2)
(`rb1_tracked.out` B2 section), because on the fixture's non-flat panel the q95-mean gap is real
and the noise adds 1.645 sigma to it, not a gap from nothing. A q95 of observed occupancy is what
a peak-targeting agency would actually compute, so the bias is part of the rule's performance,
which is the axis's stated purpose.
**Verdict: REFUTED as a finding** (restates a disclosed, tested property). Advisory remainder: 26
of the 52 "peak better" cells are sigma = 0.1 cells, and any count over the 54 cells pools 27
noise cells with 27 clean ones; the axis would be better described as "measurement bias of the
peak statistic" than "noise", and a sigma = 0 subtotal belongs next to any cell count.

## Extra (found on the way, Advisory)

- pricing_rules.yaml:40-41 names a `cruising_minutes_at_reference` axis in scenarios.yaml that does
  not exist (the design reports c* instead of varying the level). Stale comment.
- `rb1_tracked.out`: the seattle_rule vs peak_band pair has 63 rep-years with breakeven <= 0 and
  126 where the Seattle rule prices higher; the paired table's `comparator_searches_more` handles
  it, but the "the higher-priced rule gives more welfare above c*" reading is only safe for the
  two same-instrument pairs.

## Summary of verdicts

| Claim | Verdict | Severity proposed | What must change in the statement |
|---|---|---|---|
| B1(i) c* > 0 is a theorem | SURVIVES (narrowed) | Material | Say c* is positive by construction (verified 43,200 rep-years per pair, including the 12 beyond the revenue peak); the sweep's content is c*'s size only |
| B1(ii) c* is the shape's | SURVIVES | Material (Blocking for "52 of 54 at the config level") | 92% of the gap is full block-hours; the cap sets c* (0.2 / 1.9 / 9.5 min at caps 0.999 / 0.99 / 0.95); report c* in full-block minutes (10-14 median, stable); the config's 5 min at 95% is 32 min at a full block, above the Shoup range the config cites; at 14 min the peak rule wins 39/54, at 8 min 1-6 |
| B1(iii) latent CS vs served search | SURVIVES | Material | The two terms count different populations; either consistent fix lowers c* 15-45% at the median, halves the range top (max 2.6-2.9) |
| B1(iv) form extrapolation | NARROWED | Advisory | Median robust (1.90 vs 2.06 at 100 reps across forms); range top not (7.3 vs 18.5); peak rules price at 2-4x the anchor; add to stated limits |
| B1(v) bounds bind | NARROWED | Advisory | Bounds are a documented part of the rules; they bind in 48/54 cells but move c* < 0.2 except at start 0.60 (-25%); state and flag |
| B2 19 min / 3-7 / 46 of 54 | SURVIVES (narrowed to plan, draft report, memory) | Advisory | Exactly the pre-PR-#12 sweep (55be807); current tables: max 7.33 at year 8 (8.84 any year), 52 of 54; fix review_plan:41-42, audit_2026-10-16.md:27, memory |
| B3 noise axis one-sided | REFUTED | (Advisory note) | Disclosed and tested property; on the fixture it moves c* by < 0.4 min; label the axis as measurement bias and give sigma = 0 subtotals |
| B4 identity test / ordering_violations | SURVIVES (narrowed) | Advisory | Test asserts gain > 0 and scd > 0 (the identity); rename; state the revenue condition as the elasticity at the prices reached; 12 violating rep-years per pair in the tracked sweep (e = -0.7, $4.4-5.0) |

Probes and outputs: `rb1_tracked.py/.out`, `rb2_old_sweep.out` (+ `old_paired_55be807.csv`),
`rb3_replica.py`, `rb3_replica_default.out`, `rb3_replica_nobounds.out`, `rb3_cells_*.csv`,
`rb3_rows_*.parquet`, `rb4_fullblock_units.out`, `cfg_nobounds/`. No full sweep was run (one
replication, 54 cells, 8 years, twice).
