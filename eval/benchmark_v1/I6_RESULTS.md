# I6: briefing organization, conciseness and PDF readability (Phase 4.5) — FICTIONAL TEST DATA

Development split only. No held-out data was read, run or scored. Protected data was not modified. Owner approval
(2026-11-12): Phase 2 (CP-3), with up to $5 of live API spend for its evaluation. Branch `worktree-i6-review`; not
pushed, not merged into `master`.

## Starting state (checked before any change)

- **Phase 1 was already committed** as `eec8d50`, and its parent is `b3b2021` (I5, the tip of `master`). So I5 was
  already incorporated, no merge was needed, and there were **no integration conflicts**. The header of
  `I6_PHASE1.md` ("from `ae77f95`", "I5 in progress") describes the state before that rebase.
- One uncommitted file, `contract.py`, held an unfinished start of Phase 2: the topic sections and wording with
  `layout=True`, but no drafter rules and no switch. It was kept and completed, not redone.

## Changes (company-independent)

| ID | Change | Files |
|---|---|---|
| P5 | **Where things go (one home per fact).** New drafter rules, only when I6 is active. They give each section a role: our_relationship holds the current position (open items, latest contact, proposal, I5 price position as one analysis item); opportunities holds not-yet-proposed add-ons with their list-price cost, plus at most two fit hypotheses for an introduction or demo; competitive_positioning holds named competitors only; meeting_recommendations holds actions that refer to figures instead of restating them. An empty section's reason is written for the reader. | `briefing.py` |
| P6 | **Concise.** Each fact stated once; the most decision-relevant item first; one or two sentences (about 45 words) per item; no price-list boilerplate; short items for conflicts already disclosed. Brevity never drops a required label (synthetic record, hypothesis to verify, not a quote, not an agreed price, date not stated, tier limit). The first contract rule now asks for a meaning only when it is a specific implication. | `briefing.py` |
| P7 | **Contract placement** (the Phase 1 proposal, with I5's results placed): the list price goes once, in our_relationship next to the price position; the demonstration plan goes in meeting_recommendations, one item per capability area; the I5 price and addition topics say "state this once"; capabilities of another product are not pitched without supporting evidence (fixes I5 weakness 2). The topic IDs, evidence groups and markers are unchanged, so coverage stays comparable between the arms. | `contract.py` |
| P8 | **PDF readability.** Items, notes, disclosures and sources are indented under their heading (on the right in Hebrew). A small gap separates items, but only when it costs no font step. Source lines are no longer justified, so URLs do not stretch them. The text of every item is unchanged. | `pdf_export.py` |
| P9 | **Evaluation support.** `--no-i6` (exactly the I5 prompt); `--dotenv` and `--ledger`, so a worktree run reads the main checkout's key in place (never copied) and records against the single shared ledger; run records save `section_notes`; the shape script reports whether the item gap was kept. | `benchmark_live.py`, `benchmark_harness.py`, `briefing_shape.py` |

**The I6 switch:** `contract.LAYOUT_ENABLED`, which takes effect only together with I5 (`briefing.i6_active()`).
With I6 off, the system prompt and the contract are byte-identical to I5 (tested).

**Not changed:**
- the I5 business analysis (`business.py`) and its figure check;
- selection and the scorer (1.1);
- the offline template and the saved demonstration: the template does not read the contract, and this is tested;
- held-out data.

### One correction during evaluation (the planned correction allowance)

B1 emptied Opportunities in all four customer scenarios. In T1 and L1 the drafter moved the Records Retention Add-on
in with the proposal, so O6b passed only vacuously (4/4 vacuous).

- **Cause:** my opportunities rule. "Never an addition to the existing proposal" was read as covering any requested
  addition. I5's analysis already separates the two cases: more of a proposed product has `quantity_after_addition`
  and belongs with the proposal; a new add-on does not.
- **Fix (before A2):**
  - the rule now follows that classification and says to cite the request and the price list, not the proposal;
  - the I6 wording of an add-on topic says "in opportunities … not an existing term" and "Do not cite the
    proposal".
- **Confirmed:** in B2 and B3 the add-on is back in Opportunities for T1 and L1, and O6b passes non-vacuously in
  both. B1 is reported as the pre-correction run.

## Live comparison

**Configuration:**
- **Arms:** A = I5 (`--no-i6`), B = I6. Order A1, B1, (correction), A2, B2, B3.
- **Identical in both arms:** six development scenarios, models, settings, fixture news, clock 2026-11-09, scorer
  1.1.
- **Caps:** `--run-cap 0.40`, experiment-only `--daily-cap 2.60`, the main ledger.
- **Free dry run:** the I6 drafting prompt is 24.7–41.2k characters, against I5's 22.3–38.2k (+8–10%).

### Automated metrics (scorer 1.1, unchanged)

| Metric | A1 | A2 | B1 (pre-fix) | B2 | B3 |
|---|---|---|---|---|---|
| R1 / R2 / R3 | 31/31, 16/16, 15/15 | same | same | same | same |
| O1 number consistency | 38/38 | 33/33 | 37/37 | 39/39 | 39/39 |
| O2a / O2b citations | 23/23, 92/92 | 23/23, 88/88 | 23/23, 85/85 | 23/23, 81/81 | 23/23, 83/83 |
| O3a / O3b / O3c | 5/5, 3/4, 6/6 | same | same | same | same |
| O4 / O5a / O5b | 5/5, 6/6, 6/6 | same | same | same | same |
| O6a open items | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 |
| O6b existing terms not opportunities (vacuous) | 4/4 (2) | 4/4 (2) | 4/4 (**4**) | 4/4 (2) | 4/4 (2) |
| O7a customer-grounded recommendations | 5/6 | 5/6 | 5/6 | 5/6 | 6/6 |
| O7b no unsupported product/competitor advice | 23/24 | 22/24 | 21/22 | 21/22 | 24/25 |
| O8 safety | 22/22 | 21/21 | 23/23 | 25/25 | 24/24 |
| Essential topics communicated | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 |
| I5 business topics communicated | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 |
| Figures not traceable to evidence or analysis | 0 | 0 | 0 | 0 | 0 |
| Calculated figure stated as a fact | 0 | 0 | 0 | 0 | 0 |
| Coverage repairs used | 0 | 0 | 1 | 1 | 1 |

- **O3b** (P2's "stored since 2020" versus "decided in 2022") fails identically in every run of both arms. It
  predates I6.
- **O7b:**
  - **A failures:** E1 recommendations naming Engineering Vault (A1, A2), and an M2 recommendation naming
    Engineering Vault (A2).
  - **B failures:** one per run, always an M2 demonstration-plan step naming the Records Retention Add-on. I6 moves
    the demo plan into recommendations, which makes I5's open scorer question (O7b against the product-demo
    purpose) more visible. The statement itself is accurate and cited.
- **Coverage repairs:** each B run's repair was triggered by a conditional eligibility check. Every first draft
  already communicated every essential topic.

### Briefing shape (P1 measures, `scripts/briefing_shape.py`)

| Measure | A1 | A2 | B1 | B2 | B3 |
|---|---|---|---|---|---|
| Median words (max) | 448 (539) | 441.5 (578) | 336.5 (376) | 322.5 (413) | 359.5 (397) |
| Figures/dates restated across sections | 27 | 24 | 1 | 0 | 2 |
| Competitive items without competitor evidence | 3 | 1 | 0 | 0 | 0 |
| Empty Opportunities, customer scenarios | 2/4 | 2/4 | 4/4 | 2/4 | 2/4 |
| Empty sections with the drafter's specific reason | 8/8 | 10/10 | 13/13 | 12/12 | 11/11 |
| PDF: smallest font; briefings at 9 pt | 8.0; 4/6 | 8.0; 4/6 | 9.0; 6/6 | 8.5; 5/6 | 8.5; 5/6 |
| PDF: shortened / overflow | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| PDF: gap between items kept | 2/6 | 3/6 | 5/6 | 5/6 | 5/6 |

The A arm's empty sections also carry reasons, because Phase 1 (P3) keeps the drafter's notes in both arms.

### Success criteria (from the Phase 1 proposal)

| # | Target | Result | Met |
|---|---|---|---|
| S1 | Empty Opportunities in customer scenarios with an unquoted request: 0/4, O6b 4/4 non-vacuous | B2, B3: 2/4 (P2, C1); O6b 4/4, 2 non-vacuous, as in A | **No, by design** (below) |
| S2 | Competitive items without competitor evidence: 0 | 0, 0, 0 (A: 3, 1) | Yes |
| S3 | Restated figures and dates at most half of A | 1, 0, 2 (A: 27, 24) | Yes |
| S4 | Every PDF one page, not shortened, at ≥ 8.5 pt | 18/18; minimum 8.5 (A: 8.0) | Yes |
| S5 | Median words not above A | −19% to −27% | Yes |
| S6 | Empty sections with a specific reason: all | 36/36 | Yes |
| S7 | No regression: coverage, scorer metrics within noise, O8 full | coverage 50/50 and 13/13 in every run; O8 full; O7b B failures = demo-scorer conflict | Yes |
| S8 | Manual audit: six dimensions not lower; organization and conciseness scored | see below | Yes (not scored 0–4) |

**S1, by design:** the target assumed every unquoted request would sit in Opportunities. I kept I5's safeguard
instead, which you asked to preserve: more of a product already proposed (P2's 60 users) is discussed with the
proposal, because B3 of I5 failed O6b when it sat in Opportunities. C1's request is a term question whose price
effect cannot be calculated, and it becomes a verify recommendation. Both briefings now say why Opportunities is
empty, for example "the user addition extends the existing proposal".

## Manual review

**Scope:**
- **Read in full:** the six B1 briefings; T1 and L1 in B3; E1 and M2 in B2; the M2 Opportunities and recommendations
  in A1.
- **Spot-checked:** the other B briefings.
- **Rendered:** P2 as a PDF, from I5, A and B.
- **Scanned (all 30 briefings):** the CP-2 critical checklists (lexical match), and every "agreed", "approved" and
  "approval".

This is lighter than the CP-2 audit, and the dimensions were judged, not scored 0–4.

**Factual accuracy: unchanged.**
- No untraced figure in any run.
- The I5 results appear exactly in every B briefing: 5.8% and 9.6% (USD 44.20 escalation price), 8.8%, 5.9%,
  USD 3,120 / 37,440 / 74,880, USD 1,920 / 23,040, USD 720 / 8,640, and the 3-day / tomorrow / 7-day deadlines.

**Important omissions: none.**
- **Checklist:** all B runs 38/38 (A1 38/38; A2 37/38, missing T1's 14 November quote date).
- **Shorter briefings dropped no critical item.** What disappeared is the restatement and price-list boilerplate.
  For example, P2's recommendation no longer repeats "USD 49 against USD 52 … billed annually in advance".

**Commercial status: kept.**
- Every commercial "agreed" or "approved" in the B briefings is negated or conditional: "approval is not recorded",
  "it is not an agreed price", "verify whether the existing offer's discount was approved", "not a quote or an
  agreed price".
- The other uses are recorded customer agreements (to pilot, to run a workshop) and product "approval workflows".

**Purpose relevance: better.**
- **M2 (product demo):** I5 described each capability twice, in six Opportunities items and again in the
  recommendations. B has a six-step demonstration plan, one step per area, and at most one fit hypothesis.
  Engineering-Vault-only options (customer-supplied keys, single-tenant cloud) are no longer pitched to a hospital
  network. The SCIM disagreement and the missing CRM/SharePoint sync are still flagged.
- **Negotiations:** Competitive positioning no longer holds product facts.

**Contradiction recognition:** the same in both arms (O3a, O3c full; P2's O3b failure in both).

**Grounded recommendations:** the same or better (O7a 5/6, 5/6, 6/6 against 5/6, 5/6).

**Organization (new dimension): clearly better.**
- **P2:** Our relationship runs request → open tasks → proposal with price position (one analysis item) → addition
  cost → earlier meeting.
- **Recommendations:** each starts with the action and refers back instead of restating ("prepare the revised quote
  for the promised deadline, 7 days from the briefing date").
- **L1:** keeps I5's best insight, the "Completed" task against the correspondence, as a verify action.

**Conciseness (new dimension): clearly better.** Median −25%, restatements about 0, all PDFs at 8.5–9 pt, and the
item gap kept in 15 of 18.

**Weaker:**
- **E1 (introduction) is lean:** 134–216 words against 252–264, with one fit hypothesis (Core Business approval
  workflows for maintenance records) and two discovery questions. Its checklist is complete, but the CP-2 checklist's
  hypothesis named Engineering Vault for infrastructure; B uses another documented product.
- **B2 M2** has no fit hypothesis ("the demonstration plan covers it"), which the "at most two" rule allows.
- **Wording:** one T1 recommendation (B3) reads "within seven days and five days from the briefing date".

## Remaining problems and owner decisions

1. **S1 placement.** Should more of an already-proposed product (P2's 60 users) appear under Opportunities (the
   Phase 1 proposal) or stay with the proposal (the I5 safeguard, kept here)? An owner decision; it changes only
   P2-type scenarios.
2. **O7b against the product-demo purpose** (open since I5): with the demo plan in recommendations, every B run fails
   O7b once on M2. This is a scoring decision; the scorer was not changed.
3. **Eligibility trigger false positives.** The conditional check flags an item that cites a capability's passage
   and contains a trigger word ("deployment", "workflow") without mentioning the capability. This triggers one
   coverage repair per B run, about 1–2 extra calls and +$0.003–0.006 per run. The triggers could be narrowed in a
   later increment.
4. **E1 brevity:** consider asking for one or two hypotheses in an introduction rather than "at most two".
5. **Cost per run:** +19% (A mean $0.091, B mean $0.108), from the longer prompt and the repair in item 3.
6. **Offline template (P7 of Phase 1)** is still unchanged; it needs the owner's decision about the saved
   demonstration.
7. **Benchmark-derived example in the evaluated prompt.** The evaluated I6 rule said to refer to figures "(\"the
   60-user request\", …)"; 60 users is DEV-P2's own request. I noticed it during the final check and replaced it with
   the generic "the requested addition" before committing. The committed prompt therefore differs from the
   evaluated one by those three words, and was not re-run live. P2's B briefings may have been slightly helped
   (they say "the requested user addition"). The other five scenarios have no 60-user figure.
8. **Small samples:** three I6 runs (one before the correction) and two I5 runs. The shape gains are much larger
   than the run-to-run spread; the scorer metrics are not distinguishable from noise, which is the target.

## Owner acceptance (2026-11-12)

I6 was accepted at `9a40549`. Decisions:
- **P2 and C1 keep an empty Opportunities section** when no genuine new opportunity is supported. The briefing says
  why.
- **Product names are appropriate in a demonstration** when the evidence and the eligibility rules support them.
- **The benchmark scorer stays unchanged (1.1).** Its limitations are documented below.
- **Deferred:** minor cosmetic issues (for example "within seven days and five days") and recomposing the offline
  demonstration.

**Scorer and measure limitations** (how I6 results should be read):

| Measure | Limitation | Reading for I6 |
|---|---|---|
| O7b (no unsupported product/competitor advice) | Matches product names in recommendations as text. A demo-plan step that names a product is flagged even when the product evidence and eligibility support it. | M2's one O7b failure per I6 run (Records Retention Add-on) is a scorer limitation, not an unsupported claim (owner decision above). |
| O6b (existing terms not opportunities) | Vacuous when Opportunities holds no customer evidence. | P2 and C1 pass vacuously by design: an empty Opportunities section with a stated reason is the accepted outcome. |
| Eligibility (conditional coverage) | Lexical triggers: an item citing a capability's passage that contains a trigger word ("deployment", "workflow") counts as "cited only" even when it does not mention the capability. | Every I6 "cited only" eligibility result was such a false positive. Each causes one coverage repair (about +$0.003–0.006 per run). |
| Coverage of essential topics | A lexical proxy: an item citing the evidence and stating a marker. | It shows that content is present, not its quality; quality comes from the manual review. |
| P1 restated figures and dates | The same token, not necessarily the same fact. | Approximate; the A/B difference (24–27 → 0–2) far exceeds this uncertainty. |
| CP-2 checklist scan (this report) | A lexical match per checklist item. | Supplemented by reading the briefings. |

**Final-wording check (before integration).**
- **Run:** one live development run, DEV-P2 only, I6 on, at `9a40549`
  (`runs/benchmark_v1/cp0/20261112T051011Z_i6_final_P2`).
- **Why P2:** it is the scenario whose 60-user figure the old example used.
- **Result, the same as P2 in B2 and B3:**
  - essential topics 13/13 and I5 topics 4/4;
  - 0 untraced figures and no repair;
  - no scorer failure;
  - 0 restatements, 8.5 pt, and both empty sections with a specific reason.
- **The generic wording is used:** "Confirm the requested addition".
- **Cost:** $0.0195 (2 calls). I6 total: **$0.5264**.

**Pre-integration checks:**
- **Clean:** both checkouts were clean.
- **No missing commits:** `b3b2021` (I5) is an ancestor of `9a40549`, and `master` had no commit missing from I6.
- **Held-out:** the freeze is valid (`assert_heldout_frozen`, hashes only, in both checkouts); executions 1 of 3,
  unchanged.
- **Protected data** (index, history database, walkthrough, `data/`) in the main checkout: no file modified after
  2026-11-09.
- **No held-out or `data/` file** is changed by I6.

## Cost, time and verification

**Spend** (main ledger; every run "Protected local data unchanged: yes"; no stop):

| Run | Calls | Cost |
|---|---|---|
| A1 | 19 | $0.0971 |
| B1 | 21 | $0.1069 |
| A2 | 20 | $0.0845 |
| B2 | 22 | $0.1060 |
| B3 | 23 | $0.1124 |
| **Total** | **105** | **$0.5069**, against the $5 approval |

- The estimate was $0.40–0.55.
- Ledger total before I6: $2.0352; after: $2.5421.
- The dry runs made no call.

**Elapsed time** (Israel time, UTC+2):
- Start: 05:45 (state check).
- Coding and tests: 05:47–06:01.
- Live runs: 06:02–06:20, including the correction.
- Review, final tests and report: 06:20–06:30.
- **Total about 45 min,** against an estimate of 2¼ h (range 1½–3 h).

**Tests:**
- **Full suite before the evaluation:** 760 passed, 0 failed (5 min 3 s).
- **After the correction:** first the I6 and I5 test files, 57 passed; then the full suite, **760 passed, 0 failed**
  (5 min 14 s).
- **After the final three-word change to the example** (item 7 above): every test file that loads the drafter
  rules or the contract (`test_layout_i6`, `test_briefing`, `test_contract_i31`, `test_business_i5`, `test_llm`)
  and the production-name guard, 114 passed.
- **New in `tests/test_layout_i6.py` (9 tests):**
  - the rules with I6 off are exactly the I5 rules, and I6 is active only with I5;
  - every I6 contract edit applies exactly once;
  - layout changes only the section and wording, never the measured ids, groups or markers;
  - an extension stays with the proposal while a new add-on goes to Opportunities, and I5's wording is unchanged;
  - the purpose-brief addition;
  - P2 and M2 offline: the same topics and evidence in both arms, the I6 sections, an identical offline briefing,
    and saved notes;
  - the PDF indent (EN/HE), text unchanged, headings at full width;
  - the larger font is preferred over the item gap.

**Data:**
- **Held-out:** none read or run. A directory listing of the main checkout's `runs/benchmark_v1/` showed held-out
  folder names; none was opened.
- **Key:** read in place from the main checkout's `.env`, never copied or printed. The live script scans every
  output for it.
