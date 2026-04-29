# Philadelphia Parking Authority — Right-to-Know Law (RTKL) Request Packet

This folder contains a ready-to-submit RTKL request packet for the data the
demand-based pricing model needs. The model runs on synthetic stubs today; real
PPA transaction data is the gating dependency for credible numerical
recommendations.

## Files

- `rtkl-request-ppa.md` — the substantive request text (drop into the Records
  Requested box of the Pennsylvania OOR standard form).
- `cover-letter-council.md` — short cover note to send to a sympathetic Council
  office (Squilla, Gauthier, or O'Rourke) asking them to co-sign or transmit.
- `oor-appeal-template.md` — pre-drafted appeal letter to file with the
  Pennsylvania Office of Open Records if PPA denies.

## Submission procedure (per PPA's Right-to-Know Law Policy)

PPA *only* accepts requests on the OOR standard form. **Anonymous or verbal
requests are not considered.** The form is at:

  https://www.openrecords.pa.gov/Documents/RTKL/RTKRequestForm.pdf

Submit the completed form to PPA's Open Records Officer **one of three ways**:

| Mode | Address |
|---|---|
| Email (preferred) | OpenRecordsOfficer@philapark.org |
| Mail or hand delivery | The Philadelphia Parking Authority, Attn: Open Records Officer, 701 Market Street, Suite 5400, Philadelphia, PA 19106 |
| Fax | 215-683-9619 |

**Form gotchas — easy to miss:**

1. **Check the legal-resident affirmation box.** The form warns: *"failure to
   check this box may result in the denial of my request and the dismissal of
   any appeal filed with the Office of Open Records."* This is non-trivial —
   PPA can reject your appeal on this technicality alone.
2. **"Submitted to Agency Name"** at the top must read exactly:
   `The Philadelphia Parking Authority (Attn: AORO)`.
3. **"Records Requested"** must be a request for *records*, not a question.
   Avoid "Why does..." or "Can you tell me..." phrasings. Always frame as
   "Please provide records..."
4. **Set a fee threshold.** The form asks "Notify me before processing if fees
   will be more than $___." For a research request, set $50 — forces PPA to
   negotiate before generating large invoices, and gives you cost intel for
   appeals.
5. **Choose electronic delivery.** Per PPA's fee schedule, "Records Delivered
   via Email — No additional fee may be imposed." Pick "Yes, electronic" under
   "DO YOU WANT COPIES?" to avoid per-page charges.

## PPA fee schedule (relevant excerpts)

- Records via email: **no fee**
- Black & white copies: up to $0.25/page
- Specialized documents (likely how PPA classifies bulk transaction exports):
  **up to actual cost** — this is the biggest fee risk
- Postage: actual USPS first-class

## Response timeline (statutory)

| Stage | Statutory deadline |
|---|---|
| PPA must grant, deny, or invoke 30-day extension | **5 business days** from receipt |
| If 30-day extension invoked | up to **30 calendar days** total |
| If PPA does not respond | request is **deemed denied** |
| Your window to appeal to OOR | **15 business days** from PPA's denial / deemed denial |
| OOR must issue final determination | **30 days** from appeal receipt |
| Either side's window to appeal OOR ruling to Commonwealth Court | **30 calendar days** |

So worst case: ~75 days from submission to final OOR determination, plus
court time if either party escalates.

## Strategic context

- **PPA has a small open-data footprint.** OpenDataPhilly lists only one PPA
  dataset (the Parking Locator). No transaction or occupancy data is
  proactively published. So everything substantive must come via RTKL.
- **PPA is a state authority**, not a city department (per Act 22 of 2001).
  RTKL is the only mandatory disclosure mechanism for non-employees.
- **Researchers have rarely obtained bulk transaction data**, per the
  research-doc literature review. A coordinated request via a Council office
  carries far more weight than an individual request.
- **City Controller's office** has standing to push for PPA data and has
  audited PPA finances (Rhynhart 2020); a Controller-routed request may also
  succeed where a direct one fails.

## Recommended sequence

1. Send the cover letter (`cover-letter-council.md`) to Squilla's, Gauthier's,
   or O'Rourke's chief of staff. Ask whether they'll either (a) submit on PPI
   letterhead with their endorsement, or (b) introduce you to PPA's
   Government Affairs lead before you submit.
2. While waiting, submit the OOR form yourself. Do not wait — the 5-day clock
   helps you regardless.
3. Track the response date PPA stamps on the form (item 4(d)–(e) of the
   policy: PPA assigns a tracking number on receipt). Mark your calendar.
4. If PPA invokes the 30-day extension, that's normal for bulk-data requests
   and not adversarial.
5. If PPA denies, file the OOR appeal within 15 business days using the
   template. The OOR ruled in favor of requesters in ~60% of decided appeals
   in recent years.

## What if PPA only releases partial data?

- Even **one zone-month** of real transactions is enough to calibrate the
  synthetic baseline intercept and fit a non-degenerate elasticity posterior
  for that zone. Don't reject a partial release.
- If PPA cites Section 708(b)(17) (records identifying a specific individual)
  to redact, that's standard for parking transaction data — accept session-
  level data with anonymized plate hashes.
