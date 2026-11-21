# CP-2 briefing quality audit (Phase 4.5, before I3) — FICTIONAL TEST DATA

Manual audit by Claude Code of the 24 existing CP-2 live briefings: 6 development scenarios × runs A1, B1, A2 and B2,
in `runs/benchmark_v1/cp0/20261110T05*_cp2_*`. It makes no new API calls and touches no held-out data. Production
code, benchmarks and protected data are unchanged. Clock: 2026-11-09.

## Method

- **Expected critical information** came from the fictional company specifications
  (`eval/benchmark_v1/dev/companies/*.json`) and the source passages, not from the briefings. Those passages are the
  proposal, correspondence, meeting record, price list, product sheet, policy and news. The benchmark's `expected`
  blocks were used only to map evidence IDs.
- Each briefing was compared with a per-scenario checklist and with what actually reached the drafter (the
  `drafting_input` field). A missing item can therefore be traced either to **selection** (it never reached the
  model) or to **drafting** (it reached the model and was not used).
- **Scoring:** each dimension is scored 0–4 per briefing. The tables show means over the 4 runs.

| Dimension | 4 | 2 | 0 |
|---|---|---|---|
| Factual accuracy | no unsupported statement | one material unsupported certainty | fabricated critical figure |
| Important omissions | 4 × share of the critical checklist present | | |
| Purpose relevance | content and recommendations serve the meeting type (negotiation: price position and approvals; follow-up: open items; introduction: fit hypothesis; demo: what to show) | partly | not at all |
| Contradiction recognition | every genuine contradiction stated, attributed and unresolved; nothing compatible called contradictory | one of two found, or found and then silently dropped | missed, or presented as consistent |
| Specific vs generic | concrete numbers, dates and customer terms carry the briefing | mixed with boilerplate | generic |
| Grounded recommendations | every recommendation cites evidence it follows from | partly; one uncited or one irrelevant | ungrounded |

**Critical checklists** (from the specification; 6–7 items each):

| Scenario | Checklist |
|---|---|
| P2 negotiation | proposal terms (180 × $49, valid 20 Dec); request for 60 more users; quote due 16 Nov; questionnaire due 12 Nov; audit-readiness concern; factory count 4 vs 5 contested; price position (list $52, so 5.8% already off) |
| T1 follow-up | proposal terms (250 × $31, 31 Dec); 8 TB retention request; quote open, due 14 Nov; checklist completed; seven-year migration concern; fresh Rotterdam customs-terminal news |
| C1 negotiation | proposal terms (600 × $47, 15 Dec); 36-month price question; quote in progress, due 20 Nov; import template open, due 10 Nov; subcontractor-adoption concern; two-site pilot; price position (list $52, so 9.6% off) |
| L1 follow-up | proposal terms (120 × $32, 31 Jan 2027); 3 TB retention request; revised quote completed; retention periods open, due 25 Nov; confidentiality concern; retention workshop; Lyon office (30-day news) |
| E1 introduction | origin; wind-farm count 21 vs 24 contested; fresh offshore news; maintenance-record history; no relationship stated; product-fit hypothesis (Engineering Vault serves infrastructure) |
| M2 product demo | origin; hospital count 9 vs 12 contested; two clinics opened Oct 2026; digital consent since 2025; no relationship stated; demo content (relevant capabilities: workflows, retention and legal hold, data region, encryption, SSO) |

Genuine contradictions: P2 has two (factory count, and "stored since 2020" versus "decided in 2022"); E1 and M2 have
one each (count). C1, T1 and L1 have none; their chronologies are compatible.

## Scorecard

| Dimension | Overall | P2 | T1 | C1 | L1 | E1 | M2 |
|---|---|---|---|---|---|---|---|
| Factual accuracy | **3.8** | 3.0 | 4.0 | 3.8 | 4.0 | 4.0 | 4.0 |
| Important omissions | **3.5** | 3.2 | 4.0 | 3.6 | 3.6 | 3.4 | 3.0 |
| Purpose relevance | **2.8** | 2.8 | 3.8 | 3.5 | 3.2 | 2.0 | 1.2 |
| Contradiction recognition | **2.4** | 1.2 | n/a | n/a | n/a | 3.0 | 3.0 |
| Specific vs generic | **2.6** | 3.0 | 3.0 | 3.2 | 3.0 | 2.0 | 1.2 |
| Grounded recommendations | **3.5** | 4.0 | 4.0 | 4.0 | 3.5 | 3.0 | 2.8 |

**Overall pattern:** the customer scenarios (P2, T1, C1, L1) are accurate and specific. The new-lead scenarios (E1
introduction, M2 demo) are accurate but generic, and M2 does not serve its purpose.

**False-positive check:** no compatible chronology or copied aggregator figure was called a contradiction in C1, T1,
L1 or E1 (0/16).

**Hygiene, 24 of 24 briefings:**
- no unreviewed draft note leaked (budget freeze, exclusivity, competitor hint, 30% discount);
- no stale news or look-alike company used;
- no quote page cited;
- no fabricated figure.

## Consistency between repeated runs

Mean per briefing, across all six dimensions:

| Run | A1 | B1 | A2 | B2 |
|---|---|---|---|---|
| Mean | 3.11 | 3.27 | 3.18 | 3.06 |

Spread across the four runs, by scenario:

| Scenario | Spread | Assessment |
|---|---|---|
| E1 | 0.06 | stable |
| T1 | 0.20 | stable |
| L1 | 0.31 | moderate |
| C1 | 0.51 | moderate |
| M2 | 0.61 | unstable |
| P2 | 0.76 | unstable |

- **A versus B:** the gap is smaller than the run-to-run spread. No quality-dimension difference between A and B is
  claimed, which is consistent with `CP2_RESULTS.md`.
- **The main source of inconsistency is selection, not wording.** For the same scenario, the evidence that reaches the
  drafter differs between runs: the agent's supplementary retrieval varies. Three of the most important omissions are
  passages present in only 1 of 4 inputs:

| Passage | Present in | Missing from (never reached the drafter) |
|---|---|---|
| Engineering Vault list price `NVQ-PRC-2026-v1#2` (P2) | A1 | B1, A2, B2 |
| Customer's 36-month price question `NVQ-COR-BXC-001#2` (C1) | A1 | B1, A2, B2 |
| 3 TB retention request `NVQ-COR-BXL-001#2` (L1) | B2 | A1, B1, A2 |

  When the passage was present, the drafter used it every time.
- **Wording variability also matters for the P2 chronology:** the same input produced "consistent" (A1, B2), silently
  dropped (B1) or omitted (A2).

## Error register

Severity:
- **C (critical):** would mislead the seller or leaves the meeting's purpose unserved.
- **M (major):** an important item missing or wrong in some runs.
- **m (minor):** quality or efficiency.

| # | Sev. | Scenario / runs | Finding | Evidence | Layer | Fix in |
|---|---|---|---|---|---|---|
| E1 | C | P2 A1, B2 | Chronology contradiction presented as established: "board decided in 2022" and "stored since 2020" stated side by side as consistent. B1 drops the 2020 statement; A2 omits both. Recognised in 0/4. | `NVQ-PUB-BXP-001#2`, `#3`; A1/B2 `company_overview` | drafting (no temporal reasoning) | I4 |
| E2 | C | M2, all 4 | Product-demo briefing contains no product, security or retention evidence: no `NVQ-PRD-*` or `NVQ-POL-002` passage reached the drafter. Recommendations reduce to "ask which workflows they want to see". | M2 `drafting_input` ID lists | selection (purpose-blind) | I3 |
| E3 | M | P2 B1, A2, B2 | List price of the proposed product missing from the input, so no price position; irrelevant Core Starter/Business rows (2025 and 2026) and the retention row were included instead. No run computes that $49 is 5.8% below $52, or the effect of 240 users. | `NVQ-PRC-2026-v1#2` only in A1 | selection | I3 |
| E4 | M | L1 A1, B1, A2 | Customer's explicit 3 TB retention request absent; only the correspondence header reached the drafter. | `NVQ-COR-BXL-001#2` only in B2 | selection | I3 |
| E5 | M | C1 B1, A2, B2 | Customer's own price question (36-month term) absent; known only indirectly from the meeting task. Price position (9.6% off list) computed only in B1; A2 and B2 omit the list price. | `NVQ-COR-BXC-001#2` only in A1 | selection and drafting | I3, I5 |
| E6 | M | P2, E1, M2: 11 of 12 contradiction instances | Contradictions are stated only in inference text; formal contradiction disclosures are 0/12 (the disclosures are only gap notices). P2 A1 also omits the factory-count conflict. | `disclosures` fields | drafting | I4, I6 |
| E7 | M | E1, all 4 | Introduction gives no fit hypothesis: the product sheet (Engineering Vault for infrastructure organisations) was never retrieved. Engineering Vault appears only via the competitor brief, as "if relevant". | E1 `drafting_input` | selection | I3 |
| E8 | m | C1, all 4 | Import-template task due 10 November (the day after the clock) is listed with its date but never flagged as due tomorrow. | `HIST-MTG-*` task line | drafting (no open-item derivation) | I5 |
| E9 | m | Customer scenarios | No run quantifies requested add-ons from the list price (T1: 8 TB × $240 = $1,920 per month; L1: 3 TB = $720 per month). T1 A1 and B1 state the per-TB price only. | `NVQ-PRC-2026-v1#3` | drafting | I5 |
| E10 | m | 20 of 24 competitive items; 19 of 32 opportunities | Boilerplate hedges ("does not establish…", "unverified"). Engineering-drawing competitor material is repeated for a law firm, a logistics firm and a hospital network. | briefings' `competitive_positioning` | selection and drafting | I3, I5 |
| E11 | m | M2 B2 | One recommendation has no citation; another suggests drawing-register positioning for a hospital network. | M2 B2 `meeting_recommendations` | drafting | I5 |
| E12 | m | P2, all 4 | The "Nivarque replied that the quote will be sent by 16 Nov" passage never reaches the drafter (covered by the meeting commitment, so low impact). T1's "proposal sent 1 Oct" also never reaches it. | `NVQ-COR-BXP-001#3`, `NVQ-PRP-BXT-001#1` | selection | I3 |
| E13 | m | E1 all; M2 | Undated history ("began as a municipal utility", "formed by a merger") stated without "date not stated". | `NVQ-PUB-*-001#4` | drafting | I4 |
| E14 | m | C1 A1 | Superseded 2025 price ($48) presented as a competing record ("confirm the applicable list price"), although the 2026 list is labelled approved and current. | `NVQ-PRC-2025-v1#2` | selection (superseded row included) | I3 |
| E15 | m | M2, all 4 | Undated data page (`markets-quotes.example`) still reaches the drafter; it was never cited. | `WEB-53c441291d34` | selection | I3 |

**Latent issue, not visible in these outputs:** the knowledge base contradicts itself on SCIM. `NVQ-PRD-001#3` says
Enterprise only; `NVQ-POL-002#2` says Business and Enterprise. Neither passage reached any of these briefings, but a
demo or security briefing would hit it once I3 selects product evidence (I4).

## Prioritised improvements

| Priority | Item | Addresses | Expected effect |
|---|---|---|---|
| **1** | **I3 purpose- and customer-specific selection.** Deterministically include, without relying on the agent:<br>• each customer correspondence body, not just headers;<br>• the current list-price row for every product in the customer's proposal, and the add-on rows for add-ons the customer requested;<br>• for product-demo and introduction meetings, the product sheet and security/integration FAQ rows that match the industry.<br>Drop superseded price rows, unrelated tiers and data pages; include competitor material only when the customer's evidence makes it relevant. | E2–E5, E7, E10, E12, E14, E15 | Removes the main source of run-to-run variation and the two weakest purpose scores (M2 1.2, E1 2.0) |
| **2** | **I4 temporal reasoning.** Classify decision versus state; detect "state since X" earlier than "decided in Y" for the same subject; formal disclosure; "date not stated" marking; resolve the SCIM conflict before demo briefings use it. | E1, E6, E13, latent SCIM issue | Fixes the only accuracy failures (P2 3.0) |
| **3** | **I5 derived open items and grounded recommendations.**<br>• Compute due and overdue status against the clock ("due tomorrow"), the price position against list and approval thresholds, and the cost of requested add-ons.<br>• Recommendations must cite an open item.<br>• At most one labelled generic tip; no competitor advice without customer evidence. | E5, E8–E11 | Specificity and negotiation usefulness |
| **4** | **I6 / CP-3 prompt.** Purpose rules: negotiation, follow-up, introduction and demo each require named sections. Use formal disclosure when the profile marks something contested. Replace the boilerplate hedges with one provenance line. | E6, E10, residual drafting variation | Needs CP-3 approval; measure only after I3–I5 |

**Suggested I3 acceptance additions (development split only):**
- E3, E4 and E5's passages and the M2/E1 product rows reach the drafter in 100% of offline runs;
- no superseded or unrelated price row reaches the drafter.

## Limits

- One reviewer (Claude Code), not the owner's audit.
- Fictional development data, 4 runs per scenario.
- Scores are ordinal judgements against the stated rubric and checklists. They are useful for ranking problems, not
  as precise measurements.
