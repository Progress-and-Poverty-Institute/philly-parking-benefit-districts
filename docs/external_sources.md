# External Sources Register

Secondary sources (press, rankings, reports) consulted for this project that are not in `research/`.
Each entry records what the source supports, where it bears on the model, and any figure that
must not be reused as a model input. Peer-reviewed references cited in the white paper live in
`outputs/reports/white_paper/Report.tex`.

A source listed under "located, not read" has been found by search but its page has not been
opened. Do not cite or quote it until the page has been read and the entry promoted.

---

## Located, not read

### *Philadelphia Inquirer*, "Why Philly was just ranked the worst big U.S. city for drivers," 13 October 2026

- **URL**: <https://www.inquirer.com/news/philadelphia/philadelphia-drivers-traffic-car-theft-costs-wallethub-20261013.html>
- **Status**: located 2026-10-13. The session's network blocked inquirer.com and wallethub.com;
  everything below is a search result's summary. Byline reported as Erin McCarthy, unconfirmed.
- **Underlying source**: WalletHub, *2026's Best & Worst Cities to Drive In*, released
  6 October 2026, <https://wallethub.com/edu/best-worst-cities-to-drive-in/13964>. A composite
  index of the 100 largest US cities on 30 weighted measures (ownership and maintenance cost,
  traffic and infrastructure, safety, access to vehicles and maintenance).
- **Consistent across summaries**: Philadelphia ranked 100th of 100, for the second year running,
  with a score of 36.35 of 100.
- **Inconsistent across summaries** (do not quote any of these until read): the average parking
  rate measure (Philadelphia highest of 100, or 78th), car theft (highest, or 91st), congestion
  hours per auto commuter (tied worst, or tied 65th), the category ranks, and the top city.

### Where it bears on this project

- **Framing only.** No model input. It could support the white paper's context on the cost of
  driving and parking in Philadelphia once read.
- **The parking-rate measure is not a curb price.** WalletHub's "average parking rate" most likely
  comes from an off-street or app-based price source (unconfirmed). It is not PPA's meter rate
  and must not be used for `price_usd_per_hr` or a zone's current price. If it is an off-street
  price, it bears only on the curb-garage substitution the research review calls for (garage
  prices exogenous in baseline runs), and only after its source and geography are known.
