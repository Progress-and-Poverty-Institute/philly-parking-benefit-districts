# Records Requested — paste into the OOR Standard Form

> **Submitted to Agency Name**: The Philadelphia Parking Authority (Attn: AORO)
>
> **Person Making Request**: Russell Richie
> **Company**: Progress and Poverty Institute / 5th Square
> **Email**: drussellmrichie@gmail.com
>
> **Records Delivery**: Yes, electronic (CSV / Parquet / Excel acceptable)
> **Fee threshold**: notify me before processing if fees exceed **$50**.
> **Legal-resident affirmation box**: ✅ checked.

---

## Records Requested

I am requesting the following records relating to on-street paid parking,
residential permit parking, and parking citations issued by the Philadelphia
Parking Authority. The records are sought to support a non-commercial research
project on demand-responsive curb pricing in Philadelphia. Where any portion of
a record is exempt under 65 P.S. § 67.708, I am requesting that the Authority
**redact only the exempt portion and release the balance**, as required by
Section 706.

For the period **January 1, 2023 through the most recent month for which data
exists**, please provide:

### 1. Parking meter and meterUP / Parkmobile transaction records

A session-level export of all paid parking transactions occurring at on-street
metered spaces in the City of Philadelphia, including all of the following
fields where they exist in the Authority's source systems:

- Transaction or session identifier
- Meter identifier and / or block-face / segment identifier
- Cross-streets or address of the metered location
- Latitude and longitude (or the existing PPA spatial reference)
- Posted hourly rate at the time of the transaction
- Session start timestamp (date and time)
- Session end or expiration timestamp
- Paid duration in minutes
- Amount paid in U.S. dollars
- Payment channel (single-space meter, multi-space pay station, meterUP,
  Parkmobile, other)
- Payment method (cash, credit card, mobile)
- A masked or hashed plate identifier sufficient to compute return-visit
  frequency without re-identifying any individual

I request the data in **electronic form (CSV, Parquet, or Excel)**, delivered
via email or shared drive. To minimize processing burden, I am happy to
accept the data **as it exists in the Authority's data warehouse or vendor
back-end (Flowbird, Parkmobile / EasyPark)**, without reformatting.

### 2. Residential Permit Parking (RPP) issuance records

A row-per-permit export of all RPP permits issued, renewed, or expiring in the
above period, including:

- Permit identifier (anonymized or hashed if necessary)
- RPP zone
- Issue date and expiration date
- Vehicle class (passenger, motorcycle, commercial, etc.)
- Permit type (annual, temporary 15-day, temporary 30-day, motorcycle, low-
  income waiver, etc.)
- Annual fee paid
- Whether a low-income waiver was applied (yes/no — no income data needed)

### 3. On-street parking citation records

A row-per-citation export for citations issued at on-street locations
(including expired meter, no permit in RPP zone, street-cleaning, double-
parking, bus-zone, bike-lane, fire-hydrant, and similar codes), including:

- Citation identifier (anonymized)
- Citation date and time
- Block-face / segment identifier and / or street and cross-streets
- Citation code and short description
- Fine amount and any escalation
- Outcome (paid, dismissed, in appeal, in collections)
- Vehicle class if recorded

### 4. Reference / metadata files

For interpretation of items 1–3:

- A current export of all metered locations including identifier, cross-
  streets, geometry, posted rates, hours of paid operation, and any time-of-
  day rate banding.
- The current RPP zone boundaries (shapefile or GeoJSON).
- A code book / data dictionary for the transaction, permit, and citation
  exports.

### 5. Format and access

I am willing to accept the records in **whichever format imposes the lowest
processing cost on the Authority**. If a bulk export would generate a
"Specialized Documents" charge, please notify me before processing so we can
discuss scope. I would prefer:

- **Email delivery if files are under ~50 MB total**, since under PPA's
  published fee schedule, "Records Delivered via Email — No additional fee
  may be imposed."
- **A shared drive or SFTP link** if larger.
- A single CD or USB drive (per the published fee schedule, up to $3.00 per
  disc or actual cost) if electronic transfer is not feasible.

### 6. Statutory framing

These records are presumptively public under 65 P.S. § 67.301 and are not
subject to any of the enumerated exemptions in § 67.708 except as to specific
personally identifying fields (license plate, name, address). Where such
fields exist, **I am requesting that they be redacted or hashed rather than
withholding the entire record** (Section 706, severability of records).

If the Authority believes that any portion of this request is unduly
burdensome under § 67.703, I welcome the opportunity to **narrow the scope
in consultation with the Open Records Officer** before any denial. A reduced
scope — e.g., one calendar year for a single zone — would still be useful for
the research, and is less likely to trigger fee or burden concerns.

Thank you for your prompt attention. I look forward to your response within
the statutory five business days, or notice of any extension under § 67.902.

— Russell Richie
