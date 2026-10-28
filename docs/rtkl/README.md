# Philadelphia Parking Authority: Right-to-Know Law request packet

The pricing model runs on a synthetic segment fixture and synthetic demand
(`audits/audit_2026-10-14.md`). Observed parking data from the Parking Authority is what
would let it estimate occupancy and price response for real zones. This folder holds the
requests for that data.

## Status of this project's requests

**Requests A and B: sent 2026-10-15; extended to 21 November 2026.** The cover email and both
attachments went to `OpenRecordsOfficer@philapark.org` at 3:45 p.m. without the request forms.
The two completed forms followed in a reply in the same thread at 4:38 p.m. The Authority dates
receipt to 15 October.

On 22 October 2026 the Authority's Right to Know Officer, Alanna D. Buchanan, sent one
extension letter per request, Nos. 26-0151 and 26-0152. Each takes the 30-day extension,
citing staffing, legal review of whether the records are public, and redaction of non-public
information. The anticipated response date for both is on or before 21 November 2026. The
letters do not say which number is A and which is B; the table assumes they follow the order
sent. If no response arrives by 21 November, the request is deemed denied and can be appealed to
the Office of Open Records.

**Narrowed on 26 October 2026.** On 23 October the Authority asked whether both requests could
be narrowed, because its search was producing a large volume of records. The reply of 26 October
narrowed them as follows:

- **A item 1 (sessions):** limited to metered blocks in University City, Northern Liberties and
  Fishtown, and South Philadelphia's commercial corridors, offering exact boundaries. Limited to
  two periods, 1 May to 30 June 2025 and 1 September to 31 October 2025. Existing hourly totals
  by pay station or zone are offered in their place.
- **A item 2 (RPP permits):** withdrawn.
- **A item 3 (citations):** limited to meter violations (expired meter, over the time limit at a
  meter, parked in an unmetered space) in the same areas and periods.
- **A item 4 (data dictionaries):** for whatever is released under items 1 and 3.
- **B items 1, 2 and 4:** unchanged, with a request to release them without waiting on A.
- **B item 3 (occupancy studies):** limited to final reports and summary tables.

No. 26-0145 was narrowed the same day to the same two periods, with its area and its inventory
and rate items unchanged. Matching periods matter for the elasticity design: the zones outside
Center City are the unchanged-rate control for the 1 July 2025 rise (see "Using a partial
release").

The filled forms and the letters carry the requester's home address and are not tracked.

| Request | Contents | Sent | Tracking no. | Due | Outcome |
|---|---|---|---|---|---|
| A | sessions in three outer areas (two periods), meter citations, data dictionaries | 2026-10-15 | 26-0151 (assumed) | 2026-11-21 | extended 2026-10-22; narrowed 2026-10-26 |
| B | meter inventory with spaces, rate schedules, occupancy reports, revenue by zone | 2026-10-15 | 26-0152 (assumed) | 2026-11-21 | extended 2026-10-22; narrowed 2026-10-26 |

## Requests in flight elsewhere

The sibling project `C:\projects\philly-road-pricing` filed **Request No. 26-0145** on
2026-10-06: paid on-street sessions inside the area bounded by I-676, I-95, South Street and
I-76, with that area's meter locations, hours and rate schedules. The request originally asked for
January 2025 to June 2026; on 26 October 2026 it was narrowed to 1 May to 30 June and 1 September
to 31 October 2025. The Authority extended its response to **13 November 2026**. Its status is kept in that repo's
`docs/data_request_priorities.md` (section 1.2). Those records cover Center City Core and most of
Center City Area across the 1 July 2025 rate rise, which is the price variation the elasticity
model needs. The requests here exclude them by name.

## Files

- `rtkl-request-ppa.md`: the two requests filed from this project (A: data exports; B: existing
  reference records), each the attachment to its own request form, with field-by-field form
  notes.
- `submission-email.md`: the cover email and the verified submission rules.
- `cover-letter-council.md`: optional note asking a Council office to endorse or transmit a
  request.
- `oor-appeal-template.md`: appeal letter to the Office of Open Records if a request is denied.

## Submission rules

Read from the Authority's transparency page and its Right to Know Law Policy on 2026-10-15
(details and citations in `submission-email.md`):

- Requests only on the Authority's own Request Form (2025 version, linked from
  <https://philapark.org/transparency/>), one form per request.
- By email to `OpenRecordsOfficer@philapark.org`, by fax, or by mail or hand to 701 Market
  Street, Suite 5400. No anonymous or verbal requests. No reason is required.
- After 4:30 p.m. counts as the next business day.

**Fees** (the policy's Exhibit B): no fee for email delivery or redaction; "specialized
documents" up to actual cost, paid before release. Set the form's fee-notification threshold so
the Authority asks before charging.

## Timeline

| Stage | Deadline | Source |
|---|---|---|
| Grant, deny, or notice of extension | 5 business days from the business day after receipt | PPA policy 4(c)–(d) |
| Extension | up to 30 calendar days, longer by agreement | PPA policy 4(c) |
| No response by the deadline | deemed denied | PPA policy 4(c) |
| Appeal to the Office of Open Records | 15 business days from the denial's mailing date | PPA policy 7 |
| OOR final determination; appeal to court | not checked here | the OOR's current guidance |

## Recommended sequence

1. Send the two requests (`submission-email.md`). The five-day clock starts on receipt.
2. Optionally, ask a Council office to endorse or transmit (`cover-letter-council.md`).
3. Record each tracking number and due date in this file when the Authority replies.
4. An extension is routine for bulk data. If a request is denied, the denial must cite the
   exemption relied on; appeal within 15 business days using `oor-appeal-template.md`.

## Using a partial release

- **Elasticity needs a price change.** A zone has one posted rate at a time, so a slice of
  sessions without a rate change cannot identify its elasticity (audit finding 5). The useful
  minimum is any zone observed across the 1 July 2025 rate rise; No. 26-0145 is designed to
  supply that for the central zones.
- **Paid sessions are not occupancy.** Permit holders, placard users and non-payers park without
  paying. Converting sessions to occupancy needs the number of spaces each meter serves
  (Request B, item 1) and some measure of unpaid use (occupancy studies, B item 3, or citation
  rates, A item 3).
- **Elasticity also needs a control.** The model has a calendar-period term, so Center City
  Core and Center City Area alone, both raised on 1 July 2025, do not identify a price
  response: some zone or rate class whose rate did not change must be in the data
  (`elasticity/identification.py` checks this before any fit).
- **Loading a release.** Map the export's column names, time format and rate-area labels in
  `config/ppa_ingest.yaml`, then run `scripts/03b_ingest_ppa.py` (panel by block face, period and
  hour), `scripts/04_fit_elasticity.py` and `scripts/05_run_scenarios.py --ppa data/processed/ppa`.
  The ingest stops on anything it would otherwise have to guess.
- **Redacted fields are acceptable.** The requests ask for nothing that identifies a person or
  vehicle, so a release under Section 708(b) with those fields removed still serves the model.
