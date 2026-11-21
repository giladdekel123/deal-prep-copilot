# I5: business reasoning and actionable recommendations (Phase 4.5) — FICTIONAL TEST DATA

Development split only. No held-out data was read, run or scored. Protected data was not modified. I4 is preserved
at `ae77f95`. Owner approval (2026-11-12): up to $5 additional API spend, including retries.

## Plan and cost estimate (recorded before any paid call, 02:33)

- **Design:** interleaved A/B on the six audited scenarios: A = I4 (`--no-i5`), B = I5. Order A1, B1, A2, B2, B3.
- **Negative run:** one live negative-variant run on the negotiations P2 and C1, with the evidence perturbed in
  memory:
  - `missing_prices`: list prices and policies removed;
  - `ambiguous_terms`: incompatible units and contradictory approval thresholds.
- **Dry run (free), draft prompt size:** I5 is 22–38k characters, against I4's 20–28k. The business analysis adds
  about 2.5k tokens.
  - Worst case per run: $0.60 for I5 and $0.59 for I4, with each briefing capped at $0.10 by the production guard.
- **Expected actual cost:**
  - an I4 run about $0.08 (I4: $0.072–0.097);
  - an I5 run $0.15–0.30, from the larger prompts and more coverage repairs;
  - the negative run about $0.10–0.15.
  - Total about **$0.6–1.2**.
- **Worst case for the plan:** 2 × $0.59 + 3 × $0.60 + $0.40 ≈ $3.4. This is below the $5 approval and the
  estimated $3.32 of remaining credit only if every briefing hit its cap, which has never happened (actual spend has
  been 15–25% of worst case).
- **Daily cap:** I set the experiment-only `--daily-cap` to $2.00, because the planned total can exceed the
  production $1.00 per UTC day. Nothing has been spent on 2026-11-12 UTC so far.
- **Per-run caps:** `--run-cap 0.40`. Protected-data fingerprints are taken before and after every run.

## Implementation

- **`src/deal_prep/business.py` (new, deterministic, no company-specific rules).** It works only from the drafting
  input and records every result with its formula, inputs and evidence IDs:
  - **Price position:** the discount of each proposed price from the current list price of the same product, tier,
    unit and currency.
  - **Approval:** the policy tier that discount falls in, and the price below which the next tier is needed. An
    approval tier is never presented as an approval.
  - **Requested additions:** list-price cost of what the customer asked for, only when units match.
  - **Requested terms:** checked against the minimum term. A price effect is never assumed.
  - **Deadlines:** tasks and commitments with days left (overdue, today, tomorrow, within 7 or 30 days) and proposal
    validity.
  - **Status checks:** a completed task while correspondence still shows the request open.
  - **Product and tier eligibility limits.**
  - **Suggested meeting questions.**
  - A missing, ambiguous or unit-incompatible input gives `not_calculable` / `ambiguous` and a "verify" item, never
    a number.
- **Contract and drafter (`contract.py`, `briefing.py`, `pipeline.py`):** the results become essential topics with
  required citations. The live drafter receives `business_analysis` with these rules:
  - use the given figures exactly; do not calculate;
  - turn findings into recommendations;
  - state eligibility limits in the same item.
- **Figure check:** a new check traces every figure in the draft to the evidence or to the analysis.
- **Evaluation script (`benchmark_live.py`):**
  - `--no-i5` gives the I4 arm;
  - `--variant missing_prices|ambiguous_terms` perturbs the evidence in memory only;
  - `--scenarios` selects a subset;
  - `--daily-cap` is an experiment-only daily cap.
- **One correction during evaluation:** B3 put the request for 60 more users under Opportunities (O6b 3/4: existing
  terms shown as an opportunity). An addition that extends an existing proposal now goes under Our relationship.
  Run B4 (P2 only) confirmed the fix (O6b 1/1). The rule only applies to additions to an existing proposal's product,
  so no other scenario was re-run.
- **Tests:**
  - `tests/test_business_i5.py` has 22 tests, including the negative cases (missing price, unit mismatch, ambiguous
    policy, no policy, requested term, status disagreement, no figure invented).
  - `tests/test_contract_i31.py`: the I3.1 topic assertion now excludes the I4/I5 topic kinds, which are tested in
    their own files. The I3.1 assertions themselves are unchanged.

## Live comparison

**Configuration:**
- **Arms:** A = I4 drafter (`--no-i5`), runs A1 and A2. B = I5, runs B1, B2 and B3. Everything else is identical
  between the arms: models (gpt-6.1-terra drafter, gpt-6-luna agent), settings, fixture news, clock (2026-11-09) and
  scorer 1.1.
- **Run order:** A1, B1, A2, B2, B3.
- **Extra runs:** two negative variants on P2 and C1, and B4 on P2 after the correction.

### Automated metrics (scorer 1.1, unchanged)

| Metric | A1 | A2 | B1 | B2 | B3 |
|---|---|---|---|---|---|
| R1 / R2 / R3 | 31/31, 16/16, 15/15 | same | same | same | same |
| O1 number consistency | 38/38 | 40/40 | 36/36 | 38/38 | 34/34 |
| O2a / O2b citations | 23/23, 100/100 | 23/23, 100/100 | 23/23, 88/88 | 23/23, 91/91 | 23/23, 88/88 |
| O3a / O3b / O3c | 5/5, 3/4, 6/6 | same | same | same | same |
| O6a open items | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 |
| O6b existing terms not opportunities | 4/4 | 4/4 | 4/4 | 4/4 | **3/4** (fixed; B4 1/1) |
| O7a customer-grounded recommendations | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 |
| O7b no unsupported product/competitor advice | 20/21 | 18/18 | **19/23** | **22/24** | **21/23** |
| O8 safety | 22/22 | 22/22 | 22/22 | 23/23 | 21/21 |
| **I5 business topics communicated** (measured identically in both arms) | **2/13** (11 cited only) | **1/13** (12 cited only) | **13/13** | **13/13** | **13/13** |
| Figures not traceable to evidence or analysis | 0 | 0 | 0 | 0 | 0 |

### Manual review

The review covered all 30 six-scenario briefings, B4 and the 4 negative-variant briefings. I recomputed every I5
calculation from the source passages.

**Calculations: all correct.** No arithmetic or traceability errors were found in any run.

| Scenario | Results checked |
|---|---|
| P2 | (52 − 49) / 52 = 5.8%, within account-executive authority. The 15% limit is USD 44.20. 60 more users at list: USD 3,120 per month, USD 37,440 for 12 months, USD 74,880 over the 24-month minimum, 240 users in total. |
| C1 | 9.6%, same USD 44.20 limit. 36-month term: meets the 24-month minimum, price effect not calculable. |
| T1 | 8.8%. 8 TB at USD 240 per TB: USD 1,920 per month, USD 23,040 for 12 months. |
| L1 | 5.9%. 3 TB: USD 720 per month, USD 8,640 for 12 months. |
| Deadlines | 3, 5, 7, 11 and 16 days, and "tomorrow" for C1's import template. |

**Commercial distinctions are kept.**
- Each of the 15 occurrences of "agreed price" / "approved" in the I5 customer briefings is negated or conditional:
  - "the offer is not an agreed price";
  - "approval is not recorded";
  - "verify whether the existing 5.8% discount was approved rather than assuming approval".
- List prices, proposals, list-price costs ("not a quote") and approval tiers are never confused.

**Customer briefings, I4 versus I5.**
- I4 put list price and offer side by side and left the reader to interpret them: "Discuss … USD 49 … and the
  approved current list price of USD 52". It never stated a discount, a cost, the price at which approval escalates,
  or urgency.
- I5 states the conclusions. Examples:
  - **C1:** "The existing 9.6% position is within account-executive authority, but its approval is not recorded";
    "Confirm and send the import template: … due tomorrow"; "Ask what price outcome Corvanne expects for 36 months:
    that meets the 24-month minimum, but no evidenced rule establishes a price reduction."
  - **L1:** "Ask whether Brisk received the revised quote and what it still awaits: the meeting record marks sending
    it Completed, but correspondence says it will be sent by 18 November". I4 noticed this in one of two runs, without
    explanation.
  - **P2:** the 60-user addition is priced at list and labelled "not a quote"; the questionnaire is due in 3 days.

**E1 introduction and M2 product demo (O7b failures).** I classified each flagged item.

- **E1:**
  - I5 runs present Engineering Vault and Core as "Hypothesis to verify". Each is cited to the product sheet and
    explicitly not claimed as a need, and each recommendation is phrased as a discovery question ("Ask how drawings
    … are managed, and whether Engineering Vault's drawing register … would be relevant").
  - The I4 arm does the same: A1 has the same hypotheses, and its recommendation fails O7b in the same way.
  - These are **reasonable, explicitly labelled hypotheses, not unsupported factual claims**. The CP-2 audit (E7)
    asked for a product-fit hypothesis in introductions.
  - The higher I5 failure count comes from more recommendations (3 versus 2 in A2), not from different claims.
- **M2:**
  - Every product statement matches the product sheet or security FAQ, and the SCIM disagreement is flagged in all
    runs.
  - New in I5, from the eligibility rule: B1 and B2 recommendations mention customer-supplied keys and single-tenant
    private cloud "available only to Engineering Vault customers". This is accurate and qualified, but **of low
    relevance** to a hospital network, for which Engineering Vault is not the obvious product.
  - This is a minor relevance weakness, not a factual error. The eligibility rule should drop options the customer is
    unlikely to qualify for, rather than state the limit (follow-up below).
  - B1's "Business-tier-only approval workflows" matches the product sheet ("The Business tier adds configurable
    approval workflows").
- **O7a (M2, 5/6 in every run):** product-demo recommendations rely on product evidence. I5 cites customer evidence
  in 2–3 of 4–5 recommendations, I4 in 2 of 4–5.
- **The scoring criterion is unchanged.** O7b treats any product named in a new-lead recommendation without customer
  evidence as unsupported. For a product demo this conflicts with the purpose rules, which ask for demo content. This
  is for the owner to decide; I have not changed it.

**Negative tests (4 briefings): no fabricated conclusion.**

| Variant | Result |
|---|---|
| `missing_prices` (P2, C1) | "Verify the applicable list price before assessing the negotiation position"; "do not present an estimated price"; formal `topic_gap` disclosures. |
| `ambiguous_terms`, unit mismatch (per site against per user) | "The units differ, so do not claim a calculated discount". |
| `ambiguous_terms`, contradictory thresholds (up to 15% / above 10%) | "The overlap is ambiguous; an approval tier is not an approval". |

The ambiguity is stated in the text only; there is no separate formal disclosure for it.

**Regressions.**
- B3's O6b placement error: fixed and confirmed.
- The M2 eligibility-relevance issue above (minor).
- Length: the mean briefing grew from 2,466 to 2,876 characters (+17%) and from 3.2 to 3.9 recommendations. Empty
  non-relationship sections went from 1.1 to 1.2 per briefing.
- No significant quality regression was found.

## Remaining weaknesses

1. **Approval policy missing for follow-up meetings:** T1 and L1 say "no discount-approval policy is in the evidence;
   verify". This is honest, but selection does not include the policy for follow-ups (I3 selection gap).
2. **Eligibility limits are stated instead of filtered:** Engineering-Vault-only options appear in a healthcare demo
   (M2).
3. **O7b versus product-demo purpose:** this is a scoring decision for the owner.
4. **Ambiguous policies are stated only in text,** not formally disclosed.
5. **Length grew about 17%,** and section placement issues remain (product capabilities under Competitive positioning
   in L1). Both are already in the I6 scope (organization and conciseness).
6. **Cosmetic:** units in analysis question text are lower-case singular ("60 user", "8 tb"). The drafter
   reformatted them in every reviewed briefing.

## Cost, time and verification

**Spend:**

| Run | Cost |
|---|---|
| A1 | $0.0869 |
| B1 | $0.1056 |
| A2 | $0.0730 |
| B2 | $0.0848 |
| B3 | $0.0991 |
| NEG missing | $0.0292 |
| NEG ambiguous | $0.0424 |
| B4 (P2) | $0.0204 |
| **Total** | **$0.5414** (118 calls), against the $5 approval |

- This matches the ledger for 2026-11-12. The estimate was about $0.6–1.2.
- Per six-scenario run: I4 $0.080, I5 $0.097 (+21%). Two I5 briefings (T1 in B1 and B3) and one negative-variant briefing (C1, ambiguous terms) needed one coverage
  repair call each.

**Elapsed time:**
- Coding, tests and live runs: 01:57–03:03 (66 min), including the full suite.
- After the interrupted session, status review: about 10 min.
- Manual review, checks and report: 03:34–03:45 (about 11 min, plus commit).
- **Total about 1 h 27 min,** against an estimate of 1 h 40 min–2 h 55 min (most likely 2 h 10 min). The 45–70 min
  estimate for the remaining work was beaten because no code change or re-run was needed.

**Checks, run sequentially:**
- **Full suite after the last code change:** 737 passed, 0 failed (5 min 4 s).
- **After the review:** rehearsal 35/35, consistency check 36/36.
- **Held-out data:** freeze valid; executions 1 of 3 (not used).
- **Protected data:** no file or folder in the protected scope changed after 2026-11-09. Every live run reported
  "Protected local data unchanged: yes".
- **Fingerprint:** the shell fingerprint is `9b3ee414d3a5f3e5` under C collation. Under `en_US.UTF-8` collation,
  the shell setting used at CP-2, it is `f1c6b23d3bb84a1a`, identical to CP-2. The difference is only `sort` order
  in this shell.
- **Secret scan of committed files:** clean. `tvly-` appears only in the existing redaction pattern in `pipeline.py`.
- **I6 worktree:** `worktree-i6-review` untouched.
