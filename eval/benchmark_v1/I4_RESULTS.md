# I4: chronology, conflicting information, undated history and event dates (Phase 4.5) — FICTIONAL TEST DATA

Development split only. No held-out data was read, run or scored. Protected data was not modified. I3.1 is preserved
at `448e2ed`, and the CP-2, I3 and I3.1 baselines are unchanged. Owner approval (2026-11-11): up to $5 additional API
spend, including retries.

## Owner decision applied

- A state dated earlier than a formal decision about the same subject ("since 2020" against "decided in 2022") is a
  **chronological ambiguity**, not a contradiction. The activity may have begun before it was formalised.
- It is disclosed, citing both sources, and neither date is treated as established.
- Only different figures for the same statement are a **contradiction** (unresolved conflict).

## Changes (company-independent)

**New: `src/deal_prep/chronology.py`.** All rules read only the sanitized drafting input.
- **Contradictions:** public sources from different documents that make the same statement with different figures
  (via the existing `evidence_profile.figure_relations`). The official side is listed first.
- **Decision/state pairs:** "in YYYY … decided to …" and "since YYYY …" about the same subject (at least 2 shared
  content words).
  - The state is earlier than the decision → `chronological_ambiguity`.
  - Otherwise compatible, and not disclosed.
- **Undated history:** a past-event statement (passive past or a historical verb) with no year or month →
  `statement_date: not_stated`.
- **News event dates:** dates in the item's own text → `event_dates_in_text`, kept apart from the provider's
  publication estimate.

**Changes in existing modules:**
- **`disclosures.py`:** derived conflicts become formal required disclosures (`conflict:derived:*`), quoting and
  citing both passages. A conflict already curated in the manifest is not disclosed twice.
- **`citations.py`:** a fact citing one side of a derived conflict must cite every side (`conflict_side_dropped`).
  Inferences are unaffected.
- **`evidence_profile.profile`:** new fields `ambiguous_with`, `statement_date` and `event_dates_in_text`. Empty
  fields are not sent.
- **`contract.py`:**
  - each ambiguity becomes a `chronology:n` topic that requires both sides together;
  - each undated statement becomes a conditional `undated:<id>` topic: "date not stated" is required only if the
    statement is used;
  - coverage reports these separately;
  - the repair comparison counts them.
- **`briefing.py`:** I4 rules on conflicts, the ambiguity wording (neither "consistent" nor "contradiction"), undated
  statements, and event versus publication date.
- **`demo.py` (offline template):** an ambiguity is shown as "The timeline is unclear: … neither is treated as
  established".
- **`benchmark_live.py`:**
  - `--no-i4` selects the I3.1 arm;
  - `--daily-cap` is an experiment-only daily cap (see Spending).

**Not changed:** selection, the I3.1 contract, models, the scorer, provenance, the SCIM data (still a curated,
disclosed conflict), held-out data and the saved demonstration.

## Results (live; six audited scenarios)

A = I3.1 (`--no-i4`), runs A1 and A2. B = I4, runs B1, B2r and B3.

### Acceptance criteria

| Criterion | A (I3.1) | **B (I4)** |
|---|---|---|
| P2 chronology: formal disclosure citing both statements | 0 of 2 | **3 of 3** (chronological ambiguity) |
| P2 chronology: never "consistent", never one side established | yes | **yes; both sides in one item, 3 of 3** |
| Contested counts (P2, E1, M2): formal disclosure, both figures attributed | 0 of 6 | **9 of 9** |
| No false conflicts: compatible pairs (C1, T1, L1, E1, M2) and aggregator copies | none | **none** (O3a 5/5; 0 extra disclosures) |
| Undated history marked or omitted (scorer O3c) | 4 of 12 | **18 of 18** (all used and marked) |
| News: event date from the text (or "not stated"), publication date only as the provider's estimate | 2 of 10 | **15 of 15** |
| SCIM (M2): disclosed, no tier asserted or promised | yes | **yes, 3 of 3** |
| I3.1 preserved | yes | **yes** (details below) |

- **News, A arm:** most items say "news published 8 November 2026 reports…", giving the provider's estimate as a
  stated publication date. Two items flag it as the provider's, and M2 also gives the text's "October 2026".
- **News, B arm:** "the event date is not stated; the provider estimates publication on 25 October 2026", or the
  text's own date (M2: "opened two outpatient clinics in October 2026").
- **I3.1 preserved:**
  - coverage: 37/37 in every B run (the I3.1 topics plus P2's chronology topic);
  - O6a 12/12, O6b 4/4, O2a 23/23, R1 31/31, O8 full;
  - list price and approvals in P2 and C1, and the six-area demo plan in M2.

### Scorer 1.1 (unchanged)

| Metric | I3.1 B4 | I3.1 B5 | A1 | A2 | **B1** | **B2r** | **B3** |
|---|---|---|---|---|---|---|---|
| O3b formal contradiction disclosure | 0/4 | 0/4 | 0/4 | 0/4 | **3/4** | **3/4** | **3/4** |
| O3b_text contradiction stated in text | 4/4 | 4/4 | 4/4 | 4/4 | 0/1 | 0/1 | 0/1 |
| O3c undated marked | 2/6 | 2/6 | 3/6 | 1/6 | **6/6** | **6/6** | **6/6** |
| O1 number consistency (partial) | 36/36 | 39/39 | 33/34 | 36/37 | **40/40** | **40/40** | **36/36** |
| O6a open items | 12/12 | 11/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 |
| O7b no unsupported product/competitor advice | 19/19 | 19/19 | 20/21 | 16/20 | 16/17 | 17/20 | 19/19 |
| O7a customer-grounded recommendations | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 |
| R1, R2, R3, O2a, O3a, O4, O5a, O5b, O6b, O8 | full | full | full | full | full | full | full |

- **O3b 3/4 and O3b_text 0/1 are the intended result of the owner decision, not failures of I4.**
  - The benchmark's generator classes P2's "state since 2020 / decided 2022" as a contradiction.
  - O3b accepts only `unresolved_conflict` disclosures. O3b_text then looks for contradiction words ("conflict",
    "unresolved", …), while the briefing deliberately says "how the statements relate is unclear".
  - The other three contradictions (the contested counts) pass O3b formally in every B run.
  - The scorer was not changed.
- **O1:** the remaining A failures were the news-window wording. B has none.
- **O7b:** the failures occur in both arms (A2: 4, B2r: 3). They are product names in recommendations for the new
  leads (E1, M2), mostly "for Engineering Vault" next to customer-supplied keys and private cloud. That is the
  product-eligibility caveat being stated, so the failures are a scorer-rule tension, not caused by I4.

### Manual audit (Claude Code; CP-2 rubric)

- **Read in full:** B3's P2, E1 and M2.
- **Checked through the I4 criteria for all 18 B briefings:** disclosures, chronology wording, undated marking,
  news-date wording.
- **I3.1 content:** read through the coverage report and the scorer.
- **Bias risk:** the same reviewer designed I4.

| Dimension | I3.1 (B4/B5) | **I4** | Change |
|---|---|---|---|
| Factual accuracy | 3.9 | **3.9** | News dating more precise. The M2 Engineering Vault–only caveat is still missing in one recommendation (backlog). |
| Important omissions | 4.0 | **4.0** | |
| Purpose relevance | 3.9 | **3.9** | |
| Contradiction recognition | 3.0 | **4.0** | Formal disclosure plus correct wording in P2, E1 and M2 |
| Specific vs generic | 3.8 | **3.8** | |
| Grounded recommendations | 4.0 | **4.0** | |

**Examples (B3):**
- **P2:** "Pellmar's … source says its board decided in 2022 to keep all quality certificates in one digital archive,
  and separately says every certificate has been stored in its digital archive since 2020. How the statements relate
  is unclear; the practice may have preceded formalisation."
  - Plus the formal disclosure `conflict:derived:chronology:2`, citing both passages.
- **E1:** "began as a municipal utility; date not stated". The compatible pair "decided in 2018 … stored since 2020"
  is stated as fact, without a false flag.
- **M2:** "Hospital count is unresolved: … 9 … HealthOrg Index says 12." Plus the formal figure disclosure and the
  SCIM disclosure, and "flag the unresolved SCIM tier discrepancy and verify availability before making a tier
  commitment".

**Regressions:** none found in the finished briefings.

**Remaining issues (backlog, unchanged):**
- section placement: product capabilities appear under "Competitive positioning", and Opportunities is often empty;
- the Engineering Vault–only caveat for customer-supplied keys and private cloud;
- E1's fit hypothesis uses Core for maintenance records rather than Engineering Vault for the offshore project.

**Not addressed in I4:** "unresolved decisions / status disagreements" (proposal item 5) was left out, as allowed.
I3.1 B4/B5 already stated L1's completed-task versus open-correspondence discrepancy.

## Spending

| Run | Arm | Cost | Calls | Protected data |
|---|---|---|---|---|
| A1 | I3.1 | $0.082158 | 20 | unchanged |
| B1 | I4 | $0.096516 | 22 | unchanged |
| A2 | I3.1 | $0.083357 | 19 | unchanged |
| B2 (partial) | I4 | $0.016091 | 3 | unchanged |
| B2r | I4 | $0.083715 | 19 | unchanged |
| B3 | I4 | $0.071647 | 18 | unchanged |
| **Total** | | **$0.433484** | 101 | 6/6 unchanged |

- **Against the approval:** $0.43 of the $5 approved. Before the runs I estimated about $0.40 expected and about
  $2.5 worst case.
- **Cumulative:** experiment spend is $1.493859.
- **Credit:** about $3.32 remains if the $4.32 figure was current. It cannot be read with an API key.
- **Daily cap refusal (B2):** the production daily cap ($1.00 per UTC day) refused T1's draft call in B2 before
  anything was sent, because $0.9746 had already been spent on 2026-11-11 UTC.
  - I added an experiment-only `--daily-cap` (default: the production cap) and reran B2 as B2r with $1.50.
  - The production cap and code are unchanged.
  - The partial B2 (2 briefings, 1 refused) is excluded from the quality results.
- **Per briefing:** about $0.014 for I4, against about $0.014 for I3.1 in the same session. The prompts are about
  2–3k characters longer.

## Verification

- **Full suite after the I4 code:** 701 passed. It took 36:28, against 4–10 min earlier.
  - Measured cause: memory pressure on the machine (2.4 GB of 15.8 GB free; one offline scenario took 52 s, mostly
    the index build).
  - Not the I4 code: the new code adds 5–25 ms per briefing (I4 on/off timing, e.g. `required_disclosures` 2.6 →
    7.7 ms, `build_messages` 10.5 → 34.3 ms).
- **After the `--daily-cap` script change:** `test_benchmark.py` and `test_chronology_i4.py` were rerun: 87 passed
  in 52 s. `src/` was unchanged after the full suite.
- **New: `tests/test_chronology_i4.py`:**
  - ambiguity versus contradiction;
  - compatible and later states not disclosed; unrelated subjects never paired;
  - generic phrasing beyond the benchmark sentences;
  - copies with the same figure are not conflicts;
  - undated detection, including the "may" false positive;
  - event versus publication date;
  - profile links;
  - I4 switched off gives the I3.1 profile;
  - the citation rule on a real P2 bundle.
- **Deterministic offline check of all 12 development scenarios:** no false conflict, all briefings valid, P's
  chronology disclosed as an ambiguity, and the P/E/M counts as contradictions.
- **Integrity:** fingerprints before and after all 6 live runs were unchanged. No held-out access.
- **Offline template edit reverted:** a template edit that would have changed the saved demonstration's output was
  reverted. The saved demo is untouched.

## Elapsed time (for future estimates)

**Estimate given at start: 1 h 45 min – 3 h 30 min.** Start 22:49; finish 01:29 (2026-11-12).

| Part | Estimate | Actual |
|---|---|---|
| Coding plus targeted tests and probes (22:49–23:03) | 55–80 min | about 14 min |
| Full test suite (23:03–23:39) | 15–25 min (all tests) | **36 min** (one run; memory-bound machine) |
| Live API waiting (23:40–23:53, 00:55–01:01) | 15–25 min | about 19 min (5 runs plus 1 partial; 2.5–4 min each) |
| Idle gap after the daily-cap refusal (session waiting, no work; 23:53–00:55) | – | about 62 min |
| Analysis, audit, write-up, final tests, commit (01:01–01:29) | 30–40 min | about 28 min |
| **Total wall clock** | **1 h 45 min – 3 h 30 min** | **2 h 40 min** (about 1 h 38 min excluding the idle gap) |

**Lessons for future estimates:**
1. Coding was much faster than estimated. Pattern-level additions on top of existing machinery are quick.
2. Test time depends on the machine's free memory, ranging from 4 to 36 minutes for the same suite. Check free memory
   before the full suite, or run only the affected test files plus one final full suite.
3. The production daily cap ($1.00 per UTC day) has to be planned for when one evaluation session spans several
   experiments. Use the experiment `--daily-cap` explicitly when the owner-approved ceiling allows it.
