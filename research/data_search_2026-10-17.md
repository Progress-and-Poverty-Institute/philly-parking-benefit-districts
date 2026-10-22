# Data search for four unsourced inputs, 2026-10-17

Read-only pass, about 10 documents read plus web-search result pages (list at the end). No code, config or tracked output was touched and no pipeline script was run. Downloads are in `research/sources/data_search_2026-10/` (Controller audit 2020, Planning Commission Center City parking study 2020, PPA IS2 statements for March 2025 and June 2025).

Compared against: `outputs/tables/revenue_gap_decomposition.csv`, `config/zones.yaml`, `config/demand_baseline.yaml`.

**Headline.** No public source supplies Philadelphia on-street occupancy, official meter hours by area, or a paid share. The useful finds are: (a) the Carto `parking_violations` table, real but ending in 2017; (b) PPA's own monthly statements, which give a revenue-per-space benchmark and show convenience fees booked apart from the meter line; (c) the PPA holiday page (nine free days) and the July 2025 rate increase, which also shows the benchmark year ran at lower Center City rates than the model.

## 1. Priced hours

| Source | What it says | Status |
|---|---|---|
| PPA, "Holiday parking", https://philapark.org/holiday-parking/ (read 2026-10-17) | Nine days a year with no meter enforcement: New Year's Day, MLK Day, Easter Sunday, Memorial Day, Juneteenth, July 4, Labor Day, Thanksgiving, Christmas Day. "meter parking will be enforced on holidays during which there is normal retail activity." | Verified (page text) |
| PPA, "Meters", https://philapark.org/meters/ | No enforcement days or hours; time limits vary by location, read the posted sign. | Verified (absence) |
| Inquirer, 2022-04-06, Fitzgerald | No hours stated. | Verified (absence) |
| Parkopedia block listings, third party | Examples: Mon-Sat 8:00-22:00 enforced at some Center City blocks; Mon-Wed 8:00-18:30 and Thu-Sat 8:00-24:00 at one South Philadelphia block. | **Unverified**: search snippets of a non-official site |

**Versus the model.** The model uses 8-20 weekday and Saturday, no Sunday (3,744 h/yr), and 8-18 in South Philadelphia (3,120 h/yr). No official source for hours was found, so nothing confirms or contradicts those windows; the unofficial listings suggest hours vary by block and some run past 20:00. The one verified correction is the nine free days, at most about 9/312 = -2.9% of annual hours (Easter Sunday and some others fall on unpriced days, so the true cut is smaller). The model's `52 x weekly hours` ignores them.

**Philadelphia Code, Chapter 12-1000 "Parking Meter Regulations and Penalties"** (code library, read 2026-10-17; §§ 12-1001 to 12-1006 checked) sets no days or hours of meter operation. Hours are therefore not in the ordinance. They are set by posted signs or regulation, and the RTKL meter inventory is the route to them.

**Effort.** Holidays: one config entry plus a small change in `pricing/priced_hours.py`. Hours by block: needs the RTKL meter inventory or the meterUP zone table (each block side has its own meterUP zone number per the Meters page); neither is public.
**Recommendation.** Use the nine-holiday rule. Hours by area: wait for RTKL. Skip Parkopedia.

## 2. Occupancy in priced hours

No measured on-street occupancy for Philadelphia was found. Everything located is off-street:

| Source | Value | Measures | Status |
|---|---|---|---|
| City Planning Commission, Center City parking inventory 2015 (reported in WHYY, Planetizen, Philadelphia Magazine, 2016) | 73.9% occupancy | 169 off-street public facilities, Center City, 2015 | **Unverified**: search snippets; the 2015 PDF was not read |
| Planning Commission, Center City Parking Study 2020 (downloaded, keyword-searched, pp. 2-5) | Off-street occupancy at PPA facilities 41-51% for most of 2020; on-street revenue in Center City down 97.8% in April 2020 vs April 2019, with a moratorium on meter enforcement | COVID year | Verified |
| Old City District, Old City Parking Study 2022 (Econsult), https://oldcitydistrict.org/old-city-parking-study-2022 | 55% overall utilisation, four count times, 14 off-street facilities, more than 3,000 spaces | Old City, off-street | Verified (web page); PDF not read |

**Versus the model.** Model capacity-weighted mean 0.54 (0.45 South Philadelphia to 0.60 Center City Core). The garage figures do not bear on curb occupancy. The 2015 text reportedly says on-street meters "remain bargains" against garages: qualitative, not a number.
**Effort / recommendation.** Nothing to bring in; skip for calibration. RTKL session data are the only route to measured occupancy. Out-of-city context (SFpark, SDOT) is unread.

## 3. Posted rates

| Source | Value | Status |
|---|---|---|
| PhillyVoice, Tanenbaum, 2025-06-26, https://phillyvoice.com/center-city-parking-ppa-rate-increase-philadelphia-july-1 | Effective 2025-07-01: Center City Core (Arch to Locust, 4th to 20th) $3.00 to $4.00/h; Center City Area (Spring Garden to Bainbridge, Schuylkill to Delaware, excl. Core) $2.50 to $3.50/h; long-term meters (4-hour and 12-hour limits) $1.50 to $2.50/h. Projected $4M a year for the School District. First increase since 2014. | Verified for the article; a news report, not the PPA notice. WHYY and NBC10 snippets agree (unverified in full) |
| PPA Meters page | Example block (201 Columbus Blvd): $1.50/h, four-hour limit. Overstay doubles then triples the rate. "No current plans to change the parking meter rates." | Verified; the page predates the 2025 increase |
| Inquirer 2022-04-06 | Overtime ticket $36 Center City, $26 elsewhere | Verified |

**Versus `zones.yaml`.** Core $4.00, Area $3.50 and long-term $2.50 match. University City ($2.00), South Philadelphia and Fishtown ($1.50) have no source in anything read. Floors: nothing found; still assumptions.

**Statutory fee caps, Philadelphia Code § 12-1005** (code library, read 2026-10-17; capture at `research/sources/data_search_2026-10/phila_code_12-1005_capture_2026-10-17.txt`). Verified. The Code sets a maximum hourly fee ("up to"), and the Department sets the rate beneath it:

| Area (Code boundaries) | Code maximum | `zones.yaml` posted | `zones.yaml` ceiling |
|---|---|---|---|
| Center City Core: Arch, 4th, Locust, 20th (§ 12-1005(4), Bill 250200, 2025) | $4.00 | $4.00 | $8.00 |
| Center City Area: Spring Garden, Bainbridge, Schuylkill, Delaware, excluding the Core (§ 12-1005(3)(a), Bill 250200) | $3.50 | $3.50 | $7.00 |
| University City: Schuylkill, University/Woodland, 40th, Filbert/34th/Arch (§ 12-1005(3)(b), since 2010) | $2.50 | $2.00 | $6.00 |
| Everywhere else, "except ... as expressly provided for by special ordinances" (§ 12-1005(2), 2014) | $1.00 | $1.50 (South Philadelphia, Fishtown) | $4.00 |

What follows from the table:
- **The Center City rates are at their legal maxima.** Posted Core and Area rates equal the Code maximum. Any scenario that prices above them (Seattle steps, Arnott-Inci, the sweep) needs Council to amend § 12-1005, as Bill 250200 did in 2025. The `zones.yaml` ceilings are therefore reform ceilings, not current law. That is a property of the scenarios, worth stating in the paper.
- **The $1.50 outer-neighbourhood rate is above the Code's default cap of $1.00.** Either a special ordinance covers South Philadelphia and Fishtown (not found; the Code library's special ordinances were not searched) or the $1.50 rate is wrong for those areas. **Unresolved.** Check against the RTKL rate schedule.
- **Rates and caps have different areas and bounds.** The University City rate area in the Code differs from the model's University City box (`bbox` in `zones.yaml`), and the Code's maximum ($2.50) leaves room above the posted $2.00.
- **Mobile-payment rules are not in the model.** Time beyond the posted limit costs 2x, then 3x, the base fee, up to three times the initial limit (§ 12-1005(5)). The model has no time limits, so it carries none of that premium. A $0.40 processing fee is charged on each app transaction.

**The benchmark year ran at the old rates.** The FY2025 meter revenue ($40.8M, year to 3/31/2025) was booked at $3.00 Core and $2.50 Area. Re-pricing only those two zones in the model's revenue identity (spaces x hours x occupancy x price, from the decomposition csv) gives about 0.77 of the current model revenue, so the ratio would be about 2.7x instead of 3.45x. This is my arithmetic on the csv, not a rerun, and it assumes every Core and Area space is at the zone rate rather than the long-term rate. It also holds occupancy fixed. Under the model's own demand law (exponential, e = -0.60 at the posted rate), occupancy at the old rates is higher by exp(0.6 x 1/3.50) = 1.19 in the Area and exp(0.6 x 1/4.00) = 1.16 in the Core. Model revenue at the old rates is then about $124M, a ratio of about 3.0x. The benchmark-year ratio is therefore about 2.7-3.0x, depending on whether occupancy responds to the rate.
**Effort.** A config value (prior schedule with effective date) plus one benchmark row; small.
**Recommendation.** Use: report the benchmark ratio at the rates in force in the benchmark year.

## 4. Paid share and compliance

### 4a. OpenDataPhilly "Parking Violations" (Carto)
- Access: Carto SQL API, table `parking_violations`, `https://phl.carto.com/api/v2/sql?q=...`, public, no key. Only small aggregate queries were run.
- Schema: `cartodb_id, the_geom, anon_ticket_number, issue_datetime, state, anon_plate_id, division, location, violation_desc, fine, issuing_agency, lat, lon, gps, zip_code`.
- **Years: 2012-01-01 to 2017-12-31 only.** 9,412,858 rows (1.51M in 2012 rising to 1.72M in 2017). It predates the kiosk roll-out, the mobile app's growth and the 2025 rates.
- In 2017: METER EXPIRED CC 419,621; METER EXPIRED 213,377; OVER TIME LIMIT 211,524; HP RESERVED SPACE 23,199. `CC` presumably means Center City (inferred; no documentation read). 632,998 rows start with `METER EXPIRED`, of which 1,561 lack lat/lon. No code for placard misuse at a meter.
- Plates are anonymised (`anon_plate_id`).

**Proxy for enforcement or non-payment?** Only for enforcement intensity (expired-meter tickets by block, 2012-2017). A ticket count is detection effort times violation rate; without patrol hours it cannot give a paid share.
**Effort.** One SQL-aggregated query loader: about 100 lines plus a test.
**Recommendation.** Benchmark of enforcement geography only; do not use for the paid share.

### 4b. Mobile payment and how revenue is booked
- Inquirer 2022: almost 70% of meter payments on mobile (PPA officials), about 27% of customers pay at kiosks, mechanical meters 3% of fees. Verified in the article; the shares measure different things.
- PPA Meters page: meterUP (Parkmobile) charges $0.40 per app transaction.
- PPA IS2, year to 3/31/2025 (`IS2_March-2025.pdf`, p. 1): Revenue - Meters $40,795,664 (prior year $39,860,097; budget $38,814,742); Credit Card Convenience Fees $2,798,670 (prior year $2,903,079) as a separate line; Revenue - Tickets $98,669,457. Verified. That the meter line excludes the convenience fees is my **inference** from the line layout; the statement does not say. The fees ($2.8M) are too small to explain the gap in any case.
- PPA IS2, three months to 6/30/2025 (`IS2_June-2025.pdf`, p. 1): Revenue - Meters $10,622,186 (prior-year quarter $10,361,020). Quarter is before the July increase. Verified.
- Meter revenue grew 2.3% from FY2024 to FY2025, consistent with no rate change.

### 4c. Revenue per space
Controller audit 2020 (`controller_ppa_audit_2020.pdf`, p. 4 and p. 19): 15,406 spaces and 651 employees, and $37M of metered revenue against Portland's $36M on 14,000 spaces. Verified in the PDF; the Portland figures are the audit's, not checked at source.
Revenue per space: PPA FY2025 $40.8M / 15,406 = $2,648 (the space count is from 2020); Portland $36M / 14,000 = $2,571 (audit figures); model $140.7M / 22,653 = $6,211. The model is 2.3x the PPA per space. The decomposition already isolates this as hours x occupancy x price x paid share; this gives it a second anchor, with Portland showing the same order of magnitude as the PPA.

### 4d. Placards
- Snippets only (PPA ADA page and visitphilly guide, not opened): placard or plate holders get 60 extra minutes beyond the posted limit; wheelchair-lift vehicles park without time limit or kiosk fees where time-limited. **Unverified.** A 2024 ordinance (Bill 240613-AA) amended these provisions; its text was not read.
- **Philadelphia Code § 12-1117, "Designation and Use of Disability Parking Spaces"** (code-library export, `research/sources/data_search_2026-10/philadelphia-pa-1.pdf`, as amended by Bill No. 240613-AA and Bill No. 250208, both effective 2025-07-07; read in full). Verified:
  - (2)(c): on each side of each hundred block with metered parking, one space is reserved for vehicles with a disability permit. That space is "regulated by a parking meter", so it is still paid.
  - (2)(d): only a wheelchair lift-equipped van carrying a person with a disability may park "without limitation as to time and without payment of any parking meter fees".
  - The section grants placard holders no general exemption from meter fees. The 60-extra-minutes allowance in the snippet above is not in this section; it may sit elsewhere in the Code or in PPA practice (unverified).
  - So legally exempt non-payment is confined to lift-equipped vans. Any larger unpaid share would be non-compliance, not exempt use.
  - For capacity: each metered block side's reserved space is still a metered space, so it stays in the count, but general parkers cannot use it.
- No Philadelphia placard-misuse rate was found. A CBS report of about 80 people ticketed daily is about accessible spaces and ramps, not meters (snippet; unverified).

**Recommendation.** Use the revenue-per-space and fee-line facts as benchmarks; skip placards until RTKL sessions give paid versus unpaid occupancy.

## 5. PPA audited financial statements, FY2025 (added 2026-10-17)

Philadelphia Parking Authority, "Financial Statements, Years Ended March 31, 2025 and 2024" (combined Authority report, CliftonLarsonAllen LLP), https://philapark.org/wp-content/uploads/Signed-Final-Reports-COMBINED-PPA-1.pdf, local copy in `research/sources/data_search_2026-10/ppa_audit_fy2025/`. The management's discussion and analysis (printed pp. 4-12, PDF pp. 7-15) was read in full. It is scanned, with no text layer. The notes and statements (PDF pp. 16-75) were not read.

**What it does not have.** There is no meter revenue, meter count or space count by area or district. The on-street figures are citywide, so the benchmark cannot yet be compared zone to zone.

What it does have, all verified on the page:

| Fact | Value | Page (printed) |
|---|---|---|
| Pay-by-plate kiosks citywide, "one kiosk per block" | 1,667 | 6 |
| Monthly payments through the mobile app | about 786,000 (82%) | 6 |
| Monthly credit-card payments at kiosks | 172,087 (17%) | 6 |
| App and card together, as a share of all parking payments | nearly 99% | 6 |
| Meter revenue collected through mobile payments | 80% of receipts | 6 |
| Act 9 threshold (the City's first tier) for FY2025 | **$48,966,144** | 6 |
| Expense to the City of Philadelphia, FY2025 (FY2024) | $108,484,366 ($116,547,269) | 10 |
| Expense to the School District of Philadelphia, FY2025 (FY2024) | **$0** ($7,174,560) | 10 |
| Net parking revenue paid to the Department of Aviation, FY2025 | $68,734,019 | 4, 11 |
| On-Street gross revenue growth, FY2024 to FY2025 | "nearly $12 million" | 10 |

The same pages explain why the City and School District payments fell: higher direct and support expenses of on-street operations (p. 11). Net Revenue is defined on p. 11 as tickets, meters, towing, storage, booting, auctions and other on-street revenue, less direct operating expenses, allocated support costs (excluding depreciation) and capital purchases.

What follows:
- **The School District received nothing in FY2025.** Net on-street revenue did not exceed the $48.97M threshold.
  - *Inference:* the line "Expense to the City" appears to include the Department of Aviation's $68.7M, a City department. That would leave about $39.8M of Act 9 net revenue to the City, below the threshold. The statement does not itemise this.
- **The model's allocation understates the threshold.**
  - `config/allocation.yaml` uses the statute's starting $35M and does not apply the § 6109(g)(3) escalator. The FY2025 threshold under the escalator is $48.97M.
  - The PBD share comes only from what the School District would otherwise receive. So the escalated threshold, together with the actual net revenue (gross revenue less on-street expenses), decides whether a PBD could be paid at all.
  - Net revenue pools tickets, meters and the rest, less all on-street costs. So in FY2025, an additional dollar of meter revenue would have reached the School District only after net revenue first covered the shortfall below the threshold (about $9M, by the inference above).
  - The fix is a config value, `general_fund_minimum_usd`, with a dated source and a year. Whether the model should allocate net rather than gross revenue is a modelling decision for later.
- **Transactions.** About 958,000 app and kiosk-card payments a month is about 11.6M a year, counting the remaining 1% at the same rate. At $40.8M of meter revenue that is about $3.50 per transaction (convenience fees are a separate line, section 4b). This is a cross-check for paid occupancy once rates and durations are known.
- **Spaces per block.** 15,406 metered spaces (Controller, 2020) over 1,667 kiosks (one per block, FY2025) is about 9 spaces per kiosk block. The two counts are five years apart. This is a cross-check for the RTKL inventory, and for the model's 10-space search unit.

## 6. Meter hours: where they are set (added 2026-10-17)

No public document gives Philadelphia's metered hours by area. Checked:

- **PPA Meters page** (https://philapark.org/meters/). No hours schedule. Its meterUP walkthrough uses one example block, 201 Columbus Boulevard: $1.50 an hour, a four-hour limit, free after 6 p.m. The page also says there are "no current plans to change the parking meter rates", so it predates July 2025. The example is a Center City long-term meter (four- and twelve-hour limits), which the July 2025 increase moved from $1.50 to $2.50. It is not an outer-zone rate, and it does not settle the $1.50 question in section 3.
- **PPA Laws & Enforcement page** (https://philapark.org/Enforcement). It gives officers' patrol hours, not meter hours: 6:30 a.m. to 11 p.m. Monday to Thursday, 6 a.m. to 3 a.m. Friday and Saturday, and 7:30 a.m. to 10 p.m. Sunday. It points to the Code for the rules.
- **Regulations of the Department of Streets** (compilation certified 2024-02-27, 244 pp., https://www.phila.gov/media/20240307174251/department-of-streets-regulations-20240227.pdf; local copy). It has only Title I (Sanitation) and Title II (Highway). A text search finds no "parking meter", "metered", "meter zone" or "limited time parking".
- **A 1982 bill**, seen only as a search snippet and not read. It is said to amend Chapters 12-900 and 12-1000 so that the Streets Department may set limited-time parking regulations in areas named by special ordinances. That would explain why Chapter 12-1000 states no hours: they would be set block by block, by Streets Department regulation, and shown on signs. Unverified.
- **Parkopedia block listings** (third party, unverified, conflicting). Different blocks show 8 a.m. to 6:30 p.m. Monday to Saturday; 8 a.m. to 10 p.m. Monday to Sunday; and Monday to Wednesday until 6:30 p.m. with Thursday to Saturday until midnight. These are not usable as data. They only suggest that hours vary by block, in both directions, around the model's one window per zone (8 a.m. to 8 p.m. Monday to Saturday; South Philadelphia 8 a.m. to 6 p.m.).

**Conclusion.** Priced hours stay a stated assumption until the RTKL meter inventory arrives. Request A asks for hours by meter. Nothing public says whether the model's windows are too long or too short.

## 7. Occupancy and payment compliance in two US programmes (added 2026-10-17)

These are out-of-city measurements. They bound what is plausible; they are not Philadelphia values. Both programmes set rates to hit an occupancy target, and Philadelphia's rates are not set that way.

### 7a. Seattle, 2019 Annual Paid Parking Study

SDOT, "2019 Paid Parking Study Report" (January 2020), https://www.seattle.gov/documents/Departments/SDOT/ParkingProgram/PaidParking/FINAL_2019_PaidParkingStudy_Report.pdf; local copy, pp. 10-11 table.

**Method.** Every paid block is counted from 8 a.m. to two hours after paid parking ends. Counts are taken on one Tuesday, Wednesday or Thursday in spring. Occupancy is counted cars over legal spaces, whether paid or not. The target is 70-85%, and paid parking ends at 8 p.m. in most areas.

**Space-weighted means over the 2019 columns.** These cover 30 areas and 10,875 spaces. Ballard Locks summer is dropped as a seasonal duplicate. Westlake North and South are dropped because they have no evening value. The script is `research/sources/data_search_2026-10/sdot_avg.py`.

| Period | Space-weighted mean occupancy |
|---|---|
| 9-11 a.m. | 0.72 |
| 11 a.m. - 6 p.m. | 0.84 |
| 6-8 p.m. | 0.75 |
| 9 a.m. - 8 p.m., hour-weighted (2, 7, 2 h) | **0.81** |
| Each area's busiest period | mean 0.87, range 0.29-1.02; a third of areas at 0.92 or above |

**Against the model.** The model's capacity-hour weighted occupancy over priced hours is about 0.54 (`revenue_gap_decomposition.csv`). That covers Monday to Saturday, 8 a.m. to 8 p.m. Its stated weekly peaks are 0.92 at high intensity and 0.62 at low intensity (`demand_baseline.yaml`). These are inside Seattle's range of busiest-period values.
- So a priced-hour mean of 0.54 is low next to a managed US programme, not high.
- Unless Philadelphia's metered curb is much emptier than Seattle's, occupancy is not the factor that inflates modelled revenue.
- Two differences make this a weak bound. Seattle counts midweek days only, while the model averages Saturday in. And Seattle's rates are tuned to its target.

### 7b. San Francisco, SFpark pilot evaluation

SFMTA, "SFpark Pilot Project Evaluation" (June 2014), https://sfmta.com/media/13816/download (full report, 73 pp.), with the summary at https://www.sfmta.com/sites/default/files/reports-and-documents/2018/04/sfpark_eval_summary_2014.pdf; local copies. Ch. 4, "Parking enforcement", printed pp. 80-81.

**Definition.** Payment compliance is the time spaces are paid and occupied, over the time they are occupied. It is measured with in-ground sensors plus meter payment data, on blocks that took part in all ten rate adjustments. The window is Monday to Saturday, 9 a.m. to 6 p.m.

| | Before | After |
|---|---|---|
| Weekdays | 45% | 54% |
| Saturdays | 53% | 60% |
| By area, weekdays (after) | Downtown 39% to Marina 66% | |

- Only 14 of nearly 200 blocks had compliance of 85% or more.
- **Disabled placards were "by far the largest source of non-payment".** California exempts placard holders from meter fees. The share of parked vehicles displaying a placard was 21% before and 20% after, in pilot areas.
- **Occupancy.** In the Fillmore case study, block groups at $2.00 before the pilot averaged 61-86% occupancy, weekdays 9 a.m. to 6 p.m. (printed p. 14 of the summary). The report gives no single average for all areas.

**What transfers to Philadelphia, and what does not.**
- Philadelphia exempts only wheelchair lift-equipped vans (§ 12-1117, section 4d). So San Francisco's main source of non-payment mostly does not apply, and its compliance figures are not Philadelphia's.
- *Inference:* if every placard car was unpaid, then among cars without placards San Francisco's weekday compliance was about 0.45/0.80 to 0.54/0.80, or 0.56-0.68. This is an upper reading. Some placard cars paid, and some of the non-placard unpaid time was attended vehicles or other permits.
- **For the gap.** The model assumes a paid share of 1.0. On its own, paid share would need to be 0.29 to close the gap, or about 0.33-0.37 once the benchmark-year rates are allowed for (section 1's 2.7-3.0x).
  - A paid share near San Francisco's non-placard range would close roughly half the gap. Taking 0.6 as an illustration, 3.45x becomes about 2.1x, and 2.7-3.0x becomes about 1.6-1.8x.
  - This is the largest single lever with outside evidence behind it. But the evidence is from another city, and only the RTKL sessions can measure Philadelphia's paid share.
- **For ingestion.** `config/ppa_ingest.yaml` turns paid minutes into occupancy by dividing by (1 - `unpaid_use.unpaid_share`). With 0.0, paid occupancy stands in for occupancy, which is a lower bound. If compliance in Philadelphia is anything like San Francisco's, that bound sits well below true occupancy. So the unpaid share is a load-bearing statement when the sessions arrive, not a formality. San Francisco's figures (an unpaid share of 0.40-0.55 across weekdays and Saturdays, before and after the pilot, or about 0.32-0.44 among non-placard weekday cars, by the inference above) are the only published range found, and they are out of city.

## Ranked shortlist (after the reset, Thursday 2026-10-22)

0. **Act 9 threshold** (section 5): FY2025 $48,966,144 in place of the unescalated $35M in `allocation.yaml`, with a dated source. This is the item that bears most on the PBD and School District rows; it is a model input, so it waits for the user's go-ahead to rerun.
1. **Benchmark-year rate schedule** (config + one benchmark row, about 20 lines and a test). The only verified item that moves the ratio (about 3.45x to about 2.7-3.0x by the estimate above).
2. **Nine free holidays** (config entry + small `priced_hours` change, about 10-20 lines). Up to -3% on hours.
3. **Revenue-per-space row** in `revenue_benchmark.csv`, after RTKL settles spaces; a few lines.
4. **Violations loader** (about 100 lines): 2012-2017 enforcement geography only. Lowest value for the gap.
5. **Wait for RTKL (due 2026-10-23, extended on 2026-10-22 to 2026-11-21)** for occupancy, hours by block and paid share, which nothing public supplies.
   - When the sessions are ingested, state `unpaid_use.unpaid_share` from evidence rather than leaving 0.0 (section 7b).
   - The paid share of 1.0 in `revenue.forecast` is the assumption with the most outside evidence against it (section 7b).

## What was not found
- Official enforcement days and hours by area.
- Any measured Philadelphia curb occupancy.
- Posted rates for University City, South Philadelphia, Fishtown; any PPA floors or ceilings.
- Any Philadelphia paid-share, compliance or placard-misuse rate for meters. San Francisco's are in section 7b.
- Meter revenue by area (IS2 statements and the FY2025 audit report citywide totals only). Payment counts are in the audit's MD&A (section 5).
- Any special ordinance setting meter fees outside Center City and University City (code library search, 2026-10-17: § 12-1005 is the only Philadelphia match). The $1.50 outer-zone rate is unresolved.
- Violations data after 2017.

## Unread leads
Planning Commission 2015 and 2021 Center City parking studies (curb text); Old City 2022 PDF; PPA audited financial statements or board materials; PPA ADA page and Bill 240613-AA; the CBS 2025 story on a $4M on-street net-revenue decline attributed to kiosks; the 1982 bill on Streets Department limited-time regulations (section 6); SDOT's annual study data on data.seattle.gov (block level, 2014 on).

## Needs the user to fetch
1. **Resolved; no hours found.** This URL now redirects (checked 2026-10-17) to Philadelphia Code § 12-1117 on American Legal Publishing's code library, saved as `philadelphia-pa-1.pdf` (see 4d). That section has no meter hours. The meter chapter, Chapter 12-1000, has none either (see section 1), so hours come from signs or regulation and are left to the RTKL inventory. Original citation: **City of Philadelphia, "Parking meter laws" (2018), https://www.phila.gov/media/20180806114511/Parking-meter-laws.pdf**: returned 403 to automated download. Need the days and hours metered parking is enforced and holiday rules; it may be the official source for input 1. Save under `research/sources/data_search_2026-10/`.
2. **City Planning Commission, "2015 Parking Study", https://www.phila.gov/media/20190724160659/2015_Parking_Study.pdf** (optional): whether it reports on-street occupancy; only off-street figures were seen in snippets.
3. **PPA, "ADA Accessible Parking", https://philapark.org/adaparking** (optional): exact wording of the 60-minute allowance.

## Documents read
Controller PPA audit 2020 (keyword pages); Planning Commission Center City Parking Study 2020 (keyword pages); Old City Parking Study 2022 web page; PhillyVoice 2025-06-26; PPA Meters page; PPA Holiday page; Inquirer 2022-04-06; PPA IS2 March 2025 (p. 1); PPA IS2 June 2025 (p. 1); Carto `parking_violations` (schema and aggregate queries). The IS2 URL for August 2026 returned 404. Added 2026-10-17: PPA Laws & Enforcement page; Regulations of the Department of Streets (2024, text search); SDOT 2019 Paid Parking Study (occupancy table); SFpark Pilot Project Evaluation (Ch. 4) and its summary.
