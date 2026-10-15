# External Sources Register

Secondary sources (news, rankings, agency pages) consulted for this project that are not in
`research/`. Each entry records what the source supports, where it bears on the model or the
white paper, and any figures that must not be reused as model inputs. Figures here are fixed
values from a published document, not model outputs.

---

## Philadelphia Inquirer (2026-10-13), WalletHub ranks Philadelphia the worst big U.S. city for drivers

- **Article**: Erin McCarthy, "Why Philly was just ranked the worst big U.S. city for drivers,"
  *The Philadelphia Inquirer*, October 13, 2026.
  <https://www.inquirer.com/news/philadelphia/philadelphia-drivers-traffic-car-theft-costs-wallethub-20261013.html>
- **Underlying study**: Adam McCann, "Best & Worst Cities to Drive in 2026," WalletHub,
  October 6, 2026, data as of September 8, 2026.
  <https://wallethub.com/edu/best-worst-cities-to-drive-in/13964>
- **Method**: 30 metrics for the 100 most populous cities (city proper only), weighted into four
  dimensions. "Average Parking Rate" is a full-weight metric (about 4.3 of 100 points) under cost
  of ownership; WalletHub does not publish its definition or data source.

### Key figures

Read against WalletHub's page on 2026-10-14: Philadelphia ranks **100th of 100** (total score
36.35); 76th on cost of ownership, 96th on traffic and infrastructure, 95th on safety. It is
**78th-highest of 100 on parking rates**.

Reported by the Inquirer only (WalletHub's page gives ranks, not values):

| Measure | Philadelphia | Rank of 100 |
| --- | --- | --- |
| Average rate at five garages near City Hall, 3-5 p.m. | $20.60 | 78th most expensive |
| Average car commute | 32 minutes | 88th longest |
| Average monthly car insurance premium | $263 | 52nd highest |

### Where it bears on this project

- **The only sourced Center City garage price the project has.** It is a two-hour afternoon
  window, the same length as the white paper's example parking event. The white paper's
  Executive Summary prices two hours in a Rittenhouse garage at $30-$40 and says garage rates
  are "three to five times" the meter; neither figure has a source. At $4/hour the meter charges
  $8 for two hours, against $20.60 here, about 2.6 times. The two are different garages (City
  Hall, Rittenhouse), so this does not refute the paper's range, but it is the figure a reader
  can check.
- **Cross-elasticity context.** `config/elasticity_priors.yaml`'s `curb_to_garage` assumes
  garages substitute for the curb; the size of the curb-garage price gap is what makes that
  substitution matter.

### Do not reuse as model inputs

- **The $20.60** is five garages at one location and time of day, as the Inquirer read
  WalletHub's data. It is not a city-wide or block-level off-street price.
- **WalletHub's score and ranks** are an index of weighted metrics, not a measurement.
