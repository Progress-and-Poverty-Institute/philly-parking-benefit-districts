# Demand-based curb parking pricing model for Philadelphia - Claude

*Extracted from Claude AI on 4/28/2026, 5:41:52 PM*

---

# Demand-Based Curb Parking Pricing in Philadelphia: A Comprehensive Research Review for Model Development

*Prepared for Russell Richie, Progress and Poverty Institute / 5th Square Advocacy*
*April 2026*

This review surveys the theory, empirical literature, implementation experience, Philadelphia institutional context, and modeling methodology relevant to building a quantitative model of demand-responsive curb parking pricing for Philadelphia. It is structured to support three complementary deliverables — a PPI/5th Square white paper, an academic paper, and an operational pricing or simulation tool — and is written with deliberate skepticism toward weakly-supported claims, including some by Donald Shoup and his collaborators.

## 1. Theory and Economics of Curb Parking Pricing

### 1.1 The Shoupian core argument

Donald Shoup's *The High Cost of Free Parking* (Planners Press / APA, 2005; updated 2011) and the edited follow-up volume *Parking and the City* (Routledge, 2018) form the canonical case for performance-based curb pricing. The core argument has three parts: (i) underpriced curb parking generates "cruising" externalities (circling cars contribute disproportionately to congestion, emissions, and crash risk); (ii) the "right price" for curb parking is the lowest price that leaves about one of every eight spaces empty — Shoup's famous **85% occupancy target**; (iii) revenues from properly priced curb parking should be returned to the metered neighborhoods through **parking benefit districts (PBDs)** in order to build a constituency for pricing reform. Shoup's *Parking Benefit Districts* article (*Journal of Planning Education and Research*, 2024) is the most up-to-date statement of the PBD argument and reviews case studies from Pasadena, Austin, Mexico City (EcoParq), and Beijing.

Critical caveats Russell should keep in mind. The 85% rule is a **rule of thumb, not a derived optimum** — Shoup himself describes it as "the lowest price that leaves one space free," but the actual welfare-maximizing occupancy is a function of the elasticity of demand, the density of cruising, walk-time disutility, and substitution to off-street parking and other modes. Several economists (notably Inci, 2015, and Arnott & Inci, 2006, 2010) have shown that under standard assumptions the welfare-maximizing curb price is the price that **eliminates cruising entirely without leaving curb parking unsaturated** — which is conceptually different from "85%" and may correspond to different occupancies depending on local conditions. In the Arnott–Inci framework cruising is a stock variable whose density adjusts to clear the market; the optimal policy raises the price until cruising is just driven to zero. This is a more rigorous foundation for the model than the 85% heuristic and should be the underlying theoretical structure cited in the academic paper. [REPEC](https://ideas.repec.org/a/eee/juecon/v60y2006i3p418-442.html)

### 1.2 Welfare economics: cruising, congestion, deadweight loss, distribution

The classic externality story is that underpricing curb parking creates excess demand → cars cruise → cruising imposes congestion, emissions, pedestrian/cyclist crash risk, and bus delay externalities on third parties. The deadweight loss has two pieces: (a) the standard Harberger triangle from underpricing, and (b) the additional waste from search frictions ("rent-seeking through queueing"). Shoup's well-known stylized estimate that ~30% of urban traffic in some downtowns is cruising (Shoup, 2006, "Cruising for Parking," *Transport Policy*, 13(6): 479-486; Hampshire & Shoup, 2018, *Journal of Transport Economics and Policy*) has been **challenged**: van Ommeren, Wentink & Rietveld (2012) using Dutch self-reported data find average cruising time of only ~36 seconds per trip in a city with consistent on- and off-street pricing; Hampshire & Shoup (2018) themselves acknowledge their share-of-traffic-cruising estimates are highly dependent on assumptions about trip lengths. Russell should treat the headline "30% of traffic is cruising" claim as an upper-bound estimate from saturated, underpriced contexts rather than a generic stylized fact. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0965856417302884)

Distributional incidence is theoretically ambiguous. Curb parking users in Philadelphia are not uniformly affluent (delivery workers, contractors, off-shift hospital staff), but the population of car owners in dense Philadelphia neighborhoods is on average **substantially higher-income than the population of carless households** — about a third of Philadelphia households are car-free, concentrated in lower-income communities (data Russell's organization has cited). Manville (2017, 2021, and TREC seminar 2019, "Congestion Pricing Efficiency and Equity") has argued that curb and congestion pricing are progressive *relative to the existing transportation finance system*, which is heavily regressive (gas taxes, sales taxes, fee structures). This is an important framing argument for the white paper. [5th Square](https://www.5thsq.org/2023_issues)[Streetsblog Los Angeles](https://la.streetsblog.org/2019/01/16/the-benefits-of-congestion-pricing)

### 1.3 Performance-based vs. flat-rate pricing

Theoretically, time- and place-varying pricing dominates flat pricing whenever marginal external cost varies in space and time, which is virtually always the case in dense cities. The empirical question — addressed in §3 — is whether the bureaucratic costs and political risks of frequent rate changes outweigh the welfare gains relative to a coarser block-of-time, block-of-zone tariff. A reasonable working hypothesis for Philadelphia: a **Seattle-style "annual price review with time-of-day differentiation"** delivers most of the welfare gain of an SFpark-style 6-week adjustment cycle, with substantially lower implementation overhead.

### 1.4 Land-value-tax / Georgist framing

Curb space is publicly-owned land. The Georgist argument — particularly relevant given Russell's role at the Progress and Poverty Institute — is that the rent generated by scarce, location-specific curb space is a pure public asset and should be captured by the public, not given away to motorists who happen to live nearby (or to suburban commuters). Under a strict LVT framing:

- **Free curb parking is a privatization of the rent on public land.** The going market rent for off-street parking in Center City Philadelphia exceeds $300/month; capitalizing that rent over a typical 10' × 20' parking space at ~200 sq ft of street area implies an annualized land value transfer in the thousands of dollars per space per year being given away under the current $35–$75 residential permit regime.
- A Georgist-flavored white paper can frame curb pricing as "**land value capture for the curb**" — analogous to LVT for parcels. Shoup himself makes a Georgist argument in *The High Cost of Free Parking* (Ch. 17, "Taxing Parking") and in his 2011 ACCESS piece on parking benefit districts: market-priced residential permits act like a progressive income tax (richer neighborhoods → higher permit prices), where flat residential permits act like a regressive flat tax. [Accessmagazine](https://www.accessmagazine.org/wp-content/uploads/sites/7/2016/11/access49-web-almanac.pdf)
- This connects naturally to PPI's broader LVT program: curb pricing is a low-political-cost entry point to **rent-capture more generally**, since (a) it doesn't require state constitutional amendment as full LVT does in Pennsylvania, and (b) it has a built-in efficiency argument (eliminating cruising) that doesn't require winning the equity argument first.

### 1.5 Recent (post-2020) academic literature

Notable post-2020 work:

- Lehner & Peer (2019, *Transportation Research A* 121: 177-191), "The price elasticity of parking: a meta-analysis." This is the highest-quality recent meta-analysis (50 studies, seemingly unrelated regression), and replaces Concas & Nayak (2012) as the authoritative reference. **Cite this as the primary source for elasticity priors.** [Vienna University of Economics and Business](https://research.wu.ac.at/en/publications/the-price-elasticity-of-parking-a-meta-analysis-3/)
- Inci, E. (2015), "A review of the economics of parking," *Economics of Transportation* 4(1): 50-63. Best concise theoretical review.
- Arnott, Inci & Rowse (2015), "Downtown curbside parking capacity," *Journal of Urban Economics* 86: 83-97 — extends Arnott-Inci to endogenous curb capacity.
- Hess, D. B. (ed.) (2024), *The Shoup Doctrine: Essays Celebrating Donald Shoup and Parking Reform* (Routledge) — 33 chapters, 37 contributors, probably the most comprehensive recent state-of-the-field volume. [Booked on Planning](https://www.bookedonplanning.com/post/the-shoup-doctrine)
- Several papers on **agent-based and reinforcement-learning approaches** to dynamic pricing (Fabusuyi & Hampshire, 2018, *Transportation Research A*; Saharan, Bawa & Kumar, 2020 and similar in *Algorithms* and *Expert Systems with Applications*) — these are the methodological frontier for the operational deliverable but should be approached skeptically since most are simulation-only with thin empirical validation.

## 2. Empirical Literature on Parking Demand Elasticities

### 2.1 The headline numbers

Two meta-analyses anchor the literature:

- **Concas & Nayak (2012), "A Meta-analysis of Parking Pricing Elasticity"** (Center for Urban Transportation Research, USF; TRID 1130741). Baseline direct elasticity of parking demand: **−0.39**, broadly consistent with the long-standing −0.30 rule of thumb. Estimates are highly site-specific. [Semantic Scholar](https://www.semanticscholar.org/paper/A-Meta-analysis-of-Parking-Pricing-Elasticity-Concas-Nayak/9987448a5f0d8e7cc26b858e29d406d39e2b1b6c)
- **Lehner & Peer (2019)**, *Transportation Research A* 121: 177-191. 50 studies; distinguishes elasticity of occupancy (EPO), dwell time (EPD), and volume (EPV); finds substantial differences between revealed-preference (RP) and stated-preference (SP) estimates, with SP studies systematically producing larger elasticities. **Recommend Russell anchor on RP estimates only.** [REPEC](https://ideas.repec.org/a/eee/transa/v121y2019icp177-191.html)

For practical priors in a Philadelphia model:

- Short-run EPV: ~ −0.3 to −0.5 (most observed central tendency).
- Long-run/equilibrium: more elastic, often in the range −0.6 to −1.0 because of substitution to off-street, transit, mode shift, time-shift.
- Dwell-time elasticity: substantially smaller in absolute value (~ −0.1 to −0.2). This matters because a price increase that reduces dwell time *more* than it reduces volume can leave occupancy roughly unchanged — a phenomenon documented at SFpark.

### 2.2 Cross-elasticities

Less well-documented but important. Calthrop, Proost & Van Dender (2000, *Urban Studies*) and Inci's (2015) review summarize: curb-to-garage cross-elasticity is positive and substantial when off-street capacity is available; curb-to-transit is positive but small; curb-to-ride-hail is increasingly relevant but understudied. **Russell's model should include explicit curb-garage substitution terms, with garage prices held exogenous in baseline runs and made endogenous in advanced versions.**

### 2.3 Time-of-day, day-of-week, spatial spillover

Pierce & Shoup (2013), "Getting the Prices Right," *JAPA* 79(1): 67-81 — the canonical SFpark elasticity paper — shows elasticities vary substantially by time of day and trip purpose, and that drivers respond more strongly after multiple price adjustments (suggesting a learning/awareness component). **Their central elasticity estimates are not endogeneity-corrected**, a limitation pointed out by Millard-Ball, Weinberger & Hampshire (2013, JAPA, comment) and again in their 2014 paper. The endogeneity is severe: SFpark adjusted prices in response to observed occupancy, which mechanically biases naive elasticity estimates. [Streetsblog](https://sf.streetsblog.org/2013/08/07/shoup-sfpark-yields-promising-results-lessons-for-demand-based-pricing)[Ucla](https://millardball.its.ucla.edu/wp-content/uploads/sites/22/2022/06/Millard-Ball_Weinberger_Hampshire_2014_Assessing_the_impacts_SFPark.pdf)

Spatial spillover to nearby unmetered streets is **a first-order concern in Philadelphia**, where metered Center City and University City directly abut residential permit zones. Alemi, Rodier & Drake (2018, *Transportation Research A*), "Cruising and on-street parking pricing: A difference-in-difference analysis…" provides one of the few credible spatial-spillover studies and finds non-trivial substitution.

### 2.4 Methodology

The highest-quality designs are:

- **Difference-in-differences with control blocks** (SFpark; Chatman & Manville 2014; Millard-Ball et al. 2014).
- **Discrete-choice estimation** using stated/revealed preference surveys (well-summarized in Hess & Polak's various works).
- **Structural models** — e.g., Fabusuyi & Hampshire (2018), "Rethinking performance-based parking pricing," *Transportation Research A*, which estimates a forward-looking pricing model with embedded elasticities.

The cleanest natural experiment to date is probably Ottosson, Chen, Wang & Lin (2013) on Seattle, which preceded and seeded the Seattle program, but it has only modest external validity for Philadelphia.

### 2.5 Heterogeneity

Lehner & Peer's meta-analysis confirms that elasticity varies substantially with land-use density, mix, income, transit availability, and most importantly **with the level of price already in place** (demand becomes more elastic as prices rise — consistent with simple linear demand). Russell should not assume a constant elasticity citywide; the model should have neighborhood-specific elasticities estimated either from local data or borrowed from comparable contexts using a hierarchical Bayesian approach.

## 3. Dynamic / Demand-Responsive Pricing Implementations

### 3.1 SFpark (San Francisco)

The most studied and most cited program. Key sources:

- **SFMTA (2014), SFpark Pilot Project Evaluation and SFpark Pilot Project Evaluation Summary** (sfmta.com/reports). Headline pilot-area results: parking availability hit the 60-80% target 31% more often, blocks "full" 16% less often, search time down 43% (~5 min), VMT from cruising down 30%, citations down 23%, and **average meter rates dropped $0.11/hr (4%)**. [San Francisco Municipal Transportation Agency](https://www.sfmta.com/press-releases/sfpark-evaluation-shows-parking-easier-cheaper-pilot-areas)
- **Pierce & Shoup (2013)**, *JAPA*, "Getting the Prices Right." Optimistic interpretation.
- **Millard-Ball, Weinberger & Hampshire (2014)**, *Transportation Research A* 63: 76-92, "Is the curb 80% full or 20% empty? Assessing the impacts of San Francisco's parking pricing experiment." More skeptical, instruments for endogeneity, finds meaningful but smaller effects.
- **Chatman & Manville (2014)**, *Research in Transportation Economics* 44: 52-60, "Theory versus implementation in congestion-priced parking: An evaluation of SFpark, 2011–2012." **Key skeptical finding**: a price system that targets *average* occupancy may not improve parking availability at peak times and may not reduce cruising; price changes had no detectable association with parking duration, turnover, or carpooling. Their conclusion: cities targeting cruising should price on **minimum vacancy**, not average occupancy, and price changes likely need to be larger. [REPEC](https://ideas.repec.org/a/eee/retrec/v44y2014icp52-60.html)
- Hampshire & Shoup (2018), *JTEP*, "What Share of Traffic is Cruising for Parking" — methodologically improved but still relies on strong assumptions.

**Honest summary for Russell**: SFpark improved availability and reduced cruising in pilot areas, but the magnitude of the cruising reduction is contested, and the program's implementation cost (federal grant ~$23M, sensors, integration) was substantial. Sensors were ultimately abandoned for cost reasons; the citywide expansion runs largely on transaction data + occasional license-plate-recognition surveys. **This is good news for Philadelphia**: a sensor-free program is feasible.

### 3.2 LA Express Park

Launched May 2012 in downtown LA with a $15M federal grant + $3.5M city match, expanded to Westwood (2015), Hollywood (2018), Venice (2019). Documented by LADOT; Trellint (formerly Conduent) is the operating vendor. ITS Knowledge Resources summary (itskrs.its.dot.gov/2024-b01821): **37% reduction in parking duration in downtown LA, 26% in Venice, 19% in Hollywood, 10% increase in availability, 16% revenue increase in some areas**. Westwood results were marginal because the city's $2/hr cap forced most meters to bind at the cap. [Laexpresspark](https://www.laexpresspark.org/about-la-expresspark/)[Trellint](https://trellint.com/insights/la-express-park-parking-smarter-with-demand-pricing)

LA Express Park's pricing engine adjusts rates seasonally rather than every 6 weeks, with time-of-day differentiation. The 2024 LADOT RFP (cityclerk.lacity.org/onlinedocs/2024/24-0061_rpt_DOT_01-16-24.pdf) is a useful reference for what an integrated parking management system (IPMS) procurement looks like, including back-end data analytics, pricing engine, and parking guidance systems.

### 3.3 Seattle — the most institutionally relevant model for Philadelphia

Seattle's **performance-based parking pricing program** (SDOT, established 2010 via Seattle Municipal Code 11.16.121) is in many ways a better template for Philadelphia than SFpark, for three reasons: (i) it operates **without sensors**, using transaction data + manual occupancy counts feeding a statistical model; (ii) prices change **once a year** by ±$0.50 increments; (iii) it uses largish price zones rather than individual blocks. Detailed annual reports document the rate adjustment process; the most recent is the *2024 Paid Parking Annual Report* (June 2025). Target: 1-2 spaces available per block; occupancy target 70-85%. Seattle's work has been published academically (e.g., Ottosson et al. 2013; Fiez & Ratliff, 2018, "Data-Driven Spatio-Temporal Analysis of Curbside Parking Demand: A Case Study in Seattle," arxiv:1712.01263). [Parking Reform Atlas + 4](https://www.parkingreformatlas.org/parking-reform-cases-1/seattle-performance-based-parking-pricing-program)

**Russell should treat Seattle as the operational benchmark.** It demonstrates that a transaction-based, annually-adjusted, zone-based system can deliver Shoupian outcomes at low cost, which fits the PPA's institutional capacity and Philadelphia's political risk tolerance.

### 3.4 Washington, D.C.

DDOT's Performance-Based Parking Pilot launched in 2008 in the Ballpark District (sponsored by Councilmember Tommy Wells), expanded to Columbia Heights and H Street NE. Mixed results — Metropolitan Planning Council's evaluation noted only 9-10% of metered blocks reached the 85% threshold in the early period. DDOT's curbFlow pilot (2019-2020) reduced double-parking by 64% via reservable commercial loading zones — **highly relevant to Philadelphia given chronic UPS/Amazon double-parking** that has cost UPS ~$9M in citations. [Pedshed + 2](https://pedshed.net/?p=170)

### 3.5 Pittsburgh — the most institutionally-relevant Pennsylvania case

Pittsburgh's experience matters because it shows what's possible **under Pennsylvania state law** with city-controlled parking (Pittsburgh Parking Authority is a separate institution, but PA's enabling legislation framework is comparable in some respects). Key milestones:

- 2013-2015: CMU Tepper professors Mark Fichman and Stephen Spear ran a multi-year demand-responsive pricing experiment near CMU, monthly rate adjustments. [M21](https://mobility21.cmu.edu/can-dynamic-pricing-help-ease-pittsburghers-parking-headaches/)
- 2014: City ordinance authorized expansion to Downtown, Squirrel Hill, North Side, Shadyside. [PublicSource](https://www.publicsource.org/can-dynamic-pricing-help-ease-pittsburghers-parking-headaches/)
- 2023: Pittsburgh City Council unanimously approved dynamic pricing for **Lawrenceville** (sponsored by Councilor Deb Gross), with revenue dedicated to neighborhood mobility infrastructure (a parking benefit district structure). [WESA](https://www.wesa.fm/politics-government/2023-10-24/lawrenceville-dynamic-street-parking-prices)[WESA](https://www.wesa.fm/politics-government/2023-10-24/lawrenceville-dynamic-street-parking-prices)
- 2022-2024: Pittsburgh **Smart Loading Zones** pilot — 70% turnover increase, 60% reduction in average park duration. [City of Pittsburgh](https://engage.pittsburghpa.gov/smart-loading-zones)

**The Pittsburgh case is the single most important domestic comparator for Russell** — same state, same legal framework, same enabling-legislation environment, working PBD-style precedent.

### 3.6 Other cities and international

- **Calgary**: zone-based, large zones, simple algorithm — referenced by Seattle and parking reform advocates.
- **NYC**: largely flat-rate metered, but DOT's "PARK Smart" program ran demand-based pilots in Park Slope, Greenwich Village, and the Upper East Side starting 2008-2009; NYC's recent congestion pricing rollout (Jan 2025) has shifted attention.
- **Boston**: Back Bay performance pricing pilot 2017-2019.
- **Chicago**: Chicago infamously sold its meters in a 75-year concession in 2008, sharply constraining any dynamic-pricing reform — **a cautionary tale**.
- **Madrid**: Servicio de Estacionamiento Regulado (SER), with differential rates by emissions class.
- **Amsterdam**: among the most aggressive curb-pricing regimes worldwide; van Ommeren et al. work uses Amsterdam data.
- **Mexico City (EcoParq)**: 26,000 metered spaces with 30% of revenue returned to neighborhoods — the cleanest implementation of Shoup's PBD model. [Sage Journals](https://journals.sagepub.com/doi/10.1177/0739456X221141317)

### 3.7 Algorithmic approaches

Three families:

1. **Rule-based threshold adjustment** (SFpark, Seattle, LA Express Park): if avg occupancy in zone z, time-band t > upper threshold, raise price by Δ; if < lower threshold, lower by Δ; otherwise no change. Simple, transparent, auditable. **Recommended baseline.**
2. **Statistical / forward-looking optimization**: regress occupancy on price and covariates, solve for price that hits target occupancy (Fabusuyi & Hampshire 2018; LA Express Park's pricing engine uses something like this). More efficient but less transparent.
3. **Machine learning / reinforcement learning**: Q-learning, deep RL, multi-agent RL (Saharan et al. 2020; Tian et al. 2023 in *Algorithms*; Mitsopoulou & Kalogeraki 2018). **Honest assessment: most of this literature is simulation-only and uses synthetic demand. Operational deployment is rare. Useful for the academic paper but probably overkill — and politically risky — for a real Philadelphia rollout.** [MDPI](https://www.mdpi.com/1999-4893/16/1/32)[DOAJ](https://doaj.org/article/d8b8f2d7c524402d99a3092a846aa680)

### 3.8 Data infrastructure

Three tiers, in increasing cost order:

- **Tier 1 (cheapest, recommended starting point)**: Transaction data from pay-by-plate meters and meterUP/Parkmobile + periodic LPR or manual occupancy surveys. This is the Seattle approach. PPA is already collecting most of this data.
- **Tier 2**: Add ML-based occupancy estimation from transaction patterns (well-developed in academic literature; see Yang, Qian et al., various papers).
- **Tier 3**: In-pavement sensors (SFpark v1, LA Express Park). High capex, high opex, frequent breakage. Both SFpark and LA found that sensor data quality degraded over time. **Not recommended for Philadelphia.**

### 3.9 Vendor landscape

- **IPS Group** — single-space and multi-space meters; widespread in mid-size US cities.
- **Flowbird** (formerly Parkeon / Cale) — pay stations and back-end management; significant US footprint.
- **Parkmobile / EasyPark** — mobile payments. **PPA's meterUP is a Parkmobile product.**
- **Trellint** (formerly Conduent / Xerox) — full IPMS, runs LA Express Park.
- **Passport Labs** — payments + analytics.
- **Automotus, curbFlow, Coord (now Populus)** — newer entrants, curb management and digital reservation.

### 3.10 Political economy

The single most important framing decision is **revenue-neutrality vs. revenue-positive**. SFpark and Seattle both initially marketed themselves as **fundamentally about availability, not revenue**, with the empirical finding that average rates often *fell* in pilot areas (SFpark's 4% average decline). This neutralized "money grab" critiques. The same playbook will be necessary in Philadelphia, particularly given the PPA's reputation. Equity provisions (low-income exemptions, PBD structure, return of revenue to local mobility improvements) buy critical political cover. Business-district reactions tend to flip from opposition to support once turnover increases visibly — Old Pasadena is the canonical case.

## 4. Philadelphia Institutional Context

### 4.1 PPA governance and state control

The Philadelphia Parking Authority is **a Pennsylvania state authority**, not a city department, since the **2001 state takeover (Act 22 of 2001)** under the Republican legislative majority and Gov. Schweiker. The takeover was upheld by the PA Supreme Court (*City of Philadelphia v. Philadelphia Parking Authority*, 2003). The Governor appoints PPA board members. This is the central political constraint on parking reform in Philadelphia. [Philadelphia](https://philadelphia.wiki/a/Philadelphia_Parking_Authority)[FindLaw](https://caselaw.findlaw.com/court/pa-commonwealth-court/1239620.html)

### 4.2 Revenue distribution

Revenue allocation is fixed by **Act 9 of 2005** (codifying the 1994 On-Street Agreement of Cooperation), then **Act 39 of 2011**, then **Act 84 of 2012**, which set a **$35M/year minimum payment to the City General Fund** with annual escalators tied to PPA gross revenue increases; remaining net on-street revenue goes to the **School District of Philadelphia**. Recent figures: [PA General Assembly + 2](https://www.legis.state.pa.us/WU01/LI/TR/Reports/2013_0041R.pdf)

- FY2017: $35.35M to General Fund + $9.77M to SDP = $45.1M total. [Philadelphia Parking Authority](https://philapark.org/2017/05/ppa-funding-to-the-school-district-how-does-it-work/)
- 2021 City General Fund minimum: ~$41.7M; SDP received ~$0 due to a disputed accounting that was later partially reversed (PPA agreed to let SDP keep $10.8M of a claimed $14.4M "overpayment"). [Billy Penn](https://billypenn.com/2022/10/03/philadelphia-parking-authority-history-patronage-politics-tickets/)[NBC10 Philadelphia](https://www.nbcphiladelphia.com/news/local/philly-school-district-gets-to-keep-10-8m-overpayment-from-ppa/3227092/)
- City Controller Rebecca Rhynhart's 2020 audit found the District may have lost $77.9M cumulatively due to PPA financial management. Council's 2022 hearings (Helen Gym resolution) escalated the political conflict. [WHYY](https://whyy.org/articles/city-controllers-report-says-ppa-needs-to-tighten-finances-to-better-fund-philly-schools/)

**Implication for Russell's model**: any revenue forecast under different pricing rules needs to model the **discrete bargaining** between the General Fund minimum and the residual to SDP. Revenue increases under pricing reform will accrue largely to the School District, which is a very strong political messaging asset for the white paper.

### 4.3 Current rate structure (as of 2026)

Effective July 1, 2025 — first increase in over a decade, recommended by the city's Tax Reform Commission and adopted in the FY26 budget: [Philadelphia Parking Authority](https://philapark.org/2025/06/changes-to-philadelphia-parking-meter-rates-effective-july-1-2025/)

- **Center City Core** (Arch–Locust × 4th–20th): **$4.00/hr** (was $3.00). [WHYY](https://whyy.org/articles/ppa-street-parking-rates-increase-center-city-philadelphia/)
- **Center City Area** (Spring Garden–Bainbridge × Schuylkill–Delaware, excluding Core): **$3.50/hr** (was $2.50). [WHYY](https://whyy.org/articles/ppa-street-parking-rates-increase-center-city-philadelphia/)
- **Center City Long-term meters** (4-hr and 12-hr): **$2.50/hr** (was $1.50). [WHYY](https://whyy.org/articles/ppa-street-parking-rates-increase-center-city-philadelphia/)
- Neighborhood corridors: typically $1.50–$2.00/hr.
- **MeterUP (Parkmobile) tiered pricing** is in place in several zones — progressive rates that increase with session length, though not signed on the street. [ParkMobile](https://support.parkmobile.io/hc/en-us/articles/36854964319643-Philadelphia-Parking-Authority-MeterUP-s-Tiered-Pricing)
- Expected additional revenue from the 2025 increase: ~$4M/year. [WHYY](https://whyy.org/articles/ppa-street-parking-rates-increase-center-city-philadelphia/)

### 4.4 Residential Permit Parking (RPP)

Reformed September 1, 2024, via City Ordinance Bill #240335 (sponsor: Councilmember Mark Squilla): [The Philadelphia Inquirer](https://www.inquirer.com/news/philadelphia/residential-parking-permit-prices-philadelphia-2024-ppa-20240805.html)

- Flat **$75/year** per vehicle (was sliding scale: $35/$50/$75/$100/$100…). [Jegtheme](https://www.experiencepa.com/parking-permits-in-philadelphia/)[WHYY](https://whyy.org/articles/philadelphia-vehicle-permits-change-limits-rate/)
- Cap of **3 permits per household**. [Philadelphia Parking Authority](https://philapark.org/residential-parking-permit/)[WHYY](https://whyy.org/articles/philadelphia-vehicle-permits-change-limits-rate/)
- **Low-income waiver** for first vehicle (TAP, CAP, CRP, Senior Discount eligibility). [Jegtheme](https://www.experiencepa.com/parking-permits-in-philadelphia/)
- Motorcycle/scooter: $50/yr. [Philadelphia Parking Authority](https://philapark.org/residential-parking-permit/)
- Temporary permits sharply increased (15-day: $15→$75; 30-day: $30→$150) effective Aug. 1, 2024. [NBC10 Philadelphia](https://www.nbcphiladelphia.com/news/local/ppa-more-than-double-cost-residential-parking-permits/3937013/)
- After July 1, 2026, the Department may increase the application fee by regulation, no more than once every three years and not exceeding regional CPI-U growth. [AmLegal](https://codelibrary.amlegal.com/codes/philadelphia/latest/philadelphia_pa/0-0-0-286076)

The previous $35/yr base had been unchanged since 1983. Even at $75/yr, the permit price is **roughly 1-2% of the market rent** for a comparable off-street space in the same neighborhood — i.e., a >98% subsidy for on-street storage of private vehicles on public land. This is the single strongest lever for the white paper's headline argument. [The Philadelphia Inquirer](https://www.inquirer.com/news/philadelphia/residential-parking-permit-prices-philadelphia-2024-ppa-20240805.html)

### 4.5 Recent reform proposals and politics

- **Cherelle Parker administration (2024-)**: generally pro-driver in rhetoric, but signed off on the 2025 meter increase and the 2024 RPP reform. Parker's FY26 and FY27 budgets retain the Zero Fare Program funding ($25M proposed for FY27), suggesting some openness to mode-shift policies. [5thsqadvocacy](https://www.5thsqadvocacy.org/)
- **Council**: Mark Squilla (1st District, sponsor of RPP reform) is the most active on parking; Jamie Gauthier (3rd District, West/Southwest Philly) and Nicolas O'Rourke (At-Large, Working Families) have been allied with urbanist priorities. Helen Gym is no longer on Council.
- **5th Square's 2024 platform** explicitly called for "dynamic-priced parking, basing meter rates on demand." [5th Square PAC](https://www.5thsq.org/2024_issues)
- **DVRPC's 2020 report** *Strategies for Managing Residential Parking in Philadelphia* (Publication #20026) is the only major public-sector study of the RPP program in the past decade and is a critical reference.

### 4.6 State law constraints

- **No general preemption** of dynamic pricing — Pittsburgh's Lawrenceville pilot (2023) operates without state enabling legislation.
- The PPA's enabling statute (Pennsylvania Parking Authority Law, 53 Pa. C.S. §§ 5501-5517) gives it broad authority over on-street parking management in Philadelphia, including rate-setting subject to City Council approval of the underlying ordinance (Title 12 of the Philadelphia Code).
- **Residential permit pricing requires City Council action** (as the 2024 Squilla bill demonstrated), and any expansion of RPP zones requires a petition process under §12-2702 et seq.
- Demand-responsive metered pricing **does not require state legislation** but does require Council authorization for rate changes via the traffic code. [WHYY](https://whyy.org/articles/ppa-street-parking-rates-increase-center-city-philadelphia/)

## 5. Modeling Methodology

### 5.1 Discrete choice models

The standard parking-choice modeling approach is a **nested logit** of mode, parking type (curb, off-street, garage, transit + walk, ride-hail), and location. Hess & Polak's various papers are the standard methodological references. **Mixed logit** with random coefficients on price captures heterogeneity in willingness-to-pay across user types (residents, commuters, visitors, commercial). For the academic paper, a **mixed logit estimated on stated-preference + revealed-preference data** is the credibility frontier.

### 5.2 Spatial econometrics

Spatial spillover is endemic in curb pricing — pricing a block redirects demand to adjacent unmetered or differently-priced blocks. Approaches:

- **Spatial Durbin / SAR / SEM models** with row-standardized contiguity weights at the block-face level.
- **Difference-in-differences with explicit spillover terms** (Clarke 2017's spillover-robust DiD; Butts 2021 working paper).
- For simulation, an **agent-based model with explicit search behavior** on a road network captures spillover most directly (see §5.3).

### 5.3 Agent-based simulation

- **MATSim**: open-source, Java-based, well-suited to citywide simulation with curb parking modules (the parking-search contrib module). Steep learning curve.
- **SUMO + custom Python agents**: lighter, more flexible for prototyping.
- **Custom Python ABM**: Mesa or AgentPy; appropriate for a focused academic paper but harder to scale to all of Philadelphia.
- **Equilibrium models with cruising**: Arnott-Inci style closed-form models calibrated to Philadelphia parameters can complement simulation and provide analytical benchmarks. Geroliminis (2015) and related work on "macroscopic fundamental diagram of parking" extend this.

### 5.4 ML for occupancy prediction

Given limited sensor coverage, the model needs to estimate occupancy from transaction data. Approaches that work:

- **Gradient-boosted trees (XGBoost / LightGBM)** predicting block-level occupancy from transactions, time, weather, events, calendar.
- **Bayesian state-space models** (PyMC or Stan) propagating uncertainty in occupancy estimates into pricing decisions.
- **Transactions-to-occupancy gap models**: account for unpaid parking (residential permit holders, disabled placards, scofflaws) — Hampshire & Shoup (2018) and Yang & Qian (2017) provide methods.

### 5.5 Welfare estimation

- **Consumer surplus** under nested logit: standard logsum × (1/marginal-utility-of-income), differenced before/after pricing.
- **Cruising deadweight loss**: ½ × cruising VMT × marginal external cost of cruising mile (combine EPA SC-CO2, congestion delay cost, crash cost from Anderson & Auffhammer 2014). Calibrate cruising VMT to Hampshire-Shoup or local survey.
- **Producer / public surplus**: net revenue change.
- **Welfare incidence by income decile**: requires linking ACS census tract demographics to predicted parking demand by location and trip purpose.

### 5.6 Revenue forecasting

Run scenarios under different elasticity assumptions:

- Pessimistic (E = −0.7): revenue rises with price up to a clear maximum, after which it falls.
- Central (E = −0.4): revenue rises monotonically through plausible price ranges.
- Optimistic (E = −0.2): revenue rises sharply.

Provide credible intervals via bootstrap or Bayesian posterior samples. **Don't commit to a point forecast.**

### 5.7 Curb space as multi-use

Frame curb in terms of competing uses with implicit hourly land rents: parking, loading, transit (bus/trolley) lanes, bike lanes, parklets, dining. Schaller (2018), Roe & Toocheck (2017, ITE), and the National Association of City Transportation Officials' *Curb Appeal* / *Blueprint for Autonomous Urbanism* / *Curbside Management* documents are the operational references. **The 5th Square study citing Toronto's CaféTO program ("49× more revenue than parking fees") is a useful headline number** but should be presented with caveats — it's gross retail revenue, not curb rent capture. [5th Square](https://www.5thsq.org/2023_issues)

## 6. Data Sources for Philadelphia

| Source | What | Access |
| --- | --- | --- |
| **PPA transaction data** | Meter and meterUP transactions, residential permits, citations | Right-to-Know Law (RTKL) request; PPA has historically been resistant but City Controller and SDP have negotiated access. Recommend a coordinated RTKL with 5th Square + PPI. |
| **Open Data Philly** | Street centerlines, zoning, building footprints, ACS overlays, traffic counts, "PPA Parking Facility Look-Up" | opendataphilly.org/categories/transportation; CC-licensed |
| **DVRPC TIM 2** | Regional travel demand model, mode/destination logsums, household travel survey, employment forecasts | Free for research use with DVRPC permission; runs in PTV VISUM with Python wrappersDVRPC |
| **DVRPC RPP report**(2020) | Most comprehensive existing analysis of Philadelphia residential permit parking | dvrpc.org/products/20026 |
| **Census/ACS, LEHD/LODES** | Demographic and employment density at block-group/tract level | Free, federal |
| **SEPTA GTFS, GTFS-Realtime** | Transit service frequency, ridership for substitution analysis | Free |
| **InRIX, StreetLight, Replica** | Origin-destination flows, trip purposes | Commercial; DVRPC and PennDOT have institutional licenses Russell may be able to leverage |
| **Parkmobile/Flowbird** | Backend transaction data | Vendor APIs; PPA has data-sharing rights but rarely shares externally |
| **OpenStreetMap** | Street segments, parking-relevant tags | Free, but US curb-regulation coverage is poor |
| **SharedStreets / CurbLR** | Open standard for curb regulation digitization, linear-referencedMediumMedium | sharedstreets.io/curbLR; github.com/curblr/curblr-spec.**Recommend Philadelphia produce a CurbLR feed; a 5th Square / PPI volunteer mapping project using the open-source CurbWheel GitHub could be a complementary deliverable.** |
| **PennDOT crash and traffic data** | Road network, AADT | PennDOT OneMap |
| **Philadelphia Code Title 12**(Traffic Code) | Statutory parking regulations | codelibrary.amlegal.com/codes/philadelphia |

A practical issue: PPA has not historically published bulk transaction data. A formal **RTKL request through the City Controller's office or a friendly Council member** (Squilla, Gauthier, O'Rourke) is much more likely to succeed than a direct request from an advocacy organization.

## 7. Complementary Policy Questions a Model Should Address

A model whose only output is "the optimal price per block per hour" misses most of what's politically interesting. Russell's model should support:

1. **Curb-space allocation**: comparative welfare of converting metered spaces to loading zones, bike lanes, parklets, or BRT/bus-only lanes. Use shadow prices from the pricing model as the opportunity cost of conversion. The Toronto CaféTO comparison and the NYC dining-shed evaluations are useful empirical anchors.
2. **RPP market pricing**: the strongest single recommendation in the white paper should be **graduated market pricing for residential permits**, with low-income waivers preserved. At Philadelphia densities (Center City and University City), market-clearing residential permit prices are likely in the **$500-$2,500/year** range based on comparable cities.
3. **Loading zone pricing**: the curbFlow / Pittsburgh Smart Loading Zones models offer a low-political-cost path to revenue and double-parking reduction. UPS alone has paid $9M+ in Center City congestion fines in recent years — direct evidence of unmet willingness-to-pay for legitimate curb access. [WHYY](https://whyy.org/articles/philadelphia-vehicle-permits-change-limits-rate/)
4. **Equity provisions**: low-income exemption for one residential permit; revenue use through **PBDs** funding sidewalk repair, transit, bike infrastructure, ADA improvements; explicit incidence analysis by ACS income decile.
5. **Revenue use**: returning a meaningful share (Mexico City uses 30%) to metered neighborhoods through a PBD structure; the **remainder, by state law, currently flows to the School District** — an unusually strong distributional argument unique to Philadelphia.
6. **TNC fee interaction**: Philadelphia's existing rideshare fee (1.4% to PPA, the rest to SDP and a parking trust fund) — Russell has prior modeling experience here. Coordinated dynamic pricing of curb parking + TNC pickup/dropoff fees in dense corridors avoids modal arbitrage.
7. **Climate / VMT**: per the SFpark evaluation, properly priced curb parking reduced cruising VMT by 30% in pilot areas. A citywide rollout in Philadelphia could plausibly reduce on-the-order-of 1-3% of total city VMT, with corresponding GHG, NOx, PM, and crash benefits. Don't overstate — the cruising-reduction literature is contested. [San Francisco Municipal Transportation Agency](https://www.sfmta.com/sites/default/files/reports-and-documents/2018/04/sfpark_eval_summary_2014.pdf)

## 8. Practical Implementation Stack

For the **operational tool / Philadelphia simulation**, recommended stack given Russell's Python proficiency:

- **Data**: pandas, GeoPandas, DuckDB (large transaction data), Polars for performance.
- **Choice models**: pylogit, xlogit, or biogeme (Python). For STATA-style discrete-choice, larch is also good.
- **Spatial econometrics**: pysal / spreg.
- **Bayesian inference**: PyMC (preferred for hierarchical elasticities by neighborhood) or NumPyro.
- **ML**: scikit-learn, XGBoost, LightGBM.
- **Simulation**: Mesa or AgentPy for ABM; for transport-network-aware simulation, MATSim with Python wrappers, or osmnx + custom code for lighter-weight network analysis.
- **Optimization**: cvxpy for convex pricing problems; gurobipy if academic license available for MIP formulations of curb-allocation problems.
- **Reproducibility**: nbdev / quarto for the academic paper; FastAPI + Streamlit for an interactive policy demonstrator that PPI/5th Square can showcase.

**Open-source codebases worth building on**:

- parking-search MATSim contrib module.
- Fiez & Ratliff's Seattle codebase (associated with arxiv:1712.01263).
- LADOT and SFMTA have published partial data dictionaries; SFpark sensor data is available via SFMTA open data.
- SharedStreets CurbLR + CurbWheel for curb inventory.

**Validation** is hard because true parking occupancy is unobserved citywide. Use Seattle's approach: cross-validate model-predicted occupancy against periodic LPR or in-person counts on a representative sample of blocks; report calibration plots and prediction intervals; ensure the operational pricing rule is robust to model misspecification (Seattle's ±$0.50 step is intentionally conservative).

## 9. Critical Perspectives and Limitations

This is the section the white paper should engage with most honestly. The strongest critiques:

1. **The 85% rule is a heuristic, not an optimum.** Chatman & Manville (2014) is the most pointed empirical critique — they show price changes targeting average occupancy may not improve availability when it matters (peak times) and may not reduce cruising. The model should target **probability of finding a space within X blocks**, not raw occupancy. [REPEC](https://ideas.repec.org/a/eee/retrec/v44y2014icp52-60.html)
2. **SFpark's cruising reduction claim is partly contested.** Millard-Ball, Weinberger & Hampshire (2014) instrument for endogeneity; their estimates of cruising reduction are smaller and less certain than SFMTA's headline 30% VMT figure. Hampshire & Shoup's (2018) "share of traffic that's cruising" estimates rely on strong assumptions about trip distance and search time. **Be honest: cruising is real and pricing reduces it, but the magnitudes in the field are smaller and noisier than Shoup-canon implies.**
3. **Regressivity at the user level is real**, even if the system is progressive overall. Some metered users are low-wage workers and contractors. Mitigations: low-income exemption for one RPP; preserve free curb parking outside core demand zones; ensure revenue use benefits low-income transit riders disproportionately (Manville's strongest argument).
4. **Gentrification critique**: dynamic pricing in commercial corridors can accelerate the displacement of low-margin businesses, especially those reliant on long-stay customers (hair salons, ethnic grocers). The Seattle annual review and the Pittsburgh Lawrenceville model both include explicit business-impact analysis. **Russell's model should include neighborhood-level "small business exposure" diagnostics.**
5. **Behavioral / salience**: drivers don't always know prices, especially with mobile payment + tiered structures (the Philadelphia meterUP tiered system is **not signed on-street**, per the City ordinance). The LA Express Park ethnographic work (Glasnapp & Isaacs 2014) documented widespread misunderstanding of time-of-day stickers. **Implication for Philadelphia**: signage, app design, and predictability of price changes matter as much as the algorithm. Too-frequent changes (SFpark's 6-week cycle) erode driver awareness; Seattle's annual cycle works better. [ParkMobile](https://support.parkmobile.io/hc/en-us/articles/36854964319643-Philadelphia-Parking-Authority-MeterUP-s-Tiered-Pricing)[Springer](https://link.springer.com/chapter/10.1007/978-3-319-07293-7_31)
6. **Gaming and enforcement**: residential permit fraud is endemic; LA Express Park ethnography found heavy abuse of disabled placards (8+ hour parking sessions). Pennsylvania has no statewide disabled-placard reform on the table. **Any pricing reform must be paired with enforcement reform** — automated LPR enforcement, photo-based bus-lane enforcement (Philadelphia is rolling this out on 150+ buses/trolleys), and tightening of placard issuance. [Springer](https://link.springer.com/chapter/10.1007/978-3-319-07293-7_31)[WHYY](https://whyy.org/articles/ppa-street-parking-rates-increase-center-city-philadelphia/)
7. **The PPA itself is a problem.** Multiple audits (state Auditor General 2017; City Controller 2020) have documented financial mismanagement, inflated staffing, and underpayment to the School District. **A pricing reform that delivers more revenue to a poorly-managed authority is a politically vulnerable proposal.** The white paper should pair pricing reform with **PPA governance reform** — at minimum, requiring more transparent cost accounting and faster pass-through to SDP. Alternatively, the model can be agnostic about who operates the program and leave that question to the political deliverable.
8. **Endogenous land use**: long-run effects of curb pricing include reduced minimum parking requirements, more housing, mode shift, and reduced car ownership. These are the strongest welfare benefits but the hardest to quantify. The model should distinguish **partial-equilibrium (short-run) revenue and welfare estimates** from **general-equilibrium (long-run) estimates with land-use feedback** — and acknowledge uncertainty in the latter is large.

## 10. Core Reading List

The 10 most important and relevant items, in priority order:

1. **Shoup, D. C. (2011).** *The High Cost of Free Parking* (updated edition). Chicago: Planners Press / American Planning Association. ISBN 978-1932364965. The foundational work; Ch. 16 ("The Right Price for Curb Parking"), Ch. 17 ("Taxing Parking"), and Ch. 19 ("Turning Small Change into Big Changes") are most directly relevant.
2. **Shoup, D. C. (ed.) (2018).** *Parking and the City*. New York: Routledge. ISBN 978-1138497122. Edited volume with case studies (Mexico City EcoParq, Pasadena, Austin, Beijing).
3. **Hess, D. B. (ed.) (2024).** *The Shoup Doctrine: Essays Celebrating Donald Shoup and Parking Reform*. Routledge. Most comprehensive recent state-of-the-field volume; 33 chapters.
4. **Pierce, G., & Shoup, D. (2013).** "Getting the Prices Right: An Evaluation of Pricing Parking by Demand in San Francisco." *Journal of the American Planning Association*, 79(1), 67-81. [https://doi.org/10.1080/01944363.2013.787307](https://doi.org/10.1080/01944363.2013.787307)
5. **Millard-Ball, A., Weinberger, R., & Hampshire, R. (2014).** "Is the Curb 80% Full or 20% Empty? Assessing the Impacts of San Francisco's Parking Pricing Experiment." *Transportation Research Part A: Policy and Practice*, 63, 76-92. The essential skeptical companion to Pierce & Shoup. [https://doi.org/10.1016/j.tra.2014.02.016](https://doi.org/10.1016/j.tra.2014.02.016)
6. **Chatman, D. G., & Manville, M. (2014).** "Theory versus implementation in congestion-priced parking: An evaluation of SFpark, 2011-2012." *Research in Transportation Economics*, 44, 52-60. [https://doi.org/10.1016/j.retrec.2014.04.005](https://doi.org/10.1016/j.retrec.2014.04.005)
7. **Lehner, S., & Peer, S. (2019).** "The price elasticity of parking: A meta-analysis." *Transportation Research Part A: Policy and Practice*, 121, 177-191. The authoritative recent meta-analysis (50 studies). [https://doi.org/10.1016/j.tra.2019.01.014](https://doi.org/10.1016/j.tra.2019.01.014)
8. **Arnott, R., & Inci, E. (2006).** "An integrated model of downtown parking and traffic congestion." *Journal of Urban Economics*, 60(3), 418-442. Plus Inci, E. (2015), "A review of the economics of parking," *Economics of Transportation*, 4(1), 50-63. The theoretical backbone.
9. **SFMTA (2014).** *SFpark Pilot Project Evaluation* and *Evaluation Summary*. [https://www.sfmta.com/reports/sfpark-pilot-project-evaluation-summary](https://www.sfmta.com/reports/sfpark-pilot-project-evaluation-summary). The single most thorough public-sector evaluation of demand-responsive curb pricing.
10. **DVRPC (2020).** *Strategies for Managing Residential Parking in Philadelphia*. Publication #20026. [https://www.dvrpc.org/products/20026](https://www.dvrpc.org/products/20026). The only major public-sector study of Philadelphia residential parking in the past decade — essential local context.

**Honorable mentions worth including in a longer bibliography**: Shoup, D. (2024) "Parking Benefit Districts," *JPER*, 44(4); Hampshire, R., & Shoup, D. (2018) "What Share of Traffic is Cruising for Parking," *JTEP*, 52(3); Fabusuyi & Hampshire (2018) "Rethinking performance based parking pricing," *Transportation Research A*; van Ommeren, Wentink & Rietveld (2012) on Dutch cruising; Fiez & Ratliff (2018) on Seattle data-driven pricing; the SharedStreets CurbLR specification; Manville, M. (TREC 2019) "Congestion Pricing Efficiency and Equity"; and the Seattle SDOT 2024 Paid Parking Annual Report.

## Recommended Next Steps for Russell

1. **Submit a coordinated RTKL request** through a sympathetic Council office for PPA meter transaction data (anonymized at session level), residential permit issuance by zone, and citation data — the legal backbone for any quantitative model.
2. **Calibrate a Seattle-style transaction-based occupancy model** as the technical core, with a hierarchical Bayesian elasticity prior centered on −0.4 with neighborhood-level shrinkage.
3. **Build three scenario layers**: status-quo + 2025 increase (baseline); Seattle-style annual review with time-of-day differentiation citywide; full Shoupian PBD with market-priced residential permits and revenue return to neighborhoods.
4. **The white paper's headline argument should be a Georgist one**, not a Shoupian one: Philadelphia is giving away the rent on its most valuable public land. Pricing it properly is good economics, good for schools (because of the SDP revenue allocation), good for housing (by reducing parking-driven NIMBYism), and consistent with PPI's broader land-value-capture program.
5. **The academic paper should engage the Chatman-Manville and Millard-Ball critiques head-on** — using Philadelphia data to test whether targeting minimum vacancy at peak rather than average occupancy across the day yields better cruising-reduction outcomes. This is a publishable contribution, not just a Philadelphia case study.
6. **The operational deliverable** should default to a transparent, auditable rule-based system (Seattle-style ±$0.50 / annual cycle / large zones) with the more sophisticated ML/RL machinery available as an "advanced" mode for academic and analytical purposes. Do not advocate for a black-box ML pricing system as the public-facing recommendation; the political and accountability risks are high and the welfare gains over a simple rule-based system are modest.

---

*Extracted from Claude AI • Conversation ID: `2eb9f7c8-d8d6-4637-89ce-37a6844b4064` • Date: 2026-04-28 • [View original](https://claude.ai/chat/2eb9f7c8-d8d6-4637-89ce-37a6844b4064)*

*Edit and convert to PDF/DOC at [markdown.vc](https://markdown.vc)*

---

*This document was extracted using Claude Research Extractor*
*Total links preserved: 67*