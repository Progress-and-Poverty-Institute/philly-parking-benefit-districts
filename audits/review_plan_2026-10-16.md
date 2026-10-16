# Second methods review: plan (2026-10-16)

This is the plan for the second adversarial audit of the model, following the
`analysis-audit` skill, after the code work from the first audit (`audit_2026-10-14.md`) was
merged (pull requests #4 to #12, 2026-10-15 to 2026-10-16). It is a planning document, not the
audit: nothing below is a finding until a wave agent has verified it and a refuter has failed
to knock it down. Numbers here are hand-typed observations frozen on 2026-10-16; the audit
report carries its own frozen numbers.

**Deliverable:** one dated file, `audits/audit_2026-10-16.md`, with the skill's structure: a
scoped findings list (severity x confidence, evidence, reproduction path), a coverage statement,
a refuted-candidates section, a "since the last audit" section that says which of the 27
earlier findings are closed, changed or still open, and a ranked work list. The audit changes
nothing in the repo.

**Out of scope, by the user's instruction:** the white paper (`Report.tex`) and the Quarto draft
(`notebooks/paper/*.qmd`). Both are known to be stale and will be rewritten once after this
audit; do not file findings about their prose. Dimension 5 (reporting) is off. The same two
exceptions as before apply: factual claims in `README.md`, `CLAUDE.md` and the memory files
about what the pipeline runs on are premises to test, and a mechanism the papers name that the
code does not implement is a dimension-1 scope-drift finding.

---

## 1. The argument under review, as it now stands

The model no longer claims to forecast Philadelphia. After the first audit it claims three
narrower things, each resting on the merged pipeline:

1. **Scenario pipeline (scripts 02 to 07).** On the 3,145 real street segments that the model
   treats as metered (City centerline streets with at least half commercially zoned frontage
   inside the five zone boxes; a stand-in until the Parking Authority inventory arrives), under
   a stated weekly occupancy profile (`config/demand_baseline.yaml`: anchors from the priced
   curb's own covariate distribution, levels 0.62 to 0.92 peak that are assumptions), a
   Seattle-style per-band rule and an Arnott-Inci busiest-priced-hour rule both *cut* Center
   City rates and revenue falls ($141M status quo, $76M Seattle, $82M full PBD; consumer
   surplus +$88M / +$81M; `outputs/tables/comparison_table.csv`). The documents say these are
   conditional on the levels, not findings.
2. **Chatman-Manville sweep (`scenarios/cm_sweep.py`).** Targeting the peak statistic rather
   than the mean gives more welfare (surplus + revenue - search cost) only when cruising is
   costly enough: the breakeven is 1 to 3 minutes of search at 95% occupancy on a 10-space
   block when blocks are alike, 3 to 7 minutes at high block dispersion, up to 19 with
   inelastic demand (`outputs/tables/cm_sweep_paired.csv`, 54 cells x 100 replications).
3. **Real-data path.** Every raw layer is real and marked; the Parking Authority release can be
   ingested through `config/ppa_ingest.yaml` into a segment x period x hour panel; a rank test
   decides whether any zone's elasticity is identified before PyMC runs.

The inferential step behind 1 and 2 is now: *a stated occupancy profile on real streets, a
stated demand law (exponential, anchored at the posted rate), a stated search-cost shape and
level, pushed through pricing rules, tell us the structure of the trade-offs, not their size in
Philadelphia.* The audit's central question is whether that narrower claim is sound, and
whether any output is still presented, in code or docs, as more than that.

---

## 2. Scope decisions

| Decision | Choice | Why |
|---|---|---|
| Depth | **deep** on what changed; **standard** on what the first audit cleared and no PR touched | 76 files changed, +7,700 / -1,500 lines since the first report. Untouched modules (`revenue/allocation.py`, `pricing/priced_hours.py`, `pricing/seattle_rule.py`, `io/raw_cache.py`) are sampled, not re-enumerated. |
| Dimensions | 1, 2, 3, 4; 5 off | User instruction. |
| Canonical artifacts | `config/*.yaml`, `src/phillyparking/`, `scripts/0[1-7]*.py`, `scripts/derive_baseline_anchors.py`, `outputs/tables/*`, `outputs/figures/*`, `outputs/models/{status_quo,seattle,full_pbd}/`, `data/processed/segments.meta.json` | What the papers and app will consume. |
| Historical / non-canonical | `docs/PLAN.md`, `research/*.md` (claims to verify, not evidence), `notebooks/*.ipynb` (scaffolds; 05 and 06 call functions that no longer exist), `audits/audit_2026-10-14.md` (claims to re-verify, not settled) | File findings only where live code depends on them. |
| Prior audit | `audit_2026-10-14.md`, 27 findings. Treat every "closed by PR #n" as a claim: re-verify the four Blocking ones and the Material ones that touched the model (5 to 15, 17 to 20, 23, 24). | Prior audits are commonly wrong about what has since been closed. |
| Expensive | Fast suite 60 s (`-k "not hierarchical_bayes"`); the PyMC test alone 8 to 10 min (no C compiler). Script 02 about 30 s; 05 about 2 min with the seed range; 06 about 2 min; 07 `--rebuild-cm-sweep` about 70 min. Script 01 `--refresh` hits the network and overwrites `data/raw/`. | Agents re-run into scratch via `PHILLYPARKING_OUTPUTS_DIR` / `PHILLYPARKING_DATA_DIR`; never `--refresh`; the sweep only at small n. |
| Must not write to | `outputs/`, `data/`, `docs/`, `README.md`, `CLAUDE.md`, memory, source. Probes go to `audits/_scratch/` (gitignored). | Audit posture. |

---

## 3. What changed since the first audit (verified from the merge log)

| PR | What it did | First-audit findings it addresses |
|---|---|---|
| #4 | One priced-hours mask; Arnott busiest priced zone-hour; Seattle per-band dead band; two-cycle reporting | 3, 7, 8, 9, 10 |
| #5 | Guards: config-derived revenue hours, `meta.json` provenance, generated scenario table, app reads `outputs/models/` | 20, 21, 22, A1, A2 |
| #6 | Elasticity and seed ranges (`scenario_ranges.csv`); Act 84 waterfall; commensurable CS | 6, 11, 15 |
| #7 | One rule module; paired sweep; per-cell tables; sweep relabelled as an illustration | 13, 23 (and 4 in part) |
| #8 | Provenance markers on `data/raw/`; loader fixes; PPA ingestion stage; identification rank test; absolute anchors | 5, 17, 18, 19, 24 |
| #9 | OSM fetches bypass osmnx's response cache | (found in use, not in the audit) |
| #10 | Real segments: curb classes, commercial-frontage stand-in, `load_priced_segments`, `philadelphia` anchor set generated from the priced curb | 2 (the fixture), 24 |
| #11 | Chatman-Manville sweep redesigned as a welfare test: search cost, surplus, breakeven | 4, 13 |
| #12 | One demand law (`demand/response.py`), exponential default; CS as its integral; seed loop skipped on loaded segments | 14, 15 |

Not addressed by any PR, and still open as far as this plan knows: 1 (the occupancy levels are
still stated; the sign of the scenario results still rests on them), 12 (the x10 scale is gone
but no external number checks the new scale), 16 (the incidence figure is a labelled
placeholder), 21 in part (notebooks), 25 to 27 (paper prose, out of scope here).

---

## 4. Decision inventory: the denominator

Every item is a choice that moves an output. The audit's coverage statement reports which were
examined. Letters continue the first plan's scheme; new or changed items are marked **new**.

### A. Raw layers (`io/`, script 01)
- A1 **new**: provenance markers; unmarked files refused; synthetic only opt-in under `.synthetic` names. Guard: does the refusal fire on a marker with `kind: synthetic` under a real name?
- A2 **new**: osmnx response cache disabled during fetches (PR #9). Is the Carto / ArcGIS / Census path cached anywhere else that would mislabel a fetch time?
- A3: no public meter inventory; `fetch_meters` raises. The priced-curb stand-in (B4) is the consequence.

### B. Segments and joins (`spatial/`, script 02)
- B1: 80 m pieces of the City centerline; capacity = length / 7 m x 0.85, one curb per centerline, no deduction for intersections, hydrants beyond the 0.85, bus stops, loading zones, driveways. Total priced capacity 22,653 spaces.
- B2 **new**: classes 1, 6, 9, 10, 12, 14, 15 dropped as "no curb"; 13 and 18 kept but never priced.
- B3 **new**: `commercial_frontage_share` over a 25 m flat-ended buffer, zoning group "Commercial/Commercial Mixed-Use" only (industrial, special-purpose, institutional and mixed residential excluded).
- B4 **new**: priced curb = class 2 to 5 and frontage share >= 0.5, inside a zone box. Sensitivity recorded in PR #10: 0.1 -> 38,380 spaces, 0.25 -> 30,572, 0.5 -> 22,653, 0.75 -> 17,161. No check against any Parking Authority count.
- B5: zone boxes are rectangles; `zone_for_point` gives the smallest box; a block in no box is "other" and never priced.
- B6: join columns (`spatial/join.py` docstring): 15 m ACS buffer with share weighting, 200 m LODES, 400 m transit, 100 m POIs. 125 segments dropped for touching no block group.

### C. Zones, rates, priced hours (`config/zones.yaml`)
- C1: five boxes, posted rates, floors and ceilings, priced hours. The research note's rate table is the source; the Parking Authority's own schedule is Request B.
- C2: `priced_curb` block: `no_curb_classes`, `street_classes`, `frontage_buffer_m`, `min_commercial_share`.

### D. Baseline occupancy (`demand/synthetic_baseline.py`, `config/demand_baseline.yaml`, `scripts/derive_baseline_anchors.py`)
- D1: kernels (office, retail, residential) and the mix softmax; `mix_temperature` 2.5; `offpeak_floor` 0.20, `offpeak_span` 0.10, `low_demand_peak` 0.62, `peak_target` 0.92: all stated. The first audit's finding 1 said the reform signs are these numbers; that is still true on real segments.
- D2 **new**: anchor sets. `philadelphia` centers and scales are the mean and sd of log1p(covariate) over the priced curb, and the intensity bounds its 5th and 95th percentiles: by construction 5% of priced blocks sit at each end. The spatial pattern follows covariates; the level is D1's. Is the 5/95 construction any better founded than the fixture's?
- D3 **new**: covariate weights (0.55 jobs, 0.35 POIs, 0.25 density, -0.15 transit) unchanged from the fixture era; unsourced.
- D4: `max_clipped_share` warning only.

### E. Demand law and elasticity (`demand/response.py`, `elasticity/`, `config/elasticity_priors.yaml`)
- E1 **new**: `demand_form: exponential`; the prior is the elasticity at the posted rate; elasticity e p / p_ref; revenue peak at p_ref / |e| ($10 for Center City Core). The choice rests on Lehner and Peer's qualitative finding that higher prevailing prices are more elastic; the *rate* at which elasticity rises is the form's, not measured. Linear and constant forms selectable.
- E2 **new**: `apply_elasticity` needs `reference_price`; a zone the table does not cover may hold, never move. Every caller passes the posted rate except the sweep (start price) and `revenue_curve` (baseline price).
- E3: priors -0.2 / -0.4 / -0.7 at the posted rate; the earlier finding 26 (attribution) is a paper matter but the numbers still enter the model.
- E4: hierarchical model unchanged (log-log). Is "its estimate is the elasticity at the observed prices" right once the model that *uses* the estimate is exponential? (It is the local elasticity; the audit should check what a log-log fit returns on data generated by the exponential law across a rate change like July 2025's.)
- E5: `identification.check_identification`: rank test; period term; two changed zones without a control are unidentified.

### F. Pricing rules (`pricing/`, `scenarios/runner.py`)
- F1: Arnott step: busiest priced capacity-weighted zone-hour to 1 - target vacancy, inverted through the demand law anchored at the posted rate; zone floors and ceilings; fixed point or two-cycle.
- F2: Seattle rule: per zone x band, capacity-weighted priced-hour mean, 0.70 / 0.85 dead band, two steps at 0.95.
- F3 **new**: targeting rules for the sweep: `peak_zone`, `mean_zone`, `peak_band`, `mean_band`, `seattle_rule`; unweighted block-hours; rate in force read from priced rows.
- F4: `target_vacancy` 0.15 shared by pricer and scorer.

### G. Revenue and allocation (`revenue/`)
- G1: revenue = served cars x price over priced hours x 52; full compliance; no meterUP fees, no citations, no off-street.
- G2: Act 84 waterfall with a fixed $35M General Fund minimum (the statute escalates it) on gross meter revenue (the statute's base is net, citywide).
- G3 **new**: no external scale check replaces the old x10; the Parking Authority's reported meter revenue (Request B item 4) is the check.

### H. Welfare (`welfare/`)
- H1: cruising DWL proxy: excess over 0.85 x 5 min x $20/h, priced hours only. Still the scenarios' cruising measure.
- H2 **new**: consumer surplus = exact integral of the demand law over priced block-hours (`runner._annual_cs_change`), on the baseline panel's demand as q_ref. Under Seattle it is +$88M against $76M revenue: is a surplus gain larger than the revenue base credible, and is surplus on *all* demand (including the induced demand that then cruises) the right object when the runner's only search-time term is H1?
- H3 **new**: search cost for the sweep (`welfare/targeting_welfare.py`): a block of K spaces at occupancy o is full with probability o^K; a driver passes p / (1 - p) full blocks; level `minutes_at_reference` 5 min at 95% on 10 spaces; mean stay 1.5 h; cap 0.99; VOT $20. The sweep's result is a breakeven in the *level*, so its validity rests on the *shape*: independence of spaces, geometric search, no spatial correlation between neighbouring blocks, no balking. A refuter should attack the shape.
- H4: `welfare/consumer_surplus.py` (nested logit) is tested but no longer used by the pipeline; `pricing/optimizer.py`, `validation/*`, `demand/ml_occupancy.py`, `demand/occupancy_estimator.py`: live or dead?

### I. Scenario orchestration, the sweep, provenance (`scenarios/`, scripts 05 to 07)
- I1 **new**: `load_priced_segments` drops zone "other"; script 05 falls back to the fixture below 5 named segments; the fixture is only reached in tests now.
- I2 **new**: sweep design: fixture n=120 seed 42 ("other" dropped), start price $2 for every zone, `start_occupancy` scaling of latent demand per zone, lognormal block multiplier, yearly observation noise, 8 reviews, 100 paired replications. Within-day shape is D1's kernels. Every rule starts at $2 although posted rates differ by zone.
- I3 **new**: breakeven = (surplus diff + revenue diff) / search-cost diff per minute, per replication; medians per cell. Division by near-zero for comparisons that price alike (`peak_band` vs `peak_zone`).
- I4: ranges: elasticity scenarios at the headline seed; the seed range only on the fixture (degenerate on loaded segments: nothing depends on the seed). So no headline number on real segments carries any interval beyond the three elasticities.
- I5: provenance in `meta.json`: segment source, counts, filter, priced-curb rule, anchor set, config hashes, commit, dirty flag.

### J. Guards (`tests/`)
- J1: 337 fast tests; the PyMC parameter-recovery test. Which defects that move a headline number would no test catch? Candidates: a wrong `min_commercial_share`, a wrong anchor set silently chosen, a changed kernel, `search_cost` parameters, the $35M minimum.
- J2: `derive_baseline_anchors.py --check` and `07 --check` are on-demand, not in the suite.

### K. The real-data path (`ingest/ppa.py`, script 03b, 04)
- K1: `config/ppa_ingest.yaml` column mapping; `unpaid_share` 0 (paid occupancy as a lower bound); periods cut at rate effective dates; every ambiguity raises.
- K2: `--stub` known-answer export; is the known answer independent of the code that computes it?
- K3: with real occupancy for covered segments and the baseline for the rest, how do the two coexist in one scenario run? (The runner takes one panel.)

---

## 5. Pre-audit observations (candidate findings, to be verified independently)

Recorded by the person who wrote the fixes, so they carry that bias; the waves must treat them
as hypotheses. None is settled.

- **O1 (D1, I1).** The scenario signs still come from the stated levels. On real priced
  segments the Center City priced-hour mean sits below 0.70, so both rules cut. Finding 1 of the
  first audit is not closed; it has moved from a fixture to real streets with the same numbers.
- **O2 (B1, B4, G3).** 22,653 priced spaces and $141M status-quo revenue have no external
  check. The commercial-frontage rule's threshold moves capacity by 2x across 0.1 to 0.75.
- **O3 (H2).** The consumer-surplus row dwarfs revenue under the cuts. The integral is
  arithmetically right for the law; whether the law's surplus over induced demand that cannot
  find a space should count, when the cruising term is the H1 proxy, is a dimension-3 question.
- **O4 (H3).** The sweep's breakeven depends on the search-cost *shape*. `o^K` with independent
  spaces gives near-zero cost below 85% and a knee at 95%; a correlated model (neighbouring
  blocks full together) would move the knee down and the breakeven up or down. Nothing tests
  the shape.
- **O5 (E1, E4).** The exponential form doubles the elasticity at twice the posted rate. The
  revenue peak at $10 is therefore the form's extrapolation. The hierarchical model fits a
  constant elasticity; on data spanning one rate change it would return something between the
  two local elasticities. Is the prior slot consistently interpreted?
- **O6 (I2).** All sweep zones start at $2 while the demand law is anchored there, so the
  sweep's elasticities are at $2, not at the posted rates; a peak rule raising to $5 faces
  elasticity 2.5e. The cells' meaning depends on this anchoring.
- **O7 (D2).** The `philadelphia` anchors put 5% of priced blocks at each end by construction,
  the same rank-like device the first audit's finding 24 criticised, now fixed in config
  instead of floating with the loaded set. Fixed is better; founded it is not.
- **O8 (H4, J1).** Dead modules: nested-logit CS, optimizer, validation, ML occupancy,
  `ppa_stub.load_transactions`; notebooks 05 and 06 call signatures that do not exist.
- **O9 (G2).** The General Fund minimum is a fixed $35M; the statute escalates it and applies
  to net citywide revenue. At $141M gross the School District row is the residual.
- **O10 (K3).** No code path mixes observed occupancy for covered segments with the baseline
  for the rest; the `--ppa` run prices only the inventory's segments.
- **O11 (J1).** The guard set still cannot catch a wrong constant: every stated parameter can
  change without a test failing (the tests derive expectations from the same config).
- **O12 (I4).** No headline number has an interval beyond the three elasticity scenarios.

---

## 6. Execution plan

### 6.1 Waves and agents

Cap: three agents concurrently, at most one on the top tier at a time. Every agent writes each
confirmed item to `audits/_scratch/<dim>/findings.md` as it goes and returns only a summary plus
the list.

**Wave 1: orient (mid tier, high effort; one cheap agent).**

| Agent | Dimension | Brief |
|---|---|---|
| 1a | 4 (data -> segments -> anchors -> baseline) | Re-run scripts 02, derive_baseline_anchors and 03 into scratch; diff against `data/processed/`. Test A1 (marker refusal), B2 to B4 (curb classes, frontage share, threshold) on hand-built geometry with known answers; reproduce the PR #10 threshold sensitivity; check B1's capacity arithmetic; D2's 5/95 construction. Confirm determinism (I5). |
| 1b | 4 (demand law -> rules -> revenue -> welfare -> sweep -> outputs) | Re-run 05 and a small sweep into scratch; diff every number in `comparison_table.csv` and `cm_sweep_window_dependence.csv` against a recomputation. Verify E1/E2 (every caller passes the right reference price; no `(p_new / p_old) ** e` survives), F1's inversion, H2's integral by hand on a two-segment panel, H3's search cost against its formula, I3's breakeven arithmetic. Guard injection (J1): change each stated constant in O11 and record which tests fire. |
| 1c | 1 + parameter provenance (cheap tier) | Two-restatement diff: what `README.md`, `CLAUDE.md` and the memory say each stage does versus what it computes. Parameter provenance table: for every constant in `config/*.yaml` and `derive_baseline_anchors.py`, the source or "stated"; verify the ones with a named source (Lehner and Peer; SDOT 2024 report; USDOT VOT; Shoup 2006 cruising range; the centerline CLASS codes; Act 84 § 6109(g)). Flag, do not settle. |

**Wave 2: soundness (top tier, xhigh effort; serial).** Each receives wave 1's findings files.

| Agent | Dimension | Brief |
|---|---|---|
| 2a | 2 Assumptions | Enumerate every assumption in §4 plus wave 1's; load-bearing or not; for each load-bearing one, what would make it false and whether anything tests it. Lead with D1, D2, E1, H2, H3, B4, G2. |
| 2b | 3 Inference | For each claim in §1: estimand versus claim; what is true by construction (the sweep's ordering identities, the 5/95 anchors, the breakeven's linearity); whether the welfare objects (H1 proxy in the scenarios, H3 search cost in the sweep) support the conclusions drawn; what the exponential form's extrapolation licenses; what real data would and would not change (K3, O10); whether the "structure, not size" framing is itself sound. |

**Wave 3: refute (top tier, high effort; one or two at a time).** Every Blocking or Material
candidate goes to a fresh refuter with file paths and the claimed defect only, told to find the
benign reading. Lenses: reproduces; code path as claimed; intended design misread. Survivors
keep their severity; the rest go to "refuted candidates".

**Synthesis (top tier, in the audit session).** Triage; count findings by dimension; write the
"since the last audit" table (27 rows: closed / changed / open, with evidence); the report; the
ranked work list that the paper rewrite will take as given.

### 6.2 Budget

| Item | Estimate |
|---|---|
| Wave 1 (3 agents) | 0.6M tokens |
| Wave 2 (2 top-tier agents) | 0.5M |
| Wave 3 (expect 8 to 12 candidates at 80k each) | 0.8M |
| Synthesis and report | 0.3M |
| **Total** | **about 2.2M tokens**, roughly 1.6M on the top tier |

Check the budget before each wave; if wave 3 cannot be afforded in full, refute Blocking
candidates only and mark the rest "unrefuted".

### 6.3 Stop rules and hygiene

- No agent runs script 01 with `--refresh`, writes under `outputs/` or `data/`, or edits
  source. Re-runs use `PHILLYPARKING_OUTPUTS_DIR` and `PHILLYPARKING_DATA_DIR` under
  `audits/_scratch/` (already gitignored).
- The sweep is run only at small n (a few replications); the tracked parquet is read, not
  rebuilt.
- A check with no output has not passed.
- If the budget runs out, the report says where the audit stopped.

### 6.4 Model and effort allocation

Wave 1: Sonnet at high effort (1c: Haiku or Sonnet at medium). Waves 2 and 3 and the
synthesis: Fable at xhigh. The audit runs in its own session on Fable, as the first did.

---

## 7. Deferred and out of scope

- `Report.tex`, `notebooks/paper/*.qmd`, `docs/rtkl/cover-letter-council.md` prose (one
  rewrite after this audit).
- Streamlit app behaviour beyond what it reads.
- Performance, style, repo tidiness, except where a live consumer depends on a dead module.
- The Parking Authority data itself (not yet received; requests due 2026-10-23 and
  2026-11-13).

## 8. Decisions needed from the user before launch

1. Approve the scope: deep on the changed components, standard on the untouched ones, papers
   out.
2. Confirm the budget order of magnitude (about 2.2M tokens) or name a cap.
