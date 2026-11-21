# I3 results: customer correspondence and purpose-aware retrieval (Phase 4.5) — FICTIONAL TEST DATA

Development split only. No held-out data was read, run or scored, and no paid call was made. Scorer 1.1 is
unchanged, so every difference below is an application change. Requirements came from the CP-2 quality audit
(`CP2_QUALITY_AUDIT.md`, committed unchanged in `5ef7681`): its error register, critical checklists and suggested
acceptance additions.

## Root cause (from the audit, confirmed in the CP-2 records)

- **Fixed searches ignored the meeting's purpose.** Every briefing ran the same top-5 searches:
  - the vendor query always returned the Starter and Business rows of both the 2025 and 2026 price lists;
  - the battlecard was always included;
  - the customer search usually returned the correspondence header without its body.
- **The agent filled the gaps at random.** Whatever else arrived came from the agent's supplementary searches,
  which differed between runs.
- **Measured:** the CP-2 inputs minus the agent's additions equal the pre-I3 offline input exactly, at 31/45
  critical items in every run. The agent raised this to 34–36/45, a different subset each time.

## Changes (company-independent; no benchmark names or IDs in production code)

**New: `src/deal_prep/selection.py`.** It runs in `gather_research` after the ranked searches and before the
conflict and comparison sources. All rules read document metadata and text only.

| # | Rule | Fixes |
|---|---|---|
| 1 | **Customer records whole:** every passage of each approved, current record of the customer (proposal, correspondence, meeting notes). Draft and superseded records are excluded. Caps: 8 documents, 12 passages each. | E4, E5, E12 |
| 2 | **Products in play:** products of the current price list named in the customer's approved records, including approved meeting records. Draft notes never count. | — |
| 3 | **Pricing in force only:** a list is used only if it is approved, not superseded, and effective on the briefing date.<br>• With products in play: only their rows (the tier the records name) plus the list's notes.<br>• For a new lead: the whole current list, not a ranked subset. | E3, E14 |
| 4 | **Purpose documents:**<br>• negotiation → commercial policy (discount approval, validity, billing);<br>• product_demo → product overview and security/integration FAQ, whole;<br>• introduction → the product descriptions only.<br>Each document is picked by one ranked search within its document type. | E2, E7 |
| 5 | **Product passages:** product-overview passages about a product in play (the first product they name), for any purpose. | — |
| 6 | **Competitor material** (owner decision at the I3 review): kept only if the competitor (name or registered alias) is named in customer, profile or news evidence. Otherwise no passage naming a competitor reaches the drafter. A battlecard passage naming no competitor is kept only if it covers a product in play, and then as vendor evidence, never as competition. Rule: `select_competition` (run after news); agent screen: `battlecard_exclusion`. | E10 (selection part) |
| 7 | **Public sources:** every verbatim excerpt of a public document already retrieved for the company, not only those that ranked. | M2 "digital consent since 2025" |

**Elsewhere:**
- **Agent:** `agent.run_agent` screens internal lookups with the same exclusion rules (`selection.screen`). The agent
  still only adds evidence.
- **Data pages:** in `evidence_profile.is_data_page`, an undated page on a quote or market-data URL is now a data
  page, not news (E15). Undated ordinary news is still kept, as before (tested).
- **Explainability:** `pipeline.prepare_briefing` returns `result["selection"]`: the reason for every drafting-input
  passage, every excluded passage with its reason and stage, the products in play and the competitor decision. The
  benchmark record carries it (`benchmark_harness.run_scenario`, not scored). The trace gains `purpose_selection` and
  `competition_selection` entries.
- **Lookup helper:** `kb_index.passages_where`, a metadata lookup with no ranking. `document_passages` now uses it.
- **Not changed:** models, prompts, the scorer, the offline template, citation and conflict rules, provenance
  labels, I1 meeting history, held-out data, production history.

## Results: offline template, development split (12 scenarios; 2 repeats, identical)

Pre-I3 baseline: run `20261111T174604Z`, taken from a clean worktree at `5ef7681` (see the process note).
Post-I3: run `20261111T175433Z`.

| Metric | news_fixture pre → I3 | news_off pre → I3 |
|---|---|---|
| R1 must-reach evidence | 44/62 → **62/62** | 34/52 → **52/52** |
| O2a must-cite cited | 38/46 → **46/46** | 28/36 → **36/36** |
| O2b cited evidence not a distractor | 90/98 → **116/116** | 80/88 → **106/106** |
| O6a required open items | 15/18 → **18/18** | 15/18 → **18/18** |
| O7b no unsupported product/competitor advice | 26/38 → **26/30** | 36/48 → **36/40** |
| O1 number consistency (partial) | 92/92 → 94/94 | 82/82 → 84/84 |
| O4 checkable disclosures true | 8/8 → 10/10 | 32/32 → 34/34 |
| O8 safety (partial) | 50/50 → 52/52 | 50/50 → 52/52 |
| O3c undated marked | 2/12 (2 vacuous) → 2/12 (0 vacuous) | same |
| O6b existing terms not under Opportunities | 2/8 (2 vacuous) → 0/8 | same |
| R2, R3, O3a, O3b, O3b_text, O5a, O5b, O7a | unchanged | unchanged |

**How to read the two that look worse:**
- **O6b:** the two earlier passes were vacuous. T1's proposal price row never reached the drafter, so no
  opportunity existed. It now arrives, and the offline template's existing rule (proposal shown under Opportunities)
  applies to T1 as it already did to C, L and P. This is a drafting defect made visible, not a selection regression
  (I5).
- **O3c:** L1's undated statement now reaches the drafter and passes substantively instead of vacuously.

**Remaining failures are all drafting:**
- O7b: 4 cases, the template's fixed "use the battlecard" line in the Engineering Vault scenarios;
- O6b: 8 cases;
- O3c: 10 cases;
- O3b: 8 cases.

## Comparison with the CP-2 baseline (six audited scenarios, drafting input)

Each audit checklist item was mapped to the passage(s) that carry it. An item counts when any of those passages is
in the drafting input. CP-2 counts are live runs, including the agent's additions. The I3 count is the
deterministic mandatory selection with no agent; in live runs the agent can only add to it.

| Input | Critical items | Superseded rows | Unrelated price rows | Irrelevant battlecard passages | Data page | Passages |
|---|---|---|---|---|---|---|
| CP-2 A1 | 36/45 | 15 | 8 | 16 | 1 | 140 |
| CP-2 B1 | 34/45 | 14 | 8 | 16 | 1 | 134 |
| CP-2 A2 | 34/45 | 13 | 8 | 16 | 1 | 137 |
| CP-2 B2 | 34/45 | 12 | 8 | 16 | 1 | 129 |
| Pre-I3 / CP-2 without agent | 31/45 | 12 | 8 | 16 | 1 | 119 |
| **I3 (no agent)** | **45/45** | **0** | **0** | **0** | **0** | 152 |

Per scenario, I3 versus the CP-2 range:

| Scenario | CP-2 | I3 |
|---|---|---|
| P2 | 7–8/8 | 8/8 |
| T1 | 6/7 | 7/7 |
| C1 | 5–7/7 | 7/7 |
| L1 | 6–7/7 | 7/7 |
| E1 | 5/6 | 6/6 |
| M2 | 4/10 | 10/10 |

**Audit acceptance additions:** both are met, tested in `tests/test_selection_i3.py`, and deterministic.
- The passages for E3, E4 and E5, and the M2/E1 product rows, reach the drafter in 100% of offline runs.
- No superseded or unrelated price row reaches the drafter.

**Prompt size (dry run, free):** I3 drafting prompts are 15.8k–24.3k characters before any agent additions. CP-2 B
live prompts were 14.6k–21.9k characters with them. Worst case per briefing is $0.059–$0.065, within the $0.10 cap.

**Offline finished briefings (template, six scenarios):**
- P2, T1, C1, L1: the email item now states the customer's request instead of "its content was not among the
  retrieved records".
- P2, C1, L1: the price shown is the proposed product's row (Engineering Vault $52; Core Business $34) instead of
  Starter $18.
- T1, L1, E1, M2: the competitor advice is gone.
- L1: gains the official 2021 decision statement.
- M2: carries the SCIM conflict disclosure.
- The template does not use product or policy evidence, so the M2/E1 gains show only with the live drafter.

## Audit error register: status after I3

| # | Status |
|---|---|
| E2 (M2 no product/security evidence) | **Fixed at selection:** product overview and security FAQ reach the drafter. |
| E3 (P2 list price missing) | **Fixed at selection.** Computing the 5.8% position is drafting (I5). |
| E4 (L1 3 TB request) | **Fixed at selection.** |
| E5 (C1 36-month question) | **Selection part fixed.** The price position (9.6% off) is I5. |
| E7 (E1 no fit hypothesis) | **Selection part fixed:** the product descriptions reach the drafter. Whether the drafter forms a hypothesis needs the live check. |
| E10 (boilerplate, irrelevant competitor material) | **Selection part fixed:** battlecard out of T1, L1, E1 and M2. The hedging boilerplate is drafting (I5/I6). |
| E12 (P2 reply, T1 sent date) | **Fixed at selection.** |
| E14 (superseded 2025 price) | **Fixed:** in mandatory selection and in agent lookups. |
| E15 (undated data page) | **Fixed.** |
| E1, E6, E13 | I4 (temporal reasoning, formal disclosure, undated marking); not addressed. |
| E8, E9, E11 | I5 (derived open items, add-on cost, grounded recommendations); not addressed. |

**Latent SCIM conflict:** both SCIM statements now reach the product-demo briefing. The existing conflict rules
catch it: `conflict:C2` is disclosed and no fact may cite either side (tested). The knowledge base still contradicts
itself; resolving it is I4 or a data correction. Introductions do not receive the SCIM passage.

## Factual accuracy

- Offline, automated proxies only (none of them is a factual-accuracy score):
  - every number in a fact occurs in its cited passages (O1 94/94 and 84/84; number consistency only);
  - every citation is a non-distractor (O2b 116/116 and 106/106);
  - safety checks pass (O8 52/52 and 52/52).
- Unchanged and verified per scenario: no unreviewed draft phrase, stale, look-alike or passing-mention news, or
  provenance-label change reaches the drafter.
- The live drafter's factual accuracy with the larger input is covered by the live evaluation below.

## Competitor rule correction (owner decision, after the offline results above)

**The decision:** exclude competitor-specific passages unless the customer evidence identifies the competitor, and
never imply that an unmentioned competitor is involved. Neutral price-objection guidance may stay only where it is
grounded in the customer's requests or in relevant product and pricing evidence.

**Implemented as rule 6 above.**
- A passage counts as naming the competitor when it contains the competitor's registered name or alias.
- Every battlecard passage in this knowledge base names "Solquend", so none qualifies as neutral guidance.
- As a result, no development scenario receives battlecard material. P2 and C1 lose it too.
- Neutral price guidance for negotiations comes from the commercial policy (discount approval, validity), which
  rule 4 already includes.

**Tests:**
- every one of the six scenarios: no battlecard passage in the input, and no competitor name in the input or the
  briefing;
- the name/alias rule and the neutral-passage rule (unit tests);
- the battlecard returns when the news names the competitor (production KB).

**Existing tests adapted to the decision:**
- `test_orchestrator`: two tests now check the ranked battlecard search through the trace instead of the bundle.
- `test_citations`: two fixtures cite vendor evidence instead of a battlecard passage.
- `test_app`: the battlecard-citation check is kept, but Arup now has no battlecard item, so it no longer exercises
  that check in this setup.

**Not re-measured offline** (no lengthy benchmark, per instruction). The offline table above predates this
correction; the expected effect is the removal of the 4 O7b template failures in C1, C2, P1 and P2.

## Live evaluation (owner-approved: two runs, at most $0.30 each)

**Setup:** six development scenarios, the CP-2 configuration B unchanged (gpt-6.1-terra drafter, gpt-6-luna agent,
low effort, 4,000 / 600 output tokens, evidence profile on), fixture news, history seed, clock 2026-11-09 and
scorer 1.1. Run folders (gitignored): `runs/benchmark_v1/cp0/20261111T182250Z_i3_1` and `20261111T182528Z_i3_2`.

| Run | Calls | Cost |
|---|---|---|
| I3-1 | 19 | $0.068319 |
| I3-2 | 20 | $0.063758 |
| **Total** | **39** | **$0.132075** of the $0.60 approved |

- **Ledger:** cumulative experiment spend is now $0.495938 of the $10 authorization; 2026-11-11 holds $0.132075
  over 39 calls.
- **CP-2 B for comparison:** $0.0657 and $0.0597 per run, 22 and 21 calls.
- **Connections and errors:** no blocked connections, no refused calls, and all 12 briefings are `briefing_ready`.

### Drafting input (selection)

Both live runs reach 45/45 critical checklist items. They contain 0 superseded rows, 0 unrelated price rows, 0
competitor passages and 0 data pages, in 146 and 147 passages. CP-2 reached 34–36/45, in 129–140 passages. The
agent added at most one passage per scenario (a claims summary). Every gap below is therefore a drafting failure,
not a retrieval failure.

### Automated metrics (scorer 1.1, news_fixture)

| Metric | CP-2 A1 | CP-2 B1 | CP-2 A2 | CP-2 B2 | **I3-1** | **I3-2** |
|---|---|---|---|---|---|---|
| R1 must-reach evidence | 25/31 | 24/31 | 24/31 | 25/31 | **31/31** | **31/31** |
| O2a must-cite cited | 21/23 | 21/23 | 21/23 | 22/23 | **23/23** | **23/23** |
| O2b non-distractor citations | 60/60 | 56/56 | 53/53 | 57/57 | 64/64 | 67/67 |
| O1 number consistency (partial) | 36/37 | 33/34 | 31/32 | 34/35 | 31/34 | 34/36 |
| O3b formal contradiction disclosure | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| O3b_text contradiction stated in text | 2/4 | 3/4 | 3/4 | 3/4 | 4/4 | 3/4 |
| O3c undated marked | 2/6 | 3/6 | 3/6 | 2/6 | 2/6 | 2/6 |
| O4 checkable disclosures true | 4/4 | 4/4 | 4/4 | 4/4 | 5/5 | 5/5 |
| O5a official verbatim preferred | 4/5 | 6/6 | 5/6 | 6/6 | 6/6 | 6/6 |
| O6a open items | 7/12 | 6/12 | 5/12 | 8/12 | **9/12** | **9/12** |
| O6b existing terms not opportunities | 4/4 | 3/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| O7a customer-grounded recommendations | 6/6 | 4/6 | 6/6 | 5/6 | 5/6 | 4/6 |
| O7b no unsupported product/competitor advice | 14/14 | 15/15 | 12/13 | 15/16 | 14/14 | 13/13 |
| R2, R3, O3a, O5b, O8 | full | full | full | full | full | full |

- **O1:** every failure (3 and 2) is the drafter describing the news window or the news date ("last 48 hours",
  "30-day context", "October 25"), as in CP-2. None is a factual figure.
- **O6a, still missing:**
  - T1 and L1, both runs: the date of the latest contact;
  - P2 (I3-1): the scorer did not match "November 12";
  - C1 (I3-2): the template's due date.

### Manual audit (Claude Code; same rubric, checklists and 0–4 scale as `CP2_QUALITY_AUDIT.md`)

Means over the two I3 runs, with the CP-2 means (4 runs) in brackets. This is the same single reviewer, not the
owner's audit.

| Dimension | Overall | P2 | T1 | C1 | L1 | E1 | M2 |
|---|---|---|---|---|---|---|---|
| Factual accuracy | **3.9** (3.8) | 3.5 (3.0) | 4.0 (4.0) | 4.0 (3.8) | 4.0 (4.0) | 4.0 (4.0) | 4.0 (4.0) |
| Important omissions | **3.7** (3.5) | 3.4 (3.2) | 4.0 (4.0) | 3.3 (3.6) | 4.0 (3.6) | 4.0 (3.4) | 3.2 (3.0) |
| Purpose relevance | **3.1** (2.8) | 3.0 (2.8) | 4.0 (3.8) | 3.5 (3.5) | 3.8 (3.2) | 3.0 (2.0) | 1.5 (1.2) |
| Contradiction recognition | **2.7** (2.4) | 2.0 (1.2) | n/a | n/a | n/a | 3.0 (3.0) | 3.0 (3.0) |
| Specific vs generic | **3.0** (2.6) | 3.0 (3.0) | 3.0 (3.0) | 3.5 (3.2) | 3.5 (3.0) | 3.0 (2.0) | 1.8 (1.2) |
| Grounded recommendations | **3.9** (3.5) | 4.0 (4.0) | 4.0 (4.0) | 4.0 (4.0) | 4.0 (3.5) | 4.0 (3.0) | 3.5 (2.8) |

**Critical items present in the final briefings:**
- I3: 35.5/39 in each run.
- CP-2: about 33.8/39 on average, derived from the audit's omission scores.

**Consistency across runs:**
- Mean per briefing: I3-1 3.39 and I3-2 3.48. CP-2: 3.06–3.27.
- Spread between the two runs per scenario: P2 0.17, T1 0.00, C1 0.06, L1 0.10, E1 0.00, M2 0.47. CP-2, over 4 runs:
  0.76, 0.20, 0.51, 0.31, 0.06, 0.61.
- Two runs show less spread than four by construction, so only the direction is claimed. Selection is now
  identical between runs; the remaining variation is wording.

**Improvements:**
- **Customer requests and commitments are in every final briefing:** L1's 3 TB request (CP-2: 1 of 4), C1's
  36-month question cited from the customer's own email (1 of 4), P2's 60 users and the reply date, T1's 8 TB and
  the quote not yet sent.
- **No competitor material in any briefing.** L1 (I3-1) states that the evidence identifies no competing vendor.
  The drawing-register positioning for a law firm, a logistics firm and a hospital network (E10) is gone.
- **Introduction (E1):** both runs describe Engineering Vault's drawing and transmittal capabilities from the
  product sheet. Both link them to the new offshore connection as a question, not an assumed need (E7). Purpose
  2.0 → 3.0; grounded 3.0 → 4.0.
- **Product evidence in recommendations:**
  - T1 (I3-2) and L1 (both runs): retention schedules, legal holds and disposal certificates for the retention
    workshop or request;
  - E1 (both runs).
- **Commercial grounding:** the discount-approval policy is cited in P2 and C1 in both runs; C1 (I3-2) states the
  15% threshold. No superseded price appears anywhere (E14).
- **No hygiene failure in 12 of 12:**
  - no unreviewed draft note, data page or stale news;
  - no unmentioned competitor and no fabricated figure;
  - 1 uncited recommendation (M2, I3-1), against 1 in CP-2's 24 briefings.

**Regressions and non-improvements:**
- **C1 completeness 3.6 → 3.3, within run variation:**
  - neither run states the price position, although the $52 list price reached the drafter in both (CP-2: 1 of 4
    runs);
  - I3-2 omits the import template's due date.
- **P2 price position, still 0 of 2:** the list-price row is cited only as "verify the applicable list price"; the
  $52, the 5.8% position and the effect of 240 users are not stated (I5).
- **M2 product demo, still the weakest:**
  - all ten checklist items reached the drafter, but neither briefing shows the product: no workflows, retention or
    legal hold, data region or encryption;
  - the only product content is the SCIM conflict ("resolve or verify SCIM tier before committing"). That is a
    valid caution, but it is now the most prominent product statement in a demo briefing;
  - I3-1 adds an uncited generic recommendation.
  - Selection fixed the input; the drafter does not use it for this purpose. This needs purpose rules in the
    prompt (CP-3 / I6) or derived demo content (I5).
- **P2 chronology contradiction (critical E1), still 0 of 2:**
  - I3-1 states both dates and calls them "not necessarily contradictory";
  - I3-2 keeps "decided in 2022" and drops "since 2020" (I4).
- **Unchanged:** formal contradiction disclosures (0/4 per run), undated history unmarked (E13), and no item flagged
  as due tomorrow (E8). I4/I5.

**Purpose and factual-accuracy verdict:**
- Relevance and completeness increased, and accuracy did not fall. No unsupported factual or commercial claim was
  found, and P2's accuracy rose because the chronology was no longer called "consistent" outright.
- The gain is concentrated in customer follow-ups and the introduction. The demonstration briefing remains the main
  purpose failure, and it is now clearly a drafting failure.

## Verification

- **Full suite:** 657 passed, including 53 new I3 tests. All 604 existing tests passed unchanged.
- **Benchmark `20261111T175433Z`:** deterministic across 2 repeats, protected data unchanged, 0 outbound connections.
- **Held-out:** not compiled, read or run. No benchmark name in production code (checked by the run).
- **Spend (offline stage):** the live ledger was unchanged at $0.3639; no paid call was made before the approved
  live runs.
- **After the competitor correction:**
  - full suite: 665 passed;
  - protected data: `chroma_db/`, `runs/history.sqlite`, the walkthrough folder, `data/` and `app/` were last
    modified before this session (checked by modification time after the live runs, since the live script does not
    fingerprint);
  - the held-out split was not compiled, read or run.
- **Process note:** the first pre-I3 baseline (`20261111T172558Z`) reported "protected data changed", because
  `src/` was edited while it ran. The code had already been loaded, and the edit did not change behaviour. A clean
  re-run from a worktree at `5ef7681` gave identical metrics with protection intact. That worktree's run folder was
  removed with the worktree; its summary was kept. The comparison above uses the first baseline's records, which
  match it.

## Limitations

- **Product detection is by exact name.** A record that names a product only in short form (for example
  "Engineering Vault" without "Nivarque") does not put it in play.
- **Tier matching** looks for the tier as a capitalised word in the customer's records. An unrelated "Business" at
  the start of a sentence would add that tier's row.
- **Whole-document inclusion** assumes short records. Larger knowledge bases rely on the caps (8 documents ×
  12 passages; 12 price rows), which have not been tested at scale.
- **Small sample:** fictional development data. The live layer has two runs per scenario and a single reviewer, so
  the scores are ordinal judgements for ranking problems, not precise measurements.
