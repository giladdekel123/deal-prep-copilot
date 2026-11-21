# Draft requirements: summary, clarifications and remaining mapping notes (for owner review)

**Status:** DRAFT, not frozen, not scored. Requirements are those proposed by ChatGPT and the project owner; Claude Code added only evidence IDs and expected-content wording taken from the 104-passage inventory (commit 8cb3dfc) and the approved fictional histories (a17c9f7). Assessment fields are empty. The consolidated human-readable copy is `CHECKLISTS_FOR_REVIEW.md`.

## 1. Final count: 43 items = 15 Critical + 28 Major

Previous draft (c597151): 44 items = 15 Critical + 29 Major. The only change in count is **one Major item fewer**: TGT-A M3 (no post-cutoff information) was moved into shared safeguard S1 and is not scored as a fact. TGT-A now has 2 Critical + 2 Major. All other items were reworded, not added or removed.

| Scenario | Critical | Major | Total |
|---|---|---|---|
| AAL-A | 2 | 3 | 5 |
| AAL-B | 3 | 4 | 7 |
| DBS-A | 1 | 4 | 5 |
| DBS-B | 2 | 4 | 6 |
| TGT-A | 2 | 2 | 4 |
| TGT-B | 1 | 4 | 5 |
| TOY-A | 2 | 3 | 5 |
| TOY-B | 2 | 4 | 6 |
| **Total** | **15** | **28** | **43** |

## 2. Clarifications applied in this round

1. **TGT-A M3 -> shared safeguard S1.** S1 now also says nothing published after 2026-11-15 10:00 UTC may be presented as available at the cutoff; it is an error check and the absence of future information earns no credit.
2. **TGT-B M3.** No specific public development is mandatory. Target Corporation must be identified correctly; any public context included must be accurate, dated and relevant to the follow-up. If none is included and none is materially relevant, the context component is NE, not Pass, and the item is scored on identification alone.
3. **AAL-A C1.** Now distinguishes the first-half 2026 period, continuing-operations underlying EBITDA $4,002m (AAL-05, AAL-25), total Group underlying EBITDA $3,830m (AAL-28), and the shareholder-attributable loss ($858m) and Steelmaking Coal impairment ($0.9bn; AAL-07, AAL-08) as different measures. It requires an accurate basis for every figure and material context, not specific wording or repetition. **Reading to confirm:** one correctly labelled EBITDA basis is enough; the item fails if bases are mixed or mislabelled, and it does not require both EBITDA figures to be stated.
4. **TOY-A C2.** Primary support is the two dated figures, 3,400,000 million yen on 4 Aug 2026 (TOY-14) and 3,900,000 million yen on 5 Nov 2026 (TOY-13); the 500bn yen revision is established by comparing them, with no quotation required. The presentation (TOY-25, TOY-26) is corroboration only and its provenance limitation is preserved.
5. **DBS-B.** C2 preserves both conflicting SCIM statements (NVQ-PRD-001 and NVQ-POL-002) verbatim and unmerged. M1 states that the vendor evidence supports the EU and US regions only (plus private cloud for Engineering Vault); stating or implying Asian or Singapore hosting is a failure.

## 3. Final review checks

- **Evidence or explicit negative safeguard.** Every item cites at least one supporting ID checked mechanically against the inventory and the record register (no unknown ID). Items with no source passage are explicit negative or judgement assessments against the scenario's records: AAL-B C3 (partly), TGT-B M4, TOY-B C2 and M1 and M4, and the "no inference" clause of AAL-B M4. TGT-A M3 (formerly unsupported) now sits in S1.
- **Nothing graded against absent information.** Each expected-content statement was re-read against the cited passages or records. Where a vendor document is silent (Asian hosting, implementation price, a 28% price figure), the form says so and does not require it. TGT-B public context is optional.
- **Not tuned to outputs.** No briefing, retrieval trace, PDF or run result of this or any earlier evaluation was opened or used to write or change these items; they come from the owner's and ChatGPT's wording, the 104 passages, the fictional histories and the vendor documents. (The earlier scored form was read for its layout only.)
- **Practical relevance.** Critical items are the protocol's critical classes (current offer, approval authority, leaked draft, wrong figure or source, undisclosed conflict, missing latest results and cause, invented relationship). Major items are one idea each, and several are "at least one of" a short list.
- **No requirement to repeat the corpus.** The forms cite 71 distinct inventory passages in total as possible support, but that is a menu: the largest lists (AAL-A 22, TOY-A 21, DBS-A 15, TGT-A 13 IDs) offer alternatives and context, and each item needs one correct supported statement, not all cited passages. Nothing requires the briefing to reproduce all 104.
- **No automatic passes.** S4 and S5 can only be exercised in AAL-B and DBS-B; elsewhere, and whenever the relevant material did not reach the drafter, they are NE. Conditional requirements (TGT-B context) are NE when their condition does not arise.

## 4. Remaining notes for the owner (no further change made)

1. **AAL-A M3 and TOY-A M3** accept "at least one" dated development from a short list.
2. **AAL-A C2.** No passage says "pending" in so many words; it follows from AAL-12 (30 Jul) and AAL-15 (20 Oct), the later being current.
3. **AAL-B C2.** The CFO rule is NVQ-POL-001 (above 25%); "no approval" is shown by absence and by NVQ-PRP-322; the records give the 28% only as a percentage.
4. **AAL-B C3.** NE if the draft note's content never reached the drafter.
5. **DBS-A C1.** The 5% decline is in DBS-03 (release) and DBS-12 (briefing, which prints "$" for Singapore dollars).
6. **DBS-B.** `VENDOR_CANON.md` (authoring reference, not in the knowledge-base manifest) lists SCIM under Business; it is not retrievable and not used as evidence. NVQ-PRD-001 says "Enterprise tier"; the product table names the top tier Engineering Vault (Enterprise), and the briefing is not required to equate them.
7. **TOY-A and TOY-B** both have the purpose introduction; no change made. TOY-17 and TOY-18 come from the briefing transcript created 9 Nov.
8. **Negative and judgement items** (TGT-B M4, TOY-B C2, M1, M4) are assessed against the full record set for the scenario.
9. **Retrieval isolation.** `src/` and `app/` contain no reference to `eval/fresh_evaluation/`; the knowledge base loads from `data/kb_v1`. Once approved, the checklists must stay out of the application's retrieval and drafting inputs.
10. **Result scale.** Pass / Partial / Fail for items; NE for safeguards and conditional items; P(v) and NA are not used unless the owner restores them.

## 5. Scoring-procedure clarification (latest round; no requirement changed)

Mandatory items are judged on the final generated briefing. A retrieval trace may establish whether S4 or S5 was exercised, but never that the final briefing handled the material correctly. Not exercised is NE, not Pass. TGT-B M3: identification and optional public context are scored independently; no context included means that component is NE and the identification score is unaffected. The 43 items, severities, evidence references and cutoff are unchanged. See the end of `SHARED_SAFEGUARDS.md`.

## 6. Pre-freeze scoring clarification: Target Australia (20 Nov 2026; owner-approved; motivated by corpus compatibility)

This is a change of what is assessed, not a reference correction. The three approved Target Australia passages (TGT-21 Wesfarmers annual report, TGT-22 and TGT-24 archived Target Australia and Kmart Group pages) describe a different company, and the application's document schema cannot hold them as retrievable material about Target Corporation without a false label or a leak to other companies. They are therefore excluded from the run corpus (preserved unchanged in the inventory and the raw sources; see `run_materials/EXCEPTIONS.md`). Consequences for scoring:

- **TGT-A C1** (Critical): requires correct identification of Target Corporation as the U.S. company, supported by TGT-01, TGT-02 and TGT-04. The element "Target Australia is part of Wesfarmers and has no affiliation with Target Corporation" is removed; the briefing is not required to explain Target Australia's ownership. The prohibition on attributing any Target Australia fact to Target Corporation is retained. If Target Australia never arises, that comparison is recorded as NE.
- **TGT-B M3** (Major): the evidence mapping drops TGT-22 (supporting IDs TGT-01, TGT-04); the two independent components are otherwise unchanged.
- The 43 items, all severities and all other requirements are unchanged.
