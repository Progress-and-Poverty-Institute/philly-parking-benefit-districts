# Audit paused, 2026-10-16 (second methods review)

Paused on the parent session's instruction to protect the session budget. Nothing was committed;
the worktree (branch claude/audit-2026-10-16-1cfc47 at b27c7b2) has only untracked files under
`audits/` (`audit_2026-10-16.md` draft and `_scratch/`). No tracked file was changed. No network
fetch was made; no script ran against the tracked tree.

## What each wave produced on disk (all under audits/_scratch/)

- `GROUND_RULES.md`: the binding brief every agent read (paths, PYTHONPATH prefix, stop rules).
- Wave 1a (dim4a/, Sonnet high, ~312k tokens): `findings.md` (12 findings, 23 clean items,
  prior-finding statuses for 2, 17, 18, 19, 24), probes `probe_t1_*` to `probe_t8_*` with outputs,
  `inject/` (12 guard injections with pytest outputs), scratch reruns of scripts 02 and 03
  (bit-exact reproduction of segments.parquet and demand_panel.parquet).
- Wave 1b (dim4b/, Sonnet high, ~400k): `findings.md` (17 findings, 30 clean; prior statuses for
  3-11, 13-15, 20-23, A1-A5, A12, A13; saved by the orchestrator because the agent's Write was
  refused), probes `p01_*` to `p13_*` with outputs, `guard/` and `guard_summary.txt` (15
  injections), scratch run of script 05 (`run05.log`; byte-exact match to tracked tables and saved
  models), 3-rep 3-year sweep (matches tracked parquet, 2,430 rows), `chk07/`.
- Wave 1c (dim1/, Sonnet medium, ~320k): `findings.md` (16 findings, 15 clean; prior statuses for
  1, 2, 12, 16, 25-27, A6, A11, A14-A16; saved by the orchestrator), `parameters.md` (provenance of
  ~65 constants, web-checked where a source is named), `modules.json`, probes `probe_*` with outputs
  (breakeven, dead keys, dead modules, notebooks, zone occupancy, bbox).
- Wave 2a (dim2/, Fable xhigh, ~384k): `findings.md` (47-row assumption inventory; 11 findings
  2-1 to 2-11; prior statuses for 1, 24, 25, 26; 16 clean), probes `probe_a_floors*` (three floor
  configs, `cfg_nofloor/`, `cfg_reportfloor/`), `probe_b_levels`, `probe_b2_offpeak`,
  `probe_c_sweep_cs` (sweep replica matching the tracked parquet to 0 on reps 0-1; per-cell
  breakeven CSVs; `probe_c_rows.parquet`), `probe_e_form`, `probe_f_runner_welfare`,
  `probe_j_provenance`, all with `.out`.
- Wave 2b (dim3/, Fable xhigh, ~380k): `findings.md` (30-step inferential inventory; 13 findings
  3-1 to 3-13; prior statuses for 3, 4, 6, 10, 12, 13, 14, 15; 20 clean), probes
  `probe_a_dwl_by_zone`, `probe_b_tracked_sweep`, `probe_c_null_control`, `probe_d_bounds_in_sweep`,
  `probe_d2_zone_prices`, with `.out`.

## Refuters (wave 3): stopped before any verdict

- Refuter A (scenario pipeline: candidates A1 kernel-mix / floors / "structure not size", A2 two
  cruising models and the surplus row, A3 ordering not robust within ranges; Fable high): stopped
  about 4 minutes in. Left under `refute/RA/`: reruns of the dim2/dim4b probes
  (`a_floors_part1.out`, `a_floors_nofloor_rerun.out`, `b_levels.out`, `b2_offpeak.out`,
  `f_welfare.out`, `p03_stat.out`) and two probes of its own (`ra_mix.py/.out`: varying the kernel
  mix; `ra_searchbins.py/.out`: search-cost by occupancy bin). No `verdict.md`.
- Refuter B (sweep: candidates B1 breakeven unidentified (i-v), B2 "19 minutes / 46 of 54" not in
  any artifact, B3 noise axis one-sided, B4 the identity test; Fable high): stopped while reading
  the source. `refute/RB/` is empty. No `verdict.md`.
- Refuter C (demand form, guards, scope drift: 2-7/4b-2, 4b-7/4a-12/1-16, 1-8/1-1/1-14/1-2/1-7,
  1-12): never launched. `refute/RC/` is empty.
- The three refuter briefs are in this session's transcript (the Agent calls) and can be re-issued
  verbatim.

## Report state

`audits/audit_2026-10-16.md` (untracked, draft) has: header, Scope (argument, read, ran, not
examined, depth, waves and spend), the Coverage denominator table, Not checked, and the complete
"Since the last audit" table (27 findings + A1-A16, each with evidence). Placeholders remain for:
Verdict, findings-by-dimension counts, Findings (ranked), Refuted candidates, Recommended order.

## What remains to finish

1. Wave 3: re-issue refuters A, B, C (or, if the budget does not allow, refute the Blocking
   candidates only and mark the rest "unrefuted" in the report, as the plan's section 6.2 allows).
   Candidate severities going in: Blocking-candidates are 3-1/2-4/2-5 (scenario signs and sizes
   are the inputs' and the floors'; "structure, not size" does not follow) and 3-2/2-2/2-3 (the
   sweep's breakeven is unidentified: a theorem in sign, the scorer's shape in size); Material
   candidates are 2-1 (two cruising models), 2-7/4b-2 (demand-form extrapolation), 4b-7/4a-12
   (guards), 1-8 (unimplemented mechanisms), 1-1/1-14/1-2/1-7/1-12 (README premises, app page 3,
   "metered" stand-in, CCC box, config rates), 3-3 (19 min / 46 of 54 in no artifact).
2. Synthesis: fill Verdict, counts by dimension, Findings, Refuted candidates, Recommended order in
   `audits/audit_2026-10-16.md`.
3. Commit the report and `audits/_scratch/` (needs `git add -f`, the directory is gitignored), push
   the branch, open the PR "audits: second methods review (2026-10-16)" against master; do not merge.

## Budget at pause

Session context 36% of 1M. Account: 5-hour window 59% before wave 2b (not re-read since); weekly
all-models 51%; weekly Fable 73% after wave 2a (wave 2b and the two partial refuters since). Spend so
far: wave 1 ~1.03M, wave 2 ~0.76M, refuters partial (unknown, small). Plan estimate was 2.2M.
