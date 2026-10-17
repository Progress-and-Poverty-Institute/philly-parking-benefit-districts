# Parameter provenance table (wave 1c, 2026-10-16)

Columns: constant | value | file:line | source the file names | source check | read by code?
"stated" = the file calls it an assumption; "none" = no source named anywhere. Reader column: Y(path) = consumed on the
result path; Y(off-path) = consumed only by a module with no non-test caller; app = Streamlit page only; N = dead
(grep over src/scripts/app; probe `probe_deadkeys.py`, output `probe_deadkeys.out`, hand-adjudicated).
Web checks give the URL and what it says. FLAG = discrepancy or unsupported; no judgment call is settled here.

## config/zones.yaml
| constant | value | line | named source | check | read? |
|---|---|---|---|---|---|
| ccc.current_rate | 4.00 | 10 | "research doc 4.3 / post-July-2025 PPA structure" (l.1-3) | VERIFIED: PPA notice effective 2025-07-01, Core $3.00 -> $4.00 https://philapark.org/?p=28772 | Y (runner._zone_current_prices) |
| cca.current_rate | 3.50 | 21 | same | VERIFIED same notice ($2.50 -> $3.50) | Y |
| ccc/cca long_term_meter_rate | 2.50 | 11, 22 | same | VERIFIED same notice (4h/12h meters $1.50 -> $2.50) | N (dead key) |
| ucity.current_rate | 2.00 | 32 | none; l.2-3 calls secondary zones "pilot expansion zones" | FLAG: not in the PPA notice (it lists Core, Area, long-term only). Report.tex:240 says $2.50; an undated Parkopedia listing also says $2.50 for University City meters. No PPA figure found for $2.00. | Y |
| south_philly.current_rate | 1.50 | 40 | none | FLAG: not found in any PPA notice (Report.tex:241 says $2.00) | Y |
| fishtown.current_rate | 1.50 | 49 | none | FLAG: same (Report.tex:242 says $2.00) | Y |
| floors ccc / cca / ucity | 1.00 | 12, 23, 34 | none | none; Report.tex:238-240 gives 2.00 / 1.50 / 1.00 | Y (Seattle and Arnott clip). BINDS: saved prices put cca and ucity at exactly 1.00 in both reforms |
| floors south_philly / fishtown | 0.50 | 41, 50 | none | none; Report says 1.00 | Y. BINDS: both at 0.50 in both reforms |
| ceilings ccc / cca / ucity | 8 / 7 / 6 | 13, 24, 35 | none | none | Y; never binds (comparison_table n_zones_at_ceiling = 0) |
| ceilings south_philly / fishtown | 4 / 4 | 42, 51 | none | none | Y; never binds |
| priced_hours weekday / saturday / sunday | [8,20] / [8,20] / null (south_philly [8,18]) | 14, 25, 35, 44, 53 | none | none (PPA hours not cited) | Y (pricing.priced_hours) |
| bbox (5 zones) | lon/lat boxes | 15, 26, 36, 45, 54 | the description column (Arch-Locust x 4th-20th, etc.) | FLAG: CCC box does not match its own description; finding 1-5 | Y (spatial.zones.zone_for_point) |
| description, role | text | 9, 16, ... | n/a | n/a | N (dead) |
| priced_curb.no_curb_classes | [1,6,9,10,12,14,15] | 64 | PASDA metadata "read 2026-10-16" | VERIFIED: PASDA CityPhillyStreets layer 18 (202403) CLASS legend: 0 Navy Yard, 1 Expressways, 2 Major Arterial, 3 Minor Arterial, 4 Collector, 5 Local, 6 Driveway, 9 Low Speed Ramps, 10 High Speed Ramps, 12 Non Travable, 14 City Boundary, 15 Walking Connector (https://maps.pasda.psu.edu/server/rest/services/pasda/CityPhillyStreets/MapServer/19/metadata). Codes 13 and 18 (config l.63 "kept but never priced") are NOT in that legend; segments.parquet has 159 class-13 and 10 class-18 segments. | Y (spatial.segments) |
| priced_curb.street_classes | [2,3,4,5] | 65 | same | VERIFIED labels. Class 5 (local) supplies 878 of the 3,145 priced segments (28%). | Y |
| frontage_buffer_m | 25 | 70 | none ("An assumption") | stated | Y |
| min_commercial_share | 0.5 | 71 | none | stated. Reconciles: priced capacity in segments.parquet = 22,653 spaces (ccc 7,328 + cca 7,777 + ucity 2,165 + south 2,728 + fishtown 2,655) on 3,145 segments (993 + 1,115 + 254 + 407 + 376). PR #10 sensitivity (plan B4): 0.1 -> 38,380, 0.25 -> 30,572, 0.75 -> 17,161 not re-run. | Y |
| rpp.base_annual_fee_usd | 75.00 | 75 | Bill #240335 | VERIFIED https://philapark.org/residential-parking-permit/ ($75 flat per vehicle, eff. 2024-09-01) | app only (4_Equity_Analysis) |
| rpp motorcycle 50, household_cap 3, low_income waiver, temp_15 75, temp_30 150 | | 76-80 | Bill #240335 | VERIFIED same PPA page | N (dead; ppa_stub hard-codes its own 50/75) |
| rpp.market_pricing_targets (ccc 2500, cca 1800, ucity 1500, south 800, fishtown 800, other 500) | | 83-89 | "research doc section 7 estimate ($500-$2,500 range)" | not checked (a research note is a claim, not evidence) | app only (4_Equity_Analysis: unweighted mean x an input of 80,000 permits); no model consumer |

## config/demand_baseline.yaml
| constant | value | line | source named | check | read? |
|---|---|---|---|---|---|
| covariates.*.intensity_weight | 0.55 jobs, 0.35 POIs, 0.25 pop density, -0.15 transit | 23-26 | none | stated (header l.17 "STATED, NOT MEASURED") | Y |
| covariates.*.mix_weight | 1.0 / 1.2 / 0.9 | 23-25 | none | stated | Y |
| anchor_sets.synthetic_fixture | centers 7.62, 3.17, 9.74, 2.70; scales 1.07, 0.97, 0.72, 0.91; low -1.22, high 1.25 | 32-35 | "the demo fixture, rounded" | derived from the fixture | Y (tests, CM sweep only) |
| anchor_sets.philadelphia | centers 6.95, 1.48, 8.65, 5.36; scales 1.56, 0.95, 1.90, 0.67; low -1.21, high 1.26 | 40-43 | generated by scripts/derive_baseline_anchors.py | `derive_baseline_anchors.py --check` run (read-only, data dir = main checkout): "philadelphia anchors up to date". By construction (script l.34-35) 5% of the priced curb sits at each end. | Y |
| peak_target | 0.92 | 54 | "unsourced calibration assumptions" | stated (02-methods.qmd calls it the "SFpark target") | Y |
| low_demand_peak | 0.62 | 55 | same | stated | Y |
| offpeak_floor / offpeak_span | 0.20 / 0.10 | 56-57 | same | stated | Y |
| mix_temperature | 2.5 | 58 | none | no source | Y |
| max_clipped_share | 0.20 | 62 | none | diagnostic only | Y (warning) |
| source_anchor_sets | fixture -> synthetic_fixture; file -> philadelphia; ppa_inventory -> philadelphia | 47-50 | | | Y |
| Kernel constants in demand/synthetic_baseline.py (not in config) | office: weekday 9-17h at 1 - 0.15\|h-13\|/4, shoulders 0.5, rest 0.05, Sat 0.15/0.03, Sun 0.02 (l.43-60); retail: weekday 11-14h 1.0, 17-22h 0.85, 9-11 and 14-17 0.55, Sat 0.95/0.7, Sun 0.7 (l.63-90); residential: 22-7h 1.0, 7-9 0.85, 9-17 0.45 weekday / 0.65 weekend, evening 0.7 (l.93-107); occupancy_sd = 0.04 + 0.02(1 - \|2(occ-0.5)\|) (l.235) | | none | hand-drawn; the within-day shape of every scenario and of the sweep comes from them | Y (kernels) |
| scripts/derive_baseline_anchors.py | percentiles 5 / 95; rounding 2 dp (l.29-30, 34-35) | | none | stated in docstring | Y |

## config/pricing_rules.yaml
| constant | value | line | source | check | read? |
|---|---|---|---|---|---|
| seattle_rule.step_usd | 0.50 | 8 | "SDOT 2024 Paid Parking report" (l.6) | VERIFIED in part. The 2024 report legend: "Occupancy above 85%; $0.50 rate increase" and "Occupancy below 70%; rate decrease" (decrease amount not in the legend; area tables show $0.50 moves). https://www.seattle.gov/documents/Departments/SDOT/ParkingProgram/PaidParking/2024_PaidParking_Report_Final.pdf (73 pp, text extracted) | Y |
| seattle_rule.occ_high / occ_low | 0.85 / 0.70 | 9-10 | same | VERIFIED: "Our target occupancy rate for on-street parking is 70-85%" | Y |
| seattle_rule.occ_very_high | 0.95 | 12 | none ("Optional second tier") | FLAG: no double step in the 2024 report text or legend | Y |
| seattle_rule.max_step_per_cycle | 2 | 14 | none | FLAG: same | Y |
| Review frequency (scenarios.yaml seattle cycle_years: 1) | 1 per year | scenarios.yaml:20 | implied SDOT | FLAG: report says "adjusting rates three times per year in the spring, summer, and fall". `cycle_years` is itself dead; the runner simply loops one review per year. | N (dead key); behaviour annual |
| time_of_day_bands | [[8,12],[12,16],[16,20]] | scenarios.yaml:21 | implied SDOT per-time-of-day | FLAG: SDOT reports Morning / Afternoon / Evening with sampled times of its own (Belltown sheet: 9-10am, 11am-4pm, 6-7pm); the model's bands are its own | Y |
| Statistic: capacity-weighted band mean over priced hours | | 5-7 | "as in SDOT's 2024 report" | PARTIAL: report reports average occupancy per time period and area, and states its on-target criterion per blockface ("one to two available spaces on a blockface"); whether the rate rule uses area or blockface averages is not stated in the text read | Y |
| chatman_manville.occ_low / occ_high / step | 0.70 / 0.85 / 0.50 | 23-25 | equal to seattle_rule (guard test) | n/a | Y |
| chatman_manville.peak_quantile | 0.95 | 26 | none | stated | Y |
| arnott_inci.target_vacancy | 0.15 | 30 | "cruising just eliminated" | the 15% is Shoup's 85% rule of thumb, not an Arnott-Inci derived value | Y |
| arnott_inci.value_of_time_usd_per_hr | 20.00 | 33 | "2024 USDOT default for local personal travel ~ $17.90; bump for downtown" | FLAG: USDOT's guidance is the Sept-2016 memo (local personal = 50% of hourly median household income; $13.60 per person-hour in 2015 dollars per FAA's reproduction of the table, https://www.faa.gov/regulations_policies/policy_guidance/benefit_cost/econ-value-section-1-tx-time.pdf ; the transportation.gov memo returned 403, so not read at source). A "2024 default of $17.90" is a CPI scaling, not a published 2024 USDOT figure; $20 is a stated bump. | Y in targeting_welfare / cm_sweep; the scenarios' DWL scorer uses a hard-coded 20.0 (welfare/cruising_dwl.py:13,45), not this key |
| avg_cruising_minutes (no config key) | 5.0 | welfare/cruising_dwl.py:12,43; pricing/arnott_inci.py:49; scenarios/cm_sweep.py:197 | none | hard-coded in three places | Y |
| search_cost.minutes_at_reference | 5.0 | 45 | Shoup (2006) "3.5 to 14 minutes" | Range VERIFIED: Shoup, Transport Policy 13:479-486, abstract and Table 1 (17 studies 1927-2001, average search time 3.5-14 min, mean 8.1; 8-74% of traffic cruising). FLAG: these are average times to find a curb space in congested downtowns, not conditional on 95% occupancy or a 10-space block; 5.0 is below the Table 1 mean. Comment l.40-41 says the sweep varies the level through `scenarios.yaml cruising_minutes_at_reference`: that key does not exist (grep) and the sweep does not vary the level (it reports a breakeven). | Y |
| search_cost.reference_occupancy / reference_capacity | 0.95 / 10 | 46-47 | none | stated | Y |
| search_cost.mean_duration_hr | 1.5 | 48 | "stated 90-minute mean stay" | stated | Y |
| search_cost.occupancy_cap | 0.99 | 49 | none | stated | Y |
| global_floor_usd / global_ceiling_usd | 0.50 / 10.00 | 52-53 | none | used only for zones absent from zones.yaml (seattle_rule.zone_bounds) | Y (fallback) |

## config/allocation.yaml
| general_fund_minimum_usd | 35,000,000 | 24 | Act 84, 75 Pa.C.S. 6109(g)(2)-(3) | VERIFIED against the enrolled act text (legis.state.pa.us 2012/0/0084..PDF, extracted): "(i) Up to $35,000,000 ... (ii) ... net annual revenue ... exceeds $35,000,000 ... all of the excess to the general fund of a school district of the first class"; transfers are "net of the operating and administrative expenses"; para (3): the $35M rises by $35M x the percentage increase in GROSS revenue. The config comment states this and that the model applies neither the escalator nor the net basis. | Y |
| Auditor General FY2017 $38.9M (comment l.21) | | | AG audit Dec 2017 | not checked (not a model input) | n/a |

## config/elasticity_priors.yaml
| constant | value | line | source | check | read? |
|---|---|---|---|---|---|
| central.mean / sd | -0.40 / 0.15 | 9-10 | Lehner & Peer 2019, TR-A 121:177-191 (50 studies, SUR) | FLAG, unverifiable at source: the abstract (https://ideas.repec.org/a/eee/transa/v121y2019icp177-191.html ; WU repository page) gives no point value, no range and no price-level result; the full text is paywalled and not read. A secondary citation (Gragera et al.) reads the paper as a range of about -0.6 to -0.1 depending on specification. Prior audit finding 26 traced -0.40 to Concas-Nayak. sd 0.15 feeds only ElasticityScenario.sd (provenance, app fan chart). | central.mean: Y (script 04 prior-only fallback); sd: off the result path |
| scenarios pessimistic / central / optimistic | -0.70 / -0.40 / -0.20 | 51-53 | none stated for the bracket | FLAG: the bracket is the project's; not in the abstract | Y (headline, ranges) |
| context_shifts cbd 0, mixed_use -0.05, residential -0.10, long_run -0.30 | | 19-22 | "higher prevailing prices (Lehner-Peer table 5)" | table 5 not read (paywalled); FLAG unverified | Y only via elasticity/priors.central_prior (no non-test caller); mixed_use and long_run read by nothing. No scenario applies a context shift: every zone gets the same scalar. |
| dwell_time mean / sd | -0.15 / 0.05 | 26-28 | none | none | N |
| cross.* (garage 0.30, transit 0.05, rideshare 0.10, forgo 0.05; sd 0.10/0.03/0.05/0.03) | | 32-36 | Calthrop-Proost-Van Dender 2000; Inci 2015 | not checked | off-path (priors.cross_priors, no non-test caller) |
| demand_form | exponential | 47 | "Lehner & Peer 2019: higher prevailing prices are more elastic" | FLAG: not in the abstract; the rate at which elasticity rises (proportional to price, e p / p_ref) is the form's, not measured | Y |
| hierarchy.city_mu_prior -0.40 / 0.20; neighborhood_sd_prior 0.10 / 0.05; zone_sd_prior 0.05 / 0.03 | | 58-60 | none | stated | Y in script 04 only (needs PPA data); on no published number |

## config/scenarios.yaml
| constant | value | line | source | check | read? |
|---|---|---|---|---|---|
| rpp_policy.kind (flat / market_clearing), annual_fee_usd 75 | | 9-11, 22-24, 37-38 | | | N (only revenue_share_to_pbd is read, runner.py:325) |
| full_pbd.rpp_policy.revenue_share_to_pbd | 0.30 | 39 | "Mexico City EcoParq precedent" | VERIFIED as precedent: 30% of meter income earmarked for neighbourhood improvements (ITDP https://www.itdp.org/mexico-city-parking/ ; 2012-15 coverage, current rule not checked) | Y |
| pricing_policy.target_vacancy (full_pbd) | 0.15 | 35 | | | Y |
| rolls_forward_years | 0 / 20 / 10 | 13, 28, 41 | none | caps, not horizons | Y |
| cycle_years, description, notes | | | | | N (dead) |
| chatman_manville_sweep: fixture n=120 seed 42; elasticity [-.2,-.4,-.7]; start_occupancy [.6,.75,.9]; block_dispersion [0,.3,.6]; observation_noise [0,.1]; start_price 2.00; n_replications 100; rolls_forward_years 8; comparisons | | 51-61 | none | stated design axes; start_price 2.00 is not the posted rate of any Center City zone | Y |
| elasticity_scenario per scenario | central | 12, 25, 40 | | | Y |

## config/ppa_ingest.yaml
Column names, paths and formats are placeholders for an export that has not arrived (header l.4-11). Substantive constants: unpaid_use.unpaid_share 0.0 (l.60-62, "assumption (not measured)"); checks max_unmatched_session_share 0.01, max_rate_mismatch_share 0.01, over_capacity_tolerance 1.05, max_over_capacity_share 0.0 (l.65-68; no source; read by ingest/ppa.py); sessions.max_session_hours 12; sessions.columns.channel is dead (read nowhere).

## Dead keys (no consumer on any path, grep + adjudication)
zones: description, role, long_term_meter_rate_usd_per_hr (x2), rpp.motorcycle_annual_fee_usd, household_cap, low_income_first_vehicle_waiver, temp_15_day_usd, temp_30_day_usd.
elasticity_priors: dwell_time.*, context_shifts.mixed_use, context_shifts.long_run.
scenarios: scenarios.*.description, .notes, pricing_policy.cycle_years (seattle, full_pbd), rpp_policy.kind, rpp_policy.annual_fee_usd.
ppa_ingest: sessions.columns.channel.
Read only off the result path: rpp.base_annual_fee_usd and rpp.market_pricing_targets (app page 4), context_shifts.cbd/residential and cross.* (priors.py, no non-test caller), central.sd, hierarchy.* (script 04).
