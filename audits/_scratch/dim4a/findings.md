# Wave 1a (dimension 4, implementation) findings: raw layers -> segments -> priced curb -> anchors -> baseline panel

Branch claude/audit-2026-10-16-1cfc47 @ b27c7b2. Probes and outputs sit beside this file.
Reproduction (task 1): runA/runB = script 02 then 03 into scratch (raw junction, network proxy blocked);
runC/data/processed = junction to the real processed dir (derive --check only).

## Reproduction results (task 1; not findings)
- Script 02 (runA, runB) vs real data/processed/segments.parquet: 58,966 rows, 31 columns, identical dtypes and
  column order, identical segment_id order, every non-geometry column exactly equal (0 differing cells), geometry
  exactly equal. Priced = 3,145, priced capacity = 22,653. segments.meta.json identical in every field except
  created_utc (layer fetched_utc, priced_curb_rule included). Output: probe_t1_diff.out.
- Script 03 (runA, runB) vs real demand_panel.parquet: 528,360 rows, occupancy and occupancy_sd exactly equal,
  parquet file SHA-256 identical, demand_panel.key identical (f1027dbb...2227). runA == runB. Output: probe_t1_panel.out.
- derive_baseline_anchors.py --check against the real processed dir: "philadelphia anchors up to date", exit 0
  (derive_check_real.out).
- Determinism (plan I5): two independent runs of 02 and 03 are bit-identical. Segment ids are sha1 of parent key,
  no builtin hash(); baseline noise rng is seeded.

## Findings

### 4a-1  segments.meta.json carries build_report = null; the 125 uncovered-segment drop and the no-curb drop are unrecorded
- Severity: Advisory (provenance gap; nothing downstream reads it). Confidence: Verified ran.
- Plan: B6 ("125 dropped for touching no block group"), I5; prior-audit theme "nothing dropped without a count".
- Evidence: real data/processed/segments.meta.json has `"build_report": null` (task-1 diff reproduces it exactly).
  spatial/segments.py docstring (lines 3-5) says "Every input line is accounted for in
  `segments.attrs["build_report"]`; nothing is dropped without a count". `build_segments` does set the attr
  (segments.py:200s, keys no_curb_dropped=1397, segments=59091, neighborhood_unmatched=377), but
  `join_acs` -> `_merge_checked` -> `segments.drop(...).merge(...)` returns a frame with empty `attrs`
  (probe_t1_buildreport.out: attrs ['build_report'] after build_segments, [] after join_acs), so
  scripts/02_build_segments.py:92 `segs.attrs.get("build_report")` is None. The 125 segments dropped by
  `join_acs(uncovered="drop")` are only in a log warning (join.py: "join_acs: 125 of 59091 ... dropped"); meta
  n_segments is 58,966 with no record of the 59,091 -> 58,966 step, the 1,397 no-curb rows, or 377 segments with no
  neighbourhood. `priced_curb_rule` survives only because assign_priced_curb runs last and sets it on the final frame.
- Repro: probe_t1_buildreport.py (output beside).

### 4a-2  commercial_frontage_share is a ratio over zoned land only, so segments with almost no zoned land inside the buffer are priced on a sliver
- Severity: Advisory (483 spaces = 2.1% of priced capacity below 0.1 zoned coverage; 2,376 = 10.5% below 0.25). Confidence: Verified ran.
- Plan: B3, B4. Code: spatial/join.py `join_zoning` (comm / zoned.replace(0, nan), fillna(0)); spatial/segments.py `assign_priced_curb`.
- What the code does: share = commercial area / (area of ANY zoned land in the 25 m flat buffer). The denominator is not the
  buffer, so the amount of land the share is computed on is unconstrained. Hand-built: a 1 m2 commercial sliver with the
  rest of the buffer unzoned gives share 1.0 (probe_t2_handbuilt.out: "1 m2 commercial sliver ... share 1.0").
  Zero zoned land in reach gives 0.0 (priced never); so "no land" -> unpriced but "one sliver" -> fully commercial.
- On the real table (probe_t2_zoning.out): zoned coverage of the buffer for the 3,145 priced segments has median 0.52,
  p10 0.24; 73 priced segments have <10% of the buffer zoned (e.g. VINE ST class 2, ccc, coverage 0.00007, share 1.0, 8 spaces;
  N CHRISTOPHER COLUMBUS BLVD coverage 0.0004), 357 have <25%. The docstring says the buffer "has to reach across half
  the street to the lots"; wide rights-of-way (Columbus Blvd, expressway frontage) fail that and the share is then decided
  by whichever lot corner is nearest.
- What passes (Clean): the stored share is reproduced to 2e-16 from the raw zoning layer; the zoning layer has negligible
  overlap (2,502 m2 of 279.8 km2; no double counting); a lot beyond a flat segment end contributes 0; a lot over the
  centreline is handled as stated.
- Also: a 50/50 geometry yields 0.500000000016, so `>= 0.5` is decided by floating-point noise for exactly-balanced
  frontage (157 class 2-5 in-box segments sit within 0.01 of 0.5; +/-0.05 around 0.5 moves capacity 25,103 / 22,653 / 20,180,
  probe_t2_real.out). Not a bug, a reminder that B4's threshold is a knife-edge for ~5% of priced capacity per 0.01.
- Repro: probe_t2_handbuilt.py, probe_t2_zoning.py, probe_t2_real.py.

### 4a-3  Capacity: floor-per-piece loses 6.1% of capacity, 12 priced segments have capacity 0, and the "one curb per centerline" rule is documented nowhere
- Severity: Advisory on the arithmetic; the scale question itself is O2 (Material, unverifiable here). Confidence: Verified ran.
- Plan: B1, O2. Code: spatial/segments.py:38-39,152 `max(0, int((piece.length / 7.0) * 0.85))`.
- Verified: capacity == floor(length_m/7*0.85) for all 58,966 rows (0 mismatches). Floor is taken per ~80 m piece:
  priced sum 22,653 against 24,134 unrounded (-1,481 spaces, -6.1%); 126 segments (12 priced; lengths 2.3-8.2 m) get 0.
  Priced length 198.7 km -> 114.0 spaces/km (one curb would be 121.4 before flooring). The reduction is one-directional
  (always rounds down) so it is a bias, not noise.
- One curb per centerline: the City centerline is one line per street, so every street contributes one curb's worth of
  spaces; two-sided metered streets (the CBD norm) would carry up to 2x, while no deduction is taken for intersections,
  bus stops, loading zones or driveways beyond the 0.85. The constant is named DRIVEWAY_HYDRANT_SLACK; no code comment or doc
  (grep over *.py *.md *.yaml for "one curb|both side|per curb") states that only one curb is counted. The sign of the net
  error is unknown; the scale of every dollar output is proportional to it. No external count (Parking Authority inventory,
  Request B) is used. [My recollection that PPA reports roughly 10k metered spaces citywide is unverified here and not relied on.]
- Zero-capacity priced segments carry weight 0 in capacity-weighted statistics, but are rows in the panel and the
  priced-segment count (3,145 includes 12 that earn nothing).
- Repro: probe_t3_capacity.py (output beside).

### 4a-4  zones.yaml `ccc` box does not match its description
- Severity: Advisory (needs a decision whether the description or the coordinates is the source of truth). Confidence: Verified ran on street positions.
- Plan: C1, B5. config/zones.yaml:13-20 describes "Arch-Locust x 4th-20th" but the box is lon -75.170..-75.140, lat 39.945..39.960.
  From the centerline table (probe_t2_boxes.out): Arch St lat 39.9543, Locust 39.9481, Pine 39.9455, Vine 39.9574, Callowhill 39.9586;
  S 4th lon -75.1486, S 18th -75.1714, S 20th -75.1747, S 2nd -75.1452. So the box spans Pine to just above Callowhill (not Locust to Arch),
  cuts off at ~18th/19th (not 20th) and runs east of 4th to the river (Columbus Blvd -75.140). VINE ST is the largest
  priced street in ccc (360 of 7,328 spaces) though it lies ~0.003 deg (330 m) north of Arch. cca "Spring Garden-Bainbridge x
  Schuylkill-Delaware" is likewise a box; boxes cannot follow the real rate zones, and the $4.00 rate is applied to every
  priced block in the box. Whether PPA's zone is the box or the description is Request B's question.
- Repro: probe_t2_boxes.py.

### 4a-5  `segments.meta.json` `synthetic_layers` and the priced-curb rule are write-only: nothing downstream refuses a synthetic or stale segment table
- Severity: Advisory (A1 is otherwise sound; this is the hole between script 02 and scripts 03/05). Confidence: Verified read (grep) + Verified ran for the load path.
- Plan: A1, B4, I5. Evidence: `grep -rn "synthetic_layers\|segments.meta.json" src scripts app` finds the writer (scripts/02_build_segments.py:87)
  and two readers that take only `priced_curb_rule` (scripts/05_run_scenarios.py:53-56, scripts/derive_baseline_anchors.py:66). Script 02 with
  `--allow-synthetic` writes to the same `data/processed/segments.parquet`. `load_segments` stamps `segment_source = {"kind": "file"}`
  (segments.py `load_segments`), `source_anchor_sets` maps `file` -> `philadelphia`, so a segment table built partly from synthetic
  layers is loaded, anchored to `philadelphia`, run and (script 05) labelled `kind: file` with no warning; derive_baseline_anchors.py
  would derive anchors from it. The `synthetic_layers` list that exists to flag this is not read by 03, 05, 06, derive, the app.
- Same shape for staleness: zones.yaml `priced_curb` (min_commercial_share, street_classes, buffer) is read at script-02 time only.
  Changing it without rerunning 02 leaves segments.parquet, the anchors and every scenario on the old priced set; script 05 copies the
  file's `priced_curb_rule` from meta (true to the file) and hashes zones.yaml (config_sha256) but never compares the two. The
  scratch injection in task 7 (min_commercial_share 0.9) shows the consequence for the tests (see below).
- Repro: grep above; probe_t8_checks.py shows `load_priced_segments` attaches only {"kind": "file", ...}.

### 4a-6  Raw-cache provenance: marker is not bound to content, the cache key of `load_pois` ignores `tags`, and a cached synthetic stand-in is served without retrying the real fetch
- Severity: Advisory. Confidence: Verified ran. Plan: A1, A2.
- (a) Marker not bound to content: `load_layer` accepts any file whose sidecar says `kind: real`; the marker holds layer/kind/source/url/fetched_utc/file
  but no size or hash, and `file` is not compared with the filename at read time. Replacing the parquet after marking is accepted
  (probe_t6_provenance.out, case 4: file with x=[999] loaded under a real marker). The marker is therefore a record of a fetch, not a guarantee about the bytes.
- (b) `osm_loader.load_pois(tags=...)` always reads `raw/osm/pois.parquet` whatever `tags` are asked for: `load_pois(tags={'amenity':['school']})`
  returned the 6,893 default-tag rows (probe_t6b_tags_gtfs.out); the returned marker truthfully names the original tags, the caller is just not told they were not honoured.
  Only the default is used in the pipeline today.
- (c) With `allow_synthetic` and an existing `<stem>.synthetic<suffix>`, `load_layer` returns it without trying the real fetch
  (raw_cache.py: the `spath.exists()` branch precedes the fetch loop), so a stale synthetic persists after the network returns until deleted
  (it does log a warning). Probe: case 3b/3c.
- What passes (A1 Clean): unmarked real-name file refused with and without the opt-in (cases 1, 1b); `kind: synthetic` marker under the real name refused with and
  without the opt-in (2, 2b); a `.synthetic` file is read only with the opt-in or env switch (3a raises LayerFetchError and tries the real fetch; 3b, 3c accepted);
  a `.synthetic` file whose marker says real is not served as real (3d). All 11 files under the real data/raw have a marker with kind=real and a matching file name
  (probe_t6_provenance.out, case 5); fetched_utc values are all 2026-10-16 13:24-13:33Z. Script 01 exits 1 on any non-real layer (scripts/01:104-107; not run, per stop rules).
- A2: no other cache. `grep lru_cache|requests_cache|CachedSession|ox.settings` finds only `load_config`'s lru_cache (_config.py:47, harmless across processes) and the osmnx
  `use_cache=False` context manager (osm_loader.py:31-43), restored in `finally`. Carto, ArcGIS, Census, LODES and SEPTA loaders use plain `requests.get`.
- Repro: probe_t6_provenance.py, probe_t6b_tags_gtfs.py.

### 4a-7  The baseline-panel cache key covers data, anchors and seed but not the code that shapes the panel
- Severity: Advisory (Material if kernels are ever tuned: plan J1 lists "a changed kernel" as a defect no guard catches). Confidence: Verified ran.
- Plan: D1, I5; checklist "cache keys". `panel_cache_key` (demand/synthetic_baseline.py `panel_cache_key`) hashes segment_id + the four covariates, the anchors dict
  (config) and the seed. The three kernels (`_office_kernel`, `_retail_kernel`, `_residential_kernel`), the mix softmax form, the interpolation and the occupancy_sd formula are code.
  Probe: replacing `_office_kernel` with a constant changes the panel but `panel_cache_key` stays identical (probe_t8_checks.out: "key changes when the OFFICE KERNEL (code) is replaced: False | panel changes: True").
  Script 05 reuses `demand_panel.parquet` whenever the key matches (scripts/05_run_scenarios.py:84-91), so after editing a kernel the scenarios silently run on the old panel.
  Script 03 rewrites the panel, script 06 recomputes; only 05 (and thus the app) reads the cache. The key also does not include a code version/commit.
- Repro: probe_t8_checks.py.

### 4a-8  The land-use mix is not rescaled between anchor sets, so on real segments it is far more extreme than on the fixture it was tuned on, and pop_density's 4% near-zero tail dominates both the mix and the pop scale
- Severity: Advisory (a parameter-meaning issue behind D3; it moves weekly shape, not level). Confidence: Verified ran.
- Plan: D1, D3, D2. `_mix_weights` (synthetic_baseline.py) uses `mix_weight * (log1p(x) - center)` with NO division by the anchor set's scale, and
  `mix_weight` / `mix_temperature` are shared by every anchor set. On the fixture the inputs' sd are (jobs 1.07, pois 1.16, pop 0.65) after weighting; on the
  `philadelphia` priced curb they are (1.56, 1.14, 1.71) (probe_t5_mix.out). The same `mix_temperature` 2.5 therefore produces a much sharper mix on real
  segments: 38.5% of priced segments have one land-use weight >0.9, against 29% for the fixture segments under their own anchors (probe_t5_mix.out); mean office share in ccc is 0.54.
- pop_density: the log1p sd of 1.90 used as the `philadelphia` scale is driven by the 3.9% of priced segments with density below 100 /km2 (z < -3 down to -4.55);
  excluding zeros the sd is 0.80 (probe_t5_anchors.out). So pop_density's intensity weight (0.25) acts on 96% of segments with an effective spread of ~0.42 sd units while a few
  zero-population blocks (waterfront, industrial: e.g. S SWANSON ST pop 0, jobs 667) get lambda contributions of about -1.1 and the largest negative lambda (-3.78) in the set.
  Because the intensity bounds are the 5th/95th percentiles, the 5% floor group is chosen partly by this tail.
- Consequence: spatial pattern within the priced curb follows jobs and POIs for most blocks and population only at the extremes; the mix and its sharpness are artefacts of constants
  chosen for a different covariate spread. Not a bug in arithmetic; a design/meaning issue to hand to dimension 2.
- Repro: probe_t5_mix.py, probe_t5_anchors.py.

### 4a-9  O1 verified on the real panel: no zone's aggregate reaches the 0.85 line in any priced hour, and the median priced block peaks at 0.77 by construction, so both rules can only cut
- Severity: Material (carries prior finding 1 / plan O1; the judgment about meaning belongs to dimensions 2 and 3). Confidence: Verified ran.
- Plan: O1, D1, D2. probe_t5_anchors.out, on the real `demand_panel.parquet` joined to the priced segments' capacity and `priced_mask`:
  capacity-weighted priced-hour mean occupancy by zone: ccc 0.600, ucity 0.526, cca 0.524, fishtown 0.475, south_philly 0.453 (O1's "CCC below 0.70" holds, and so do
  all the others). Busiest priced capacity-weighted zone-hour (the Arnott statistic): ccc 0.758, ucity 0.641, cca 0.621, fishtown 0.593, south_philly 0.538. Every
  one is under 0.85 (target vacancy 0.15), so the pricer lowers every zone's rate by construction of the panel; the Seattle band means are all under 0.70 likewise.
- Why: anchors are mean and sd of the priced set, so the median block has lambda ~ 0, i.e. lam_norm ~ 0.49 and a weekly peak of 0.62 + 0.30 x 0.49 = 0.767, below 0.85 at its
  own busiest hour; only ~19% of priced blocks (ccc 44%, cca 12%, ucity 6%, south_philly 1.5%, fishtown 0%; probe_t5_anchors.out) peak at or above 0.85 anywhere in the week,
  and blocks of different land-use mix peak at different hours so the zone aggregate sits lower still (ccc mean segment peak 0.823 vs zone busiest hour 0.758).
  The level (0.62-0.92) and the shape (kernels) are stated; the anchors only choose who is high. Whether Center City meters really sit below 85% is exactly what Request B supplies.
- Share at cap / floor: whole priced set 4.99% / 5.02% (calibration attr), but by zone ccc 12.3% at cap vs 0% in fishtown/south_philly/ucity, floor 1.7% ccc vs 12% south_philly
  (lambda by zone, probe_t5_anchors.out). `max_clipped_share` 0.20 (a warning only) is therefore never triggered by a zone-level imbalance and cannot be (it is a set-level share).
- Repro: probe_t5_anchors.py.

### 4a-10  The priced-curb stand-in prices streets that read as waterfront or arterial frontage, with no external check of which blocks are metered (supports O2)
- Severity: Advisory (the Material part is O2 itself, unverifiable without the Parking Authority inventory). Confidence: Verified ran (street lists); the judgment that a street is "not metered" is Suspected, not checked.
- probe_t2_zonestreets.out: top priced streets by capacity include S CHRISTOPHER COLUMBUS BLVD (180 spaces), S WATER ST (128), S SWANSON ST (82), OREGON AVE (182), SNYDER AVE (148) in
  south_philly; ARAMINGO AVE (124) and FRANKFORD AVE (271) in fishtown; HEALTH SCIENCES DR (63), CIVIC CENTER BLVD (59) in ucity. The rule selects by zoning of adjacent land, so
  anything fronting CMX/commercial parcels qualifies, including frontage roads and campus-adjacent streets, while Penn-campus frontage (Special Purpose zoning) does not
  (Walnut St in the ucity longitudes: 9 of 27 segments priced). Priced share of in-box class 2-5 street length: ccc 73%, ucity 30%, cca 24%, fishtown 20%, south_philly 12%.
  No zone is empty (254 to 1,115 priced segments per zone; ucity smallest at 8% of segments, 9.6% of spaces), but zone shares are rule outputs, not counts.
- Repro: probe_t2_zonestreets.py.

### 4a-11  scripts/derive_baseline_anchors.py resolves config from `project_root()/config`, not `config_dir()`, so `PHILLYPARKING_CONFIG_DIR` is ignored and a non-`--check` run edits the tracked file
- Severity: Advisory (a hazard for anyone following the documented scratch-config override; also why the guard cannot be pointed at a copy). Confidence: Verified ran (read-only `--check` only).
- scripts/derive_baseline_anchors.py:`cfg_path = project_root() / "config" / "demand_baseline.yaml"`; every other consumer uses `load_config`/`config_dir()` (_config.py:38). With
  `PHILLYPARKING_CONFIG_DIR=<scratch copy with jobs center 7.95>` the script still printed "philadelphia anchors up to date", exit 0 (it read W/config). Only
  `PHILLYPARKING_PROJECT_ROOT=<scratch root>/config` made it see the edited copy, and then `--check` exited 1 with the stale diff (so the guard itself fires correctly). Without `--check`,
  the first form would have rewritten W/config/demand_baseline.yaml. Same pattern for `data_dir()`: it honours PHILLYPARKING_DATA_DIR (used to point it at the real processed dir).
- Related (J2): the `--check` is not part of the test suite, and the philadelphia-center +1.0 injection (below) passes every test.
- Repro: commands in this session; outputs reproduced in inject/ (cfg_ctr1, root_ctr1).

### 4a-10b  Addendum to 4a-10 and 4a-3: attributes of the centerline layer that bear on "curb that can be metered" are dropped at build time
- Severity: Advisory. Confidence: Verified ran (probe_t3_oneway.out, probe_t3_responsible.out; segment->street mapping by re-hashing seg_id|piece, 58,833 of 58,966 mapped).
- The City layer has `responsibl` (CITY 28,950, STATE 5,465, FAM 4,948, PRIVATE 937, FAIRMOUNT PARK 373, DRPA 71, PHA 155 ...), `st_type` (BRG, TUNL, RAMP, EXPY ...), `oneway` (B 22,205 /
  FT 9,847 / TF 9,196) and `multi_rep` (1,650 rows with a nonzero multiple-representation code). `build_segments` keeps none of them. Priced curb includes 13 segments (116 spaces) on
  COMMERCE ST TUNL / N 5TH TUNL / BENJAMIN FRANKLIN BRG and 72 segments (582 spaces) whose responsible party is PRIVATE, DRPA, PHA, PIDC or Fairmount Park (3% of priced capacity together)
  that a city parking authority would not meter; 247 priced segments (2,039 spaces) carry a nonzero `multi_rep`, whose meaning (divided roadways drawn twice?) I could not verify offline.
  `FAM` (879 priced segments, 6,210 spaces) is not decoded anywhere in the repo or config.
- `oneway` does not matter for the curb count (a one-way street has two curbs too); it confirms that the single-curb capacity rule is applied to 46% one-way centerlines as to two-way ones.
- Repro: probe_t3_oneway.py, probe_t3_responsible.py.

### 4a-12  Guard injection (J1, O11) for the data -> baseline segment: 7 of 12 injected constant changes move an output with ZERO failing tests, including two of the four the brief named (peak_target, a philadelphia center)
- Severity: Material (the fast suite cannot detect a wrong stated or derived constant in this segment; matches plan O11 and prior finding 20). Confidence: Verified ran.
- Method: copy of W/config per variant under inject/cfg_<name>, one edit each (diffs checked with `diff --strip-trailing-cr`), full fast suite `-k "not hierarchical_bayes"` with
  PHILLYPARKING_CONFIG_DIR=<copy>; unedited copy = 336 passed, 0 failed (the 337th test is the deselected PyMC one). Output deltas from probe_t7_delta.py (panel stage, real priced
  segments) and, for zones.yaml priced_curb edits, script 02 re-run into scratch (probe_t7_scripts02.py, probe_t7_buf50.py). Raw outputs: inject/out_<name>.txt, inject/progress.txt.

| injected change (one at a time) | tests failing | output that moved (real data) |
|---|---|---|
| zones.yaml min_commercial_share 0.5 -> 0.9 | 1: test_priced_curb::test_stand_in_prices_commercial_curb_inside_a_zone_box_only | script 02: priced 3,145 -> 2,131, capacity 22,653 -> 15,699. The failing test pins the literal "commercial_frontage_share >= 0.5" in the rule string |
| zones.yaml no_curb_classes -> [] | 1: test_priced_curb::test_roads_without_a_curb_are_dropped_and_counted | nothing in the priced set: table grows 58,966 -> 64,192 rows, priced ids identical (the gate is redundant with street_classes) |
| demand_baseline.yaml peak_target 0.92 -> 0.99 | **0** | max occupancy 0.99; ccc busiest priced hour 0.758 -> 0.802; priced-hour zone means +2 to +3 points |
| philadelphia center jobs_within_200m +1.0 | **0** | share at cap 5.0% -> 0.4%, at floor 5.0% -> 11.7%; ccc priced-hour mean 0.600 -> 0.559 |
| zones.yaml street_classes [2,3,4,5] -> [2,3] | 1 (the same test_stand_in_prices... test) | priced set shrinks |
| zones.yaml frontage_buffer_m 25 -> 50 | **0** | script 02: priced 3,145 -> 2,970, capacity 22,653 -> 22,021 (derived anchors then stale) |
| demand_baseline.yaml mix_temperature 2.5 -> 5.0 | **0** | ccc busiest hour 0.758 -> 0.741; cca 0.621 -> 0.582 |
| demand_baseline.yaml low_demand_peak 0.62 -> 0.50 | **0** | ccc busiest hour 0.758 -> 0.729; south_philly priced mean 0.453 -> 0.415 |
| philadelphia intensity_high 1.26 -> 2.26 | **0** | share at cap 5.0% -> 0.0%; max occupancy 0.92 -> 0.879 |
| jobs intensity_weight 0.55 -> 0.95 | **0** | share at cap 5.0% -> 15.4%, at floor 12.5%; ccc busiest hour 0.758 -> 0.778 |
| zones.yaml ccc current_rate 4.00 -> 6.00 | 3 (test_ppa_ingest x2, test_scenario_hours::test_arnott_ignores_busier_unpriced_hours) | scenario stage, not this segment |
| zones.yaml ccc weekday priced hours 8-20 -> 8-12 | 16 (apply_elasticity, cruising_dwl, priced_hours, scenario_hours, seattle_rule, cm_sweep) | priced-hour means and revenue |

- Reading: the stated occupancy levels, the mix temperature, the intensity weights and bounds, the derived anchors and the frontage buffer all change without a red test. The two
  threshold/class tests that fire are literal-value pins (they fail for any value other than the one in the file, harmless or not), not invariants about the priced set. The only
  guard on derived anchors is `derive_baseline_anchors.py --check`, which is outside the suite (J2). It does fire when it can see the change: jobs center +1.0 via
  PHILLYPARKING_PROJECT_ROOT gives exit 1 with the diff; the 0.9 threshold after re-running 02 gives exit 1 (n=2131, derived centers 7.30/1.61/8.58/5.46 vs 6.95/1.48/8.65/5.36;
  derive_check_msh09.out). The suite's baseline tests exercise the `synthetic_fixture` anchor set; the `philadelphia` set is covered only by test_priced_curb's anchor-set selection and
  its derived-5%-at-each-end test on random data, never by a value.
- Repro: inject/run_all.sh (single runner; two accidental concurrent runners were killed and the outputs regenerated before reading), probe_t7_delta.py, probe_t7_scripts02.py.

## Prior-audit re-verification (task 8)

| # | Verdict | Evidence on the current code |
|---|---|---|
| 2 (every published number comes from a random fixture) | **Closed** for scenarios 05/06; the CM sweep still runs on the fixture by design (not re-opened here) | Saved status_quo/seattle/full_pbd `meta.json` provenance: segment_source kind=file, n_in_file 58,966, n_kept 3,145, anchor_set philadelphia, panel cache_key f1027dbb... equal to the key of the real panel I reproduced (probe_t8_meta.out). Script 05's fallback to `make_synthetic_segments` (scripts/05_run_scenarios.py:66-76) remains but is logged and written to meta as `fallback_reason`. Task 1 reproduces everything bit-exactly from real layers. |
| 17 (real-data swap has no code path; loaders; all-NaN panel) | **Closed** for the public-data path; the PPA branch is outside this wave | All 11 raw layers load real and reproduce segments and panel exactly (task 1); SEPTA nested archive read as two feeds (probe_t6b_tags_gtfs.out: google_bus, google_rail, service date 2026-09-29 a Tuesday, 14,278 stops); ACS via Census API (1,338 block groups, pop 1.593M); a NaN covariate raises in `_z` (synthetic_baseline.py `_z`) and `check_panel` rejects a NaN panel (scripts/03 calls it before writing) (probe_t8_checks.out); panel cache key covers segment ids, covariates, anchors, seed (not kernel code: 4a-7). |
| 18 (fetch failure writes synthetic under the real name; script 01 prints OK) | **Closed** | raw_cache.py `load_layer` refuses unmarked and kind!=real files under the real name and writes synthetic only to `.synthetic` and only with the opt-in (probe_t6_provenance.out cases 1-3); scripts/01_download_public_data.py:104-107 exits 1 on any non-real layer (not run; test_script_01_exits_nonzero_when_a_real_fetch_fails is in the suite). Residue: 4a-6 (marker not content-bound; stale `.synthetic` served first) and 4a-5 (meta.synthetic_layers write-only). |
| 19 (joins do not compute what their columns say; builder loses streets) | **Closed** on the arithmetic; **partly open** on recording | pop_density = pop / land area per km2, buffer-share weighted and renormalised (hand case: 1674.6 equals round-cap area weights, half-covered case 50.0 with coverage 0.5); vehicles_per_hh = vehicles/households (2.0 exact); jobs counted from blocks whose point lies in the 200 m buffer and 40 random priced segments match an independent distance-based recompute for jobs, POIs and transit with 0 mismatches (probe_t4_joins.out); jobs vary 0 to 48,588; zone = smallest box (probe_t2_handbuilt.out); ids from seg_id, collisions raise, MultiLineString split (multipart_rows 0 on real data); neighborhood present (0 NaN on priced); pois_retail>0 for 67% of priced; has_meter is read by `assign_priced_curb` when an inventory is given. Still open: build_report and the 125 dropped segments are not recorded in meta (4a-1); the 125 are all zone "other" so no priced curb is lost. |
| 24 (calibration relative to the loaded set) | **Closed** for floating anchors; **partly open** as construction (plan O7) | Absolute centers/scales/bounds: a 25-segment subset, a single segment and the full set give identical panels (max abs diff 0.0); setting one segment's jobs to 1e9 changes only that segment (probe_t8_checks.out). The anchors are still the 5th/95th percentiles of the priced set's own lambda by construction (5.0% at the cap, 5.0% at the floor; calibration attr 0.0499/0.0502), unfounded beyond that (4a-8, 4a-9), and `derive` is the only thing tying them to the priced set (4a-11, 4a-12). |

## Clean list (checked, nothing found; the denominator)
1. Script 02 reproduces data/processed/segments.parquet exactly (58,966 rows x 31 columns, every cell, geometry), twice.
2. Script 03 reproduces demand_panel.parquet byte for byte (SHA-256) and demand_panel.key; two runs identical (determinism, I5).
3. derive_baseline_anchors.py --check on the real processed dir: up to date; centers and scales are mean and sd (ddof=0) of log1p over the 3,145 priced segments and the bounds the 5th/95th percentiles of lambda, recomputed independently in numpy (4 centers, 4 scales, 2 bounds equal after rounding).
4. no_curb_classes drop and street_class gating on hand-built classes 0,1,2,3,4,5,6,7,9,10,12,13,14,15,18 and NaN: the 7 listed classes dropped and counted; only 2-5 priced; NaN class never priced.
5. `join_zoning` known-answer geometry: both sides (1.0), one side (0.5), unequal depths (0.75), beyond buffer (0), flat end cap (0), zoning over the street (0), diagonal segment (1.0), non-commercial group (0).
6. `zone_for_point` smallest-box rule: ccc inside cca, ucity vs cca (ucity), fishtown vs cca (fishtown), shared edge with south_philly, outside -> other.
7. `assign_priced_curb`: `>= 0.5` inclusive, class 13 never priced, zone "other" never priced, zone_id = box only for priced curb, zone_box preserved; stored priced_curb equals recomputation on all 58,966 rows.
8. PR #10 threshold sensitivity reproduces exactly from the stored share column: 0.1 -> 5,360 segments / 38,380 spaces; 0.25 -> 4,237 / 30,572; 0.5 -> 3,145 / 22,653; 0.75 -> 2,352 / 17,161.
9. Stored commercial_frontage_share equals an independent recomputation from the raw zoning layer (max abs diff 2.2e-16); the zoning layer has negligible overlap (0.0009% double-counted area).
10. Priced capacity by zone: ccc 993 segments / 7,328 spaces; cca 1,115 / 7,777; fishtown 376 / 2,655; south_philly 407 / 2,728; ucity 254 / 2,165; no zone empty or implausibly small.
11. Capacity equals floor(length_m / 7 x 0.85) on all rows; length_m equals the UTM geometry length; no NaN capacity; no duplicate geometries and no shared endpoints (reverse twins) among priced segments.
12. join_acs on hand-built block groups: area-weighted pop_density, income, pct_renter, pct_white, vehicles_per_hh, and renormalisation over a half-covered buffer (acs_coverage 0.5, pop_density 50.0).
13. jobs_within_200m, pois_count, transit_trips_per_hr independently recomputed for 40 random priced segments with 0 mismatches; LODES jobs located 676,054 of 676,054; ACS 1,338 block groups, pop sum 1.593M, ALAND / polygon area median 1.00.
14. The 125 segments dropped by join_acs are all outside every zone box (bbox lon -75.28..-75.054, lat 39.858..40.109); no priced candidate is lost.
15. No NaN in the four baseline covariates among priced segments; zero shares: pois_count 14.7%, pop_density 3.9% (see 4a-8), jobs 0.2%, transit 0%.
16. Walnut St (ccc) and a residential South Philly block (S Hicks St) have plausible covariates (jobs 9,087 vs 156; POIs 30 vs 8; transit 658 vs 153; income $114k vs $79k; frontage share 1.0 vs 0.09).
17. baseline_occupancy raises without segment_source attrs and picks `philadelphia` for kind=file; a segment's baseline is independent of its companions (max abs diff 0.0); one extreme covariate moves only itself; a NaN covariate raises.
18. Provenance refusals (A1): unmarked file refused with and without the opt-in; kind=synthetic marker under the real name refused; `.synthetic` read only with the opt-in or env switch; all 11 real raw files carry kind=real markers with matching file names.
19. A2: no other cache in the loaders (only load_config's lru_cache and the osmnx cache switch restored in `finally`).
20. derive_baseline_anchors.py --check fires (exit 1, with the diff) on a +1.0 center edit and on a segment table rebuilt at the 0.9 threshold.
21. Tests in this segment pin invariants where it matters: companion independence, extreme-segment isolation, NaN raise, unmarked/synthetic refusal, join known answers (test_spatial_joins), exit codes of script 01.
22. Tracked tree untouched: worktree `git status` clean after all runs; no network fetch (proxy blocked, raw cache read through a junction).
23. `no_curb_classes` is redundant with `street_classes` for every priced output (injection: identical priced set), so it cannot be a source of a wrong number.

## Not finished / not checkable offline
- External check of 22,653 priced spaces or of which streets are metered (Parking Authority inventory; plan O2) cannot be done here.
- `FAM` (responsibl) and `multi_rep` meanings in the City centerline are undecoded; the effect on the priced set is bounded (6,210 and 2,039 spaces) but unsigned.
- Script 01 was not run (stop rule); its exit logic was read and its test is in the suite.
- Not examined: ingest/ppa.py, scenarios, welfare (other waves); the PyMC test (not run).
