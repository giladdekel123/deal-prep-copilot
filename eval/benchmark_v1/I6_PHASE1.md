# I6 Phase 1: briefing organization and conciseness (Phase 4.5) — FICTIONAL TEST DATA

Development split only. No held-out data was read, run or scored. No paid call was made. Work was done on branch
`worktree-i6-review` (from `ae77f95`), in its own worktree, while I5 is in progress on `master`; nothing is merged.
Owner approval (2026-11-12): Phase 1 (P1–P4). Phase 2 is **not** started; it needs I5 merged and CP-3.

## Scope

The plan's I6 ("live drafting update", CP-3) was largely delivered early by I3.1 (meeting contract) and I4
(chronology rules). The owner re-scoped I6 to the organization, business relevance, clarity, section placement and
conciseness of the final briefings. Phase 1 contains only the parts that do not change what the live AI receives.

## Changes (company-independent)

| ID | Change | Files |
|---|---|---|
| P1 | **Briefing-shape measurements**, a standalone script for saved development records (live or offline): words and items per section, empty sections and their reasons, empty Opportunities in customer scenarios, Competitive-positioning items without competitor evidence, figures and dates restated across sections, PDF font, shortening and source lines. Shape, not quality; the scorer is unchanged. Refuses held-out paths and non-`DEV-` scenarios. | `scripts/briefing_shape.py` (new) |
| P2 | **PDF sources grouped by document.** Cited passages of one document with the same provenance label share one numbered line (`DOC#1, #3: label`); every passage ID is still listed. A one-passage document keeps the previous `DOC#n: label` form. An item citing four passages of one price list now shows one reference instead of four. Passages with different labels stay separate, so no label is lost. | `src/deal_prep/pdf_export.py` |
| P3 | **Empty sections explained.** The citation check already requires an `empty_section:<name>` disclosure from the drafter, but its text was discarded, so the app and PDF said "see gaps" with nothing there. It is now kept as `section_notes` and shown under the empty heading ("No supported content: …"). A note that only repeats "no supported content" is dropped, so the usual pointer to the gaps stays. `section_notes` is a separate result field: the scored `disclosures` and the saved demonstration are unchanged. | `src/deal_prep/briefing.py`, `src/deal_prep/pipeline.py`, `src/deal_prep/pdf_export.py`, `app/streamlit_app.py` |
| P4 | **Phase 2 drafting proposal** (below). Not applied. | this document |

**Not changed:** prompts and contract (live input), selection, the offline template, disclosures text, the scorer,
the benchmark harness, held-out data, the saved demonstration (JSON).

## P1 baseline: existing development records (measured 2026-11-12)

Live runs: 6 scenarios each (P2, C1 negotiation; T1, L1 follow-up; E1 introduction; M2 product demo). Offline: 12
scenarios × 2 news modes (I3.1-era code). "Customers" = scenarios whose drafting input holds the customer's
relationship records.

| Run | Median words (max) | Empty Opportunities, customers | Competitive items without competitor evidence | Figures/dates restated across sections | Smallest PDF font, before → after P2 | Briefings at 7.5 pt minimum, before → after | Source lines, per passage → grouped |
|---|---|---|---|---|---|---|---|
| CP-2 A1 | 244 (284) | 0 / 4 | 0 | 5 | 9.0 → 9.0 | 0 → 0 | 60 → 38 |
| CP-2 B1 | 236 (266) | 0 / 4 | 0 | 2 | 9.0 → 9.0 | 0 → 0 | 56 → 35 |
| CP-2 A2 | 217 (258) | 0 / 4 | 0 | 4 | 9.0 → 9.0 | 0 → 0 | 53 → 32 |
| CP-2 B2 | 234 (274) | 0 / 4 | 0 | 5 | 9.0 → 9.0 | 0 → 0 | 57 → 33 |
| I3.1 B4 | 379 (428) | 3 / 4 | 2 | 20 | 8.0 → 9.0 | 0 → 0 | 96 → 39 |
| I3.1 B5 | 381 (457) | 3 / 4 | 4 | 20 | 8.0 → 9.0 | 0 → 0 | 93 → 39 |
| I4 B1 | 404 (457) | 1 / 4 | 4 | 16 | 7.5 → 8.5 | 1 → 0 | 100 → 39 |
| I4 B2r | 396 (419) | 1 / 4 | 4 | 18 | 7.5 → 8.5 | 1 → 0 | 98 → 39 |
| I4 B3 | 363 (446) | 3 / 4 | 2 | 22 | 7.5 → 8.5 | 2 → 0 | 96 → 39 |
| Offline dev (24) | 267 (317) | 0 / 16 | 0 | 4 | 9.0 → 9.0 | 0 → 0 | 230 → 134 |

No briefing was shortened or overflowed, before or after.

**Reading:**
- I3.1 made briefings complete (36/36 topics) and about 1.6× longer. It also emptied Opportunities in most
  customer scenarios and moved product facts under Competitive positioning (the rule says what is not an
  opportunity, with no positive guidance). I4 kept this pattern.
- Restated figures and dates rose from 2–5 per run (CP-2) to 16–22 (I3.1, I4). In I4 B3 all 22 are proposal terms,
  due dates and requested quantities stated in Our relationship and again in Meeting recommendations (spot-checked).
  E1's two (21 vs 24 wind farms, repeated in a discovery question) are arguably legitimate.
- P2 alone gives about one font step back on the densest live briefings (P2 and M2: 7.5 → 8.5 pt), headroom that
  I5's added content will use.
- The offline template has no empty Opportunities because it puts the existing proposal there (O6b 0/8 offline),
  which this measure does not judge.

**Limits:** the restatement count is an approximation (same token, not necessarily the same fact; it cannot see
M2's conceptual duplication of the six demo areas). Empty-section reasons are `n/a` for these records (made before
I6, and the harness does not yet save `section_notes`). One run per arm per row; small samples.

## P4: Phase 2 proposal (CP-3; not applied)

Phase 2 changes what the live AI is instructed to do, so it needs CP-3 approval. It must be written on top of I5's
final prompt, because I5 edits the same rules and contract topics and decides where its derived items appear.
Placeholders marked **[I5]** are fixed only after I5 is merged.

### Rule changes (`briefing.py`, contract rules)

1. Replace, in the first contract rule, "cites that evidence, and says what it means for this meeting" with:
   "cites that evidence. Add what it means for this meeting only when that is a specific implication (a decision,
   risk or next step), never a general phrase such as 'this provides context'."
2. New block, "Where things go (one home per fact)":
   - **our_relationship:** where the relationship stands now. Start with the latest contact and every open request
     or commitment with its status and due date; then the proposal terms with the current list price beside them
     (an inference item); then earlier meetings. **[I5: due or overdue flags and the price position go here.]**
   - **opportunities:** commercial possibilities not yet proposed: what the customer asked for beyond the current
     proposal (more users, an add-on, a different term) **[I5: with the add-on's list value]**, and, for an
     introduction or demonstration, at most two fit hypotheses tying a documented capability to the organization's
     own evidence. Never existing proposal terms.
   - **competitive_positioning:** only evidence about a named competitor. Product capabilities without a competitor
     belong in opportunities (fit) or meeting_recommendations (what to show). If no competitor is named, leave it
     empty.
   - **meeting_recommendations:** actions only. Cite the evidence, but do not restate figures and dates already
     given above unless the action needs them.
   - **empty sections:** the `empty_section:<name>` text says the specific reason; it is shown to the reader.
3. New block, "Concise":
   - state each fact once, in its home section;
   - put the most decision-relevant item first in every section (a shortened PDF keeps the first two);
   - one or two sentences per item (about 45 words); leave out price-list boilerplate (tax, billing frequency,
     effective dates) unless the meeting turns on it;
   - a conflict or ambiguity already in required_disclosures needs only a short item (both figures or dates,
     attributed, "unresolved"); the disclosure carries the quotations.

### Contract changes (`contract.py`)

| Topic | Now | Proposed |
|---|---|---|
| `list_price:*` (negotiation, follow-up) | section `meeting_recommendations`, "in a recommendation, state the list price beside the proposed terms" | section `our_relationship`, as an analysis item beside the proposal terms **[I5: or I5's price-position item]** |
| `approval_policy` (negotiation) | `meeting_recommendations` | unchanged (it governs an action) |
| `demo:*` (product demo) | `opportunities` | `meeting_recommendations`: one demonstration-plan item per area (what to show, why it may matter, to verify) |
| product-demo purpose brief | "Recommendations form a demonstration plan." | add: "Opportunities holds at most two fit hypotheses grounded in the organization's own evidence; do not describe a capability in both sections." |

Coverage is section-independent, so moving a topic's section cannot lower it. O6b (existing terms under
Opportunities) is unaffected: the proposal stays out of Opportunities, and requests cite correspondence, which O6b
allows and which makes it non-vacuous.

### Supporting change

- `scripts/benchmark_harness.py`: save `section_notes` in each record (one line), so P1 can count empty sections
  with a reason. Deferred to Phase 2 because I5 may edit the harness.

### Evaluation plan (needs owner authorization; paid)

- **Design:** A/B on the six development scenarios, as in I3.1 and I4. A = I5 final (a switch gives exactly the I5
  prompt), B = I6. Interleaved A1, B1, A2, B2; one correction run (B3) allowed.
- **Cost estimate:** about $0.014–0.02 per briefing (I4 measured about $0.014); 24–30 briefings, so **about
  $0.35–0.60 expected**, at most about $2.5 with the per-run caps. The production daily cap ($1 per UTC day) needs
  the experiment-only `--daily-cap` or two days.
- **Success criteria (B against A, development split):**

| # | Measure (P1 unless stated) | Target |
|---|---|---|
| S1 | Empty Opportunities in customer scenarios with an unquoted request | 0 / 4, with O6b 4/4 non-vacuous |
| S2 | Competitive items without competitor evidence | 0 |
| S3 | Figures and dates restated across sections | at most half of A |
| S4 | PDF | every briefing one page, not shortened, at ≥ 8.5 pt |
| S5 | Median words | not above A |
| S6 | Empty sections with a specific reason | all |
| S7 | No regression | coverage 100% communicated; scorer 1.1 metrics within the noise rule; O8 full |
| S8 | Manual audit (CP-2 rubric) | six dimensions not lower; two new ones scored for A and B: organization (placement and order) and conciseness |

### Offline template (P7; not proposed for Phase 2 without an owner decision)

The template puts the existing proposal and an unrelated general price row under Opportunities (O6b 0/8 offline).
Any change to the template changes the re-composed saved demonstration, which
`test_saved_demo_is_exactly_the_shared_template_output_for_its_stored_evidence` forbids. I5's offline
recommendations hit the same constraint; the owner's decision for I5 decides P7.

## Verification (targeted, as instructed; the full suite was not run)

| Run | Files | Result |
|---|---|---|
| 1 | `test_app.py` (PDF EN/HE, conflict-source numbering, shortening, overflow, Streamlit page), `test_briefing.py`, `test_pipeline.py`, `test_llm.py`, `test_contract_i31.py`, `test_citations.py`, the three saved-demonstration tests | 134 passed (2 min 36 s) |
| 2 | `test_offline_briefing_readability.py` (whole file, incl. one-page PDFs and the saved demo), `test_offline_news_status.py`, `test_selection_i3.py`, `test_layout_i6.py`, `test_benchmark.py::test_no_benchmark_name_or_domain_in_production_code` | 155 passed (1 min 25 s) |
| 3 | `test_app.py`, `test_layout_i6.py` again, after a one-line tidy-up in the app | 50 passed (1 min 9 s) |

- 289 distinct tests passed. The rest of the suite (701 at I4), including `test_benchmark.py` (except the name guard),
  `test_agent.py`, `test_orchestrator.py` and `test_offline.py`, was not run. The pipeline change only adds a result
  key, so the risk is low but not tested.
- **Existing tests unchanged.** `test_app.py:123` and `:139` (sources by passage ID) still pass, because a document
  cited through one passage keeps its `DOC#n: label` line.
- **New: `tests/test_layout_i6.py` (14 tests, no index, no network):**
  - grouping order, separate labels, every passage listed (EN and HE), one reference per document;
  - the drafter's specific reason kept, generic and misplaced notes dropped, 300-character cap;
  - `draft_briefing` returns the notes without changing `disclosures`;
  - the offline template produces no notes, so offline briefings are unchanged;
  - the pipeline result carries the notes, and the PDF shows them (EN and HE);
  - P1 restatement detection (years and date digits excluded), placement measures, held-out refusal.
- **Visual check:** I4 B3's P2 briefing rendered in English and Hebrew with the new renderer (one illustrative note
  added in a scratch copy). Sources went from 22 lines to 9; Hebrew keeps the grouped IDs left-to-right.
- **Held-out:** none read. Only development records from CP-2, I3.1, I4 and one offline run were read. No I5 run
  folder was opened. No API call; no `.env` in the worktree.

## Elapsed time

Estimate given at start: 2.5–3.5 h (03:25 → about 06:00–07:00 JST). Actual: 03:25–03:45, about 20 minutes. As in
I4, coding on top of existing machinery was much faster than estimated. With 1.1–1.7 GB of free memory, the
targeted tests took 5 minutes in total.
