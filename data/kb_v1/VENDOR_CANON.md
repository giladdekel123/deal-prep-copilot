# Vendor canon — Nivarque Document Systems (approved at Gate 2A, 5 Nov 2026)

> SYNTHETIC — fictional vendor. Nivarque Document Systems and Solquend Archive Systems are fictional
> organizations. Nothing in this file is a real business fact.

**Status:** Approved at Gate 2A on 5 Nov 2026, together with D2 (USD, per user per month, billed annually), D4, D5 and D6.
This file is the single synthetic source of truth for every Prompt 02 vendor/competitor document. Any unintended
contradiction between a corpus document and this canon is a defect; intended contradictions must be tagged
`fixture: intentional_conflict` with a `conflict_group`.

**Name check (5 Nov 2026):** public web searches for "Nivarque", "Solquend" and the full company names returned no
matching organization (recorded in the Gate 2A report of the private development archive, not included here). Neither name is known to be used by a real DMS company.

## 1. Identity (fictional)

| Field | Value |
|---|---|
| Vendor | Nivarque Document Systems (`org_id: nivarque`, `reality: fictional`) |
| Positioning | Document management for engineering, construction and infrastructure organizations; secondary market: general corporations needing audited approvals |
| Competitor | Solquend Archive Systems (`org_id: solquend`, `reality: fictional`) — low-cost bulk archive, no native drawing register or transmittals |
| Fictional HQ | Not specified — avoid inventing a real-looking address |

## 2. Products and tiers

| Product | Tier | Key capabilities |
|---|---|---|
| Nivarque Core | Starter | Version control, check-in/out, metadata, full-text search |
| Nivarque Core | Business | Starter + configurable approval workflows, SCIM provisioning |
| Nivarque Engineering Vault | Enterprise | Core Business + drawing register, transmittals, revision letters, issued-for-construction history, customer-managed keys, private-cloud option |
| Records Retention Add-on | Add-on | Retention schedules, legal holds, disposal certificates |
| Implementation Services | Service | Fixed-scope onboarding package (scope defined per proposal) |

## 3. Pricing policy (D2 approved)

Currency **USD**. Per-user products are priced **per user per month, billed annually in advance**.

| Product | Tier | Unit | List price (USD) | Minimum term |
|---|---|---|---|---|
| Nivarque Core | Starter | per user per month | 18 | 12 months |
| Nivarque Core | Business | per user per month | 34 | 12 months |
| Nivarque Engineering Vault | Enterprise | per user per month | 52 | 24 months |
| Records Retention Add-on | Add-on | per TB per month | 240 | 12 months |
| Implementation Services | Service | per project (fixed fee) | set per proposal | — |

- List prices exclude VAT.
- Discount approval: up to 15% by the account executive; above 15% requires written approval from the regional sales director; above 25% requires the CFO.
- Negotiated prices exist only in proposals and apply only to that proposal's customer and validity period; they never change the list price.

## 4. Price-list lifecycle and effective dates

- Price lists are versioned: `NVQ-PRC-<YYYY>-v<N>`.
- Exactly one price list is `approved` and in force on any date; a new approved list sets `effective_from`, and the previous one receives `effective_to` = day before and status `superseded`.
- Planned fixture C1: a 2025 list (Business = 30) superseded by the 2026 list (Business = 34) on 1 Oct 2026.

## 5. Document conventions

- IDs: `NVQ-<TYPE>-<NNN>` — TYPE ∈ `PRD` (product), `PRC` (price list), `POL` (policy), `CMP` (competitive), `PRP` (proposal), `COR` (correspondence), `MTG` (meeting notes), `PUB` (public-source snapshot).
- Status labels: `approved`, `draft`, `superseded`, `expired`.
- The frozen Prompt 01 documents keep their `DMS-*` IDs. No v1 document reuses that prefix.
- Every document carries `info_origin` and `creation_method` (spec v1.2 §6B).
- Every vendor, competitor and relationship document (`PRD`, `PRC`, `POL`, `CMP`, `PRP`, `COR`, `MTG`) is `info_origin: synthetic_record` and follows this canon.
- `PUB` documents are `info_origin: public_source`. They are **outside this canon's content rules**: their content comes only from cited public sources, and they may not reference Nivarque, Solquend or any other fictional organization.
- Customer-specific synthetic records (proposals, correspondence, meeting notes) about a real organization carry the banner:
  *"SYNTHETIC RECORD — fictional relationship with a real company. Not a real business fact."*

## 6. Terminology

| Use | Avoid |
|---|---|
| drawing register | drawing list, drawing log |
| transmittal | dispatch note |
| issued-for-construction (IFC) | final drawing |
| approval workflow | sign-off flow |
| retention schedule | deletion policy |

## 7. Demo companies and synthetic relationship states (D4 approved, 5 Nov 2026)

| Real organization (`reality: real`) | Synthetic relationship state | Synthetic records planned in Gate 2B |
|---|---|---|
| Shikun & Binui | proposal sent | proposal, correspondence, meeting notes |
| Ashtrom Group | new lead | none, or a single first-contact note: this case tests "no prior relationship" |
| Arup | negotiation | proposal with negotiated price (conflict fixture C3), correspondence, meeting notes |

- **Every** sales relationship, proposal, price, meeting and piece of correspondence involving these companies is **synthetic** and explicitly labelled as such. They carry `info_origin: synthetic_record`, `synthetic_relationship: true`, `synthetic_categories` and the §5 banner. None of them is a real business fact, and none implies that the real company has ever dealt with Nivarque.
- **D5:** ARUP Laboratories is a registry entry with public-source content only and **no synthetic records of any kind**.
- **D6:** create about 18 documents first, test extraction and retrieval, then grow to about 30.
