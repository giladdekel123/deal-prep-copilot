# I3.1: meeting-purpose drafting contract (Phase 4.5, early CP-3) — FICTIONAL TEST DATA

Development split only. No held-out data was read, run or scored. Owner authorization (2026-11-11): up to $5
additional OpenAI spend for this evaluation. The prepaid credit shown was $4.32, and auto-recharge stays off.
I3 is preserved at `16209bc`. The CP-2 and I3 baselines are unchanged.

## Plan and cost estimate (recorded before any paid call)

- **Design:** interleaved A/B on the six audited scenarios, same models, fixtures, clock and settings:
  - A = the I3 drafter (`--no-contract`: the prompt is exactly the I3 prompt, no repair);
  - B = the I3.1 drafter (contract plus one coverage repair).
- **Order:** A1, B1, A2, B2, A3, B3, i.e. 36 briefings. The two I3 runs of `16209bc` (I3-1, I3-2) are further A
  references.
- **Dry run (free), worst case per briefing:**
  - A: $0.059–0.063, i.e. $0.369 for six;
  - B: $0.093–0.101, i.e. $0.588 for six, with the extra repair call included.
  - The production per-briefing guard ($0.10) refuses any call that could exceed it. If it refuses the repair call,
    the valid first draft is kept.
- **Expected actual cost:** about $0.066 per A run (I3 runs: $0.064 and $0.068) and about $0.09–0.12 per B run,
  i.e. about $0.5–0.6 in total.
- **Worst case for the plan:** 3 × $0.369 + 3 × $0.588 = $2.87. This is below the $5 authorization and the $4.32
  credit.
- **Per-run caps:** `--run-cap 0.30` for A and `--run-cap 0.40` for B.
- **Integrity:** the live script fingerprints the protected data before and after every run.

## Implementation (company-independent)

- **New: `src/deal_prep/contract.py`.**
  - **Purpose briefs:** negotiation, follow-up, product demonstration, introduction and general.
  - **`essential_topics(bundle)`** derives the topics a briefing must address from the purpose and the evidence
    actually selected:
    - every customer correspondence (request, date, reply, status) and proposal (terms, validity, status);
    - approved meeting concerns and decisions, and every unresolved task;
    - list prices of products in play (negotiation, follow-up) and the discount-approval policy (negotiation);
    - for a product demo, every documented capability area: workflows, retention and legal hold, security,
      identity, data region and deployment, integrations;
    - for an introduction, a fit hypothesis that must cite both product and company evidence;
    - every contested figure from the evidence profile (both sides).
  - **`coverage(draft, topics)`** classifies each topic in the final briefing:
    - communicated: one item cites the evidence and states its content;
    - cited_only: the evidence is cited, but none of its content is stated;
    - gap_declared or missing.
  - It is a lexical proxy. Its topics come from the same evidence the drafter sees.
- **`briefing.py`:**
  - The model receives `meeting_contract` (purpose brief plus topic id, section, requirement and evidence IDs; no
    scoring markers) and short contract rules. These require:
    - stating each topic's content and citing it;
    - `topic_gap:<id>` instead of a guess;
    - figures exactly as stated, no new calculations;
    - existing proposal terms not under Opportunities;
    - statements that do not fit together kept, attributed and called unresolved;
    - specific recommendations, and no competitor unless the evidence names one.
  - `CONTRACT_IN_MODEL_INPUT = False` gives exactly the I3 prompt; it exists for the A/B comparison only.
  - **One coverage repair** (`repair_coverage`, on in the app's live mode and the B arm): only after a valid draft
    with unaddressed topics, kept only if valid and strictly more complete. Any failure keeps the first draft.
  - Model-declared topic gaps are shown with the briefing as `kind: topic_gap` disclosures.
- **Results:** `pipeline` returns `result["coverage"]`, including the first draft's counts and whether it was
  repaired. The benchmark record carries it (not scored).
- **`benchmark_live.py`:**
  - `--no-contract` selects the A arm;
  - a protected-data fingerprint is taken before and after each run, and a change fails the run;
  - the worst-case estimate includes the repair call.
- **Not changed:** selection (I3), models, the scorer, citation and conflict rules, provenance, held-out data.
  Production code contains no benchmark names (guard test).

## Correction during the experiment (one round)

- **Problem:** in B1–B3, the contract told the drafter to state the list price "under opportunities, beside the
  proposed terms". In every customer scenario it then cited the existing proposal under Opportunities (O6b 0/4 in
  all three runs). Existing terms are not opportunities.
- **Fix:** the list-price topic now goes in a recommendation, and one rule was added: existing proposal terms belong
  in `our_relationship`.
- **Verified** by two further B runs (B4, B5): O6b 4/4 in both, coverage unchanged. B4–B5 are the final drafter.
  B1–B3 are reported as the first variant.

## Spending and integrity

| Run | Arm | Cost | Calls | Protected data | Briefings |
|---|---|---|---|---|---|
| A1 | I3 | $0.066485 | 19 | unchanged | 6/6 |
| B1 | contract v1 | $0.087194 | 21 | unchanged | 6/6 |
| A2 | I3 | $0.062824 | 19 | unchanged | 6/6 |
| B2 | contract v1 | $0.073049 | 18 | unchanged | 6/6 |
| A3 | I3 | $0.048004 | 20 | unchanged | 5/6 (L1: provider HTTP 520) |
| B3 | contract v1 | $0.073040 | 18 | unchanged | 6/6 |
| B4 | contract (final) | $0.082050 | 20 | unchanged | 6/6 |
| B5 | contract (final) | $0.071794 | 19 | unchanged | 6/6 |
| **Total** | | **$0.564438** | 154 | 8/8 unchanged | 47/48 |

- **Against the authorization:** $0.56 of the $5 authorized, all within the plan's worst case of $2.87.
- **Credit:** if the $4.32 prepaid credit was current when shown, about $3.76 remains. Credit cannot be read with an
  API key, so this is not verified. It was never exhausted, and no top-up is needed.
- **Ledger:** cumulative experiment spend is $1.060376.
- **Per briefing:** about $0.011 for A and about $0.013 for B, about 20% more (larger prompt, about 1–2.5k extra
  characters).
- **Repair:** the coverage repair never fired live, because every B first draft already communicated every topic. It
  is verified offline only (tests).
- **A3 L1:** a transient provider error (HTTP 520). By design production makes no SDK retries. It is excluded from
  the quality means and counted as a failure in the scorer table.
- **Blocked connections:** none. No spending cap refused a call. The held-out split was not compiled, read or run.

## Results

### Coverage of essential topics in the final briefings (lexical proxy)

| Arm | Communicated topics |
|---|---|
| A (I3), three runs | 23/36, 20/36, 18/30 (L1 failed) |
| B, all five runs | **36/36**, on the first draft each time |

A's misses are the same in every run:
- the M2 demo areas (5 of 6 missing in all three);
- the list price in negotiations and follow-ups;
- the approval thresholds in two of three P2 and C1 runs;
- the add-on list price in follow-ups.

### Scorer 1.1 (news_fixture)

| Metric | I3-1 | I3-2 | A1 | A2 | A3 | B1 | B2 | B3 | **B4** | **B5** |
|---|---|---|---|---|---|---|---|---|---|---|
| O1 number consistency (partial) | 31/34 | 34/36 | 33/35 | 36/38 | 29/31 | 43/43 | 42/43 | 40/41 | **36/36** | **39/39** |
| O2a must-cite cited | 23/23 | 23/23 | 23/23 | 22/23 | 18/23 | 23/23 | 23/23 | 23/23 | 23/23 | 23/23 |
| O3b_text contradiction stated | 4/4 | 3/4 | 3/4 | 2/4 | 3/4 | 4/4 | 4/4 | 4/4 | **4/4** | **4/4** |
| O6a open items | 9/12 | 9/12 | 7/12 | 8/12 | 9/12 | 12/12 | 12/12 | 12/12 | **12/12** | **11/12** |
| O6b existing terms not opportunities | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 0/4 | 0/4 | 0/4 | **4/4** | **4/4** |
| O7a customer-grounded recommendations | 5/6 | 4/6 | 6/6 | 6/6 | 4/6 | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 |
| O7b no unsupported product/competitor advice | 14/14 | 13/13 | 14/14 | 15/15 | 12/12 | 18/19 | 16/17 | 16/17 | **19/19** | **19/19** |
| O3c undated marked | 2/6 | 2/6 | 2/6 | 3/6 | 3/6 | 3/6 | 3/6 | 2/6 | 2/6 | 2/6 |
| O3b formal disclosure | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| R1, R2, R3, O3a, O4, O5a, O5b | full | full | full | full | full | full | full | full | full | full |

O8 is 22/22 or 23/23 in every run except A3 (18/19: the provider error).

**Reading the remaining failures:**
- **B5 O6a:** the T1 task is stated with its date written "14 November", without the year, which the scorer's
  phrase match misses.
- **B1–B3 O7b (E1):** the fit hypothesis names Engineering Vault for a new lead. The scorer allows no product for a
  scenario without relationship records, while the contract asks for exactly such grounded hypotheses. This is a
  scorer-rule tension; the scorer is unchanged.
- **O7a in M2 (every B run):** most demo recommendations cite product evidence rather than the hospital's own.
- **B O1:** the one remaining failure is the news window wording, as before.

### Manual audit (Claude Code; CP-2 rubric, checklists and 0–4 scale)

- **B:** the final drafter, B4 and B5: 12 briefings, read in full.
- **A:** the I3 audit (I3-1, I3-2), checked against A1 in full and against the A2–A3 coverage. They are consistent:
  the same M2, list-price and approval gaps.
- **Bias risk:** the same reviewer designed the contract. The scores are ordinal judgements for ranking.

| Dimension | CP-2 | I3 (A) | **I3.1 (B)** | P2 | T1 | C1 | L1 | E1 | M2 |
|---|---|---|---|---|---|---|---|---|---|
| Factual accuracy | 3.8 | 3.9 | **3.9** | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 3.5 |
| Important omissions | 3.5 | 3.7 | **4.0** | 4.0 | 4.0 | 4.0 | 4.0 | 3.7 | 4.0 |
| Purpose relevance | 2.8 | 3.1 | **3.9** | 4.0 | 4.0 | 4.0 | 4.0 | 3.5 | 4.0 |
| Contradiction recognition | 2.4 | 2.7 | **3.0** | 3.0 | n/a | n/a | n/a | 3.0 | 3.0 |
| Specific vs generic | 2.6 | 3.0 | **3.8** | 4.0 | 4.0 | 4.0 | 4.0 | 3.0 | 3.5 |
| Grounded recommendations | 3.5 | 3.9 | **4.0** | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 |

- **Contradiction scoring:** a contradiction stated in text, attributed and unresolved but without a formal
  disclosure scores 3, as in the CP-2 and I3 audits. P2 rose from 2 to 3 because both of its contradictions are now
  stated.
- **Critical checklist items in the final briefings:**
  - B4 and B5: 39/39 each, counting E1's fit hypothesis as present (it does not use the Engineering Vault /
    infrastructure fit);
  - I3: 35.5/39;
  - CP-2: about 33.8/39.

### Concrete improvements (B4/B5 versus I3)

- **M2 product demo, purpose relevance 1.5 → 4.0.** Both runs give a six-area demo plan. Example: "Walk through
  retention schedules, legal holds and disposal certificates, and ask whether the digitally signed consent-form
  process has relevant retention requirements." The SCIM disagreement is handled correctly: "SAML 2.0 and OpenID
  Connect … they disagree on SCIM … tier availability is unresolved." The missing CRM/SharePoint sync is stated as a
  limitation. I3 had none of this.
- **P2 and C1 negotiation, list price and approvals in 4 of 4 briefings (I3: 0 of 4 for the list price).** Example,
  C1: "Discuss the requested 36-month price against the … list price of USD 52 … and the existing proposed USD 47 …
  account executives may approve discounts up to 15 percent from list; above 15 percent requires … regional sales
  director …; above 25 percent requires CFO approval."
- **P2 chronology (critical error E1), recognised in 4 of 4 B briefings (I3: 0 of 2).** Example: "the board decided
  on a single digital archive in 2022, but also says every quality certificate has been stored … since 2020. The
  relationship between those statements needs clarification", together with a recommendation to ask.
- **Follow-ups (T1, L1):**
  - the latest contact date is stated (I3: missing in every run);
  - the requested add-on is priced at list ($240/TB) with "do not present that list price as an agreed quote";
  - L1 surfaces a real inconsistency: the meeting marks the revised quote as completed, while the correspondence
    still says options are requested ("verify receipt").
- **Uncertainty is kept:** every product-fit statement is phrased "to verify, not assumed". No figure was
  calculated, so there is no unsupported price position. No competitor is mentioned anywhere.

### Regressions and remaining failures

- **Section use, minor:** Opportunities is often empty in customer scenarios (P2, C1, L1, T1 in B4/B5), and
  product-capability facts land in "Competitive positioning". No competitor is implied, but the label no longer fits
  the content. Cause: the new "existing terms are not opportunities" rule with no positive guidance for that section.
- **Imprecise caveat, M2 (both runs):** the security and deployment recommendation proposes customer-supplied keys
  and the private cloud without repeating that they are for Engineering Vault customers only. The inference item
  states it correctly. Accuracy 3.5.
- **E1, introduction:** both B4 and B5 build the fit hypothesis on Core for maintenance records. B1–B3 linked
  Engineering Vault's drawing and transmittal capabilities to the offshore connection, which is the stronger fit.
  This is run variation, not addressed.
- **Unchanged (I4/I5):**
  - contradictions are never formal disclosures (O3b 0/4 in every run);
  - undated history is unmarked (O3c 2/6);
  - no "due tomorrow" flag (C1's template, due 10 November);
  - no price position or add-on total is computed. The contract forbids new figures until I5 adds derived figures
    with their own checks.
- **First-variant regression (B1–B3, corrected):** existing proposal terms under Opportunities, as above.

### Consistency

- **Coverage:** identical (36/36) in all five B runs.
- **B4 versus B5:** the six briefings carry the same items with different wording. The only material difference is
  P2's added recommendation in B5 to clarify the chronology.
- **Per-briefing mean (manual):** B4 3.87, B5 3.87. I3: 3.39 and 3.48.

## Verification

- Full test suite: 684 passed, after the final contract correction.
- New tests: `tests/test_contract_i31.py`:
  - topics per purpose, completed tasks, and that topics use only drafting-input evidence and send no markers;
  - with the contract off, the prompt is exactly the I3 prompt;
  - repair kept only when valid and more complete; failed repairs (invalid JSON, invalid citation, model error) keep
    the first draft;
  - topic-gap disclosures are shown.
- Restored positive coverage of the competitor rule:
  `test_a_competitor_named_in_the_customers_own_records_brings_the_battlecard_and_its_advice`. A customer record
  naming the competitor brings the battlecard, and the template's competitive item cites it.
- Adapted existing test: `test_llm::test_live_mode_end_to_end_with_simulated_openai`. Live mode now makes the
  metered coverage repair call when the simulated drafter (the offline template) leaves a topic unaddressed. The
  repeat adds nothing and is not used.
- Offline benchmark: not re-run (owner instruction: live first). The template drafter ignores the contract, so
  offline briefings change only through the payload, which the template does not read.

## Limitations

- **Small sample:** six fictional development scenarios; 3 A runs and 5 B runs; a single reviewer who also designed
  the contract.
- **Coverage is a lexical proxy,** derived from the same evidence the drafter sees. It shows whether content was
  stated, not whether it was well reasoned. Selection gaps are invisible to it.
- **Domain vocabulary:** the demo areas are a fixed vocabulary for document-management products. Another product
  domain needs its own list.
- **Repair untested live:** it never fired, so its live effect and cost are not measured.
