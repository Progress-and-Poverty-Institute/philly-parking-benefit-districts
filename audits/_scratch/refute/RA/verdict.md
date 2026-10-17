# Refuter RA verdict (scenario pipeline: A1, A2, A3) — 2026-10-16

Posture: independent refuter. Read only GROUND_RULES, review_plan §1, CLAUDE.md, config/*.yaml, the
source, the named probe scripts and their saved outputs under RA/ (reused, not rerun). No findings.md read.
New probes (all cheap, saved panels only): RA/ra_zone_shares.py, ra_fixture_caps.py, ra_sweep_ratio.py,
ra_mix.py, ra_searchbins.py (earlier attempt), and one scratch-config rerun of the two reforms under the
white paper's floors (RA/cfg_report_floors, output a_floors_report_floors.out).

## A1(i) — outer zones cannot cross 0.85 under any level setting; kernel mix is the cause

Reproduction (reused): b_levels.out grid (offpeak 0.20, low_demand_peak 0.62..0.90 x peak_target 0.92/0.99):
highest outer-zone busiest priced hour = ucity 0.782 at 0.90/0.99; CCC crosses at 0.85/0.99 (0.857).
b2_offpeak.out at offpeak 0.60 / 0.85 / 0.99: cca 0.839, fishtown 0.826, south_philly 0.797, ucity 0.850.
ra_mix.out exact: ucity 0.8502 at that corner -> Arnott RAISE (marginally). So the quantifier "no setting
up to 0.99/0.85/0.60" is false at its own corner for ucity, by 0.0002.

Benign readings tried:
1. "The probes held the mix fixed while moving the levels." TRUE: probe_b_levels.py and probe_b2_offpeak.py
   pass only peak_target / low_demand_peak / offpeak_floor; mix_temperature stays at the stated 2.5.
   ra_mix.out varies it: at T=0 (uniform mix, every segment peaks at the same hour) the aligned-peak upper
   bound equals the capacity-weighted mean segment peak, 0.71-0.77 at the default levels (still < 0.85 for
   every zone, CCC 0.824) and 0.89-0.95 at 0.85/0.99 (every zone > 0.85 -> every zone RAISES). At T=1.0 and
   0.85/0.99: cca 0.839, ucity 0.820, still cut. Removing residential from the mix ("no residential") at
   0.85/0.99/0.60: cca 0.857, fishtown 0.826, ucity 0.838 -> cca crosses. So the claim is conditional on the
   stated mix constants, not only on the three levels.
2. "The cause is the mix." HALF: at the DEFAULT levels even perfectly aligned peaks give 0.71-0.77, so the
   binding constraint there is the intensity anchoring (outer zones' capacity-weighted lambda_norm is only
   0.29-0.49, ra_mix.out line 1), not the kernel mix. The mix (residential kernel peaking at 8am vs retail
   13:00) is what keeps the outer zones under 0.85 only once the levels are pushed to 0.85/0.99.
3. Residential share: b2_offpeak.out gives 0.426 / 0.551 / 0.509 / 0.341 (cca / fishtown / south_philly /
   ucity). "43-55%" excludes ucity; correct to 34-55%.

What survives: with the stated mix (T 2.5, weights 1.0/1.2/0.9), no combination of the three levels in the
probed range moves cca, fishtown or south_philly above 0.85 at the busiest priced hour, and ucity only at
the extreme corner by 0.0002; the Seattle band means stay below 0.70 in every outer zone at every setting
(b_levels.out "seattle ---"). "Both rules cut" outside CCC is therefore entailed by config/demand_baseline.yaml
(levels + anchors + mix), not by anything in the segment data beyond the covariate ranking. Every sign in
comparison_table.csv then follows: both reforms are net price cuts, |e| < 1, so revenue falls, CS rises,
DWL rises.

VERDICT: NARROWED. Wording: "at the stated mix_temperature and mix weights, no setting of the three levels
up to 0.99 / 0.85 / 0.60 brings cca, fishtown or south_philly above 0.85 (ucity reaches 0.8502 at the
corner); at the default levels the aligned-peak upper bound is already 0.71-0.77, so the intensity anchors
bind first and the kernel mix only at elevated levels; a mix temperature of 0 or dropping the residential
kernel does let outer zones cross at 0.85/0.99." Severity proposed: Material (sharpens prior finding 1: the
cut signs are a property of the baseline constructor; CLAUDE.md names only the levels as what the signs
rest on, demand_baseline.yaml "Occupancy levels (unsourced calibration assumptions...)", and never the
mix / anchor constants). Contradicts: review_plan §1's reading that the pipeline delivers "the structure
of the trade-offs": the direction of both reforms outside CCC is an input, not a result. Nothing in src/
or config/ states otherwise, so no code-doc line is contradicted.

Is "structure" defensible at all? Partly. What is NOT entailed by the inputs: CCC's level under each rule
(Seattle holds the 12-16 band at $3.50 because 0.70 <= band occ, cuts 8-12 to $2.00 and 16-20 to $1.50;
Arnott goes to the $2.75 fixed point where the busiest hour sits at 0.8498, meta.json final_prices), the
5-year convergence, no two-cycle at the central elasticity. That is rule mechanics on one zone. See A3 for
whether any ordering between the reforms is structure.

## A1(iii) — CCC's rate is the only rule-decided number and spans $1.00-2.86 across peak statistics

Reproduction (reused): p03_stat.out, one-step clipped CCC price: mean $1.00 (floor), q75 $1.571, q90
$2.672, q95 $2.855, max $2.855 (tracked fixed point $2.751). Four of five zones sit at a floor under every
statistic (five under the mean). ra_zone_shares.out: share of priced block-hours at the zone floor is 1.0
in cca, ucity, fishtown, south_philly under BOTH reforms and 0.0 in ccc.

Benign reading: the statistic choice is documented and argued (CLAUDE.md "Peak statistic: the zone's
busiest priced hour..." with four reasons and the note that it moved the full-PBD row's sign, audit
2026-10-14 finding 3). It holds: this is a known, stated sensitivity, not an unstated one. Correction to
the wording: Seattle's CCC bands ($2.00 / $3.50 / $1.50) are rule-decided too, so "the only rule-decided
number" should read "CCC is the only zone whose rates under either reform are not a floor". What is new:
scenario_ranges.csv's "range" varies elasticity only (and the seed, degenerate); the one axis the project
itself documents as sign-moving is absent from every range artifact.

VERDICT: NARROWED to "documented in CLAUDE.md, absent from the range artifacts". Severity: Advisory.
Contradicts: no stated conclusion; bears on how scenario_ranges.csv may be read.

## A1(ii) — the zone floors bind in four zones under both reforms; two-thirds of every dollar row sits where both reforms post the same price; the revenue ordering reverses without floors

Reproduction:
- a_floors_part1.out (reused), e = -0.4: unclipped one-step Arnott prices cca 0.747, ucity 0.588,
  fishtown 0.147, south_philly -0.215 against floors 1.00 / 1.00 / 0.50 / 0.50 (zones.yaml). Matches the
  claim. At e = -0.2 all four are negative; at e = -0.7 only south_philly (0.520) and fishtown (0.727)
  clear their $0.50 floor.
- RA/ra_zone_shares.out (new): both reforms post the identical price in 100% of priced block-hours in
  cca, ucity, fishtown, south_philly (all at the floor); share of each row in those four zones: revenue
  change 0.679 (Seattle) / 0.751 (full PBD), proxy DWL 0.660 / 0.691, CS 0.668 / 0.728. The claim's
  "68-75% / 66-69% / 67%" is right (CS is 67-73%). The entire difference between the reforms is CCC:
  d_rev +$6.24M, DWL -$0.18M, CS -$7.31M (full PBD minus Seattle).
- a_floors_nofloor_rerun.out (reused; floors 0.01): Seattle $60.0M > full PBD $53.2M (tracked: $75.7M <
  $82.0M). Reproduces. Mechanism: without a floor the Arnott step drives cca to $0.08 and ucity to $0.01
  (the target is unattainable, see below) while the Seattle dead band stops cca at $0.67 and ucity at
  $0.17 once a band's occupancy enters [0.70, 0.85].
- RA/a_floors_report_floors.out (NEW, scratch config RA/cfg_report_floors with the white paper's floors,
  Report.tex:238-242: ccc 2.00, cca 1.50, ucity 1.00, south_philly 1.00, fishtown 1.00; saved status-quo
  panel, e = -0.4): Seattle $91.2M, full PBD $94.8M; CCC $2.50 (bands 2.0 / 3.5 / 2.0) vs $2.751; all
  four outer zones at the (higher) floor under both. The ordering does NOT reverse: full PBD still earns
  more. That half of the claim is refuted.

Benign readings tried:
1. "Floors are a legitimate policy constraint and their binding is the finding." Largely holds: no
   authority posts a $0.08 meter, and "the rules would go below any plausible floor in four of five
   zones" is a result worth stating. But three things stop it from being benign as the pipeline stands:
   (a) the floors are unsourced (zones.yaml carries no citation for floor / ceiling; the file header
   cites research doc 4.3 for the rate structure only) and the project carries a second, different
   floor set in Report.tex:238-242 (and different posted rates for ucity / south_philly / fishtown);
   (b) the binding is invisible in the outputs: compare.py:18-26 counts n_zones_at_ceiling (0 in every
   column of comparison_table.csv) and nothing counts zones at the floor, though 4 of 5 are there under
   both reforms; the runner's final_prices carry peak_occ but no "target unattainable" flag;
   (c) because the four zones tie by construction, every between-reform difference in the table is CCC
   alone, and that is stated nowhere.
2. "The negative Arnott price is a code defect." REFUTED. price_for_demand_ratio under the exponential law
   is p_ref + p_ref ln(ratio) / e; for south_philly ratio = 0.85 / 0.538, giving -0.215: the law says the
   busiest hour reaches only 0.803 at a zero price (a_floors_part1 occ_at_zero_price), so no non-negative
   price attains the target and the exact solution is negative. np.clip(p, floor, ceiling) at
   runner.py:193 is the right handling. It is a slack target, not a bug; the defect is only that the
   slack is not reported.
3. "The ordering reverses with the Report's floors." REFUTED by the rerun above (94.8 > 91.2).

VERDICT: SURVIVES, narrowed. Keep: floors bind in four zones under both reforms at the central and
optimistic elasticities; 66-75% of every dollar row and 100% of the between-reform tie sits there;
without floors the revenue ordering reverses because a dead-band rule stops inside the band and a
target rule with an unattainable target does not. Drop: "reverses with the Report's floors" (it does not)
and any suggestion the negative price is a code defect. Add: the floors are unsourced and inconsistent
with Report.tex, and the comparison table reports ceiling binding but not floor binding. Severity
proposed: Material (undefended / unreported assumption deciding the reform comparison; no headline
sign flips because every row is a cut either way). Contradicts: compare.py:18-26 / comparison_table.csv
n_zones_at_ceiling as the only bound indicator (reads as "no bound binds"); review_plan section 1's
"structure of the trade-offs" insofar as the reform ordering is read as structure.

## A2 — two incompatible cruising-cost models; the surplus row is not commensurable with a net reading

Reproduction:
- f_welfare.out (reused): on the saved Seattle panel, proxy DWL $4.03M vs the sweep's o^K shape $107.8M
  (cap 0.95: $30.3M; latent arrivals: $112.6M); dCS $87.9M = transfer $77.3M + triangle $10.6M; net
  dCS + dRev - d(cruising) = +$19.2M (proxy) / -$80.6M (o^K) / -$3.1M (o^K, cap 0.95).
- RA/ra_searchbins.out (earlier attempt): 77% of the $107.8M comes from block-hours at >= 0.99; with K =
  10 for every block (the sweep's reference block) it is $79.2M; blocks of 1-3 spaces contribute $6.0M
  at 173 minutes of search per arrival when full.
- RA/ra_sweep_ratio.out (NEW): the tracked sweep itself carries both models per row (cm_sweep.parquet
  columns search_cost and cruising_dwl, the latter "the project's proxy, for continuity",
  cm_sweep.py:44). Final-year median search / proxy ratio = 28.6 (p10-p90 22.8-31.6), 25-30x in every
  start-occupancy x rule cell. So the 25x gap on the real panel is the two models' built-in level
  ratio at the stated 5 minutes at reference, not an artefact of real blocks or of the 1.0 clip.
- RA/ra_fixture_caps.out (NEW): fixture blocks have 4-15 spaces (mean 8.8, none <= 3); real priced
  blocks: 8.2% have <= 3 spaces, 0.4% zero. The shape's absurd tail (173-330 min) is reached only on
  real segments, but it carries $6M of the $108M, so it does not drive the comparison.

Benign readings tried:
1. "The sweep's shape is not meant for the scenario panel." Holds as a statement of intent
   (targeting_welfare.py docstring; CLAUDE.md "cs_change_total ... no search-time term"), and both
   are block-hour objects, so the application is apples to apples except for K. But intent does not
   reconcile them: the same project reports cruising at $4M in one table and would report ~$80-108M on
   the same panel with its other stated model, and the sweep's own output shows the 28x ratio on the
   fixture. The proxy measures target violation above 0.85 (a rule statistic valued at 5 min per excess
   car); o^K measures search at any occupancy. They are different quantities under one label
   ("cruising"). That is an unstated, undefended inconsistency, not a code defect.
2. "10.2% of block-hours at >= 0.99 is a clip artefact." REFUTED: those are block-hours whose latent
   demand under the law exceeds capacity (share latent > 1 = 9.1%, f_welfare.out), the regime the sweep
   also exercises (start occupancy 0.90 cells; its share_block_hours_above_high reaches 0.6). The
   question is how to cost a full block, which both models answer by assumption (proxy: 0.15 x K excess
   cars x 5 min; o^K: cap 0.99).
3. "88% transfer is the standard decomposition." Holds. For a price cut the CS integral is always mostly
   the rectangle (p_ref - p) q_ref; it cancels against the revenue row in any net, and no artifact
   presents CS alone as a welfare gain (runner.py _annual_cs_change docstring: "not a welfare total";
   CLAUDE.md "no search-time term"). Not a defect.
4. "Does any artifact invite a net reading?" None states one. But viz/tables.py ROWS puts revenue,
   cruising DWL and consumer surplus change in one table with no scale note, its CS label "(annual,
   first order)" is stale (the row is now the exact integral, runner.py _annual_cs_change), and
   README.md:93 defines the sweep's welfare as "consumer surplus + revenue - search cost", i.e. the
   formula a reader would apply to those three rows. The sign of that net depends on which of the
   project's two cruising levels is used (+$19M vs -$81M).
5. "Is $108M a fair application?" Partly. The number is dominated by the 0.99 cap (77%) and the level
   parameter; a fair statement is $30M (cap 0.95) to $108M, all 7-27x the proxy, and ~$80M with
   fixture-like blocks.

VERDICT: NARROWED. From "incommensurable surplus row" to: "the project states two cruising-cost
models 25-30x apart at its own parameters (verified in its own cm_sweep.parquet), reports the scenario
DWL row on the low one without saying so, and gives the reader the net-welfare formula (README:93) while
the scenario table carries the three rows unreconciled; the sign of a net reading depends on which
model is applied." Drop the transfer-share point as a defect (keep it as a note that CS alone is not a
gain) and the clip-artefact reading. Severity proposed: Material (undefended inconsistency between two
stated assumptions; no stated conclusion flips because no net is stated). Contradicts: no stated
conclusion; the unstated premise is that "cruising DWL" in comparison_table.csv and "search cost" in
cm_sweep_paired.csv are on comparable scales.

## A3 — the reform comparison is not robust within the project's own ranges; the seed range is degenerate

Reproduction (tracked file, no run): outputs/tables/scenario_ranges.csv. Revenue: Seattle vs full PBD =
58.5 > 55.2 (optimistic, e = -0.2), 75.7 < 82.0 (central), 103.8 < 107.5 (pessimistic). The same flip
appears in every row: DWL 1.73 < 1.99 / 4.03 > 3.85 / 6.05 > 5.52; CS 94.4 < 98.5 / 87.9 > 80.6 /
70.8 > 64.1. So no ordering between the two reforms on any outcome survives the project's own elasticity
range; the mechanism is CCC only (A1 ii): a target rule's cut depth scales with 1/|e| (one-step CCC price
4 + 4 ln(0.85/0.758)/e: $1.71 at -0.2, $2.86 at -0.4), a dead-band rule's with the band.

Benign readings tried:
1. "No artifact claims the ordering." HOLDS for everything in scope: CLAUDE.md:345 says only that the
   pessimistic elasticity gives the highest revenue "because both reforms are net price cuts" (true);
   viz/tables.py emits the table without a ranking; app/streamlit_app.py has no comparison text;
   README's scenario table is the stale 120-segment fixture (out of scope). The flip is a fact about
   the range table, not a contradiction of a stated conclusion. It bears on review_plan section 1 only
   if "structure" is read to include which reform does better: it cannot be.
2. "The degenerate seed column is a defect." REFUTED. scripts/05_run_scenarios.py:157-163 sets n_seeds
   to 0 on loaded segments with a logged warning and a correct reason (the baseline is deterministic in
   the covariates; baseline_occupancy's rng only adds 1e-9 to occupancy_sd; the CS term is an
   integral); ranges.py:65-68 then writes seed_lo = seed_p50 = seed_hi = headline and n_seeds = 1,
   which marks the column as one point. A reader who ignores n_seeds could misread equal lo / hi as
   "robust to seed", so the column is a presentation hazard at most.

VERDICT: NARROWED to Advisory: "every between-reform ordering in comparison_table.csv (revenue, DWL,
CS) reverses at the optimistic elasticity in scenario_ranges.csv; no in-scope artifact claims an
ordering, and comparison_table.csv carries no pointer to the range." Seed column: refuted as a defect
(deliberate, logged, marked n_seeds = 1). Contradicts: no stated conclusion.

## Refuted list
- A1(ii) part: "the revenue ordering reverses with the Report's floors" (RA/a_floors_report_floors.out:
  Seattle $91.2M < full PBD $94.8M).
- A1(ii) part: the negative unclipped Arnott price as a code defect (exact solution of an unattainable
  target under the stated law; clipped at runner.py:193).
- A2 part: "10.2% of block-hours at >= 0.99 is an artefact of the 1.0 clip" (it is latent demand above
  capacity, 9.1%, the regime the sweep also runs).
- A2 part: "88% transfer" as a defect (standard CS decomposition; nothing presents CS as a net gain).
- A3 part: the degenerate seed range as a defect (deliberate, logged, marked).
- A1(i) quantifier as stated (ucity reaches 0.8502 at the corner; mix constants, not only levels, carry it).

## Severity summary
- A1(i) NARROWED, Material: cut signs outside CCC are entailed by demand_baseline.yaml (levels + anchors
  + mix); CLAUDE.md attributes the dependence to the levels only.
- A1(ii) SURVIVES narrowed, Material: floors unsourced, inconsistent with Report.tex, binding unreported
  (ceiling count only), and they decide the between-reform ordering (reverses with no floors; not with
  the Report's).
- A1(iii) NARROWED, Advisory: statistic sensitivity ($1.00-2.86 one-step) is documented in CLAUDE.md but
  absent from scenario_ranges.csv.
- A2 NARROWED, Material: two cruising models 25-30x apart at the project's own parameters (its own
  sweep output shows it); scenario DWL row on the low one, unlabelled; net-welfare formula supplied by
  README for the sweep.
- A3 NARROWED, Advisory: every reform ordering flips at e = -0.2; nothing claims one; seed column fine.
